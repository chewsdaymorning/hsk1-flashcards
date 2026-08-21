"""Mock scraper: the real parsers driven from saved HTML fixtures.

Using the production parsers against fixtures (instead of hand-built fake
listings) means the test data has the same shape as live data - real expose
URLs, real CDN image URLs - so nothing has to be rewritten when switching to
the live fetcher.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Type

from wohnungssuche.models import ApartmentListing, RawListing
from wohnungssuche.scrapers.base import BaseScraper, FixtureFetcher
from wohnungssuche.scrapers.immowelt import ImmoweltScraper
from wohnungssuche.scrapers.is24 import IS24Scraper
from wohnungssuche.scrapers.kleinanzeigen import KleinanzeigenScraper

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

DELEGATES: Dict[str, Type[BaseScraper]] = {
    "is24": IS24Scraper,
    "immowelt": ImmoweltScraper,
    "kleinanzeigen": KleinanzeigenScraper,
}

FIXTURE_FILES = {
    "is24": "is24_results.html",
    "immowelt": "immowelt_results.html",
    "kleinanzeigen": "kleinanzeigen_results.html",
}


@dataclass
class MockScraper(BaseScraper):
    """Drop-in replacement for a live scraper, backed by local fixtures."""

    platform: str = "is24"
    fixtures_dir: Path = FIXTURES_DIR
    delegate: BaseScraper = field(init=False, repr=False, default=None)

    def __post_init__(self) -> None:
        if self.platform not in DELEGATES:
            raise ValueError(f"No mock fixture for platform {self.platform!r}")
        fixture = Path(self.fixtures_dir) / FIXTURE_FILES[self.platform]
        delegate_cls = DELEGATES[self.platform]
        probe = delegate_cls(config=self.config, fetcher=FixtureFetcher({}))
        host = probe.base_url.split("//", 1)[-1]
        self.delegate = delegate_cls(
            config=self.config, fetcher=FixtureFetcher({host: fixture})
        )
        self.base_url = self.delegate.base_url

    def discover(self) -> List[RawListing]:
        raws = self.delegate.discover()
        self.errors.extend(self.delegate.errors)
        return raws

    def extract(self, raw: RawListing) -> List[ApartmentListing]:
        listings = self.delegate.extract(raw)
        self.errors.extend(self.delegate.errors[len(self.errors):])
        return listings
