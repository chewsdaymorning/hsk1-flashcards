"""Platform scrapers and the fetch abstraction they share."""

from wohnungssuche.scrapers.base import (
    BaseScraper,
    FetchResult,
    Fetcher,
    FixtureFetcher,
    HttpFetcher,
    RobotsPolicy,
    ScraperError,
)
from wohnungssuche.scrapers.immowelt import ImmoweltScraper
from wohnungssuche.scrapers.is24 import IS24Scraper
from wohnungssuche.scrapers.kleinanzeigen import KleinanzeigenScraper
from wohnungssuche.scrapers.mock import MockScraper

SCRAPER_REGISTRY = {
    "is24": IS24Scraper,
    "immowelt": ImmoweltScraper,
    "kleinanzeigen": KleinanzeigenScraper,
}

__all__ = [
    "BaseScraper",
    "FetchResult",
    "Fetcher",
    "FixtureFetcher",
    "HttpFetcher",
    "IS24Scraper",
    "ImmoweltScraper",
    "KleinanzeigenScraper",
    "MockScraper",
    "RobotsPolicy",
    "SCRAPER_REGISTRY",
    "ScraperError",
]
