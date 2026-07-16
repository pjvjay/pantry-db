#!/usr/bin/env python3
"""Generate seeds/seed.sql from seeds/*.json.

The JSON files are the canonical seed data (shared shape with
pantry-api's local-dev fixtures). This script renders them into one
idempotent SQL file that the migration runner applies on every run:

  - products / recipes: INSERT ... ON CONFLICT DO UPDATE (upsert)
  - recipe_ingredients: DELETE + re-INSERT per seeded recipe, inside the
    same transaction — handles removed/reordered ingredient lines, which
    a bare upsert would leave behind.

Run after editing the JSON, commit both:

    python3 scripts/gen-seed-sql.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEEDS = ROOT / "seeds"
OUT = SEEDS / "seed.sql"


def q(value: str | None) -> str:
    """SQL-quote a string (or NULL)."""
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def main() -> None:
    products = json.loads((SEEDS / "products.json").read_text())
    recipes = json.loads((SEEDS / "recipes.json").read_text())

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
        lines.append(
            f"INSERT INTO products (id, name, description, price, category) VALUES "
            f"({p['id']}, {q(p['name'])}, {q(p.get('description', ''))}, "
            f"{p['price']}, {q(p.get('category'))}) "
            f"ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, "
            f"description = EXCLUDED.description, price = EXCLUDED.price, "
            f"category = EXCLUDED.category;"
        )

    lines += ["", "-- ─── recipes ───"]
    for r in recipes:
        lines.append(
            f"INSERT INTO recipes (slug, name, servings) VALUES "
            f"({q(r['slug'])}, {q(r['name'])}, {r.get('servings', 1)}) "
            f"ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, "
            f"servings = EXCLUDED.servings;"
        )

    lines += ["", "-- ─── recipe_ingredients (delete + re-insert per recipe) ───"]
    for r in recipes:
        lines.append(f"DELETE FROM recipe_ingredients WHERE recipe_slug = {q(r['slug'])};")
        for i, ing in enumerate(r["ingredients"], start=1):
            name = ing["name"] if isinstance(ing, dict) else ing
            category = ing.get("category") if isinstance(ing, dict) else None
            lines.append(
                f"INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) "
                f"VALUES ({q(r['slug'])}, {i}, {q(name)}, {q(category)});"
            )

    lines += ["", "COMMIT;", ""]
    OUT.write_text("\n".join(lines))
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(products)} products, {len(recipes)} recipes")


if __name__ == "__main__":
    main()
