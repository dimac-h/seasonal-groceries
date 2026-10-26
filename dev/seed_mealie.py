"""
Seed the dev Mealie (http://localhost:9925) with Dutch foods and recipes.

Usage: uv run python dev/seed_mealie.py
Writes an API token to dev/.state/mealie-token.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://localhost:9925"
STATE = Path(__file__).parent / ".state"

FOODS = {
    "tomaat": ["tomaten", "pomodori"],
    "pompoen": [],
    "prei": [],
    "banaan": [],
    "olijfolie": [],
}
RECIPES = {
    "Pompoensoep": ["pompoen", "prei", "olijfolie"],
    "Tomatensalade": ["tomaat", "verse basilicum", "olijfolie"],
    "Bananenbrood": ["banaan", "bloem"],
    "Lege schotel": ["zout"],
}


def call(method: str, path: str, body=None, token=None, form=None):
    data, headers = None, {}
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(BASE + path, data, headers, method=method)
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or b"null")


def main() -> None:
    login = call(
        "POST",
        "/api/auth/token",
        form={"username": "changeme@example.com", "password": "MyPassword"},
    )["access_token"]
    api_token = call("POST", "/api/users/api-tokens", {"name": "dev"}, login)["token"]
    STATE.mkdir(exist_ok=True)
    (STATE / "mealie-token").write_text(api_token)

    foods = {}
    for name, aliases in FOODS.items():
        foods[name] = call(
            "POST",
            "/api/foods",
            {"name": name, "aliases": [{"name": a} for a in aliases]},
            login,
        )
    for title, ingredients in RECIPES.items():
        slug = call("POST", "/api/recipes", {"name": title}, login)
        recipe = call("GET", f"/api/recipes/{slug}", None, login)
        recipe["recipeIngredient"] = [
            {
                "quantity": 1,
                "unit": None,
                "note": "" if name in foods else name,
                "food": {"id": foods[name]["id"], "name": name}
                if name in foods
                else None,
                "title": None,
                "originalText": None,
                "referenceId": None,
                "display": "",
            }
            for name in ingredients
        ]
        call("PUT", f"/api/recipes/{slug}", recipe, login)
    print("seeded", len(foods), "foods and", len(RECIPES), "recipes")


if __name__ == "__main__":
    main()
