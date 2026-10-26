"""Translation files must stay in step with each other."""

import json
from pathlib import Path

from custom_components.seasonal_groceries.const import Language

INTEGRATION = Path(__file__).parent.parent / "custom_components" / "seasonal_groceries"


def _flatten(document: dict, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for name, value in document.items():
        path = f"{prefix}{name}"
        if isinstance(value, dict):
            keys |= _flatten(value, f"{path}.")
        else:
            keys.add(path)
    return keys


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_ha_translation_files_match_strings() -> None:
    expected = _flatten(_load(INTEGRATION / "strings.json"))
    for language in Language:
        translated = _load(INTEGRATION / "translations" / f"{language.value}.json")
        assert _flatten(translated) == expected, language
