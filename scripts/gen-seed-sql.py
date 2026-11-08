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
  - nutrient_sources / nutrient_foods / nutrient_amounts / nutrient_measures /
    ingredient_nutrient_map (0008, 0009): from seeds/nutrients.json, DELETE
    (children first) + re-INSERT wholesale. _check_nutrition refuses the file
    first if a value, a reference or a library line's ingredient key is wrong.

KEEP-IN-SYNC: the store list, brand derivation, price variance, review
generation, the tokenizer, which recipe lines get an amount row, and how
nutrients.json becomes rows (nutrient_rows) are duplicated in pantry-api (pantry_planner/storeseed.py + nlsearch/units.py
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
# pantry-api's bound on a reviewed line's quantity (models.MAX_LINE_QUANTITY). A
# library line over it cannot be served as a RecipeDoc, so GET /recipes/{slug}/doc
# would fail on that recipe instead of the seed failing here.
MAX_QUANTITY = 1_000_000


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
            assert quantity is None or (is_number and 0 <= quantity <= MAX_QUANTITY), \
                f"{where}: quantity must be a number from 0 to {MAX_QUANTITY:,}, got {quantity!r}"
            assert quantity is not None or note, f"{where}: a null quantity needs a note"


# ─── nutrition (KEEP-IN-SYNC: pantry-api db.seed_from_json) ───

# The eight nutrients, per 100 g, with the unit each is stored in.
NUTRIENTS = {"energy_kcal": "kcal", "protein_g": "g", "fat_g": "g", "satfat_g": "g",
             "carbohydrate_g": "g", "fibre_g": "g", "sugars_g": "g", "sodium_mg": "mg"}
MATCH_KINDS = {"generic", "close", "none"}
SOURCE_FIELDS = ("name", "publisher", "edition", "licence", "licence_url", "attribution",
                 "url", "retrieved_at")


def nutrient_rows(data: dict) -> dict[str, list[tuple]]:
    """nutrients.json as the rows of the five tables, in file order. A food's
    source_food_id is its own field when the file has one (a CSV source with a
    FoodID), else its food_code (the CNF API names a food by its code only).
    source_code is the source's own nutrient id: a CSV's NutrientCode (or FDC
    nutrient id) as cnf-subset.py records it, else the CNF API's
    nutrient_name_id (208 for energy, 203 for protein, ...). A nutrient
    missing from per_100g gets no row: unknown, never 0."""
    sources = [(s["source"], *(s.get(k) or "" for k in SOURCE_FIELDS)) for s in data["sources"]]
    foods, amounts = [], []
    for f in data["foods"]:
        foods.append((f["ref_id"], f["source"], str(f.get("source_food_id", f["food_code"])),
                      str(f.get("food_code", "")), f["description"], f.get("state_note") or ""))
        codes = f.get("source_codes") or {}
        for n in NUTRIENTS:
            if n in f["per_100g"]:
                c = codes.get(n) or {}
                code = c.get("nutrient_code", c.get("nutrient_name_id"))
                amounts.append((f["ref_id"], n, float(f["per_100g"][n]),
                                "" if code is None else str(code)))
    measures = [(m["ref_id"], m["measure"], float(m["grams"]),
                 None if m.get("volume_ml") is None else float(m["volume_ml"]),
                 m["verbatim"], m.get("source_ref") or "") for m in data.get("measures", [])]
    mapping = [(m["ingredient_key"], m.get("ref_id"), m["match_kind"], m.get("note") or "",
                m.get("reviewed_at") or "") for m in data["map"]]
    return {"sources": sources, "foods": foods, "amounts": amounts, "measures": measures,
            "map": mapping}


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _check_nutrition(data: dict, recipes: list[dict]) -> None:
    """Refuse a nutrients.json that would put a wrong or unsupported number in
    front of a shopper. Every number must be the source's, so this checks the
    file's own consistency, not the values against a guess:

      - each food cites a listed source, its ref_id is '<source>:<id>', it has
        a verbatim description and a state note, energy and protein are
        published, and `absent` names exactly the nutrients it lacks;
      - no value is negative or infinite, and no gram nutrient is above 100 g
        per 100 g;
      - energy agrees with 4 x protein + 9 x fat + 4 x carbohydrate within
        max(25 kcal, 20%), or the food carries an atwater_note saying why not;
      - every measure and map row points at a listed food; 'none' and only
        'none' has no reference food;
      - every library recipe line's ingredient key has a map row, so a
        tokenizer change cannot silently re-key an ingredient."""
    source_ids = [s["source"] for s in data["sources"]]
    assert len(source_ids) == len(set(source_ids)), "duplicate nutrient source"
    for s in data["sources"]:
        assert s.get("name") and s.get("attribution"), f"source {s['source']}: name and attribution"
    foods: dict[str, dict] = {}
    for f in data["foods"]:
        rid = f["ref_id"]
        assert rid not in foods, f"duplicate food {rid}"
        foods[rid] = f
        assert f["source"] in source_ids, f"{rid}: unknown source {f['source']!r}"
        sid = str(f.get("source_food_id", f["food_code"]))
        assert rid == f"{f['source']}:{sid}", f"{rid}: ref_id is not '<source>:{sid}'"
        assert f.get("description", "").strip(), f"{rid}: no description"
        assert f.get("state_note", "").strip(), f"{rid}: no state_note"
        per = f["per_100g"]
        assert set(per) <= set(NUTRIENTS), f"{rid}: unknown nutrients {set(per) - set(NUTRIENTS)}"
        assert "energy_kcal" in per and "protein_g" in per, f"{rid}: energy and protein needed"
        assert set(f.get("absent", [])) == set(NUTRIENTS) - set(per), \
            f"{rid}: `absent` must name exactly the nutrients missing from per_100g"
        for n, v in per.items():
            assert _finite(v) and v >= 0, f"{rid} {n}: {v!r} is not a number >= 0"
            assert NUTRIENTS[n] != "g" or v <= 100, f"{rid} {n}: {v} g per 100 g"
        if {"fat_g", "carbohydrate_g"} <= per.keys():
            energy = per["energy_kcal"]
            atwater = 4 * per["protein_g"] + 9 * per["fat_g"] + 4 * per["carbohydrate_g"]
            assert abs(energy - atwater) <= max(25, 0.2 * energy) or f.get("atwater_note"), \
                f"{rid}: energy {energy} kcal vs Atwater {atwater:.1f} kcal and no atwater_note"
    seen_measures = set()
    for m in data.get("measures", []):
        key = (m["ref_id"], m["measure"])
        assert key not in seen_measures, f"duplicate measure {key}"
        seen_measures.add(key)
        assert m["ref_id"] in foods, f"measure {key}: unknown food"
        assert _finite(m["grams"]) and m["grams"] > 0, f"measure {key}: grams must be > 0"
        vol = m.get("volume_ml")
        assert vol is None or (_finite(vol) and vol > 0), f"measure {key}: volume_ml must be > 0"
        assert m.get("verbatim", "").strip(), f"measure {key}: no verbatim name"
    keys = set()
    for m in data["map"]:
        k = m["ingredient_key"]
        assert k not in keys, f"duplicate map key {k!r}"
        keys.add(k)
        assert m["match_kind"] in MATCH_KINDS, f"map {k!r}: match_kind {m['match_kind']!r}"
        assert (m["match_kind"] == "none") == (m.get("ref_id") is None), \
            f"map {k!r}: only match_kind 'none' has no ref_id"
        assert m.get("ref_id") is None or m["ref_id"] in foods, f"map {k!r}: unknown ref_id"
    for r in recipes:
        for i, ing in enumerate(r["ingredients"], start=1):
            name = ing["name"] if isinstance(ing, dict) else ing
            key = " ".join(_tokens(name))
            assert key in keys, f"{r['slug']} line {i}: ingredient key {key!r} has no map row"


# ─── SQL rendering ───

def q(value: str | None) -> str:
    """SQL-quote a string (or NULL)."""
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def num(value: float | None) -> str:
    """A finite float as SQL (repr is exact and stable), or NULL."""
    if value is None:
        return "NULL"
    assert math.isfinite(value), f"not a finite number: {value!r}"
    return repr(float(value))


def main() -> None:
    _check_golden()
    products = json.loads((SEEDS / "products.json").read_text())
    recipes = json.loads((SEEDS / "recipes.json").read_text())
    nutrients = json.loads((SEEDS / "nutrients.json").read_text(encoding="utf-8"))
    _check_amounts(recipes)
    _check_nutrition(nutrients, recipes)
    rows = nutrient_rows(nutrients)

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

    # Children first: amounts, measures and the map all point at a food, and a
    # food at its source.
    lines += ["", "-- ─── nutrition (0008, 0009; delete + re-insert) ───",
              "DELETE FROM ingredient_nutrient_map;", "DELETE FROM nutrient_measures;",
              "DELETE FROM nutrient_amounts;", "DELETE FROM nutrient_foods;",
              "DELETE FROM nutrient_sources;"]
    for row in rows["sources"]:
        lines.append(
            "INSERT INTO nutrient_sources (source, name, publisher, edition, licence, "
            "licence_url, attribution, url, retrieved_at) VALUES ("
            + ", ".join(q(v) for v in row) + ");")
    for row in rows["foods"]:
        lines.append(
            "INSERT INTO nutrient_foods (ref_id, source, source_food_id, food_code, "
            "description, state_note) VALUES (" + ", ".join(q(v) for v in row) + ");")
    for ref_id, nutrient, per_100g, code in rows["amounts"]:
        lines.append(
            f"INSERT INTO nutrient_amounts (ref_id, nutrient, per_100g, source_code) VALUES "
            f"({q(ref_id)}, {q(nutrient)}, {num(per_100g)}, {q(code)});")
    for ref_id, measure, grams, volume_ml, verbatim, source_ref in rows["measures"]:
        lines.append(
            f"INSERT INTO nutrient_measures (ref_id, measure, grams, volume_ml, verbatim, "
            f"source_ref) VALUES ({q(ref_id)}, {q(measure)}, {num(grams)}, {num(volume_ml)}, "
            f"{q(verbatim)}, {q(source_ref)});")
    for row in rows["map"]:
        lines.append(
            "INSERT INTO ingredient_nutrient_map (ingredient_key, ref_id, match_kind, note, "
            "reviewed_at) VALUES (" + ", ".join(q(v) for v in row) + ");")

    lines += ["", "COMMIT;", ""]
    OUT.write_text("\n".join(lines))
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(products)} products, "
          f"{len(recipes)} recipes, {n_amounts} recipe_line_amounts, {len(STORES)} stores, "
          f"{len(STORES) * len(products)} store_products, "
          f"{n_reviews} reviews, {n_terms} product_terms, "
          f"{len(rows['foods'])} nutrient_foods, {len(rows['amounts'])} nutrient_amounts, "
          f"{len(rows['measures'])} nutrient_measures, {len(rows['map'])} ingredient_nutrient_map")


if __name__ == "__main__":
    main()
