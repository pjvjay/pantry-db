#!/usr/bin/env python3
"""Build seeds/nutrients.json from a Canadian Nutrient File (CNF) download, offline.

The vendored nutrients.json was read from the CNF API one food at a time,
because downloading the CNF files has not been approved. If the owner later
downloads them (the CNF zip of CSVs, or USDA FoodData Central's SR Legacy
CSVs as a fallback), this script rebuilds the file from that download for the
same human-picked foods. It never fetches anything: every input is a local
path, kept outside the repos and never committed. Stdlib only; run it with
`python3 -I` so nothing in the data folder can shadow a module.

    python3 -I scripts/cnf-subset.py search --cnf PATH chicken thigh
    python3 -I scripts/cnf-subset.py picks --from seeds/nutrients.json --source cnf-2026 \\
        --out /tmp/picks.json
    python3 -I scripts/cnf-subset.py build --cnf PATH --picks /tmp/picks.json --out OUT.json
    python3 -I scripts/cnf-subset.py build --fdc PATH --picks picks.json --out OUT.json

PATH is a folder of CSVs or the zip itself.

`picks` turns the current nutrients.json into a picks file: the source to
write, each food by its food code with its description (to be checked against
the download), state note, whether it needs measures and whether its Atwater
exemption stands, and the ingredient map. Edit the source block (name,
edition, licence, retrieved date) before building.

`build` reads only the picked foods. It fails, naming the file and what it
expected, rather than guess:
  - a CSV whose header lacks a column this script needs (headers are matched
    by name, through the aliases below, never by position);
  - a nutrient whose unit is not the one its key says (kcal, g or mg). Energy
    is chosen by unit: of the energy rows, the one in kcal, never kJ;
  - a picked food missing from the download, or whose description differs
    from the one in the picks (unless --accept-descriptions);
  - a negative value, or a gram nutrient above 100 g per 100 g;
  - energy more than max(25 kcal, 20%) away from 4 x protein + 9 x fat +
    4 x carbohydrate, unless the pick says atwater_exempt (a human decision;
    the note's arithmetic is rewritten from the new values).

Nutrients are selected by the source's nutrient code or INFOODS tagname plus
the unit, never by NutrientID alone, which the database generates. A nutrient
the download has no row for is left out of per_100g and listed in `absent`:
unknown, never 0. In FDC mode energy is the first of nutrient 2047 (Atwater
general factors), 2048 (Atwater specific factors) and 1008 (Energy) that the
food has, and the id used is recorded in source_codes. CSVs are read as
UTF-8 (with or without a BOM), falling back to cp1252.

The CNF header and nutrient-code names below are the ones the CNF 2015
documentation uses and FDC's, written from memory and checked only against
the invented fixtures in tests/fixtures; a real download that differs fails
loudly at the header check.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
import zipfile
from pathlib import Path

NUTRIENTS = {"energy_kcal": "kcal", "protein_g": "g", "fat_g": "g", "satfat_g": "g",
             "carbohydrate_g": "g", "fibre_g": "g", "sugars_g": "g", "sodium_mg": "mg"}

# CNF: each nutrient by NutrientCode or Tagname. Energy lists both of its rows
# (kcal and kJ); the unit decides between them.
CNF_NUTRIENTS = {
    "energy_kcal": ({"208", "268"}, {"ENERC_KCAL", "ENERC_KJ"}),
    "protein_g": ({"203"}, {"PROCNT"}),
    "fat_g": ({"204"}, {"FAT"}),
    "satfat_g": ({"606"}, {"FASAT"}),
    "carbohydrate_g": ({"205"}, {"CHOCDF"}),
    "fibre_g": ({"291"}, {"FIBTG"}),
    "sugars_g": ({"269"}, {"SUGAR"}),
    "sodium_mg": ({"307"}, {"NA"}),
}

# FDC: nutrient ids in order of preference.
FDC_NUTRIENTS = {
    "energy_kcal": ("2047", "2048", "1008"),
    "protein_g": ("1003",),
    "fat_g": ("1004",),
    "satfat_g": ("1258",),
    "carbohydrate_g": ("1005",),
    "fibre_g": ("1079",),
    "sugars_g": ("2000",),
    "sodium_mg": ("1093",),
}

# logical column -> header names accepted for it
CNF_FILES = {
    "food": ("FOOD NAME", {"food_id": ["FoodID"], "food_code": ["FoodCode"],
                           "description": ["FoodDescription"]}),
    "nutrient": ("NUTRIENT NAME", {"nutrient_id": ["NutrientID", "NutrientNameID"],
                                   "code": ["NutrientCode"], "tagname": ["Tagname", "TagName"],
                                   "unit": ["NutrientUnit", "Unit"]}),
    "amount": ("NUTRIENT AMOUNT", {"food_id": ["FoodID"],
                                   "nutrient_id": ["NutrientID", "NutrientNameID"],
                                   "value": ["NutrientValue"],
                                   "source_id": ["NutrientSourceID"],
                                   "n_obs": ["NumberofObservations", "NumberOfObservations"]}),
    "factor": ("CONVERSION FACTOR", {"food_id": ["FoodID"], "measure_id": ["MeasureID"],
                                     "factor": ["ConversionFactorValue"]}),
    "measure": ("MEASURE NAME", {"measure_id": ["MeasureID"],
                                 "description": ["MeasureDescription"]}),
}
FDC_FILES = {
    "food": ("food", {"food_id": ["fdc_id"], "description": ["description"]}),
    "nutrient": ("nutrient", {"nutrient_id": ["id"], "unit": ["unit_name"],
                              "name": ["name"]}),
    "amount": ("food_nutrient", {"food_id": ["fdc_id"], "nutrient_id": ["nutrient_id"],
                                 "value": ["amount"]}),
}
# Columns a file may lack without failing.
OPTIONAL = {"source_id", "n_obs", "tagname", "code"}

_ML = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*ml\s*$", re.IGNORECASE)


class Refused(Exception):
    """The download or the picks cannot give a number this script can stand behind."""


# ─── reading the download ───

def _norm(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", Path(name).stem.upper())


class Download:
    """CSV files from a folder or a zip, found by name (case, spaces and
    underscores ignored), decoded UTF-8 then cp1252, and hashed as read."""

    def __init__(self, path: Path):
        self.path = path
        self.sha256: dict[str, str] = {}
        if path.is_dir():
            self._files = {_norm(p.name): p.name for p in path.iterdir() if p.suffix.lower() == ".csv"}
            self._read = lambda n: (path / n).read_bytes()
        elif zipfile.is_zipfile(path):
            zf = zipfile.ZipFile(path)
            names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            self._files = {_norm(n): n for n in names}
            self._read = zf.read
        else:
            raise Refused(f"{path}: not a folder of CSVs or a zip")

    def rows(self, kind: str, spec: tuple[str, dict[str, list[str]]]) -> list[dict[str, str]]:
        fname, columns = spec
        actual = self._files.get(_norm(fname))
        if actual is None:
            raise Refused(f"{self.path}: no '{fname}.csv' (found: {sorted(self._files.values())})")
        raw = self._read(actual)
        self.sha256[Path(actual).name] = hashlib.sha256(raw).hexdigest()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252")
        reader = csv.DictReader(io.StringIO(text))
        headers = [h.strip() for h in (reader.fieldnames or [])]
        pick: dict[str, str] = {}
        for logical, names in columns.items():
            found = next((h for h in headers if h in names), None)
            if found is None and logical not in OPTIONAL:
                raise Refused(f"{actual}: no column for {logical} (expected one of "
                              f"{', '.join(names)}); its header is {', '.join(headers)}")
            if found is not None:
                pick[logical] = found
        out = []
        for row in reader:
            row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            out.append({logical: row[h] for logical, h in pick.items()})
        return out


def _cnf_nutrient_ids(rows: list[dict[str, str]]) -> dict[str, tuple[str, dict]]:
    """Our nutrient key -> (the download's NutrientID, its codes), chosen by code or
    tagname and then by unit."""
    out = {}
    for key, (codes, tags) in CNF_NUTRIENTS.items():
        want = NUTRIENTS[key]
        family = [r for r in rows if r.get("code") in codes or r.get("tagname", "").upper() in tags]
        if not family:
            raise Refused(f"NUTRIENT NAME: no row for {key} (codes {sorted(codes)}, "
                          f"tagnames {sorted(tags)})")
        chosen = [r for r in family if r["unit"].strip().lower() == want]
        if key == "energy_kcal" and len(chosen) != 1:
            raise Refused(f"NUTRIENT NAME: expected one energy row in kcal, found "
                          f"{[(r.get('code'), r['unit']) for r in family]}")
        if len(chosen) != 1:
            raise Refused(f"NUTRIENT NAME: {key} must be in {want}, found "
                          f"{[(r.get('code'), r['unit']) for r in family]}")
        r = chosen[0]
        out[key] = (r["nutrient_id"], {"nutrient_code": r.get("code", ""),
                                       "tagname": r.get("tagname", ""), "unit": r["unit"]})
    return out


def _fdc_units(rows: list[dict[str, str]]) -> dict[str, str]:
    return {r["nutrient_id"]: r["unit"].strip().lower() for r in rows}


def _number(text: str, where: str) -> float:
    try:
        v = float(text)
    except ValueError:
        raise Refused(f"{where}: {text!r} is not a number") from None
    if not math.isfinite(v):
        raise Refused(f"{where}: {text!r} is not finite")
    return v


def _measure_key(verbatim: str) -> tuple[str, float | None]:
    m = _ML.match(verbatim)
    if m:
        ml = float(m.group(1))
        return f"vol_{m.group(1)}ml", ml
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", verbatim.lower())).strip("_"), None


def _atwater_note(per: dict[str, float]) -> str | None:
    """None when energy agrees with 4P + 9F + 4C, else the arithmetic, as
    gen-seed-sql.py's check reads it."""
    if not {"energy_kcal", "protein_g", "fat_g", "carbohydrate_g"} <= per.keys():
        return None
    e = per["energy_kcal"]
    at = 4 * per["protein_g"] + 9 * per["fat_g"] + 4 * per["carbohydrate_g"]
    if abs(e - at) <= max(25, 0.2 * e):
        return None
    note = (f"Published energy {e:g} kcal is outside the Atwater check against "
            f"4 x protein + 9 x fat + 4 x carbohydrate = {at:.1f} kcal.")
    if "fibre_g" in per:
        note += (f" This food has {per['fibre_g']:g} g fibre per 100 g; counting that fibre at "
                 f"2 kcal/g instead of 4 gives {at - 2 * per['fibre_g']:.1f} kcal.")
    return note + " The published value is kept as it is."


# ─── build ───

def build(download: Download, picks: dict, *, fdc: bool, accept_descriptions: bool = False) -> dict:
    files = FDC_FILES if fdc else CNF_FILES
    src = picks["source"]
    foods_csv = download.rows("food", files["food"])
    nutrient_rows = download.rows("nutrient", files["nutrient"])
    amount_rows = download.rows("amount", files["amount"])

    by_id = {r["food_id"]: r for r in foods_csv}
    by_code = {r["food_code"]: r for r in foods_csv if r.get("food_code")}
    resolved = []
    mismatched = []
    for p in picks["foods"]:
        if "food_id" in p:
            row = by_id.get(str(p["food_id"]))
        elif fdc:
            raise Refused(f"pick {p}: FDC picks name a food by food_id (fdc_id)")
        else:
            row = by_code.get(str(p["food_code"]))
        if row is None:
            raise Refused(f"pick {p.get('food_id', p.get('food_code'))}: not in the download")
        if p.get("description") and p["description"] != row["description"]:
            mismatched.append(f"{p.get('food_id', p.get('food_code'))}: picks say "
                              f"{p['description']!r}, the download says {row['description']!r}")
        resolved.append((p, row))
    if mismatched and not accept_descriptions:
        raise Refused("descriptions differ, so these may be other foods (review, then pass "
                      "--accept-descriptions):\n  " + "\n  ".join(mismatched))

    wanted = {row["food_id"] for _, row in resolved}
    values: dict[tuple[str, str], dict[str, str]] = {}
    for r in amount_rows:
        if r["food_id"] in wanted:
            values[(r["food_id"], r["nutrient_id"])] = r

    if fdc:
        units = _fdc_units(nutrient_rows)
    else:
        chosen = _cnf_nutrient_ids(nutrient_rows)

    foods_out = []
    for p, row in resolved:
        fid = row["food_id"]
        per: dict[str, float] = {}
        codes: dict[str, dict] = {}
        for key in NUTRIENTS:
            where = f"food {fid} {key}"
            if fdc:
                for nid in FDC_NUTRIENTS[key]:
                    hit = values.get((fid, nid))
                    if hit is None:
                        continue
                    if units.get(nid) != NUTRIENTS[key]:
                        raise Refused(f"{where}: nutrient {nid} is in {units.get(nid)!r}, "
                                      f"not {NUTRIENTS[key]}")
                    per[key] = _number(hit["value"], where)
                    codes[key] = {"nutrient_code": nid, "fdc_nutrient_id": nid,
                                  "unit": units[nid]}
                    break
            else:
                nid, meta = chosen[key]
                hit = values.get((fid, nid))
                if hit is not None:
                    per[key] = _number(hit["value"], where)
                    codes[key] = {**meta, "nutrient_id": nid,
                                  "nutrient_source_id": hit.get("source_id", ""),
                                  "number_observation": hit.get("n_obs", "")}
            v = per.get(key)
            if v is not None and v < 0:
                raise Refused(f"{where}: negative value {v}")
            if v is not None and NUTRIENTS[key] == "g" and v > 100:
                raise Refused(f"{where}: {v} g per 100 g")
        if "energy_kcal" not in per or "protein_g" not in per:
            raise Refused(f"food {fid}: the download has no energy or no protein for it")
        note = _atwater_note(per)
        if note and not p.get("atwater_exempt"):
            raise Refused(f"food {fid}: {note} Mark the pick atwater_exempt only after review.")
        food = {
            "ref_id": f"{src['source']}:{fid}",
            "source": src["source"],
            "source_food_id": fid,
            "food_code": row.get("food_code", fid),
            "description": row["description"],
            "state_note": p["state_note"],
            "retrieved_at": src["retrieved_at"],
            "per_100g": per,
            "absent": [k for k in NUTRIENTS if k not in per],
        }
        if note:
            food["atwater_note"] = note
        food["source_codes"] = codes
        foods_out.append(food)

    measures = []
    want_measures = [row["food_id"] for p, row in resolved if p.get("measures")]
    if want_measures and fdc:
        print("FDC mode does not read portions: no measures written; volume and count "
              "lines stay unconverted until measures are reviewed.", file=sys.stderr)
    elif want_measures:
        names = {r["measure_id"]: r["description"]
                 for r in download.rows("measure", CNF_FILES["measure"])}
        factors = download.rows("factor", CNF_FILES["factor"])
        for fid in want_measures:
            rows = sorted((r for r in factors if r["food_id"] == fid),
                          key=lambda r: (int(r["measure_id"]) if r["measure_id"].isdigit()
                                         else 0, r["measure_id"]))
            for r in rows:
                factor = _number(r["factor"], f"food {fid} measure {r['measure_id']}")
                if factor <= 0:
                    continue        # "no serving specified" rows carry no weight
                verbatim = names.get(r["measure_id"])
                if verbatim is None:
                    raise Refused(f"measure {r['measure_id']}: not in MEASURE NAME")
                key, ml = _measure_key(verbatim)
                measures.append({"ref_id": f"{src['source']}:{fid}", "measure": key,
                                 "grams": round(factor * 100, 6), "volume_ml": ml,
                                 "verbatim": verbatim, "source_ref": r["measure_id"]})

    known = {f["ref_id"] for f in foods_out}
    by_pick = {str(p.get("food_id", p.get("food_code"))): f"{src['source']}:{row['food_id']}"
               for p, row in resolved}
    mapping = []
    for m in picks["map"]:
        pick = m.get("food")
        ref_id = None if pick is None else by_pick.get(str(pick))
        if pick is not None and ref_id not in known:
            raise Refused(f"map {m['ingredient_key']!r}: food {pick} is not among the picks")
        mapping.append({"ingredient_key": m["ingredient_key"], "ref_id": ref_id,
                        "match_kind": m["match_kind"], "note": m.get("note", ""),
                        "reviewed_at": m.get("reviewed_at", "")})

    source = {k: src[k] for k in ("source", "name", "publisher", "edition", "licence",
                                  "licence_url", "attribution", "url", "retrieved_at")
              if k in src}
    source["files_sha256"] = dict(sorted(download.sha256.items()))
    return {"v": 1, "about": picks.get("about", ""), "sources": [source],
            "nutrients": {k: {"unit": u} for k, u in NUTRIENTS.items()},
            "foods": foods_out, "measures": measures, "map": mapping}


def picks_from(current: dict, source: str) -> dict:
    """A picks file from a nutrients.json: the same foods (by food code, with
    the description to check), state notes, exemptions and map."""
    ref_to_code = {f["ref_id"]: str(f["food_code"]) for f in current["foods"]}
    with_measures = {m["ref_id"] for m in current.get("measures", [])}
    old = current["sources"][0]
    return {
        "about": current.get("about", ""),
        "source": {"source": source, "name": "", "publisher": old.get("publisher", ""),
                   "edition": "", "licence": "", "licence_url": "",
                   "attribution": old.get("attribution", ""), "url": "", "retrieved_at": ""},
        "foods": [{"food_code": str(f["food_code"]), "description": f["description"],
                   "state_note": f["state_note"], "measures": f["ref_id"] in with_measures,
                   "atwater_exempt": bool(f.get("atwater_note"))} for f in current["foods"]],
        "map": [{"ingredient_key": m["ingredient_key"],
                 "food": None if m["ref_id"] is None else ref_to_code[m["ref_id"]],
                 "match_kind": m["match_kind"], "note": m.get("note", ""),
                 "reviewed_at": m.get("reviewed_at", "")} for m in current["map"]],
    }


def search(download: Download, words: list[str], *, fdc: bool, limit: int = 20) -> list[str]:
    rows = download.rows("food", (FDC_FILES if fdc else CNF_FILES)["food"])
    want = [w.lower() for w in words]
    hits = [r for r in rows if all(w in r["description"].lower() for w in want)]
    hits.sort(key=lambda r: (len(r["description"]), r["description"], r["food_id"]))
    return [f"{r['food_id']} | {r.get('food_code', '')} | {r['description']}"
            for r in hits[:limit]]


def dumps(data: dict) -> str:
    """The seed's own format: 2-space indent, UTF-8 as written, trailing newline."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="list foods whose description has every word")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--cnf", type=Path)
    g.add_argument("--fdc", type=Path)
    s.add_argument("words", nargs="+")
    b = sub.add_parser("build", help="write nutrients.json for the picked foods")
    g = b.add_mutually_exclusive_group(required=True)
    g.add_argument("--cnf", type=Path)
    g.add_argument("--fdc", type=Path)
    b.add_argument("--picks", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--accept-descriptions", action="store_true")
    p = sub.add_parser("picks", help="write a picks file from a nutrients.json")
    p.add_argument("--from", dest="src", type=Path, required=True)
    p.add_argument("--source", required=True, help="the new source id, e.g. cnf-2026")
    p.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    try:
        if args.cmd == "picks":
            current = json.loads(args.src.read_text(encoding="utf-8"))
            args.out.write_text(dumps(picks_from(current, args.source)), encoding="utf-8")
            return 0
        fdc = args.fdc is not None
        download = Download(args.fdc if fdc else args.cnf)
        if args.cmd == "search":
            print("\n".join(search(download, args.words, fdc=fdc)))
            return 0
        picks = json.loads(args.picks.read_text(encoding="utf-8"))
        data = build(download, picks, fdc=fdc, accept_descriptions=args.accept_descriptions)
        args.out.write_text(dumps(data), encoding="utf-8")
        print(f"wrote {args.out}: {len(data['foods'])} foods, {len(data['measures'])} "
              f"measures, {len(data['map'])} map rows")
        return 0
    except Refused as e:
        print(f"cnf-subset: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
