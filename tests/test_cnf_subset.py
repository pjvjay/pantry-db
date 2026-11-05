"""scripts/cnf-subset.py against the invented fixtures in tests/fixtures (stdlib only).

    python3 -m unittest discover -s tests

The fixtures use the CNF and FDC header names with made-up foods and values, so these
tests check how the script reads and refuses, never what a real food contains.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "cnf-subset.py"
CNF = ROOT / "tests" / "fixtures" / "cnf_mini"
FDC = ROOT / "tests" / "fixtures" / "fdc_mini"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gen = _load("gen_seed_sql", ROOT / "scripts" / "gen-seed-sql.py")


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args],
                          capture_output=True, text=True, check=False)


class CnfSubsetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cnf-subset-"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def build(self, data: Path = CNF, picks: Path | None = None, *extra: str,
              mode: str = "--cnf") -> tuple[subprocess.CompletedProcess, Path]:
        out = self.tmp / f"out{len(list(self.tmp.iterdir()))}.json"
        r = run("build", mode, str(data), "--picks", str(picks or data / "picks.json"),
                "--out", str(out), *extra)
        return r, out

    def picks(self, change) -> Path:
        p = json.loads((CNF / "picks.json").read_text(encoding="utf-8"))
        change(p)
        path = self.tmp / "picks.json"
        path.write_text(json.dumps(p), encoding="utf-8")
        return path

    def copy(self) -> Path:
        dst = self.tmp / "cnf"
        shutil.copytree(CNF, dst)
        return dst

    def test_energy_is_the_kcal_row_never_kj(self):
        r, out = self.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        foods = {f["food_code"]: f for f in json.loads(out.read_text())["foods"]}
        # the kJ row (3699) is listed first in NUTRIENT NAME; the kcal row is 884
        self.assertEqual(foods["501"]["per_100g"]["energy_kcal"], 884.0)
        code = foods["501"]["source_codes"]["energy_kcal"]
        self.assertEqual((code["nutrient_code"], code["unit"]), ("208", "kCal"))

    def test_nutrients_are_chosen_by_code_not_by_nutrient_id(self):
        r, out = self.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        oil = json.loads(out.read_text())["foods"][0]
        # NutrientID 803 is protein in this download; the code (203) is what names it
        self.assertEqual(oil["source_codes"]["protein_g"]["nutrient_id"], "803")
        self.assertEqual(oil["source_codes"]["protein_g"]["nutrient_code"], "203")

    def test_a_missing_nutrient_is_absent_never_zero(self):
        r, out = self.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        grain = next(f for f in json.loads(out.read_text())["foods"] if f["food_code"] == "502")
        self.assertNotIn("sugars_g", grain["per_100g"])
        self.assertEqual(grain["absent"], ["sugars_g"])
        oil = next(f for f in json.loads(out.read_text())["foods"] if f["food_code"] == "501")
        self.assertEqual(oil["per_100g"]["sugars_g"], 0.0)      # a published 0 stays 0

    def test_output_is_byte_stable_and_the_zip_reads_the_same(self):
        r1, out1 = self.build()
        r2, out2 = self.build()
        self.assertEqual((r1.returncode, r2.returncode), (0, 0), r1.stderr + r2.stderr)
        self.assertEqual(out1.read_bytes(), out2.read_bytes())
        z = self.tmp / "cnf.zip"
        with zipfile.ZipFile(z, "w") as zf:
            for p in sorted(CNF.glob("*.csv")):
                zf.write(p, f"cnf_2026/{p.name}")
        r3, out3 = self.build(z, CNF / "picks.json")
        self.assertEqual(r3.returncode, 0, r3.stderr)
        self.assertEqual(out1.read_bytes(), out3.read_bytes())

    def test_cp1252_is_read_when_utf8_fails(self):
        r, out = self.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        descs = [f["description"] for f in json.loads(out.read_text())["foods"]]
        self.assertIn("Test tomato purée, canned", descs)

    def test_a_renamed_header_fails_with_a_clear_message(self):
        data = self.copy()
        path = data / "NUTRIENT AMOUNT.csv"
        path.write_bytes(path.read_bytes().replace(b"NutrientValue", b"Value", 1))
        r, out = self.build(data, CNF / "picks.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("NUTRIENT AMOUNT.csv: no column for value (expected one of NutrientValue)",
                      r.stderr)
        self.assertFalse(out.exists())

    def test_a_unit_that_is_not_the_nutrients_fails(self):
        data = self.copy()
        path = data / "NUTRIENT NAME.csv"
        path.write_bytes(path.read_bytes().replace(b"803,203,PROT,g,", b"803,203,PROT,mg,"))
        r, _ = self.build(data, CNF / "picks.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("protein_g must be in g", r.stderr)

    def test_energy_without_a_kcal_row_fails(self):
        data = self.copy()
        path = data / "NUTRIENT NAME.csv"
        path.write_bytes(path.read_bytes().replace(b"802,208,KCAL,kCal,", b"802,208,KCAL,kJ,"))
        r, _ = self.build(data, CNF / "picks.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("expected one energy row in kcal", r.stderr)

    def test_a_negative_value_or_a_macro_over_100_g_fails(self):
        for old, new, msg in ((b"1002,803,10,", b"1002,803,-1,", "negative value"),
                              (b"1002,805,78,", b"1002,805,178,", "178.0 g per 100 g")):
            data = self.copy()
            path = data / "NUTRIENT AMOUNT.csv"
            path.write_bytes(path.read_bytes().replace(old, new))
            r, _ = self.build(data, CNF / "picks.json")
            self.assertEqual(r.returncode, 1, msg)
            self.assertIn(msg, r.stderr)
            shutil.rmtree(data)

    def test_an_atwater_violation_needs_a_reviewed_exemption(self):
        picks = self.picks(lambda p: p["foods"][2].pop("atwater_exempt"))
        r, _ = self.build(CNF, picks)
        self.assertEqual(r.returncode, 1)
        self.assertIn("outside the Atwater check", r.stderr)
        r, out = self.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        spice = next(f for f in json.loads(out.read_text())["foods"] if f["food_code"] == "503")
        self.assertIn("= 374.0 kcal", spice["atwater_note"])

    def test_a_different_description_is_refused_unless_accepted(self):
        picks = self.picks(lambda p: p["foods"][1].update(description="Test grain, brown, dry"))
        r, _ = self.build(CNF, picks)
        self.assertEqual(r.returncode, 1)
        self.assertIn("descriptions differ", r.stderr)
        r, out = self.build(CNF, picks, "--accept-descriptions")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Test grain, white, dry", out.read_text())     # the download's words

    def test_measures_carry_volume_only_for_volumes_and_skip_zero_factors(self):
        r, out = self.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        ms = {(m["ref_id"], m["measure"]): m for m in json.loads(out.read_text())["measures"]}
        self.assertEqual(ms[("cnf-test:1001", "vol_15ml")]["grams"], 13.8)
        self.assertEqual(ms[("cnf-test:1001", "vol_15ml")]["volume_ml"], 15.0)
        self.assertIsNone(ms[("cnf-test:1004", "1_large_egg")]["volume_ml"])
        self.assertEqual(ms[("cnf-test:1004", "1_large_egg")]["source_ref"], "343")
        self.assertNotIn(("cnf-test:1001", "no_serving_specified"), ms)
        # the grain was not picked for measures
        self.assertFalse(any(k[0] == "cnf-test:1002" for k in ms))

    def test_the_output_passes_the_seed_generators_checks(self):
        r, out = self.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(out.read_text(encoding="utf-8"))
        gen._check_nutrition(data, [])
        rows = gen.nutrient_rows(data)
        self.assertEqual(rows["foods"][0][:4], ("cnf-test:1001", "cnf-test", "1001", "501"))
        self.assertIn(("cnf-test:1001", "energy_kcal", 884.0, "208"), rows["amounts"])
        none = next(m for m in rows["map"] if m[0] == "garam masala")
        self.assertEqual(none[1:3], (None, "none"))

    def test_fdc_energy_prefers_2047_then_2048_then_1008_and_records_the_id(self):
        r, out = self.build(FDC, None, mode="--fdc")
        self.assertEqual(r.returncode, 0, r.stderr)
        foods = {f["source_food_id"]: f for f in json.loads(out.read_text())["foods"]}
        got = {fid: (f["per_100g"]["energy_kcal"], f["source_codes"]["energy_kcal"]["fdc_nutrient_id"])
               for fid, f in foods.items()}
        self.assertEqual(got, {"2001": (150.0, "2047"), "2002": (240.0, "2048"),
                               "2003": (52.0, "1008")})
        self.assertEqual(foods["2001"]["absent"], ["satfat_g", "fibre_g", "sugars_g", "sodium_mg"])

    def test_picks_round_trip_the_vendored_seed(self):
        out = self.tmp / "picks.json"
        r = run("picks", "--from", str(ROOT / "seeds" / "nutrients.json"), "--source", "cnf-2026",
                "--out", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        picks = json.loads(out.read_text(encoding="utf-8"))
        seed = json.loads((ROOT / "seeds" / "nutrients.json").read_text(encoding="utf-8"))
        self.assertEqual(len(picks["foods"]), len(seed["foods"]))
        self.assertEqual([m["ingredient_key"] for m in picks["map"]],
                         [m["ingredient_key"] for m in seed["map"]])
        exempt = {p["food_code"] for p in picks["foods"] if p["atwater_exempt"]}
        self.assertEqual(exempt, {str(f["food_code"]) for f in seed["foods"]
                                  if f.get("atwater_note")})
        self.assertEqual(picks["source"]["edition"], "")      # to be filled in by a person

    def test_search_lists_matching_foods(self):
        r = run("search", "--cnf", str(CNF), "test", "egg")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1004 | 504 | Test egg, whole, raw")

    def test_nothing_is_fetched(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for word in ("urllib", "http.client", "requests", "socket"):
            self.assertNotIn(f"import {word}", text)


if __name__ == "__main__":
    unittest.main()
