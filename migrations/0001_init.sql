-- 0001_init — pantry schema.
--
-- Source of truth for the deployed database schema. The API's SQLAlchemy
-- models (pantry-api/pantry_planner/db.py) mirror these tables; the API
-- never runs DDL in Kubernetes — this migration Job does.
--
-- Types map from the SQLAlchemy models:
--   Integer → integer, String → text, Float → double precision

CREATE TABLE products (
    id          integer PRIMARY KEY,
    name        text NOT NULL,
    description text NOT NULL DEFAULT '',
    price       double precision NOT NULL,
    category    text
);

CREATE TABLE recipes (
    slug     text PRIMARY KEY,
    name     text NOT NULL,
    servings integer NOT NULL DEFAULT 1
);

CREATE TABLE recipe_ingredients (
    recipe_slug text NOT NULL REFERENCES recipes (slug) ON DELETE CASCADE,
    line_no     integer NOT NULL,
    name        text NOT NULL,
    category    text,
    PRIMARY KEY (recipe_slug, line_no)
);
