"""Search configuration.

All user criteria live here.  Values can be overridden from a JSON file so the
search can be tuned without touching code (``--config my-search.json``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import List

# Wiesbaden city centre (Schlossplatz / Marktkirche).
CITY_CENTER_LAT = 50.0826
CITY_CENTER_LON = 8.2400


@dataclass
class SearchConfig:
    """User search criteria and runtime knobs."""

    # --- Location ---------------------------------------------------------
    city: str = "Wiesbaden"
    center_lat: float = CITY_CENTER_LAT
    center_lon: float = CITY_CENTER_LON
    max_distance_km: float = 4.0

    # --- Hard criteria ----------------------------------------------------
    min_rooms: float = 3.0
    min_area_sqm: float = 70.0
    max_warm_rent_eur: float = 1600.0

    # --- Exclusions -------------------------------------------------------
    excluded_districts: List[str] = field(
        default_factory=lambda: ["Erbenheim", "Mainz-Kastel", "Kastel"]
    )
    # Kitchens that are too small for the tenants.  Matched case-insensitively
    # against title + description.
    small_kitchen_terms: List[str] = field(
        default_factory=lambda: [
            "Kochnische",
            "Minikueche",
            "Miniküche",
            "Pantry",
            "Pantrykueche",
            "Pantryküche",
            "Singlekueche",
            "Singleküche",
        ]
    )
    # WG rooms, sublets and temporary rentals are not wanted.
    excluded_offer_terms: List[str] = field(
        default_factory=lambda: [
            "WG-Zimmer",
            "WG Zimmer",
            "WG-geeignet",
            "Zwischenmiete",
            "Untermiete",
            "Untervermietung",
            "Wohnen auf Zeit",
            "Wohnung auf Zeit",
            "auf Zeit",
            "Monteurzimmer",
            "Monteurwohnung",
            "Boardinghouse",
            "Serviced Apartment",
            "moebliertes Zimmer",
            "möbliertes Zimmer",
            "Zimmer zur Untermiete",
            "befristet",
            "Zeitmietvertrag",
        ]
    )

    # --- Nice to have (flagged, never filtered) ---------------------------
    wants_parking: bool = True

    # --- Tenant profile (used for the enquiry draft only) -----------------
    tenant_description: str = "Paar, Nichtraucher, keine Haustiere"

    # --- Platforms --------------------------------------------------------
    platforms: List[str] = field(
        default_factory=lambda: ["is24", "immowelt", "kleinanzeigen"]
    )
    max_pages_per_platform: int = 3
    # Fetching each expose page costs one polite request per listing; it is
    # what makes scam detection and contact extraction possible.
    fetch_details: bool = True
    max_detail_fetches: int = 15
    # HEAD-check the expose URL of every match before reporting, so a listing
    # that was taken down between scrape and click is flagged, not clicked.
    verify_links: bool = True
    max_link_checks: int = 30

    # --- Alternative discovery sources ------------------------------------
    # E-mail alerts: the portals' own Suchagent mails, read via IMAP.  The
    # password is never stored here - only the NAME of the environment
    # variable that holds it.
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password_env: str = "WOHNUNGSSUCHE_IMAP_PASSWORD"
    imap_folder: str = "INBOX"
    imap_since_days: int = 3
    imap_sender_filters: List[str] = field(
        default_factory=lambda: [
            "immobilienscout24.de",
            "immowelt.de",
            "kleinanzeigen.de",
        ]
    )
    # Fredy (github.com/orangecoding/fredy) import: path to Fredy's listings
    # storage on this machine; empty = disabled.
    fredy_db_path: str = ""

    # --- Politeness -------------------------------------------------------
    request_delay_seconds: float = 4.0
    request_timeout_seconds: float = 30.0
    max_retries: int = 3
    respect_robots_txt: bool = True

    # --- Plausibility -----------------------------------------------------
    # Anything below this warm rent per m2 is implausible for Wiesbaden and is
    # treated as a scam indicator rather than a bargain.
    min_plausible_eur_per_sqm: float = 6.0

    @classmethod
    def from_json(cls, path: str | Path) -> "SearchConfig":
        """Build a config from a JSON file, falling back to defaults."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"Unknown config keys: {sorted(unknown)}")
        return cls(**data)
