"""The cards must register in the real Home Assistant frontend and render data."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    import pytest
    from playwright.sync_api import Locator, Page

SCREENSHOTS = Path(__file__).parent / "screenshots"
NARROW_PX = 360  # below the card's 420px container-query breakpoint
WIDE_PX = 700


def _recipe(page: Page, name: str) -> Locator:
    card = page.locator("seasonal-groceries-recipes-card")
    card.get_by_text(name).first.wait_for()
    return card.locator("a.recipe", has_text=name)


def _set_card_width(page: Page, width: int) -> Locator:
    card = page.locator("seasonal-groceries-recipes-card")
    card.evaluate("(el, w) => { el.style.width = `${w}px`; }", width)
    return card


def test_cards_register_without_configuration_errors(page: Page) -> None:
    for tag in (
        "seasonal-groceries-now-card",
        "seasonal-groceries-calendar-card",
        "seasonal-groceries-recipes-card",
        "seasonal-groceries-match-card",
    ):
        assert page.evaluate("(t) => !!customElements.get(t)", tag), tag
    expect(page.get_by_text("Configuration error")).to_have_count(0)


def test_now_card_lists_seasonal_items_with_pesticide_levels(page: Page) -> None:
    card = page.locator("seasonal-groceries-now-card").first

    expect(card.locator(".row").first).to_be_visible()
    expect(card.get_by_text("Few pesticides").first).to_be_visible()
    expect(card.get_by_text("Unknown").first).to_be_visible()


def test_cards_show_credits_in_the_footer(page: Page) -> None:
    footer = page.locator("seasonal-groceries-now-card sg-credits-footer").first

    expect(footer).to_contain_text("Voedingscentrum")
    expect(footer).to_contain_text("PAN Netherlands")


def test_calendar_card_highlights_the_current_month(page: Page) -> None:
    card = page.locator("seasonal-groceries-calendar-card").first

    expect(card.locator(".head.current")).to_have_count(1)
    expect(card.locator(".cell.on").first).to_be_visible()


def test_match_card_offers_review_actions(page: Page) -> None:
    card = page.locator("seasonal-groceries-match-card")

    expect(card).to_contain_text("Which seasonal item is")
    expect(card.get_by_text("Ignore")).to_be_visible()
    expect(card.get_by_text("No season")).to_be_visible()


def test_recipes_card_shows_ranked_recipes(page: Page) -> None:
    card = page.locator("seasonal-groceries-recipes-card")

    expect(card.get_by_text("Pompoensoep")).to_be_visible()
    badge = _recipe(page, "Pompoensoep").locator(".media .score")
    expect(badge).to_have_text("2 of 2 in season")
    image = _recipe(page, "Pompoensoep").locator(".media").bounding_box()
    box = badge.bounding_box()
    assert image
    assert box
    assert box["x"] - image["x"] < image["width"] / 2, "badge sits on the left"
    assert image["y"] + image["height"] - (box["y"] + box["height"]) < 12, (
        "at the bottom"
    )


def test_recipes_card_links_to_mealie(page: Page) -> None:
    link = _recipe(page, "Pompoensoep")

    expect(link).to_have_attribute("href", re.compile(r"/g/[^/]+/r/pompoensoep$"))
    expect(link).to_have_attribute("target", "_blank")
    expect(link).to_have_attribute("rel", re.compile("noopener"))


def test_recipes_card_shows_all_recipe_details(page: Page) -> None:
    recipe = _recipe(page, "Pompoensoep")

    expect(recipe.locator("img")).to_be_visible()
    expect(recipe.locator(".tag").first).to_be_visible()
    expect(recipe.locator(".favorite")).to_have_count(1)
    expect(recipe.locator(".stars ha-svg-icon")).to_have_count(5)
    expect(recipe.locator(".stars")).to_have_attribute(
        "aria-label", "Rated 3.7 out of 5"
    )
    expect(_recipe(page, "Tomatensalade").locator(".favorite")).to_have_count(0)


def test_recipes_card_clamps_long_descriptions(page: Page) -> None:
    description = _recipe(page, "Pompoensoep").locator(".description")

    metrics = description.evaluate(
        """el => ({
            clamped: el.scrollHeight > el.clientHeight,
            height: el.clientHeight,
            line: parseFloat(getComputedStyle(el).lineHeight)
                || parseFloat(getComputedStyle(el).fontSize) * 1.5,
        })"""
    )

    assert metrics["clamped"], metrics
    assert metrics["height"] <= 3 * metrics["line"] + 1, metrics


def test_recipe_without_data_has_no_broken_elements(page: Page) -> None:
    bare = _recipe(page, "Preischotel")

    expect(bare.locator(".media ha-svg-icon")).to_have_count(1)
    for selector in ("img", ".tags", ".tag", ".stars", ".favorite", ".description"):
        expect(bare.locator(selector)).to_have_count(0)
    expect(bare.locator(".media .score")).to_have_text("1 of 1 in season")
    expect(bare.locator(".name")).to_have_text("Preischotel")


def test_recipes_card_does_not_overflow_horizontally(page: Page) -> None:
    card = _set_card_width(page, NARROW_PX)
    _recipe(page, "Pompoensoep")

    overflow = card.evaluate(
        "el => { const c = el.shadowRoot.querySelector('ha-card');"
        " return c.scrollWidth - c.clientWidth; }"
    )

    assert overflow <= 0


def test_recipes_card_switches_layout_with_its_own_width(
    page: Page, request: pytest.FixtureRequest
) -> None:
    SCREENSHOTS.mkdir(exist_ok=True)
    scenario = request.node.callspec.id
    card = _set_card_width(page, NARROW_PX)
    recipe = _recipe(page, "Pompoensoep")
    image = recipe.locator(".media").bounding_box()
    text = recipe.locator(".body").bounding_box()
    assert image
    assert text
    assert image["y"] + image["height"] <= text["y"] + 1, "narrow: image above text"
    assert image["width"] >= text["width"] - 1, "narrow: image uses the full width"
    card.screenshot(path=SCREENSHOTS / f"recipes-card-narrow-{scenario}.png")

    _set_card_width(page, WIDE_PX)
    recipe = _recipe(page, "Pompoensoep")
    image = recipe.locator(".media").bounding_box()
    text = recipe.locator(".body").bounding_box()
    assert image
    assert text
    assert image["x"] + image["width"] <= text["x"] + 1, "wide: image beside text"
    assert image["width"] < text["width"], "wide: image is a thumbnail"
    card.screenshot(path=SCREENSHOTS / f"recipes-card-wide-{scenario}.png")
