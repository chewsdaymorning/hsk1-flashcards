"""HTML and JSON report generation.

All markup lives in ``templates/report.html`` and all styling in
``static/style.css``.  Python only passes data in - no HTML is ever built by
string concatenation here (lesson 1 of the build brief).
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape

from wohnungssuche.config import SearchConfig
from wohnungssuche.models import ApartmentListing, PlatformStatus
from wohnungssuche.validation import SCAM_LABELS

LOGGER = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"


def format_eur(value) -> str:
    """1420.0 -> '1.420 €'."""
    if value is None:
        return "–"
    return f"{value:,.0f} €".replace(",", ".")


def format_number(value, decimals: int = 1) -> str:
    """3.5 -> '3,5';  86.0 -> '86'."""
    if value is None:
        return "–"
    if float(value).is_integer():
        return f"{int(value):,}".replace(",", ".")
    return f"{value:,.{decimals}f}".replace(",", "#").replace(".", ",").replace("#", ".")


class ReportGenerator:
    """Renders the daily report from Jinja2 templates."""

    def __init__(self, config: SearchConfig, output_dir: Path | str = "reports") -> None:
        self.config = config
        self.output_dir = Path(output_dir)
        self.environment = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.environment.filters["eur"] = format_eur
        self.environment.filters["num"] = format_number

    def generate(
        self,
        matches: Sequence[ApartmentListing],
        non_matches: Sequence[ApartmentListing],
        flagged: Sequence[ApartmentListing],
        platform_status: Sequence[PlatformStatus] = (),
        warnings: Dict[str, List[str]] = None,
        new_hashes: Iterable[str] = (),
        agent_log: Sequence[Dict] = (),
        timestamp: datetime = None,
    ) -> Tuple[Path, Path]:
        """Write ``<report>.html`` plus a JSON snapshot; return both paths."""
        timestamp = timestamp or datetime.now()
        warnings = warnings or {}
        new_hashes = set(new_hashes)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._copy_static()

        # Scam-flagged listings are shown in their own section, never mixed in.
        flagged_hashes = {listing.unique_hash for listing in flagged}
        clean_non_matches = [
            listing for listing in non_matches if listing.unique_hash not in flagged_hashes
        ]

        html = self.environment.get_template("report.html").render(
            generated_at=timestamp.strftime("%d.%m.%Y um %H:%M"),
            date=timestamp.strftime("%d.%m.%Y"),
            config=self.config,
            matches=list(matches),
            non_matches=clean_non_matches,
            flagged=list(flagged),
            platform_status=list(platform_status),
            warnings=warnings,
            new_hashes=new_hashes,
            agent_log=list(agent_log),
            scam_labels=SCAM_LABELS,
        )

        stamp = timestamp.strftime("%Y-%m-%d_%H%M")
        html_path = self.output_dir / f"wohnungssuche_{stamp}.html"
        html_path.write_text(html, encoding="utf-8")
        # Stable path for bookmarks and cron mails.
        (self.output_dir / "latest.html").write_text(html, encoding="utf-8")

        json_path = self.output_dir / f"wohnungssuche_{stamp}.json"
        json_path.write_text(
            json.dumps(
                {
                    "generated_at": timestamp.isoformat(),
                    "criteria": {
                        "min_rooms": self.config.min_rooms,
                        "min_area_sqm": self.config.min_area_sqm,
                        "max_warm_rent_eur": self.config.max_warm_rent_eur,
                        "max_distance_km": self.config.max_distance_km,
                        "excluded_districts": self.config.excluded_districts,
                    },
                    "platform_status": [status.__dict__ for status in platform_status],
                    "matches": [listing.to_dict() for listing in matches],
                    "non_matches": [listing.to_dict() for listing in clean_non_matches],
                    "flagged": [listing.to_dict() for listing in flagged],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        LOGGER.info("Report written to %s", html_path)
        return html_path, json_path

    def _copy_static(self) -> None:
        target = self.output_dir / "static"
        target.mkdir(parents=True, exist_ok=True)
        for asset in STATIC_DIR.glob("*"):
            if asset.is_file():
                shutil.copy2(asset, target / asset.name)


def render_enquiry(config: SearchConfig, listing: ApartmentListing) -> str:
    """Render an enquiry draft for the user to send themselves.

    This function returns text.  Nothing in this package sends it anywhere.
    """
    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,  # plain text, not HTML
    )
    environment.filters["eur"] = format_eur
    environment.filters["num"] = format_number
    return environment.get_template("anfrage.txt").render(config=config, listing=listing)
