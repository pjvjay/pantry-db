-- 0009_nutrient_measures — the source's own gram weights for a volume or a count.
--
-- A recipe line written in millilitres ("30 ml Olive Oil") or as a count
-- ("3 Eggs") has no weight, and nutrients are per 100 g. pantry-api never
-- assumes a density (not even water's 1 g/ml): it converts only with a
-- measure the reference source publishes for that food, and quotes the
-- measure verbatim in the line's receipt. A line with no such measure stays
-- unconverted, and its nutrients unknown.
--
--   measure    our key for the measure: 'vol_<n>ml' for a volume, otherwise
--              the verbatim name lowercased with '_' ('1_large_egg')
--   grams      the weight of that measure, from the source (> 0)
--   volume_ml  set for volume measures only; grams / volume_ml is the density
--              of this food, stored per row so one source's cup is never
--              confused with another's
--   verbatim   the measure name as the source publishes it ("15ml",
--              "1 large egg")
--   source_ref the source's own measure id, '' when it gives none
--
-- Mirrored by NutrientMeasureRow in pantry-api/pantry_planner/db.py (same
-- columns, nullability and defaults; the foreign key and CHECKs live here).

CREATE TABLE nutrient_measures (
    ref_id     text NOT NULL REFERENCES nutrient_foods (ref_id) ON DELETE CASCADE,
    measure    text NOT NULL,
    grams      double precision NOT NULL CHECK (grams > 0),
    volume_ml  double precision NULL CHECK (volume_ml IS NULL OR volume_ml > 0),
    verbatim   text NOT NULL,
    source_ref text NOT NULL DEFAULT '',
    PRIMARY KEY (ref_id, measure)
);
