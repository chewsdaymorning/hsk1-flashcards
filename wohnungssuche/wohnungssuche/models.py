"""Data models for the pipeline.

Plain dataclasses (no third-party dependency) with light validation.  Every
model round-trips through ``to_dict``/``from_dict`` so it can be stored in
SQLite and dumped to JSON without extra glue.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

# Hosts that mean "we made this URL up".  A listing carrying one of these is a
# bug, not a listing - see lesson 5 of the build brief.
FORBIDDEN_URL_HOSTS = {
    "example.com",
    "www.example.com",
    "example.org",
    "picsum.photos",
    "via.placeholder.com",
    "placehold.it",
    "placekitten.com",
}


class ScamReason(str, Enum):
    WESTERN_UNION = "western_union"
    VORKASSE = "vorkasse"
    UNREALISTIC_PRICE = "unrealistic_price"
    NO_CONTACT = "no_contact"
    SUSPICIOUS_TEXT = "suspicious_text"
    LANDLORD_ABROAD = "landlord_abroad"
    KEY_BY_MAIL = "key_by_mail"
    URGENCY_PRESSURE = "urgency_pressure"
    ID_DOCUMENTS_UPFRONT = "id_documents_upfront"
    INCONSISTENT_DATA = "inconsistent_data"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


def is_real_url(url: str) -> bool:
    """True if *url* is an absolute http(s) URL on a non-placeholder host."""
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    return parsed.netloc.lower() not in FORBIDDEN_URL_HOSTS


@dataclass
class RawListing:
    """One un-parsed search result, as handed from Discovery to Extraction."""

    platform: str
    source_url: str
    html: str
    fetched_at: datetime = field(default_factory=datetime.now)


@dataclass
class ApartmentListing:
    """A single apartment offer, normalised across platforms."""

    id: str
    platform: str
    url: str  # real, clickable expose URL
    title: str
    rooms: float
    area_sqm: float
    warm_rent: float

    description: str = ""
    address: str = ""
    district: str = ""
    city: str = "Wiesbaden"

    cold_rent: Optional[float] = None
    nebenkosten: Optional[float] = None
    deposit: Optional[float] = None
    # True when no Warmmiete was published and the value was derived from
    # the cold rent - shown as such in the report, never silently.
    warm_rent_is_estimated: bool = False

    lat: Optional[float] = None
    lon: Optional[float] = None
    distance_to_center_km: Optional[float] = None

    has_ebk: bool = False
    has_parking: bool = False
    has_balcony: bool = False
    has_garden: bool = False
    has_elevator: bool = False
    kitchen_size_hint: str = "unknown"  # large | small | ebk_unknown | unknown

    image_urls: List[str] = field(default_factory=list)

    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    is_private: bool = False
    # True once the expose detail page was fetched; only then is a missing
    # contact meaningful (search-result cards never carry one).
    details_fetched: bool = False

    # Outcome of the optional liveness check on the expose URL:
    # "ok" (reachable), "dead" (404/410 - listing likely taken down),
    # "unchecked" (check disabled, capped, or inconclusive e.g. bot-blocked).
    link_status: str = "unchecked"

    is_scam_flagged: bool = False
    scam_reasons: List[str] = field(default_factory=list)
    matches_criteria: bool = False
    exclude_reasons: List[str] = field(default_factory=list)

    scraped_at: datetime = field(default_factory=datetime.now)
    published_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        # Drop anything that would render as a dead link or a stock photo.
        if not is_real_url(self.url):
            raise ValueError(
                f"Listing {self.id!r} has a non-real expose URL: {self.url!r}"
            )
        self.image_urls = [u for u in self.image_urls if is_real_url(u)]

    # --- Derived values ---------------------------------------------------
    @property
    def price_per_sqm(self) -> Optional[float]:
        if self.warm_rent and self.area_sqm:
            return round(self.warm_rent / self.area_sqm, 2)
        return None

    @property
    def unique_hash(self) -> str:
        """Stable identity across platforms, used for de-duplication."""
        content = f"{self.platform}|{self.title}|{self.address}|{self.warm_rent}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    @property
    def searchable_text(self) -> str:
        return " ".join([self.title, self.description, self.address, self.district])

    # --- Serialisation ----------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["scraped_at"] = self.scraped_at.isoformat()
        data["published_at"] = (
            self.published_at.isoformat() if self.published_at else None
        )
        data["price_per_sqm"] = self.price_per_sqm
        data["unique_hash"] = self.unique_hash
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApartmentListing":
        data = dict(data)
        data.pop("price_per_sqm", None)
        data.pop("unique_hash", None)
        for key in ("scraped_at", "published_at"):
            value = data.get(key)
            if isinstance(value, str):
                data[key] = datetime.fromisoformat(value)
        return cls(**data)


@dataclass
class AgentMessage:
    """Typed envelope passed between agents."""

    sender: str
    recipient: str
    payload: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def ok(self) -> bool:
        return not self.errors

    def listings(self) -> List[ApartmentListing]:
        return list(self.payload.get("listings", []))


@dataclass
class PlatformStatus:
    """Per-platform outcome, surfaced in the report (lesson 7)."""

    platform: str
    success: bool
    listings_found: int = 0
    message: str = ""
