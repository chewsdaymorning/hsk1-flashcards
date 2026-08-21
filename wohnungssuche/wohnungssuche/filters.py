"""Criteria filter.

Splits listings into matches and non-matches and records, in German, exactly
why something was dropped, so the report can explain every decision.
"""

from __future__ import annotations

import re
from typing import List, Sequence, Tuple

from wohnungssuche.config import SearchConfig
from wohnungssuche.geo import detect_district, normalise
from wohnungssuche.models import ApartmentListing
from wohnungssuche.validation import SCAM_LABELS


def _contains_term(text: str, term: str) -> bool:
    """Whole-word match of *term* in already-normalised *text*."""
    pattern = r"\s+".join(re.escape(part) for part in normalise(term).split())
    return bool(re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text))


def format_number(value: float) -> str:
    """German-style number: 1600 -> '1.600', 3.5 -> '3,5'."""
    if float(value).is_integer():
        return f"{int(value):,}".replace(",", ".")
    return f"{value:.1f}".replace(".", ",")


class FilterEngine:
    """Applies the user's hard criteria; nice-to-haves are only flagged."""

    def __init__(self, config: SearchConfig) -> None:
        self.config = config

    def evaluate(self, listing: ApartmentListing) -> List[str]:
        """Return the reasons *listing* fails the criteria (empty = match)."""
        config = self.config
        reasons: List[str] = []
        text = normalise(listing.searchable_text)

        if listing.rooms < config.min_rooms:
            reasons.append(
                f"Nur {format_number(listing.rooms)} Zimmer "
                f"(mind. {format_number(config.min_rooms)})"
            )
        if listing.area_sqm < config.min_area_sqm:
            reasons.append(
                f"Nur {format_number(listing.area_sqm)} m² "
                f"(mind. {format_number(config.min_area_sqm)} m²)"
            )
        if listing.warm_rent > config.max_warm_rent_eur:
            estimate_note = " (geschätzt)" if listing.warm_rent_is_estimated else ""
            reasons.append(
                f"Warmmiete {format_number(listing.warm_rent)} EUR{estimate_note} "
                f"über Limit {format_number(config.max_warm_rent_eur)} EUR"
            )

        district = normalise(listing.district or detect_district(listing.searchable_text))
        for excluded in config.excluded_districts:
            if district == normalise(excluded) or _contains_term(text, excluded):
                reasons.append(f"Stadtteil ausgeschlossen: {excluded}")
                break

        if listing.distance_to_center_km is not None:
            if listing.distance_to_center_km > config.max_distance_km:
                reasons.append(
                    f"{format_number(round(listing.distance_to_center_km, 1))} km "
                    f"vom Zentrum (max. {format_number(config.max_distance_km)} km)"
                )

        # The hint is set while scraping; re-check the text so a listing built
        # from another source (or an older DB row) is judged the same way.
        small_kitchen = listing.kitchen_size_hint == "small" or any(
            _contains_term(text, term) for term in config.small_kitchen_terms
        )
        if small_kitchen:
            reasons.append("Kleine Küche (Kochnische/Pantry/Singleküche)")

        for term in config.excluded_offer_terms:
            if _contains_term(text, term):
                reasons.append(f"Kein regulärer Mietvertrag: {term}")
                break

        if listing.is_scam_flagged:
            labels = ", ".join(
                SCAM_LABELS.get(reason, reason) for reason in listing.scam_reasons
            )
            reasons.append(f"Scam-Verdacht: {labels}")

        return reasons

    def warnings(self, listing: ApartmentListing) -> List[str]:
        """Non-blocking notes worth showing next to a match."""
        notes: List[str] = []
        if listing.distance_to_center_km is None:
            notes.append("Entfernung zum Zentrum unbekannt – bitte prüfen")
        if listing.warm_rent_is_estimated:
            notes.append("Warmmiete geschätzt (nur Kaltmiete veröffentlicht)")
        if listing.kitchen_size_hint in ("unknown", "ebk_unknown"):
            notes.append("Küchengröße unklar – bei Besichtigung prüfen")
        if self.config.wants_parking and not listing.has_parking:
            notes.append("Kein Stellplatz erwähnt (nice-to-have)")
        return notes

    def filter_listings(
        self, listings: Sequence[ApartmentListing]
    ) -> Tuple[List[ApartmentListing], List[ApartmentListing]]:
        matches: List[ApartmentListing] = []
        non_matches: List[ApartmentListing] = []
        for listing in listings:
            reasons = self.evaluate(listing)
            listing.exclude_reasons = reasons
            listing.matches_criteria = not reasons
            (matches if listing.matches_criteria else non_matches).append(listing)
        # Cheapest per square metre first - the best value at the top.
        matches.sort(key=lambda item: (item.price_per_sqm or 0, item.warm_rent))
        return matches, non_matches
