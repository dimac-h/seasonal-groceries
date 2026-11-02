"""
Seed the dev Mealie (http://localhost:9925) with Dutch foods and recipes.

Usage: uv run python dev/seed_mealie.py
Writes an API token to dev/.state/mealie-token. Safe to run again: existing foods
and recipes (matched by name) are updated, not duplicated.

The recipes cover what the recipes card shows: a long description, tags, a
fractional rating, a favourite and an image. Preischotel has none of these.
"""

from __future__ import annotations

import json
import struct
import urllib.parse
import urllib.request
import zlib
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
LONG_DESCRIPTION = (
    "Een romige soep van pompoen en prei, perfect voor een koude herfstavond. "
    "Bak de prei zacht in olijfolie, voeg de blokjes pompoen toe en laat alles "
    "een half uur sudderen. Pureer de soep glad en serveer met knapperig brood, "
    "een scheutje room en wat geroosterde pompoenpitten."
)
# name: ingredients, description, tags, own rating, favourite, image colour (RGB)
RECIPES: dict[str, dict] = {
    "Pompoensoep": {
        "ingredients": ["pompoen", "prei", "olijfolie"],
        "description": LONG_DESCRIPTION,
        "tags": [
            "soep",
            "herfst",
            "vegetarisch",
            "een-wel-heel-lange-tagnaam-voor-smalle-kaarten",
        ],
        "rating": 3.7,
        "favorite": True,
        "image": (200, 110, 40),
    },
    "Tomatensalade": {
        "ingredients": ["tomaat", "verse basilicum", "olijfolie"],
        "description": "Frisse salade van tomaat en basilicum.",
        "tags": ["salade"],
        "rating": 4.5,
        "favorite": False,
        "image": (190, 50, 50),
    },
    "Preischotel": {"ingredients": ["prei"]},
    "Bananenbrood": {"ingredients": ["banaan", "bloem"]},
    "Lege schotel": {"ingredients": ["zout"]},
}


def call(method: str, path: str, body=None, token=None, *, raw=None):
    data, headers = None, {}
    if raw is not None:
        data, content_type = raw
        headers["Content-Type"] = content_type
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(BASE + path, data, headers, method=method)
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or b"null")


def png(color: tuple[int, int, int], size: int = 96) -> bytes:
    """Build a small solid-colour PNG, so no image library is needed."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)

    rows = b"".join(b"\x00" + bytes(color) * size for _ in range(size))
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def multipart(fields: dict[str, str], name: str, filename: str, content: bytes):
    boundary = "----seed-mealie"
    parts = [
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'
        ).encode()
        for key, value in fields.items()
    ]
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
        f'filename="{filename}"\r\nContent-Type: image/png\r\n\r\n'.encode()
        + content
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def find_or_create(login: str, path: str, name: str, body: dict) -> dict:
    """Return the item called `name` from a paged list, creating it when missing."""
    listing = call("GET", f"{path}?perPage=500", None, login)["items"]
    existing = next((item for item in listing if item["name"] == name), None)
    return existing or call("POST", path, body, login)


def main() -> None:
    login = call(
        "POST",
        "/api/auth/token",
        raw=(
            urllib.parse.urlencode(
                {"username": "changeme@example.com", "password": "MyPassword"}
            ).encode(),
            "application/x-www-form-urlencoded",
        ),
    )["access_token"]
    api_token = call("POST", "/api/users/api-tokens", {"name": "dev"}, login)["token"]
    STATE.mkdir(exist_ok=True)
    (STATE / "mealie-token").write_text(api_token)
    user_id = call("GET", "/api/users/self", None, login)["id"]

    foods = {
        name: find_or_create(
            login,
            "/api/foods",
            name,
            {"name": name, "aliases": [{"name": a} for a in aliases]},
        )
        for name, aliases in FOODS.items()
    }
    tags = {
        tag: find_or_create(login, "/api/organizers/tags", tag, {"name": tag})
        for tag in {t for r in RECIPES.values() for t in r.get("tags", [])}
    }
    for title, spec in RECIPES.items():
        # Mealie does not reject a duplicate name: it creates "<slug>-1".
        listed = call("GET", "/api/recipes?perPage=500", None, login)["items"]
        slug = next((r["slug"] for r in listed if r["name"] == title), None)
        slug = slug or call("POST", "/api/recipes", {"name": title}, login)
        recipe = call("GET", f"/api/recipes/{slug}", None, login)
        recipe["description"] = spec.get("description", "")
        recipe["tags"] = [
            {"id": tags[t]["id"], "name": t, "slug": tags[t]["slug"]}
            for t in spec.get("tags", [])
        ]
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
            for name in spec["ingredients"]
        ]
        call("PUT", f"/api/recipes/{slug}", recipe, login)
        if "image" in spec:
            call(
                "PUT",
                f"/api/recipes/{slug}/image",
                raw=multipart(
                    {"extension": "png"}, "image", "image.png", png(spec["image"])
                ),
                token=login,
            )
        if "rating" in spec:
            call(
                "POST",
                f"/api/users/{user_id}/ratings/{slug}",
                {"rating": spec["rating"], "isFavorite": spec["favorite"]},
                login,
            )
    print("seeded", len(foods), "foods and", len(RECIPES), "recipes")


if __name__ == "__main__":
    main()
