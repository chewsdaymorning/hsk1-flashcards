"""Orchestrator: owns state, runs the agent graph, keeps the approval queue.

Sequence: Discovery -> Extraction -> Validation -> Enrichment -> Filter ->
Reporting.  Enrichment runs before filtering because the distance criterion
needs coordinates.  Every step is a message hand-off, and a failing step is
logged and skipped rather than aborting the run.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from wohnungssuche.agents.base import BaseAgent
from wohnungssuche.agents.specialists import (
    DiscoveryAgent,
    EnrichmentAgent,
    ExtractionAgent,
    FilterAgent,
    LinkCheckAgent,
    ReportingAgent,
    ValidationAgent,
)
from wohnungssuche.config import SearchConfig
from wohnungssuche.geo import Geocoder
from wohnungssuche.models import (
    AgentMessage,
    ApartmentListing,
    ApprovalStatus,
    PlatformStatus,
)
from wohnungssuche.scrapers.base import BaseScraper, Fetcher, HttpFetcher
from wohnungssuche.scrapers.is24 import IS24Scraper
from wohnungssuche.scrapers.immowelt import ImmoweltScraper
from wohnungssuche.scrapers.kleinanzeigen import KleinanzeigenScraper
from wohnungssuche.scrapers.mock import MockScraper
from wohnungssuche.sources import EmailAlertScraper, FileMailbox, FredyScraper, ImapMailbox
from wohnungssuche.storage import Storage

LOGGER = logging.getLogger(__name__)

SCRAPER_CLASSES = {
    "is24": IS24Scraper,
    "immowelt": ImmoweltScraper,
    "kleinanzeigen": KleinanzeigenScraper,
}

EMAIL_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "emails"


def _build_email_source(config: SearchConfig, fetcher, use_mock: bool):
    """Suchagent alert mails: fixtures in mock mode, IMAP live."""
    if use_mock:
        mailbox = FileMailbox(EMAIL_FIXTURES_DIR)
    else:
        if not (config.imap_host and config.imap_user):
            LOGGER.warning(
                "email source skipped: imap_host/imap_user not configured"
            )
            return None
        password = os.environ.get(config.imap_password_env, "")
        if not password:
            LOGGER.warning(
                "email source skipped: environment variable %s is empty "
                "(it must hold the IMAP password)",
                config.imap_password_env,
            )
            return None
        mailbox = ImapMailbox(
            host=config.imap_host,
            user=config.imap_user,
            password=password,
            port=config.imap_port,
            folder=config.imap_folder,
            since_days=config.imap_since_days,
            sender_filters=config.imap_sender_filters,
        )
    # The live fetcher stays attached so detail fetches and the link check
    # work on the real portal URLs the mails point to.
    return EmailAlertScraper(config=config, fetcher=fetcher, mailbox=mailbox)


def build_scrapers(config: SearchConfig, use_mock: bool = False) -> Dict[str, BaseScraper]:
    """Create one scraper/source per configured platform.

    ``use_mock`` swaps the live transports for local fixtures; the parsers
    are identical either way.  Besides the portal scrapers there are two
    scraping-free sources: "email" (Suchagent alert mails) and "fredy"
    (a local Fredy installation's listings database).
    """
    scrapers: Dict[str, BaseScraper] = {}
    fetcher = None if use_mock else HttpFetcher(config)
    for platform in config.platforms:
        if platform == "email":
            source = _build_email_source(config, fetcher, use_mock)
            if source is not None:
                scrapers["email"] = source
            continue
        if platform == "fredy":
            if use_mock:
                LOGGER.warning("fredy source has no fixtures; skipped in --mock")
                continue
            scrapers["fredy"] = FredyScraper(config=config, fetcher=fetcher)
            continue
        if platform not in SCRAPER_CLASSES:
            LOGGER.warning("Unknown platform %r, skipped", platform)
            continue
        if use_mock:
            scrapers[platform] = MockScraper(
                config=config, fetcher=None, platform=platform
            )
        else:
            scrapers[platform] = SCRAPER_CLASSES[platform](config=config, fetcher=fetcher)
    return scrapers


@dataclass
class PipelineResult:
    matches: List[ApartmentListing] = field(default_factory=list)
    non_matches: List[ApartmentListing] = field(default_factory=list)
    flagged: List[ApartmentListing] = field(default_factory=list)
    platform_status: List[PlatformStatus] = field(default_factory=list)
    new_hashes: set = field(default_factory=set)
    agent_log: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    report_path: Optional[str] = None
    json_path: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None

    @property
    def total_found(self) -> int:
        # Flagged listings always carry an exclude reason and are therefore
        # already part of non_matches - counting them again would inflate this.
        return len(self.matches) + len(self.non_matches)


class Orchestrator:
    """Runs the graph and records the outcome."""

    def __init__(
        self,
        config: SearchConfig,
        storage: Optional[Storage] = None,
        scrapers: Optional[Dict[str, BaseScraper]] = None,
        output_dir: Path | str = "reports",
        use_mock: bool = False,
        geocoder: Optional[Geocoder] = None,
    ) -> None:
        self.config = config
        self.storage = storage
        self.output_dir = Path(output_dir)
        self.demo_mode = use_mock
        self.scrapers = scrapers if scrapers is not None else build_scrapers(config, use_mock)
        # Only a live transport can answer "is this URL still up?"; in demo
        # mode the checker stays off and the report says so instead.
        link_fetcher: Optional[Fetcher] = None
        if not use_mock:
            for scraper in self.scrapers.values():
                if isinstance(scraper.fetcher, HttpFetcher):
                    link_fetcher = scraper.fetcher
                    break
        self.geocoder = geocoder or Geocoder(
            cache_path=self.output_dir / ".geocache.json", allow_network=not use_mock
        )
        self.agents: Sequence[BaseAgent] = (
            DiscoveryAgent(config=config, scrapers=self.scrapers),
            ExtractionAgent(config=config, scrapers=self.scrapers),
            ValidationAgent(config=config),
            EnrichmentAgent(config=config, geocoder=self.geocoder, scrapers=self.scrapers),
            FilterAgent(config=config),
            LinkCheckAgent(config=config, fetcher=link_fetcher),
            ReportingAgent(config=config, output_dir=self.output_dir),
        )

    def run(self) -> PipelineResult:
        result = PipelineResult()
        message = AgentMessage(sender="orchestrator", recipient="DiscoveryAgent")

        for agent in self.agents:
            if agent.name == "ReportingAgent":
                # Persist first so the report can mark what is new.
                message.payload["new_hashes"] = self._persist(message.payload)
                message.payload["agent_log"] = list(result.agent_log)
                message.payload["demo_mode"] = self.demo_mode

            message = agent.run(message)
            result.agent_log.append(
                {
                    "agent": agent.name,
                    "duration_seconds": message.duration_seconds,
                    "errors": message.errors,
                }
            )
            if message.errors:
                result.errors.extend(f"{agent.name}: {error}" for error in message.errors)

        payload = message.payload
        result.matches = payload.get("matches", [])
        result.non_matches = payload.get("non_matches", [])
        result.flagged = payload.get("flagged", [])
        result.platform_status = payload.get("platform_status", [])
        result.new_hashes = payload.get("new_hashes", set())
        result.report_path = payload.get("report_path")
        result.json_path = payload.get("json_path")
        result.finished_at = datetime.now()

        self._queue_for_approval(result.matches)
        self._record_run(result)
        return result

    # --- state ------------------------------------------------------------
    def _persist(self, payload: Dict) -> set:
        """Store every listing seen; return the hashes that are new."""
        if not self.storage:
            return set()
        listings = payload.get("listings", [])
        try:
            return set(self.storage.save_listings(listings))
        except Exception as exc:
            LOGGER.warning("Could not persist listings: %s", exc)
            return set()

    def _queue_for_approval(self, matches: Sequence[ApartmentListing]) -> None:
        """Put matches in front of the user.  Contacts nobody, ever."""
        if not self.storage:
            return
        for listing in matches:
            try:
                self.storage.request_approval(
                    listing, note="Automatisch vorgeschlagen, wartet auf Freigabe"
                )
            except Exception as exc:
                LOGGER.warning("Could not queue %s for approval: %s", listing.id, exc)

    def _record_run(self, result: PipelineResult) -> None:
        if not self.storage:
            return
        try:
            self.storage.record_run(
                started_at=result.started_at,
                finished_at=result.finished_at or datetime.now(),
                found=result.total_found,
                new_listings=len(result.new_hashes),
                matches=len(result.matches),
                scam_flagged=len(result.flagged),
                platforms=result.platform_status,
                report_path=result.report_path or "",
            )
        except Exception as exc:
            LOGGER.warning("Could not record run: %s", exc)

    # --- approval queue helpers ------------------------------------------
    def pending_approvals(self):
        return self.storage.approvals(ApprovalStatus.PENDING) if self.storage else []
