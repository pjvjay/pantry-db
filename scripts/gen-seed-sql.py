#!/usr/bin/env python3
"""Generate seeds/seed.sql from seeds/*.json.

The JSON files are the canonical seed data (shared shape with
pantry-api's local-dev fixtures). This script renders them into one
idempotent SQL file that the migration runner applies on every run:

  - products / recipes / stores: INSERT ... ON CONFLICT DO UPDATE (upsert)
  - recipe_ingredients: DELETE + re-INSERT per seeded recipe, inside the
    same transaction — handles removed/reordered ingredient lines, which
    a bare upsert would leave behind.
  - recipe_line_amounts: INSERTed right after each recipe's lines. The
    DELETE above cascades to them (0007's foreign key), so they can only
    go in after the lines, never before.
  - store_products / reviews / product_terms: fully synthetic, derived
    deterministically from the product list (seeded PRNGs keyed on ids) —
    DELETE + re-INSERT wholesale on every run.

KEEP-IN-SYNC: the store list, brand derivation, price variance, review
generation, the tokenizer, and which recipe lines get an amount row are
duplicated in pantry-api (pantry_planner/storeseed.py + nlsearch/units.py
+ db.seed_from_json) so its local SQLite dev DB matches this schema. The
tokenizer's GOLDEN cases below are asserted on every run of this script
and, verbatim, by pantry-api's test suite (tests/test_nlsearch.py), so the
two copies cannot drift apart unnoticed; change either side → change both.

Run after editing the JSON, commit both:

    python3 scripts/gen-seed-sql.py
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEEDS = ROOT / "seeds"
OUT = SEEDS / "seed.sql"

# ─── synthetic store model (KEEP-IN-SYNC: pantry-api storeseed.py) ───

# Reference shopping location (49.28, -123.12) — three stores within
# 10 km, one at ~14 km so the distance constraint is demonstrable.
STORES = [
    (1, "Pantry Mart Downtown", 49.2820, -123.1180, "833 Granville St, Vancouver"),
    (2, "GreenLeaf Grocers Kitsilano", 49.2680, -123.1550, "2301 W 4th Ave, Vancouver"),
    (3, "ValueFoods East Van", 49.2620, -123.0700, "1605 Commercial Dr, Vancouver"),
    (4, "MegaSave Richmond", 49.1550, -123.1350, "4800 No. 3 Rd, Richmond"),
]

BRANDS_IN_NAME = ["Cadbury", "Nestles"]          # literal brand words in product names
HOUSE_BRANDS = ["PantryCo", "Fraser Farms", "Maple Ridge",
                "Coastline Foods", "Golden Gate"]

REVIEW_COMMENTS = [
    "Great value.", "Would buy again.", "Just okay.", "Family favourite.",
    "Quality varies by batch.", "Fresh and tasty.",
    "A bit pricey for what it is.", "Solid staple.",
]


def brand_for(product: dict) -> str:
    """Explicit JSON brand wins; else brand word in the name; else a house
    brand rotated by id (same-subcategory neighbours land on different
    brands, so per-brand stats have something to compare)."""
    if product.get("brand"):
        return product["brand"]
    for b in BRANDS_IN_NAME:
        if b.lower() in product["name"].lower():
            return b
    return HOUSE_BRANDS[product["id"] % len(HOUSE_BRANDS)]


def store_price(store_id: int, product_id: int, base: float) -> float:
    """Deterministic ±15% per-store variance around the reference price."""
    rng = random.Random(f"sp:{store_id}:{product_id}")
    return round(base * (1 + rng.uniform(-0.15, 0.15)), 2)


def _brand_quality(brand: str) -> float:
    """Stable per-brand mean rating in [3.0, 4.8] — some brands are just
    better, which is exactly what t3's stats should surface."""
    h = int(hashlib.sha256(brand.encode()).hexdigest(), 16) % 1000
    return 3.0 + 1.8 * (h / 999)


def reviews_for(product: dict, brand: str) -> list[tuple[int, str, str]]:
    """2–8 deterministic (rating, comment, created_at) rows per product."""
    rng = random.Random(f"rev:{product['id']}")
    mean = _brand_quality(brand)
    out = []
    for _ in range(rng.randint(2, 8)):
        rating = max(1, min(5, round(rng.gauss(mean, 0.7))))
        comment = rng.choice(REVIEW_COMMENTS)
        created = f"2026-{rng.randint(1, 6):02d}-{rng.randint(1, 28):02d}"
        out.append((rating, comment, created))
    return out


# ─── tokenizer (KEEP-IN-SYNC: pantry-api nlsearch/units.py) ───

_STOPWORDS = {"fresh", "of", "the", "a", "an", "large", "small", "medium",
              "to", "taste", "optional", "some"}


# Plurals the suffix rules get wrong ("Bay Leaves" vs a recipe's "bay
# leaf"). Not a general -ves -> -f rule: olives, cloves, chives must survive.
IRREGULAR_PLURALS = {"leaves": "leaf", "loaves": "loaf", "halves": "half"}

# A word the description negates is not a match term: "no salt added" must
# not put Crushed Tomatoes in the "salt" pool. "X-free" stays indexed.
_NEGATED = re.compile(r"\b(?:no|without)[\s-]+[a-z]+(?:[\s-]+added)?\b", re.IGNORECASE)


def _stem(token: str) -> str:
    if token in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[token]
    if token.endswith("oes") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        return token[:-1]
    return token


def _tokens(name: str) -> list[str]:
    raw = re.findall(r"[a-zA-Z]+", name.lower())
    return [_stem(t) for t in raw if t not in _STOPWORDS and len(t) > 1]


def _index_text(name: str, description: str | None) -> str:
    return f"{name} {_NEGATED.sub(' ', description or '')}"


def product_terms(product: dict) -> list[str]:
    return sorted(set(_tokens(_index_text(product["name"], product.get("description", "")))))


# (name, description) -> the product_terms they must produce. pantry-api's
# tests/test_nlsearch.py holds the same table; both must pass it.
GOLDEN_TERMS = [
    (("Bay Leaves 10g", "Dried whole bay leaves, 10g bag"),
     ["bag", "bay", "dried", "leaf", "whole"]),
    (("Olives", "Cloves, chives, two loaves and halves"),
     ["and", "chive", "clove", "half", "loaf", "olive", "two"]),
    (("Roma Tomato", "Fresh Roma tomatoes, 500g pack"), ["pack", "roma", "tomato"]),
    (("Crushed Tomatoes Canned 796ml", "Canned crushed tomatoes, no salt added, 796ml"),
     ["canned", "crushed", "ml", "tomato"]),
    (("Canadian Peanut Butter Cream", "Smooth peanut butter, no jelly, 500g"),
     ["butter", "canadian", "cream", "peanut", "smooth"]),
    (("Oat Milk 1L", "Unsweetened oat beverage, dairy-free, 1L carton"),
     ["beverage", "carton", "dairy", "free", "milk", "oat", "unsweetened"]),
    (("Jalapeno Peppers", "Fresh jalapeño peppers (jalapeños, jalapenos), ~200g"),
     ["jalape", "jalapeno", "os", "pepper"]),
]


def _check_golden() -> None:
    for (name, description), want in GOLDEN_TERMS:
        got = product_terms({"name": name, "description": description})
        assert got == want, f"tokenizer drifted: {name!r} -> {got}, expected {want}"


# ─── recipe line amounts (KEEP-IN-SYNC: pantry-api db.seed_from_json) ───

AMOUNT_KEYS = {"quantity", "unit", "note"}


def line_amount(ing: dict | str) -> tuple[float | None, str, str] | None:
    """(quantity, unit, note) for a recipe line, or None when the line states
    no amount at all. A line with any of the three keys gets a row, so a
    line that says only why its amount is unknown is still recorded."""
    if not isinstance(ing, dict) or not AMOUNT_KEYS & ing.keys():
        return None
    return ing.get("quantity"), ing.get("unit") or "", ing.get("note") or ""


def _check_amounts(recipes: list[dict]) -> None:
    """The quantity is written into the SQL unquoted, so it must be a finite
    number (json.loads accepts Infinity, which would be written as a bare
    `inf`). A null quantity means "not stated", and the shopper is owed the
    reason."""
    for r in recipes:
        for i, ing in enumerate(r["ingredients"], start=1):
            amount = line_amount(ing)
            if amount is None:
                continue
            quantity, _, note = amount
            where = f"{r['slug']} line {i}"
            is_number = (isinstance(quantity, (int, float)) and not isinstance(quantity, bool)
                         and math.isfinite(quantity))
            assert quantity is None or (is_number and quantity >= 0), \
                f"{where}: quantity must be a number >= 0, got {quantity!r}"
            assert quantity is not None or note, f"{where}: a null quantity needs a note"


# ─── SQL rendering ───

def q(value: str | None) -> str:
    """SQL-quote a string (or NULL)."""
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def main() -> None:
    _check_golden()
    products = json.loads((SEEDS / "products.json").read_text())
    recipes = json.loads((SEEDS / "recipes.json").read_text())
    _check_amounts(recipes)

    lines: list[str] = [
        "-- GENERATED FILE — do not edit by hand.",
        "-- Regenerate with: python3 scripts/gen-seed-sql.py",
        "-- Applied on every migration run; written to be idempotent.",
        "",
        "BEGIN;",
        "",
        "-- ─── products ───",
    ]
    for p in products:
        unit_qty = p.get("unit_qty")
        lines.append(
            f"INSERT INTO products (id, name, description, price, category, "
            f"subcategory, dietary_tags, unit_size, unit_qty, unit_uom, brand) VALUES "
            f"({p['id']}, {q(p['name'])}, {q(p.get('description', ''))}, "
            f"{p['price']}, {q(p.get('category'))}, {q(p.get('subcategory', ''))}, "
            f"{q(p.get('dietary_tags', ''))}, {q(p.get('unit_size', ''))}, "
            f"{'NULL' if unit_qty is None else unit_qty}, {q(p.get('unit_uom', ''))}, "
            f"{q(brand_for(p))}) "
            f"ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, "
            f"description = EXCLUDED.description, price = EXCLUDED.price, "
            f"category = EXCLUDED.category, subcategory = EXCLUDED.subcategory, "
            f"dietary_tags = EXCLUDED.dietary_tags, unit_size = EXCLUDED.unit_size, "
            f"unit_qty = EXCLUDED.unit_qty, unit_uom = EXCLUDED.unit_uom, "
            f"brand = EXCLUDED.brand;"
        )

    lines += ["", "-- ─── recipes ───"]
    for r in recipes:
        lines.append(
            f"INSERT INTO recipes (slug, name, servings) VALUES "
            f"({q(r['slug'])}, {q(r['name'])}, {r.get('servings', 1)}) "
            f"ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, "
            f"servings = EXCLUDED.servings;"
        )

    lines += ["", ("-- ─── recipe_ingredients + recipe_line_amounts "
                   "(delete + re-insert per recipe) ───")]
    n_amounts = 0
    for r in recipes:
        lines.append(f"DELETE FROM recipe_ingredients WHERE recipe_slug = {q(r['slug'])};")
        for i, ing in enumerate(r["ingredients"], start=1):
            name = ing["name"] if isinstance(ing, dict) else ing
            category = ing.get("category") if isinstance(ing, dict) else None
            lines.append(
                f"INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) "
                f"VALUES ({q(r['slug'])}, {i}, {q(name)}, {q(category)});"
            )
        # After all of this recipe's lines: the DELETE above has just cascaded
        # its old amounts away, and each amount row needs its line to exist.
        for i, ing in enumerate(r["ingredients"], start=1):
            amount = line_amount(ing)
            if amount is None:
                continue
            quantity, unit, note = amount
            n_amounts += 1
            lines.append(
                f"INSERT INTO recipe_line_amounts "
                f"(recipe_slug, line_no, quantity, unit, note) VALUES ({q(r['slug'])}, {i}, "
                f"{'NULL' if quantity is None else quantity}, {q(unit)}, {q(note)});"
            )

    lines += ["", "-- ─── stores ───"]
    for sid, name, lat, lon, address in STORES:
        lines.append(
            f"INSERT INTO stores (id, name, lat, lon, address) VALUES "
            f"({sid}, {q(name)}, {lat}, {lon}, {q(address)}) "
            f"ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, "
            f"lat = EXCLUDED.lat, lon = EXCLUDED.lon, address = EXCLUDED.address;"
        )

    lines += ["", "-- ─── store_products (synthetic; delete + re-insert) ───",
              "DELETE FROM store_products;"]
    for sid, *_ in STORES:
        for p in products:
            lines.append(
                f"INSERT INTO store_products (store_id, product_id, price) VALUES "
                f"({sid}, {p['id']}, {store_price(sid, p['id'], p['price'])});"
            )

    lines += ["", "-- ─── reviews (synthetic; delete + re-insert) ───",
              "DELETE FROM reviews;"]
    review_id = 0
    n_reviews = 0
    for p in products:
        for rating, comment, created in reviews_for(p, brand_for(p)):
            review_id += 1
            lines.append(
                f"INSERT INTO reviews (id, product_id, rating, comment, created_at) "
                f"VALUES ({review_id}, {p['id']}, {rating}, {q(comment)}, {q(created)});"
            )
    n_reviews = review_id

    lines += ["", "-- ─── product_terms (inverted index; delete + re-insert) ───",
              "DELETE FROM product_terms;"]
    n_terms = 0
    for p in products:
        for term in product_terms(p):
            n_terms += 1
            lines.append(
                f"INSERT INTO product_terms (term, product_id) VALUES "
                f"({q(term)}, {p['id']});"
            )

    lines += ["", "COMMIT;", ""]
    OUT.write_text("\n".join(lines))
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(products)} products, "
          f"{len(recipes)} recipes, {n_amounts} recipe_line_amounts, {len(STORES)} stores, "
          f"{len(STORES) * len(products)} store_products, "
          f"{n_reviews} reviews, {n_terms} product_terms")


if __name__ == "__main__":
    main()
