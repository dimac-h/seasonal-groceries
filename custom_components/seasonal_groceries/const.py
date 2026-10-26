"""Constants for the Seasonal Groceries integration."""

from enum import StrEnum

DOMAIN = "seasonal_groceries"

# Built frontend (Vite output in www/), served as a static path.
FRONTEND_PATH = f"/{DOMAIN}_frontend"
CARD_MODULE_URL = f"{FRONTEND_PATH}/seasonal-groceries-cards.js"


class Language(StrEnum):
    """
    Grocery languages. Adding a member here, plus its data file, adds a language.

    Each member needs `data/produce_<value>.json` (item names and aliases). Nothing
    else in the Python code lists languages.
    """

    NL = "nl"
    EN = "en"


DEFAULT_LANGUAGE = Language.EN


def language_for(code: str | None) -> Language:
    """Map a Home Assistant language code such as "nl" or "nl-NL" to a Language."""
    base = (code or "").split("-")[0].lower()
    try:
        return Language(base)
    except ValueError:
        return DEFAULT_LANGUAGE
