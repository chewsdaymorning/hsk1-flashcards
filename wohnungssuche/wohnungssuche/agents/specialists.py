"""The six specialist agents of the graph."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from wohnungssuche.agents.base import BaseAgent
from wohnungssuche.filters import FilterEngine
from wohnungssuche.geo import Geocoder, detect_district, haversine_km
from wohnungssuche.models import AgentMessage, ApartmentListing, PlatformStatus
from wohnungssuche.reporting import ReportGenerator
from wohnungssuche.scrapers.base import BaseScraper, Fetcher
from wohnungssuche.validation import ScamDetector

LOGGER = logging.getLogger(__name__)


@dataclass
class DiscoveryAgent(BaseAgent):
    """Fetches search-result pages from every configured platform."""

    name: str = "DiscoveryAgent"
    scrapers: Dict[str, BaseScraper] = field(default_factory=dict)

    def execute(self, message: AgentMessage) -> Dict[str, Any]:
        raw_pages = []
        statuses: List[PlatformStatus] = []
        for platform, scraper in self.scrapers.items():
            try:
                pages = scraper.discover()
            except Exception as exc:  # one platform must not stop the others
                LOGGER.warning("discovery failed for %s: %s", platform, exc)
                statuses.append(
                    PlatformStatus(platform=platform, success=False, message=str(exc))
                )
                continue
            raw_pages.extend(pages)
            statuses.append(
                PlatformStatus(
                    platform=platform,
                    success=bool(pages),
                    message="; ".join(scraper.errors[-3:]) if scraper.errors else "",
                )
            )
        return {"raw_pages": raw_pages, "platform_status": statuses}


@dataclass
class ExtractionAgent(BaseAgent):
    """Turns raw result pages into normalised listings, de-duplicated."""

    name: str = "ExtractionAgent"
    scrapers: Dict[str, BaseScraper] = field(default_factory=dict)

    def execute(self, message: AgentMessage) -> Dict[str, Any]:
        raw_pages = message.payload.get("raw_pages", [])
        statuses: List[PlatformStatus] = list(message.payload.get("platform_status", []))
        by_platform: Dict[str, int] = {}
        listings: Dict[str, ApartmentListing] = {}

        for raw in raw_pages:
            scraper = self.scrapers.get(raw.platform)
            if scraper is None:
                LOGGER.warning("no scraper registered for platform %s", raw.platform)
                continue
            try:
                parsed = scraper.extract(raw)
            except Exception as exc:
                LOGGER.warning("extraction failed for %s: %s", raw.platform, exc)
                continue
            for listing in parsed:
                # Same flat advertised twice keeps the first occurrence.
                listings.setdefault(listing.unique_hash, listing)
            by_platform[raw.platform] = by_platform.get(raw.platform, 0) + len(parsed)

        for status in statuses:
            status.listings_found = by_platform.get(status.platform, 0)
            if status.success and not status.listings_found:
                status.message = (status.message + " keine Treffer geparst").strip()

        return {
            "listings": list(listings.values()),
            "platform_status": statuses,
        }


@dataclass
class ValidationAgent(BaseAgent):
    """Flags scam indicators and implausible data."""

    name: str = "ValidationAgent"
    detector: Optional[ScamDetector] = None

    def __post_init__(self) -> None:
        if self.detector is None:
            self.detector = ScamDetector(self.config)

    def execute(self, message: AgentMessage) -> Dict[str, Any]:
        listings = message.listings()
        listings, flagged = self.detector.check_all(listings)
        payload = dict(message.payload)
        payload.update({"listings": listings, "scam_count": flagged})
        return payload


@dataclass
class EnrichmentAgent(BaseAgent):
    """Adds district, coordinates, distance and (optionally) expose details."""

    name: str = "EnrichmentAgent"
    geocoder: Optional[Geocoder] = None
    scrapers: Dict[str, BaseScraper] = field(default_factory=dict)
    detector: Optional[ScamDetector] = None

    def __post_init__(self) -> None:
        if self.geocoder is None:
            self.geocoder = Geocoder(allow_network=False)
        if self.detector is None:
            self.detector = ScamDetector(self.config)

    def execute(self, message: AgentMessage) -> Dict[str, Any]:
        listings = message.listings()
        detail_budget = self.config.max_detail_fetches if self.config.fetch_details else 0

        for listing in listings:
            if not listing.district:
                listing.district = detect_district(listing.searchable_text)

            if detail_budget > 0 and not listing.details_fetched:
                scraper = self.scrapers.get(listing.platform)
                if scraper is not None:
                    try:
                        if scraper.fetch_detail(listing):
                            detail_budget -= 1
                            # New text may reveal scam wording; re-check.
                            self.detector.check(listing)
                    except Exception as exc:
                        LOGGER.warning("detail fetch failed for %s: %s", listing.url, exc)

            if listing.lat is None or listing.lon is None:
                coords = self.geocoder.geocode(listing.address, listing.district)
                if coords:
                    listing.lat, listing.lon = coords

            if listing.lat is not None and listing.lon is not None:
                listing.distance_to_center_km = haversine_km(
                    self.config.center_lat, self.config.center_lon, listing.lat, listing.lon
                )

        payload = dict(message.payload)
        payload["listings"] = listings
        payload["scam_count"] = sum(1 for item in listings if item.is_scam_flagged)
        return payload


@dataclass
class FilterAgent(BaseAgent):
    """Applies the hard criteria and records why anything was dropped."""

    name: str = "FilterAgent"
    engine: Optional[FilterEngine] = None

    def __post_init__(self) -> None:
        if self.engine is None:
            self.engine = FilterEngine(self.config)

    def execute(self, message: AgentMessage) -> Dict[str, Any]:
        listings = message.listings()
        matches, non_matches = self.engine.filter_listings(listings)
        payload = dict(message.payload)
        payload.update(
            {
                "listings": listings,
                "matches": matches,
                "non_matches": non_matches,
                "flagged": [item for item in listings if item.is_scam_flagged],
                "warnings": {
                    item.unique_hash: self.engine.warnings(item) for item in matches
                },
            }
        )
        return payload


@dataclass
class LinkCheckAgent(BaseAgent):
    """Verifies that each match's expose URL is still reachable.

    A listing taken offline between scrape and report is the most common way a
    "real" link goes dead.  Dead matches stay visible but carry a warning; an
    inconclusive check (bot protection, robots.txt) claims nothing.
    """

    name: str = "LinkCheckAgent"
    fetcher: Optional[Fetcher] = None

    def execute(self, message: AgentMessage) -> Dict[str, Any]:
        payload = dict(message.payload)
        matches: List[ApartmentListing] = payload.get("matches", [])
        warnings: Dict[str, List[str]] = payload.get("warnings", {})

        if self.fetcher is None or not self.config.verify_links:
            return payload

        budget = self.config.max_link_checks
        dead = 0
        for listing in matches:
            if budget <= 0:
                LOGGER.info("link-check budget spent; remaining matches unchecked")
                break
            budget -= 1
            verdict = self.fetcher.verify(listing.url)
            if verdict is True:
                listing.link_status = "ok"
            elif verdict is False:
                listing.link_status = "dead"
                dead += 1
                warnings.setdefault(listing.unique_hash, []).append(
                    "Inserat nicht mehr erreichbar (evtl. schon vergeben)"
                )
            # None -> stays "unchecked"; we make no claim we cannot back up.

        if dead:
            LOGGER.info("%s match(es) point to offline exposes", dead)
        payload["warnings"] = warnings
        return payload


@dataclass
class ReportingAgent(BaseAgent):
    """Renders the HTML report and the JSON snapshot."""

    name: str = "ReportingAgent"
    generator: Optional[ReportGenerator] = None
    output_dir: Path = Path("reports")

    def __post_init__(self) -> None:
        if self.generator is None:
            self.generator = ReportGenerator(self.config, self.output_dir)

    def execute(self, message: AgentMessage) -> Dict[str, Any]:
        payload = dict(message.payload)
        report_path, json_path = self.generator.generate(
            matches=payload.get("matches", []),
            non_matches=payload.get("non_matches", []),
            flagged=payload.get("flagged", []),
            platform_status=payload.get("platform_status", []),
            warnings=payload.get("warnings", {}),
            new_hashes=payload.get("new_hashes", set()),
            agent_log=payload.get("agent_log", []),
            demo_mode=payload.get("demo_mode", False),
        )
        payload["report_path"] = str(report_path)
        payload["json_path"] = str(json_path)
        return payload
