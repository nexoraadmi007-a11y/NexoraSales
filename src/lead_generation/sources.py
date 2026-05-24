from __future__ import annotations

from src.models.schemas import Industry

LOCATION_PRIORITY = ["Abeokuta", "Ogun State", "Lagos"]

SEARCH_QUERIES = {
    Industry.school: [
        "private schools in {location}",
        "secondary schools in {location}",
        "nursery primary schools in {location}",
        "international schools in {location}",
    ],
    Industry.solar: [
        "solar installation companies in {location}",
        "solar energy companies in {location}",
        "inverter battery companies in {location}",
        "renewable energy installers in {location}",
    ],
}

BLOCKED_KEYWORDS = [
    "restaurant",
    "salon",
    "barber",
    "boutique",
    "supermarket",
    "hotel",
    "laundry",
    "fashion",
    "real estate",
]


def is_allowed_industry(name: str, category: str | None, industry: Industry) -> bool:
    text = f"{name} {category or ''}".lower()
    if any(word in text for word in BLOCKED_KEYWORDS):
        return False
    school_words = ["school", "academy", "college", "nursery", "primary", "secondary"]
    solar_words = ["solar", "energy", "renewable", "inverter", "battery", "power"]
    allowed_words = school_words if industry == Industry.school else solar_words
    return any(word in text for word in allowed_words)
