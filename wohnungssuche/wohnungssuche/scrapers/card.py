"""Generic "result card" scraper.

All three portals render their search results the same way: a list of cards,
each holding a link to the expose, a title, an address, a thumbnail and a few
key figures.  The differences are selectors and query parameters, so the
parsing lives here once and the concrete scrapers only declare their markup.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Pattern, Sequence

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

# Nebenkosten are typically ~25 % on top of the cold rent in Hessen.  Used only
# when a listing publishes no Warmmiete, and always marked as an estimate.
WARM_RENT_ESTIMATE_FACTOR = 1.25

COLD_RENT_LABELS = ("Kaltmiete", "Nettokaltmiete", "Nettomiete", "Grundmiete")
WARM_RENT_LABELS = ("Warmmiete", "Gesamtmiete", "Gesamtkosten", "warm", "inkl. NK")
EXTRA_COST_LABELS = ("Nebenkosten", "Betriebskosten", "NK")
DEPOSIT_LABELS = ("Kaution", "Kaution/Genossenschaftsanteile")


@dataclass
class ResultCardScraper(BaseScraper):
    """Base for portals whose search results are a list of cards."""

    # --- markup declaration (overridden by subclasses) --------------------
    search_path: str = ""
    item_selectors: Sequence[str] = ()
    link_selectors: Sequence[str] = ()
    title_selectors: Sequence[str] = ()
    address_selectors: Sequence[str] = ()
    rooms_selectors: Sequence[str] = ()
    area_selectors: Sequence[str] = ()
    detail_path_marker: str = "/expose/"
    id_pattern: Optional[Pattern[str]] = None

    # --- URL building -----------------------------------------------------
    def search_url(self) -> str:
        return f"{self.base_url}{self.search_path}"

    def search_params(self, page: int) -> dict:
        raise NotImplementedError

    # --- Discovery --------------------------------------------------------
    def discover(self) -> List[RawListing]:
        raws: List[RawListing] = []
        for page in range(1, self.config.max_pages_per_platform + 1):
            result = self.fetcher.get(self.search_url(), params=self.search_params(page))
            if not result.ok:
                self.log_error(f"page {page}: {result.error}")
                break
            raws.append(
                RawListing(platform=self.platform, source_url=result.url, html=result.html)
            )
            if not self._items(BeautifulSoup(result.html, "html.parser")):
                break  # empty page: no point asking for the next one
        return raws

    def _items(self, soup: BeautifulSoup) -> List[Tag]:
        for selector in self.item_selectors:
            items = soup.select(selector)
            if items:
                return items
        # Last resort: any container holding a detail link.
        containers = []
        for anchor in soup.select(f"a[href*='{self.detail_path_marker}']"):
            containers.append(anchor.find_parent(["li", "article", "div"]) or anchor)
        return containers

    # --- Extraction -------------------------------------------------------
    def extract(self, raw: RawListing) -> List[ApartmentListing]:
        soup = BeautifulSoup(raw.html, "html.parser")
        listings: List[ApartmentListing] = []
        seen_urls = set()
        for item in self._items(soup):
            try:
                listing = self.parse_item(item)
            except Exception as exc:  # one broken card must not kill the page
                self.log_error(f"could not parse a result card: {exc}")
                continue
            if listing and listing.url not in seen_urls:
                seen_urls.add(listing.url)
                listings.append(listing)
        return listings

    def parse_item(self, item: Tag) -> Optional[ApartmentListing]:
        url = self.detail_url(item)
        if not url:
            return None

        text = item.get_text(" ", strip=True)
        listing_id = self.listing_id(url)
        title = self.select_text(item, self.title_selectors) or f"Wohnung {listing_id}"
        address = self.select_text(item, self.address_selectors)

        rooms = self._rooms(item, text)
        area = self._area(item, text)
        if rooms is None or area is None:
            self.log_error(f"no rooms/area on card, skipped: {url}")
            return None

        cold_rent = parse_labeled_price(text, COLD_RENT_LABELS)
        warm_rent = parse_labeled_price(text, WARM_RENT_LABELS)
        nebenkosten = parse_labeled_price(text, EXTRA_COST_LABELS)
        deposit = parse_labeled_price(text, DEPOSIT_LABELS)
        if cold_rent is None:
            cold_rent = parse_price(text)

        warm_estimated = False
        if warm_rent is None:
            if cold_rent is not None and nebenkosten is not None:
                warm_rent = round(cold_rent + nebenkosten, 2)
            elif cold_rent is not None:
                warm_rent = round(cold_rent * WARM_RENT_ESTIMATE_FACTOR, 2)
                warm_estimated = True
        if warm_rent is None:
            self.log_error(f"no price on card, skipped: {url}")
            return None

        haystack = f"{title} {text}"
        return ApartmentListing(
            id=f"{self.platform}-{listing_id}",
            platform=self.platform,
            url=url,
            title=title,
            description=clean_text(text),
            address=address,
            rooms=rooms,
            area_sqm=area,
            cold_rent=cold_rent,
            nebenkosten=nebenkosten,
            deposit=deposit,
            warm_rent=warm_rent,
            warm_rent_is_estimated=warm_estimated,
            image_urls=self.image_urls(item),
            kitchen_size_hint=kitchen_size_hint(
                haystack, self.config.small_kitchen_terms
            ),
            **detect_features(haystack),
        )

    # --- field helpers ----------------------------------------------------
    def detail_url(self, item: Tag) -> str:
        """The real, clickable expose URL taken from the card's href."""
        selectors = list(self.link_selectors) + [f"a[href*='{self.detail_path_marker}']"]
        for selector in selectors:
            anchor = item.select_one(selector)
            if anchor and anchor.get("href"):
                url = self.absolute_url(anchor["href"]).split("#")[0]
                if self.detail_path_marker in url:
                    return url
        return ""

    def listing_id(self, url: str) -> str:
        if self.id_pattern:
            match = self.id_pattern.search(url)
            if match:
                return match.group(1)
        return re.sub(r"[^A-Za-z0-9_-]", "-", url.rstrip("/").rsplit("/", 1)[-1])[:64]

    def select_text(self, item: Tag, selectors: Sequence[str]) -> str:
        for selector in selectors:
            node = item.select_one(selector)
            if node:
                value = clean_text(node.get_text(" ", strip=True))
                if value:
                    return value
        return ""

    def _rooms(self, item: Tag, text: str) -> Optional[float]:
        raw = self.select_text(item, self.rooms_selectors)
        if raw:
            rooms = parse_rooms(raw) or parse_rooms(f"{raw} Zimmer")
            if rooms:
                return rooms
        return parse_rooms(text)

    def _area(self, item: Tag, text: str) -> Optional[float]:
        raw = self.select_text(item, self.area_selectors)
        if raw:
            area = parse_area(raw) or parse_area(f"{raw} m²")
            if area:
                return area
        return parse_area(text)

    def image_urls(self, item: Tag) -> List[str]:
        """Real CDN image URLs from the card; portals lazy-load, so data-src wins."""
        urls: List[str] = []
        for source in item.select("picture source[srcset], source[srcset]"):
            candidate = source.get("srcset", "").split(",")[0].strip().split(" ")[0]
            if candidate:
                urls.append(self.absolute_url(candidate))
        for img in item.select("img"):
            for attribute in ("data-src", "data-lazy-src", "data-original", "src"):
                value = img.get(attribute)
                if value and not value.startswith("data:"):
                    urls.append(self.absolute_url(value))
                    break
        return list(dict.fromkeys(url for url in urls if url))
