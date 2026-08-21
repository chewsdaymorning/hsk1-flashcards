"""Discovery from Suchagent alert e-mails.

The portals send every new hit of a saved search by e-mail, so instead of
scraping their result pages we read those alert mails: from a real IMAP inbox
in production (``ImapMailbox``), from saved ``.eml`` files in tests and
offline runs (``FileMailbox``).  ``EmailAlertScraper`` then turns the portal
links inside each mail into regular ``ApartmentListing`` objects, so the rest
of the pipeline does not care where a listing came from.
"""

from __future__ import annotations

import imaplib
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta
from email import message_from_bytes, policy
from email.message import Message
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup, Tag

from wohnungssuche.models import ApartmentListing, RawListing
from wohnungssuche.parsing import (
    clean_text,
    detect_features,
    kitchen_size_hint,
    parse_area,
    parse_labeled_price,
    parse_price,
    parse_rooms,
)
from wohnungssuche.scrapers.base import BaseScraper
from wohnungssuche.scrapers.card import (
    COLD_RENT_LABELS,
    WARM_RENT_ESTIMATE_FACTOR,
    WARM_RENT_LABELS,
)

LOGGER = logging.getLogger(__name__)

# The portals whose alert mails we understand:
# (host suffix, detail path marker, platform name, expose-id pattern).
PORTAL_PATTERNS = (
    ("immobilienscout24.de", "/expose/", "is24", re.compile(r"/expose/(\d+)")),
    ("immowelt.de", "/expose/", "immowelt", re.compile(r"/expose/([A-Za-z0-9]+)")),
    (
        "kleinanzeigen.de",
        "/s-anzeige/",
        "kleinanzeigen",
        re.compile(r"/s-anzeige/[^/]+/(\d+)"),
    ),
)

# How far above a link we look for the surrounding listing block.
_MAX_ANCESTOR_HOPS = 8

# IMAP date tokens are always English, independent of the process locale -
# strftime("%b") is not, so the month names are spelled out here.
_IMAP_MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def imap_since_criterion(since_days: int, today: Optional[date] = None) -> str:
    """The IMAP SINCE date for *since_days* ago, e.g. ``01-Jan-2026``."""
    reference = today or date.today()
    target = reference - timedelta(days=since_days)
    return f"{target.day:02d}-{_IMAP_MONTHS[target.month - 1]}-{target.year}"


def portal_expose_url(href: str) -> Optional[Tuple[str, str, str]]:
    """Resolve *href* to ``(platform, clean_url, expose_id)`` or ``None``.

    Understands direct portal links and the tracking redirects some alert
    mails wrap them in (the real expose URL url-encoded in a query
    parameter).  Query strings are dropped entirely - they only carry
    tracking parameters (utm_* and friends) - so the same expose always
    yields the same URL.
    """
    if not href:
        return None
    parsed = urlparse(href.strip())
    direct = _match_portal(parsed)
    if direct:
        return direct
    # Redirect wrapper: the portal URL hides in a query parameter
    # (parse_qs already url-decodes the values).
    for values in parse_qs(parsed.query).values():
        for value in values:
            if value.startswith(("http://", "https://")):
                unwrapped = _match_portal(urlparse(value))
                if unwrapped:
                    return unwrapped
    return None


def _match_portal(parsed) -> Optional[Tuple[str, str, str]]:
    """Match one parsed URL against the known portal detail-page shapes."""
    host = parsed.netloc.lower()
    for suffix, marker, platform, id_pattern in PORTAL_PATTERNS:
        if host != suffix and not host.endswith("." + suffix):
            continue
        if marker not in parsed.path:
            continue
        match = id_pattern.search(parsed.path)
        if not match:
            continue
        return platform, f"https://{parsed.netloc}{parsed.path}", match.group(1)
    return None


def _message_body(message: Message) -> str:
    """The HTML body of *message*, falling back to the plain-text part.

    Walks all multipart branches; ``get_content()`` (available through
    ``policy.default``) transparently decodes quoted-printable and base64.
    """
    html_part: Optional[Message] = None
    text_part: Optional[Message] = None
    for part in message.walk():
        if part.is_multipart():
            continue
        content_type = part.get_content_type()
        if content_type == "text/html" and html_part is None:
            html_part = part
        elif content_type == "text/plain" and text_part is None:
            text_part = part
    part = html_part or text_part
    if part is None:
        return ""
    content = part.get_content()
    return content if isinstance(content, str) else ""


class Mailbox(ABC):
    """Message transport: a real IMAP account or saved ``.eml`` files."""

    @abstractmethod
    def fetch(self) -> List[bytes]:
        """Return raw RFC822 messages."""


class FileMailbox(Mailbox):
    """Serves ``.eml`` files from a directory - for tests and offline runs."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def fetch(self) -> List[bytes]:
        return [path.read_bytes() for path in sorted(self.directory.glob("*.eml"))]


class ImapMailbox(Mailbox):
    """Fetches recent alert mails from an IMAP inbox (read-only).

    All credentials are explicit constructor arguments - nothing is read
    from the environment and nothing is hardcoded here.  Any IMAP or network
    error is logged and yields an empty result: a broken mailbox must not
    kill the pipeline run.
    """

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        port: int = 993,
        folder: str = "INBOX",
        since_days: int = 3,
        sender_filters: Optional[List[str]] = None,
    ) -> None:
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.folder = folder
        self.since_days = since_days
        self.sender_filters = list(sender_filters or [])

    def fetch(self) -> List[bytes]:
        messages: List[bytes] = []
        since = imap_since_criterion(self.since_days)
        try:
            with imaplib.IMAP4_SSL(self.host, self.port) as client:
                client.login(self.user, self.password)
                client.select(self.folder, readonly=True)
                for message_id in self._search(client, since):
                    status, data = client.fetch(message_id, "(RFC822)")
                    if status != "OK" or not data or not isinstance(data[0], tuple):
                        LOGGER.warning("IMAP fetch of message %r failed", message_id)
                        continue
                    messages.append(data[0][1])
        except (imaplib.IMAP4.error, OSError) as exc:
            LOGGER.warning("IMAP mailbox %s unreachable: %s", self.host, exc)
            return []
        return messages

    def _search(self, client: imaplib.IMAP4, since: str) -> List[bytes]:
        """Message ids matching the SINCE window and the sender filters."""
        ids: set = set()
        if self.sender_filters:
            for sender in self.sender_filters:
                status, data = client.search(None, "SINCE", since, "FROM", f'"{sender}"')
                if status == "OK" and data and data[0]:
                    ids.update(data[0].split())
        else:
            status, data = client.search(None, "SINCE", since)
            if status == "OK" and data and data[0]:
                ids.update(data[0].split())
        return sorted(ids, key=int)


@dataclass
class EmailAlertScraper(BaseScraper):
    """Extracts listings from Suchagent alert e-mails.

    ``platform`` is "email" for discovery bookkeeping, but every extracted
    listing carries the portal it really links to ("is24", "immowelt",
    "kleinanzeigen"), so downstream agents treat it like a scraped one.
    """

    platform: str = "email"
    mailbox: Optional[Mailbox] = None

    # --- Discovery --------------------------------------------------------
    def discover(self) -> List[RawListing]:
        if self.mailbox is None:
            self.log_error("no mailbox configured, e-mail discovery skipped")
            return []
        raws: List[RawListing] = []
        for raw_bytes in self.mailbox.fetch():
            try:
                message = message_from_bytes(raw_bytes, policy=policy.default)
                body = _message_body(message)
            except Exception as exc:  # one broken mail must not kill the batch
                self.log_error(f"undecodable e-mail skipped: {exc}")
                continue
            if not body.strip():
                self.log_error("e-mail without usable body skipped")
                continue
            source = clean_text(message.get("Message-ID", "")) or "mailbox"
            raws.append(
                RawListing(platform=self.platform, source_url=source, html=body)
            )
        return raws

    # --- Extraction -------------------------------------------------------
    def extract(self, raw: RawListing) -> List[ApartmentListing]:
        soup = BeautifulSoup(raw.html, "html.parser")
        listings: List[ApartmentListing] = []
        seen_urls = set()
        for anchor in soup.find_all("a", href=True):
            resolved = portal_expose_url(anchor["href"])
            if not resolved:
                continue  # footer/tracking link, not a detail page
            portal, url, expose_id = resolved
            if url in seen_urls:
                continue
            seen_urls.add(url)
            try:
                listing = self._parse_block(anchor, portal, url, expose_id)
            except Exception as exc:  # one broken block must not kill the mail
                self.log_error(f"could not parse the block around {url}: {exc}")
                continue
            if listing:
                listings.append(listing)
        return listings

    def _parse_block(
        self, anchor: Tag, portal: str, url: str, expose_id: str
    ) -> Optional[ApartmentListing]:
        block = self._listing_block(anchor)
        source = block if block is not None else anchor
        text = clean_text(source.get_text(" ", strip=True))

        rooms = parse_rooms(text)
        area = parse_area(text)
        if rooms is None or area is None:
            self.log_error(f"no rooms/area near link, skipped: {url}")
            return None

        warm_rent = parse_labeled_price(text, WARM_RENT_LABELS)
        cold_rent = parse_labeled_price(text, COLD_RENT_LABELS)
        if warm_rent is None and cold_rent is None:
            cold_rent = parse_price(text)
        warm_estimated = False
        if warm_rent is None and cold_rent is not None:
            warm_rent = round(cold_rent * WARM_RENT_ESTIMATE_FACTOR, 2)
            warm_estimated = True
        if warm_rent is None:
            self.log_error(f"no price near link, skipped: {url}")
            return None

        title = clean_text(anchor.get_text(" ", strip=True))
        if not title and block is not None:
            heading = block.find(["h1", "h2", "h3", "h4", "strong", "b"])
            if heading:
                title = clean_text(heading.get_text(" ", strip=True))
        if not title:
            title = f"Wohnung {expose_id}"

        haystack = f"{title} {text}"
        return ApartmentListing(
            id=f"{portal}-{expose_id}",
            platform=portal,
            url=url,
            title=title,
            description=text,
            rooms=rooms,
            area_sqm=area,
            cold_rent=cold_rent,
            warm_rent=warm_rent,
            warm_rent_is_estimated=warm_estimated,
            kitchen_size_hint=kitchen_size_hint(
                haystack, self.config.small_kitchen_terms
            ),
            **detect_features(haystack),
        )

    def _listing_block(self, anchor: Tag) -> Optional[Tag]:
        """Nearest ancestor that carries the listing's key figures.

        Alert mails are table layouts: link, price and size sit in sibling
        cells, so we climb until the surrounding block contains both a price
        and an area - and never past the document body, where neighbouring
        listings would bleed into each other.
        """
        node = anchor
        for _ in range(_MAX_ANCESTOR_HOPS):
            node = node.parent
            if not isinstance(node, Tag) or node.name in ("body", "html"):
                break
            if node.name not in ("table", "td", "tr", "div"):
                continue
            text = node.get_text(" ", strip=True)
            if parse_price(text) is not None and parse_area(text) is not None:
                return node
        return None
