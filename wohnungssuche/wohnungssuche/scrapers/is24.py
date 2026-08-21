"""ImmobilienScout24 scraper."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Pattern, Sequence

from wohnungssuche.scrapers.card import ResultCardScraper


@dataclass
class IS24Scraper(ResultCardScraper):
    platform: str = "is24"
    base_url: str = "https://www.immobilienscout24.de"
    search_path: str = "/Suche/de/hessen/wiesbaden/wohnung-mieten"
    detail_path_marker: str = "/expose/"
    id_pattern: Optional[Pattern[str]] = field(
        default_factory=lambda: re.compile(r"/expose/(\d+)")
    )

    item_selectors: Sequence[str] = (
        "[data-testid='result-list-item']",
        "li.result-list__listing",
        "article.result-list-entry",
    )
    link_selectors: Sequence[str] = (
        "a[data-testid='result-list-entry']",
        "a.result-list-entry__brand-title-container",
    )
    title_selectors: Sequence[str] = (
        "[data-testid='result-list-entry-title']",
        "h2.result-list-entry__brand-title",
        "h2",
        "h5",
    )
    address_selectors: Sequence[str] = (
        "[data-testid='result-list-entry-address']",
        ".result-list-entry__address",
        ".result-list-entry__map-link",
    )
    rooms_selectors: Sequence[str] = ("[data-testid='result-list-entry-rooms']",)
    area_selectors: Sequence[str] = ("[data-testid='result-list-entry-area']",)

    def search_params(self, page: int) -> dict:
        return {
            "numberofrooms": f"{self.config.min_rooms:g}.0-",
            "livingspace": f"{self.config.min_area_sqm:g}.0-",
            "price": f"-{self.config.max_warm_rent_eur:g}.0",
            "pricetype": "rentpermonth",
            "sorting": "2",  # newest first
            "pagenumber": str(page),
        }
