-- 0002_product_attributes — NL2SQL search support.
--
-- Adds the category hierarchy and product attributes the natural-language
-- retrieval filters on:
--   * category becomes the BROAD group (bakery, dairy, produce, meat,
--     pantry, snacks, frozen); new subcategory carries the fine grain
--     (bread, cheese, pasta, canned, sauce, ...). Values are re-mapped by
--     the seed refresh (seeds upsert every run), so no data migration here.
--   * dietary_tags: comma list of what the product CONTAINS
--     (dairy,gluten,meat,nuts,egg,soy) — "no dairy" filters by exclusion.
--   * unit_size (display) + unit_qty/unit_uom (canonical g|ml|each) for
--     quantity-aware size-fit ranking. Unit value = price/unit_qty,
--     computed in queries; deliberately not stored.

ALTER TABLE products ADD COLUMN subcategory  TEXT NOT NULL DEFAULT '';
ALTER TABLE products ADD COLUMN dietary_tags TEXT NOT NULL DEFAULT '';
ALTER TABLE products ADD COLUMN unit_size    TEXT NOT NULL DEFAULT '';
ALTER TABLE products ADD COLUMN unit_qty     REAL;
ALTER TABLE products ADD COLUMN unit_uom     TEXT NOT NULL DEFAULT '';

CREATE INDEX idx_products_cat_subcat ON products (category, subcategory);
