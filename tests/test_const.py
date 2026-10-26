"""Tests for the language helpers."""

import pytest

from custom_components.seasonal_groceries.const import Language, language_for


@pytest.mark.parametrize(
    ("code", "language"),
    [
        ("nl", Language.NL),
        ("nl-NL", Language.NL),
        ("EN", Language.EN),
        ("en-GB", Language.EN),
        ("de", Language.EN),
        (None, Language.EN),
        ("", Language.EN),
    ],
)
def test_language_for(code: str | None, language: Language) -> None:
    assert language_for(code) is language
