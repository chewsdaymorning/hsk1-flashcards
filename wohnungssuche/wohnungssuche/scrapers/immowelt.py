"""Immowelt scraper."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Pattern, Sequence

from wohnungssuche.scrapers.card import ResultCardScraper


@dataclass
class ImmoweltScraper(ResultCardScraper):
    platform: str = "immowelt"
    base_url: str = "https://www.immowelt.de"
    search_path: str = "/liste/wiesbaden/wohnungen/mieten"
    detail_path_marker: str = "/expose/"
    id_pattern: Optional[Pattern[str]] = field(
        default_factory=lambda: re.compile(r"/expose/([A-Za-z0-9]+)")
    )

    item_selectors: Sequence[str] = (
        "[data-testid='serp-core-classified-card-testid']",
        "div[class*='EstateItem']",
        "div[class*='SearchList'] article",
    )
    link_selectors: Sequence[str] = ("a[href*='/expose/']",)
    title_selectors: Sequence[str] = (
        "[data-testid='cardmfe-description-box-test-id'] h2",
        "h2",
        "h3",
    )
    address_selectors: Sequence[str] = (
        "[data-testid='cardmfe-description-box-address']",
        "div[class*='estateFacts'] + div",
        "address",
    )
    rooms_selectors: Sequence[str] = (
        "[data-testid='cardmfe-keyfacts-testid'] div:nth-of-type(3)",
    )
    area_selectors: Sequence[str] = (
        "[data-testid='cardmfe-keyfacts-testid'] div:nth-of-type(2)",
    )

    def search_params(self, page: int) -> dict:
        return {
            "d": "true",
            "sd": "DESC",
            "sf": "TIMESTAMP",  # newest first
            "rm": f"{self.config.min_rooms:g}",
            "sr": f"{self.config.min_area_sqm:g}",
            "pr": f",{self.config.max_warm_rent_eur:g}",
            "sp": str(page),
        }
