-- 0008_nutrition — reference nutrient values per 100 g, and which reference food
-- answers each recipe ingredient.
--
-- pantry-api computes nutrition per portion eaten from a recipe line's amount
-- (0007) and the nutrients of one reference food per ingredient. Nothing here
-- is a product's label: the catalog is synthetic and has no nutrition facts,
-- so every value is a published reference value for a generic food, cited to
-- its source and shown with its description verbatim.
--
-- Four new tables and no change to an existing one, for the same reason as
-- 0007: an API that knows about nutrition must still run against a database
-- that has not had this migration. pantry-api's load_reference returns None
-- when the tables are missing, and plans then say nutrition is not available
-- instead of failing.
--
--   nutrient_sources        one row per dataset, with its licence and the
--                           attribution line shown wherever a number is.
--                           `edition` says which edition the values are
--                           believed to be, and how sure that is.
--   nutrient_foods          one reference food per row; ref_id is
--                           '<source>:<food code>', description is verbatim,
--                           state_note says what was measured ("raw, meat
--                           only", "dry").
--   nutrient_amounts        per 100 g, one row per (food, nutrient). The
--                           nutrients are the eight below. A nutrient the
--                           source did not publish for a food has NO row,
--                           which means unknown; a stored 0 means the source
--                           published 0. Code never reads a missing row as 0.
--   ingredient_nutrient_map ingredient key (pantry-api's units.tokens() of the
--                           line's name, joined by spaces) -> reference food.
--                           match_kind is 'generic' (the same food), 'close'
--                           (a near food; `note` says how it differs) or
--                           'none' (reviewed, and no reference food fits;
--                           ref_id NULL). A key with no row at all has not
--                           been reviewed, which is a different thing.
--
-- Timestamps are ISO-8601 text, as in 0005 and 0006, so the API's SQLAlchemy
-- mirror stays identical on SQLite. Mirrored by NutrientSourceRow,
-- NutrientFoodRow, NutrientAmountRow and IngredientNutrientMapRow in
-- pantry-api/pantry_planner/db.py (same columns, nullability and defaults;
-- foreign keys and CHECKs live here only, as for every other table).

CREATE TABLE nutrient_sources (
    source       text PRIMARY KEY,
    name         text NOT NULL,
    publisher    text NOT NULL DEFAULT '',
    edition      text NOT NULL DEFAULT '',
    licence      text NOT NULL DEFAULT '',
    licence_url  text NOT NULL DEFAULT '',
    attribution  text NOT NULL DEFAULT '',
    url          text NOT NULL DEFAULT '',
    retrieved_at text NOT NULL DEFAULT ''
);

CREATE TABLE nutrient_foods (
    ref_id         text PRIMARY KEY,                -- '<source>:<food code>'
    source         text NOT NULL REFERENCES nutrient_sources (source),
    source_food_id text NOT NULL,
    food_code      text NOT NULL DEFAULT '',
    description    text NOT NULL,                   -- verbatim
    state_note     text NOT NULL DEFAULT '',        -- e.g. raw, meat only / dry
    UNIQUE (source, source_food_id)
);

CREATE TABLE nutrient_amounts (
    ref_id      text NOT NULL REFERENCES nutrient_foods (ref_id) ON DELETE CASCADE,
    nutrient    text NOT NULL CHECK (nutrient IN (
                    'energy_kcal', 'protein_g', 'fat_g', 'satfat_g',
                    'carbohydrate_g', 'fibre_g', 'sugars_g', 'sodium_mg')),
    per_100g    double precision NOT NULL CHECK (per_100g >= 0),
    source_code text NOT NULL DEFAULT '',           -- the source's own nutrient id
    PRIMARY KEY (ref_id, nutrient)
);  -- an absent row = not published = unknown

CREATE TABLE ingredient_nutrient_map (
    ingredient_key text PRIMARY KEY,
    ref_id         text REFERENCES nutrient_foods (ref_id),
    match_kind     text NOT NULL CHECK (match_kind IN ('generic', 'close', 'none')),
    note           text NOT NULL DEFAULT '',
    reviewed_at    text NOT NULL DEFAULT '',
    CHECK ((match_kind = 'none') = (ref_id IS NULL))
);
