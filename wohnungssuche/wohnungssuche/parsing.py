"""Text parsing helpers for German real-estate listings."""

from __future__ import annotations

import re
from typing import Optional

# German number formatting: 1.234,56 -> 1234.56
_NUMBER_RE = re.compile(r"\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?")

_PRICE_RE = re.compile(
    r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?)\s*(?:€|EUR\b|Euro\b)",
    re.IGNORECASE,
)
# "3 Zimmer", "3,5 Zi.", "3-Zimmer-Wohnung" - the hyphen form is common in titles.
_ROOMS_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*[-\u2013]?\s*(?:Zimmer\b|Zi\.|Zi\b|Zim\.)", re.IGNORECASE
)
_AREA_RE = re.compile(
    r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?)\s*(?:m²|m2|qm\b|Quadratmeter\b)",
    re.IGNORECASE,
)

FEATURE_PATTERNS = {
    "has_ebk": r"\bEBK\b|Einbaukueche|Einbauküche|Einbau-Kueche|Einbau-Küche",
    "has_parking": (
        r"Stellplatz|Garage|Tiefgarage|Carport|Parkplatz|TG-Stellplatz|Duplexparker"
    ),
    "has_balcony": r"Balkon|Loggia|Dachterrasse|Terrasse",
    "has_garden": r"Garten|Gartenanteil|Gartenmitbenutzung",
    "has_elevator": r"Aufzug|Fahrstuhl|Lift\b|Personenaufzug",
}

_LARGE_KITCHEN_RE = re.compile(
    r"Wohnkueche|Wohnküche|separate Kueche|separate Küche|grosse Kueche|große Küche"
    r"|Essk(?:ue|ü)che|geschlossene K(?:ue|ü)che",
    re.IGNORECASE,
)


def parse_german_number(text: str) -> Optional[float]:
    """Parse ``1.234,56`` / ``1234.56`` / ``80`` into a float."""
    if not text:
        return None
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    raw = match.group(0)
    if "." in raw and "," in raw:  # 1.234,56
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:  # 1234,56
        raw = raw.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):  # 1.234 (thousands)
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_price(text: str) -> Optional[float]:
    """Extract the first euro amount from *text*."""
    if not text:
        return None
    match = _PRICE_RE.search(text)
    return parse_german_number(match.group(1)) if match else None


def parse_rooms(text: str) -> Optional[float]:
    if not text:
        return None
    match = _ROOMS_RE.search(text)
    return parse_german_number(match.group(1)) if match else None


def parse_area(text: str) -> Optional[float]:
    if not text:
        return None
    match = _AREA_RE.search(text)
    return parse_german_number(match.group(1)) if match else None


def detect_features(text: str) -> dict:
    """Return the boolean feature flags implied by *text*."""
    return {
        name: bool(re.search(pattern, text, re.IGNORECASE))
        for name, pattern in FEATURE_PATTERNS.items()
    }


def kitchen_size_hint(text: str, small_terms) -> str:
    """Classify the kitchen as ``small``, ``large``, ``ebk_unknown`` or ``unknown``."""
    for term in small_terms:
        if re.search(re.escape(term), text, re.IGNORECASE):
            return "small"
    if _LARGE_KITCHEN_RE.search(text):
        return "large"
    if re.search(FEATURE_PATTERNS["has_ebk"], text, re.IGNORECASE):
        return "ebk_unknown"
    return "unknown"


def clean_text(value: Optional[str]) -> str:
    """Collapse whitespace; ``None`` becomes an empty string."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


_LABEL_VALUE_TEMPLATE = r"{label}\s*[:\-]?\s*(?:ca\.\s*)?({value})"
_VALUE_LABEL_TEMPLATE = r"({value})\s*(?:ca\.\s*)?{label}"

_PRICE_VALUE = r"\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?"


def parse_labeled_price(text: str, labels) -> Optional[float]:
    """Find a euro amount next to one of *labels*, in either order.

    Handles both ``Warmmiete: 1.450 €`` and ``1.450 € Warmmiete`` because the
    platforms disagree on which side the label sits.
    """
    if not text:
        return None
    for label in labels:
        for template in (_LABEL_VALUE_TEMPLATE, _VALUE_LABEL_TEMPLATE):
            pattern = template.format(
                label=label, value=_PRICE_VALUE + r"\s*(?:€|EUR|Euro)"
            )
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = parse_german_number(match.group(1))
                if value:
                    return value
    return None
