"""Kleinanzeigen (formerly eBay Kleinanzeigen) scraper.

Kleinanzeigen carries many private landlords, but also the highest share of
scam adverts - the ValidationAgent does the heavy lifting downstream.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Pattern, Sequence

from wohnungssuche.scrapers.card import ResultCardScraper


@dataclass
class KleinanzeigenScraper(ResultCardScraper):
    platform: str = "kleinanzeigen"
    base_url: str = "https://www.kleinanzeigen.de"
    # Category 203 = Mietwohnungen, location 3600 = Wiesbaden.
    search_path: str = "/s-wohnung-mieten/wiesbaden/c203l3600"
    detail_path_marker: str = "/s-anzeige/"
    id_pattern: Optional[Pattern[str]] = field(
        default_factory=lambda: re.compile(r"/s-anzeige/[^/]+/(\d+)")
    )

    item_selectors: Sequence[str] = (
        "article.aditem",
        "li.ad-listitem article",
    )
    link_selectors: Sequence[str] = (
        "a.ellipsis",
        "a[href*='/s-anzeige/']",
    )
    title_selectors: Sequence[str] = ("h2 a.ellipsis", "h2", "a.ellipsis")
    address_selectors: Sequence[str] = (
        ".aditem-main--top--left",
        ".aditem-main--top",
    )
    rooms_selectors: Sequence[str] = ()
    area_selectors: Sequence[str] = ()

    def search_params(self, page: int) -> dict:
        # Kleinanzeigen encodes filters in the path; the page number is the only
        # query parameter the public search honours reliably.
        return {"pageNum": str(page)}

    def search_url(self) -> str:
        return f"{self.base_url}{self.search_path}"
