"""Scam detection and plausibility checks.

Nothing here removes a listing - it only annotates it.  The FilterAgent decides
what to do with the annotations, and the report always shows why something was
flagged so the decision stays with the user.
"""

from __future__ import annotations

import re
from typing import Dict, List, Sequence, Tuple

from wohnungssuche.config import SearchConfig
from wohnungssuche.geo import normalise
from wohnungssuche.models import ApartmentListing, ScamReason

# Phrases are matched against normalised text (lowercase, umlauts transliterated).
SCAM_PATTERNS: Dict[ScamReason, Sequence[str]] = {
    ScamReason.WESTERN_UNION: (
        "western union",
        "westernunion",
        "moneygram",
        "money gram",
        "ria money",
        "bitcoin",
        "kryptowaehrung",
    ),
    ScamReason.VORKASSE: (
        "vorkasse",
        "vorauskasse",
        "vorauszahlung",
        "anzahlung vor der besichtigung",
        "kaution vor der besichtigung",
        "kaution vorab",
        "zuerst ueberweisen",
        "vorab ueberweisen",
        "treuhand",
        "escrow",
    ),
    ScamReason.LANDLORD_ABROAD: (
        "im ausland",
        "bin derzeit in",
        "befinde mich derzeit im ausland",
        "nicht persoenlich zeigen",
        "kann die wohnung nicht zeigen",
        "arbeite im ausland",
        "wohne im ausland",
    ),
    ScamReason.KEY_BY_MAIL: (
        "schluessel per post",
        "schluessel werden per post",
        "schluessel zusenden",
        "schluesseluebergabe per post",
        "per kurier",
        "dhl schluessel",
    ),
    ScamReason.URGENCY_PRESSURE: (
        "nur heute",
        "nur noch heute",
        "schnell entschlossene",
        "wer zuerst kommt",
        "sofort zuschlagen",
        "nur fuer kurze zeit",
    ),
    ScamReason.ID_DOCUMENTS_UPFRONT: (
        "ausweiskopie",
        "kopie ihres ausweises",
        "passkopie",
        "reisepass senden",
        "ausweis zuerst",
    ),
    ScamReason.SUSPICIOUS_TEXT: (
        "keine besichtigung moeglich",
        "ohne besichtigung",
        "gott segne",
        "god bless",
        "kontaktieren sie mich per e-mail fuer weitere details",
        "nur per whatsapp",
    ),
}

# Human-readable German labels for the report.
SCAM_LABELS: Dict[str, str] = {
    ScamReason.WESTERN_UNION.value: "Zahlung per Western Union / Krypto verlangt",
    ScamReason.VORKASSE.value: "Vorkasse vor Besichtigung verlangt",
    ScamReason.UNREALISTIC_PRICE.value: "Preis unrealistisch niedrig",
    ScamReason.NO_CONTACT.value: "Keine Kontaktdaten auffindbar",
    ScamReason.SUSPICIOUS_TEXT.value: "Verdächtige Formulierungen im Text",
    ScamReason.LANDLORD_ABROAD.value: "Vermieter angeblich im Ausland",
    ScamReason.KEY_BY_MAIL.value: "Schlüsselübergabe per Post angeboten",
    ScamReason.URGENCY_PRESSURE.value: "Zeitdruck / Dringlichkeitsmasche",
    ScamReason.ID_DOCUMENTS_UPFRONT.value: "Ausweiskopie vorab verlangt",
    ScamReason.INCONSISTENT_DATA.value: "Unplausible Eckdaten",
}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")
PHONE_RE = re.compile(r"(?:\+49|0)[\s/()-]?\d{2,5}[\s/()-]?\d{3,}")


class ScamDetector:
    """Annotates listings with scam indicators and plausibility problems."""

    def __init__(self, config: SearchConfig) -> None:
        self.config = config

    def check(self, listing: ApartmentListing) -> List[str]:
        """Return the scam reasons found for *listing* (also sets them on it)."""
        text = normalise(listing.searchable_text)
        reasons: List[str] = []

        for reason, phrases in SCAM_PATTERNS.items():
            if any(phrase in text for phrase in phrases):
                reasons.append(reason.value)

        price_per_sqm = listing.price_per_sqm
        if price_per_sqm is not None and price_per_sqm < self.config.min_plausible_eur_per_sqm:
            reasons.append(ScamReason.UNREALISTIC_PRICE.value)

        if self._is_implausible(listing):
            reasons.append(ScamReason.INCONSISTENT_DATA.value)

        # Only meaningful once the detail page was actually read - search
        # result cards never carry contact details on any of these portals.
        if listing.details_fetched and not any(
            [listing.contact_name, listing.contact_email, listing.contact_phone]
        ):
            reasons.append(ScamReason.NO_CONTACT.value)

        reasons = sorted(set(reasons))
        listing.scam_reasons = reasons
        listing.is_scam_flagged = bool(reasons)
        return reasons

    def _is_implausible(self, listing: ApartmentListing) -> bool:
        if not (0 < listing.rooms <= 15):
            return True
        if not (10 <= listing.area_sqm <= 500):
            return True
        if listing.cold_rent is not None and listing.warm_rent < listing.cold_rent:
            return True
        # A room that is on average smaller than 8 m2 is not an apartment.
        if listing.rooms and listing.area_sqm / listing.rooms < 8:
            return True
        return False

    def check_all(self, listings) -> Tuple[List[ApartmentListing], int]:
        flagged = 0
        for listing in listings:
            if self.check(listing):
                flagged += 1
        return list(listings), flagged


def extract_contact(text: str):
    """Pull an e-mail address and phone number out of free text, if present."""
    email = EMAIL_RE.search(text)
    phone = PHONE_RE.search(text)
    return (email.group(0) if email else None, phone.group(0) if phone else None)
