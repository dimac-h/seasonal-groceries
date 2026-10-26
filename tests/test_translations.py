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


def test_card_translations_have_identical_keys() -> None:
    folder = INTEGRATION / "frontend" / "src" / "translations"
    documents = {path.stem: _load(path) for path in sorted(folder.glob("*.json"))}

    assert {language.value for language in Language} <= set(documents)
    expected = _flatten(documents["en"])
    for code, document in documents.items():
        assert _flatten(document) == expected, code
        assert all(str(value).strip() for value in document.values()), code
