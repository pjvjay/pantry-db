-- 0004_product_origins — country-of-origin cache.
--
-- Backs the origin resolver in pantry-api (origins.py). Resolution is
-- three-tiered, cheapest first: this cache, then deterministic
-- keyword/subcategory heuristics (never cached — free to recompute),
-- then one batch LLM call for products no rule covers. Only the LLM
-- answers land here, so each product pays for at most one call ever.
--
-- Mirrored by the SQLAlchemy model ProductOriginRow in
-- pantry-api/pantry_planner/db.py — keep the two in sync.

CREATE TABLE product_origins (
    product_id  integer PRIMARY KEY REFERENCES products(id),
    country     text NOT NULL,
    confidence  double precision NOT NULL DEFAULT 0.0,
    source      text NOT NULL DEFAULT 'llm',
    reasoning   text NOT NULL DEFAULT '',
    resolved_at text NOT NULL DEFAULT ''
);
