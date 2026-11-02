"""
Onboard the dev Home Assistant, add the integration and a test dashboard.

Usage (after docker compose up and dev/seed_mealie.py):
    uv run python dev/setup_ha.py [--language nl|en]

Creates the user dev / dev and a dashboard at /lovelace/seasonal.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import aiohttp

HTTP_OK = 200
BASE = "http://localhost:8123"
MEALIE_EXTERNAL_URL = "http://localhost:9925"
CLIENT = f"{BASE}/"
STATE = Path(__file__).parent / ".state"
USER = {"username": "dev", "password": "dev"}
CARDS = [
    {"type": "custom:seasonal-groceries-now-card", "produce_type": "vegetable"},
    {"type": "custom:seasonal-groceries-now-card", "produce_type": "fruit"},
    {
        "type": "custom:seasonal-groceries-calendar-card",
        "produce_type": "vegetable",
        "max_rows": 12,
    },
    {
        "type": "custom:seasonal-groceries-calendar-card",
        "produce_type": "fruit",
        "max_rows": 8,
    },
    {"type": "custom:seasonal-groceries-recipes-card", "max_recipes": 5},
    {"type": "custom:seasonal-groceries-match-card"},
]


async def access_token(session: aiohttp.ClientSession) -> str:
    async with session.get(f"{BASE}/api/onboarding") as response:
        # Home Assistant answers 404 once onboarding is complete.
        steps = (
            {s["step"]: s["done"] for s in await response.json()}
            if response.status == HTTP_OK
            else dict.fromkeys(
                ("user", "core_config", "analytics", "integration"), True
            )
        )
    if not steps["user"]:
        async with session.post(
            f"{BASE}/api/onboarding/users",
            json={"client_id": CLIENT, "name": "Dev", "language": "en", **USER},
        ) as response:
            code = (await response.json())["auth_code"]
    else:
        async with session.post(
            f"{BASE}/auth/login_flow",
            json={
                "client_id": CLIENT,
                "handler": ["homeassistant", None],
                "redirect_uri": CLIENT,
            },
        ) as response:
            flow = await response.json()
        async with session.post(
            f"{BASE}/auth/login_flow/{flow['flow_id']}",
            json={"client_id": CLIENT, **USER},
        ) as response:
            code = (await response.json())["result"]
    async with session.post(
        f"{BASE}/auth/token",
        data={"grant_type": "authorization_code", "code": code, "client_id": CLIENT},
    ) as response:
        token = (await response.json())["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    for step, body in (
        ("core_config", {}),
        ("analytics", {}),
        (
            "integration",
            {"client_id": CLIENT, "redirect_uri": f"{CLIENT}?auth_callback=1"},
        ),
    ):
        if not steps.get(step):
            await session.post(
                f"{BASE}/api/onboarding/{step}", json=body, headers=headers
            )
    return token


async def add_integration(
    session: aiohttp.ClientSession, token: str, language: str
) -> None:
    headers = {"Authorization": f"Bearer {token}"}

    async def step(url: str, body: dict) -> dict:
        async with session.post(url, json=body, headers=headers) as response:
            return await response.json()

    async def find_entry() -> dict | None:
        async with session.get(
            f"{BASE}/api/config/config_entries/entry", headers=headers
        ) as response:
            entries = await response.json()
        return next((e for e in entries if e["domain"] == "seasonal_groceries"), None)

    entry = await find_entry()
    if entry is None:
        flow_url = f"{BASE}/api/config/config_entries/flow"
        flow = await step(flow_url, {"handler": "seasonal_groceries"})
        flow = await step(f"{flow_url}/{flow['flow_id']}", {"language": language})
        flow = await step(f"{flow_url}/{flow['flow_id']}", {"next_step_id": "manual"})
        mealie_token = (STATE / "mealie-token").read_text()
        result = await step(
            f"{flow_url}/{flow['flow_id']}",
            {"url": "http://mealie:9000", "token": mealie_token, "verify_ssl": True},
        )
        print("integration:", result["type"], result.get("errors"))
        entry = await find_entry()
    if entry is None:
        return

    # Home Assistant reaches Mealie by its Docker hostname, which the browser cannot
    # resolve, so recipe links need the address published on the host.
    options_url = f"{BASE}/api/config/config_entries/options/flow"
    flow = await step(options_url, {"handler": entry["entry_id"]})
    result = await step(
        f"{options_url}/{flow['flow_id']}",
        {
            "language": language,
            "write_back_aliases": False,
            "mealie_external_url": MEALIE_EXTERNAL_URL,
        },
    )
    print("options:", result.get("type"), result.get("errors"))


async def save_dashboard(session: aiohttp.ClientSession, token: str) -> None:
    async with session.ws_connect(f"{BASE}/api/websocket") as ws:
        await ws.receive_json()
        await ws.send_json({"type": "auth", "access_token": token})
        await ws.receive_json()
        config = {
            "views": [
                {
                    "title": "Seasonal",
                    "path": "seasonal",
                    "type": "sections",
                    "sections": [{"type": "grid", "cards": [card]} for card in CARDS],
                }
            ]
        }
        await ws.send_json({"id": 1, "type": "lovelace/config/save", "config": config})
        print("dashboard:", (await ws.receive_json())["success"])


async def main(language: str) -> None:
    async with aiohttp.ClientSession() as session:
        token = await access_token(session)
        STATE.mkdir(exist_ok=True)
        (STATE / "ha-token.json").write_text(json.dumps({"access_token": token}))
        await add_integration(session, token, language)
        await save_dashboard(session, token)
    print(
        f"Open {BASE}/lovelace/seasonal  (user {USER['username']} / {USER['password']})"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", choices=["nl", "en"], default="nl")
    asyncio.run(main(parser.parse_args().language))
