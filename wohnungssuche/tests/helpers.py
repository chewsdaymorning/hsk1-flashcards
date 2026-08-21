"""Shared test helpers."""

from wohnungssuche.config import SearchConfig
from wohnungssuche.models import ApartmentListing

VALID_URL = "https://www.immobilienscout24.de/expose/123456789"


def make_listing(**overrides) -> ApartmentListing:
    """A listing that passes every criterion unless overridden."""
    data = dict(
        id="is24-123456789",
        platform="is24",
        url=VALID_URL,
        title="Helle 3-Zimmer-Wohnung",
        description="Schöne Wohnung mit separater Küche und Balkon.",
        address="Bertramstraße 12, Wiesbaden",
        district="Rheingauviertel",
        rooms=3.0,
        area_sqm=82.0,
        warm_rent=1400.0,
        cold_rent=1150.0,
        distance_to_center_km=1.9,
        kitchen_size_hint="large",
    )
    data.update(overrides)
    return ApartmentListing(**data)


def config(**overrides) -> SearchConfig:
    return SearchConfig(**overrides)
