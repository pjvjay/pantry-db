-- 0007_recipe_line_amounts — how much of each library recipe line to buy.
--
-- recipe_ingredients says what a recipe needs, never how much. pantry-api's
-- GET /recipes/{slug}/doc now hands a library recipe to the shopper as
-- reviewable lines ("700 g Chicken Thighs") that /plan/spec plans as they
-- are, so each line needs an amount. The amounts get a table of their own
-- rather than columns on recipe_ingredients, for two reasons:
--
--   * An API that knows about amounts must still run against a database
--     that has not had this migration yet. pantry-api's load_line_amounts
--     returns None when the table is missing, and the recipe's lines are
--     then shown as unquantified with a warning, instead of failing.
--   * The classic plan path (/plan/{slug}) reads recipe_ingredients only,
--     so it is untouched.
--
-- The library's amounts are demo house amounts: synthetic gram and
-- millilitre amounts written for this demo, not a cookbook's, and labelled
-- that way wherever they are shown. quantity NULL means the amount is not
-- stated, and `note` then says why. unit and note are free text, '' when
-- absent.
--
-- The foreign key cascades, so seed.sql's delete + re-insert of a recipe's
-- ingredient lines also deletes that recipe's amounts; gen-seed-sql.py
-- inserts them again after the lines.
--
-- Mirrored by the SQLAlchemy model RecipeLineAmountRow in
-- pantry-api/pantry_planner/db.py (same columns, nullability and defaults;
-- the foreign key lives here only, as for every other table).

CREATE TABLE recipe_line_amounts (
    recipe_slug text NOT NULL,
    line_no     integer NOT NULL,
    quantity    double precision NULL,  -- NULL = not stated
    unit        text NOT NULL DEFAULT '',
    note        text NOT NULL DEFAULT '',
    PRIMARY KEY (recipe_slug, line_no),
    FOREIGN KEY (recipe_slug, line_no)
        REFERENCES recipe_ingredients (recipe_slug, line_no) ON DELETE CASCADE
);
