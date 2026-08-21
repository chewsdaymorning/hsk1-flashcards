"""Scraper foundations: fetching, robots.txt, rate limiting, base class.

The transport is injected (``Fetcher``) so the exact same parsers run against
live HTTP in production and against saved HTML fixtures in tests - that is how
mock and real data stay in sync (lesson 3 of the build brief).
"""

from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from wohnungssuche.config import SearchConfig
from wohnungssuche.models import ApartmentListing, RawListing
from wohnungssuche.parsing import clean_text, detect_features, kitchen_size_hint
from wohnungssuche.validation import extract_contact

LOGGER = logging.getLogger(__name__)

# Expose pages can be enormous; this much text is plenty for scam checks.
DETAIL_TEXT_LIMIT = 4000

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
}


class ScraperError(RuntimeError):
    """Raised when a platform cannot be scraped at all."""


@dataclass
class FetchResult:
    url: str
    html: str = ""
    status_code: Optional[int] = None
    ok: bool = False
    error: str = ""


class RobotsPolicy:
    """robots.txt lookups, cached per host.

    Unreachable robots.txt is treated as *disallowed*: without knowing the
    rules we do not crawl.
    """

    def __init__(self, user_agent: str, timeout_seconds: float = 15.0) -> None:
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self._cache: Dict[str, Optional[RobotFileParser]] = {}

    def _parser_for(self, url: str) -> Optional[RobotFileParser]:
        parsed = urlparse(url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        if root in self._cache:
            return self._cache[root]

        parser: Optional[RobotFileParser] = None
        robots_url = urljoin(root, "/robots.txt")
        try:
            response = requests.get(
                robots_url,
                headers={"User-Agent": self.user_agent, **DEFAULT_HEADERS},
                timeout=self.timeout_seconds,
            )
            if response.status_code in (401, 403):
                parser = None  # explicit lock-out
            elif response.status_code >= 400:
                parser = RobotFileParser()
                parser.parse([])  # no rules published -> everything allowed
            else:
                parser = RobotFileParser()
                parser.parse(response.text.splitlines())
        except requests.RequestException as exc:
            LOGGER.warning("robots.txt unreachable at %s: %s", robots_url, exc)
            parser = None

        self._cache[root] = parser
        return parser

    def can_fetch(self, url: str) -> bool:
        parser = self._parser_for(url)
        if parser is None:
            return False
        return parser.can_fetch(self.user_agent, url)

    def crawl_delay(self, url: str) -> Optional[float]:
        parser = self._parser_for(url)
        if parser is None:
            return None
        try:
            delay = parser.crawl_delay(self.user_agent)
        except AttributeError:  # pragma: no cover - very old Pythons
            return None
        return float(delay) if delay else None


class Fetcher(ABC):
    """Transport abstraction: live HTTP or saved fixtures."""

    @abstractmethod
    def get(self, url: str, params: Optional[Dict[str, str]] = None) -> FetchResult:
        ...

    def verify(self, url: str) -> Optional[bool]:
        """Is *url* still reachable?  True/False, or None if inconclusive.

        The default is deliberately None (unknown): only transports that can
        really answer the question should claim anything.
        """
        return None


class HttpFetcher(Fetcher):
    """Polite HTTP client: robots.txt, delays, rotating UA, backoff."""

    def __init__(self, config: SearchConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.user_agent = random.choice(USER_AGENTS)
        self.session.headers.update({"User-Agent": self.user_agent, **DEFAULT_HEADERS})
        self.robots = RobotsPolicy(self.user_agent, config.request_timeout_seconds)
        self._last_request_at = 0.0

    def _wait(self, url: str) -> None:
        delay = self.config.request_delay_seconds
        if self.config.respect_robots_txt:
            crawl_delay = self.robots.crawl_delay(url)
            if crawl_delay:
                delay = max(delay, crawl_delay)
        # Jitter so requests do not arrive on a metronome.
        delay += random.uniform(0, 1.0)
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < delay:
            time.sleep(delay - elapsed)

    def get(self, url: str, params: Optional[Dict[str, str]] = None) -> FetchResult:
        if self.config.respect_robots_txt and not self.robots.can_fetch(url):
            return FetchResult(
                url=url,
                ok=False,
                error="blocked by robots.txt (or robots.txt unreachable)",
            )

        last_error = ""
        for attempt in range(1, self.config.max_retries + 1):
            self._wait(url)
            self._last_request_at = time.monotonic()
            try:
                response = self.session.get(
                    url, params=params, timeout=self.config.request_timeout_seconds
                )
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                LOGGER.warning("GET %s failed (attempt %s): %s", url, attempt, exc)
            else:
                if response.status_code == 200:
                    return FetchResult(
                        url=response.url,
                        html=response.text,
                        status_code=response.status_code,
                        ok=True,
                    )
                last_error = f"HTTP {response.status_code}"
                LOGGER.warning(
                    "GET %s returned %s (attempt %s)", url, response.status_code, attempt
                )
                if response.status_code in (400, 401, 403, 404, 410):
                    break  # retrying will not help
            if attempt < self.config.max_retries:
                time.sleep(2 ** attempt)  # exponential backoff: 2s, 4s, 8s

        return FetchResult(url=url, ok=False, error=last_error or "unknown error")

    def verify(self, url: str) -> Optional[bool]:
        if self.config.respect_robots_txt and not self.robots.can_fetch(url):
            return None
        self._wait(url)
        self._last_request_at = time.monotonic()
        try:
            response = self.session.head(
                url, timeout=self.config.request_timeout_seconds, allow_redirects=True
            )
            if response.status_code == 405:  # HEAD not supported
                response = self.session.get(
                    url, timeout=self.config.request_timeout_seconds, stream=True
                )
                response.close()
        except requests.RequestException as exc:
            LOGGER.warning("verify %s failed: %s", url, exc)
            return None
        if response.status_code in (404, 410):
            return False
        if response.status_code < 400:
            return True
        # 403/429/5xx: bot protection or a hiccup, not proof the listing died.
        return None


EMPTY_RESULTS_HTML = "<html><body><div class='no-results'></div></body></html>"


class FixtureFetcher(Fetcher):
    """Serves saved HTML files so parsers can be tested without the network.

    ``mapping`` maps a URL substring to one file or to a list of files, one per
    result page.  Once a key's pages are exhausted an empty result page is
    returned, which is how the real portals signal "no more results".
    """

    def __init__(self, mapping: Dict[str, object]) -> None:
        self.mapping: Dict[str, List[Path]] = {}
        for key, value in mapping.items():
            pages = value if isinstance(value, (list, tuple)) else [value]
            self.mapping[key] = [Path(page) for page in pages]
        self._served: Dict[str, int] = {key: 0 for key in self.mapping}
        self.requests: List[str] = []

    def get(self, url: str, params: Optional[Dict[str, str]] = None) -> FetchResult:
        self.requests.append(url)
        for key, pages in self.mapping.items():
            if key not in url:
                continue
            index = self._served[key]
            self._served[key] = index + 1
            if index >= len(pages):
                return FetchResult(
                    url=url, html=EMPTY_RESULTS_HTML, status_code=200, ok=True
                )
            path = pages[index]
            if not path.exists():
                return FetchResult(url=url, ok=False, error=f"missing fixture {path}")
            return FetchResult(
                url=url, html=path.read_text(encoding="utf-8"), status_code=200, ok=True
            )
        return FetchResult(url=url, ok=False, error="no fixture registered for this URL")


@dataclass
class BaseScraper(ABC):
    """Common scraper behaviour: discover raw pages, then extract listings."""

    config: SearchConfig
    fetcher: Fetcher
    errors: List[str] = field(default_factory=list)

    platform: str = "base"
    base_url: str = ""

    @abstractmethod
    def discover(self) -> List[RawListing]:
        """Fetch search-result pages and return them un-parsed."""

    @abstractmethod
    def extract(self, raw: RawListing) -> List[ApartmentListing]:
        """Parse one raw page into listings."""

    def search(self) -> List[ApartmentListing]:
        """Convenience wrapper used outside the agent graph."""
        listings: List[ApartmentListing] = []
        for raw in self.discover():
            listings.extend(self.extract(raw))
        return listings

    def fetch_detail(self, listing: ApartmentListing) -> bool:
        """Load the expose page to enrich description, contact and features.

        Works for every portal because it only reads visible text - no
        portal-specific selectors to break.  Returns True on success.
        """
        result = self.fetcher.get(listing.url)
        if not result.ok:
            self.log_error(f"detail page {listing.url}: {result.error}")
            return False

        soup = BeautifulSoup(result.html, "html.parser")
        for tag in soup(["script", "style", "noscript", "template"]):
            tag.decompose()
        text = clean_text(soup.get_text(" ", strip=True))[:DETAIL_TEXT_LIMIT]
        if len(text) > len(listing.description):
            listing.description = text

        email, phone = extract_contact(text)
        listing.contact_email = listing.contact_email or email
        listing.contact_phone = listing.contact_phone or phone
        lowered = text.lower()
        listing.is_private = listing.is_private or any(
            marker in lowered
            for marker in ("privatanbieter", "von privat", "privater anbieter")
        )

        haystack = f"{listing.title} {text}"
        for name, value in detect_features(haystack).items():
            setattr(listing, name, getattr(listing, name) or value)
        hint = kitchen_size_hint(haystack, self.config.small_kitchen_terms)
        if hint != "unknown":
            listing.kitchen_size_hint = hint

        listing.details_fetched = True
        return True

    # --- helpers shared by concrete scrapers ------------------------------
    def absolute_url(self, href: str) -> str:
        return urljoin(self.base_url, href.strip()) if href else ""

    def log_error(self, message: str) -> None:
        LOGGER.warning("[%s] %s", self.platform, message)
        self.errors.append(message)
