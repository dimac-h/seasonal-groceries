"""The cards must register in the real Home Assistant frontend and render data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


def test_cards_register_without_configuration_errors(page: Page) -> None:
    for tag in (
        "seasonal-groceries-now-card",
        "seasonal-groceries-calendar-card",
        "seasonal-groceries-match-card",
    ):
        assert page.evaluate("(t) => !!customElements.get(t)", tag), tag
    expect(page.get_by_text("Configuration error")).to_have_count(0)


def test_now_card_lists_seasonal_items_with_pesticide_levels(page: Page) -> None:
    card = page.locator("seasonal-groceries-now-card").first

    expect(card.locator(".row").first).to_be_visible()
    expect(card.get_by_text("Few pesticides").first).to_be_visible()
    expect(card.get_by_text("Unknown").first).to_be_visible()


def test_now_card_shows_ranked_recipes(page: Page) -> None:
    card = page.locator("seasonal-groceries-now-card").first

    expect(card.get_by_text("Recipes to cook now")).to_be_visible()
    expect(card.get_by_text("2 of 2 in season")).to_be_visible()


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
