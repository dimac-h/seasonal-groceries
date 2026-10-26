"""
Browser tests against the dev Home Assistant (see dev/setup_ha.py).

Opt in with `uv run --group e2e pytest e2e` (needs `playwright install chromium`).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

if TYPE_CHECKING:
    from collections.abc import Iterator

    from playwright.sync_api import Page

HA_URL = os.environ.get("HA_URL", "http://localhost:8123")
HA_USER = os.environ.get("HA_USER", "dev")
HA_PASSWORD = os.environ.get("HA_PASSWORD", "dev-password-123")
SCREENSHOTS = Path(__file__).parent / "screenshots"

# The Home Assistant test plugin blocks sockets unless a test asks for them.
pytestmark = pytest.mark.usefixtures("socket_enabled")


@pytest.fixture(autouse=True)
def _allow_sockets(socket_enabled: None) -> None:
    """Browser tests talk to a real server."""


@pytest.fixture(
    params=[("light", 1100), ("dark", 420)], ids=["light-desktop", "dark-mobile"]
)
def page(request: pytest.FixtureRequest) -> Iterator[Page]:
    scheme, width = request.param
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport={"width": width, "height": 1400},
            color_scheme=scheme,
            locale="en-US",
        )
        page = context.new_page()
        page.goto(f"{HA_URL}/")
        page.fill("input[name=username]", HA_USER)
        page.fill("input[name=password]", HA_PASSWORD)
        page.keyboard.press("Enter")
        page.wait_for_url("**/lovelace/**", timeout=30_000)
        page.goto(f"{HA_URL}/lovelace/seasonal")
        page.wait_for_selector("seasonal-groceries-now-card ha-card", timeout=30_000)
        yield page
        SCREENSHOTS.mkdir(exist_ok=True)
        page.screenshot(
            path=SCREENSHOTS / f"{request.node.callspec.id}.png", full_page=True
        )
        browser.close()
