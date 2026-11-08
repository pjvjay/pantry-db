"""gen-seed-sql.py's nutrition rows and _check_nutrition, on the real seed (stdlib only).

    python3 -m unittest discover -s tests
"""
from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("gen_seed_sql", ROOT / "scripts" / "gen-seed-sql.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

NUTRIENTS = json.loads((ROOT / "seeds" / "nutrients.json").read_text(encoding="utf-8"))
RECIPES = json.loads((ROOT / "seeds" / "recipes.json").read_text(encoding="utf-8"))


class SeedNutritionTest(unittest.TestCase):
    def refused(self, change, message: str) -> None:
        data = copy.deepcopy(NUTRIENTS)
        recipes = copy.deepcopy(RECIPES)
        change(data, recipes)
        with self.assertRaises(AssertionError) as e:
            gen._check_nutrition(data, recipes)
        self.assertIn(message, str(e.exception))

    def food(self, data, ref_id):
        return next(f for f in data["foods"] if f["ref_id"] == ref_id)

    def test_the_seed_passes(self):
        gen._check_nutrition(NUTRIENTS, RECIPES)

    def test_rows_keep_unknowns_out_and_published_zeros_in(self):
        rows = gen.nutrient_rows(NUTRIENTS)
        amounts = {(r, n): v for r, n, v, _ in rows["amounts"]}
        self.assertNotIn(("cnf-api:4484", "sugars_g"), amounts)   # flour: sugars not published
        self.assertEqual(amounts[("cnf-api:113", "fibre_g")], 0.0)  # milk: published 0
        self.assertEqual(len(rows["amounts"]),
                         sum(len(f["per_100g"]) for f in NUTRIENTS["foods"]))
        self.assertEqual(rows["foods"][0][:4], ("cnf-api:17", "cnf-api", "17", "17"))
        self.assertIn(("cnf-api:17", "energy_kcal", 876.0, "208"), rows["amounts"])

    def test_every_library_line_has_a_map_row(self):
        keys = {m["ingredient_key"] for m in NUTRIENTS["map"]}
        for r in RECIPES:
            for ing in r["ingredients"]:
                self.assertIn(" ".join(gen._tokens(ing["name"])), keys, ing["name"])

    def test_refusals(self):
        def set_food(ref, **kw):
            return lambda d, _r: self.food(d, ref).update(kw)

        def per(ref, n, v):
            return lambda d, _r: self.food(d, ref)["per_100g"].__setitem__(n, v)

        def drop(ref, n):
            def change(d, _r):
                del self.food(d, ref)["per_100g"][n]
                self.food(d, ref)["absent"].append(n)
            return change

        self.refused(set_food("cnf-api:17", ref_id="cnf-api:18"), "ref_id is not")
        self.refused(set_food("cnf-api:17", source="nope"), "unknown source")
        self.refused(set_food("cnf-api:17", state_note=""), "no state_note")
        self.refused(per("cnf-api:113", "protein_g", -0.1), "is not a number >= 0")
        self.refused(per("cnf-api:113", "protein_g", float("inf")), "is not a number >= 0")
        self.refused(per("cnf-api:113", "fat_g", 100.5), "g per 100 g")
        self.refused(drop("cnf-api:113", "protein_g"), "energy and protein needed")
        self.refused(lambda d, _r: self.food(d, "cnf-api:113")["absent"].append("fat_g"),
                     "`absent` must name exactly")
        self.refused(lambda d, _r: self.food(d, "cnf-api:174").pop("atwater_note"),
                     "Atwater")
        self.refused(lambda d, _r: d["measures"][0].update(grams=0), "grams must be > 0")
        self.refused(lambda d, _r: d["measures"][0].update(ref_id="cnf-api:0"), "unknown food")
        self.refused(lambda d, _r: d["map"][0].update(match_kind="none"),
                     "only match_kind 'none' has no ref_id")
        self.refused(lambda d, _r: d["map"][0].update(ref_id="cnf-api:0"), "unknown ref_id")
        self.refused(lambda d, _r: d["map"].remove(
            next(m for m in d["map"] if m["ingredient_key"] == "spaghetti")),
            "'spaghetti' has no map row")
        self.refused(lambda _d, r: r[0]["ingredients"].append({"name": "Saffron"}),
                     "'saffron' has no map row")


if __name__ == "__main__":
    unittest.main()
