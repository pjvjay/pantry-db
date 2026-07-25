-- 0003_stores_reviews_terms — query-plan retrieval support.
--
-- Backs the staged query-plan executor in pantry-api (t1 existence →
-- t2 options → t3 brand statistics → t4 substitute lookups):
--   * brand: per-product brand so t3 can aggregate price/rating by brand.
--   * stores + store_products: per-store prices with lat/lon, enabling the
--     optional distance constraint ("only stores within 10 km").
--   * reviews: rating source for t3's per-brand statistics.
--   * product_terms: precomputed inverted index over tokenized
--     name+description (same stemmer as pantry-api's parser — see the
--     KEEP-IN-SYNC note in scripts/gen-seed-sql.py). Turns ingredient
--     matching into indexed key joins instead of LIKE '%…%' scans; the
--     seed refresh rebuilds it on every migration run.

ALTER TABLE products ADD COLUMN brand TEXT NOT NULL DEFAULT '';

CREATE TABLE stores (
    id      integer PRIMARY KEY,
    name    text NOT NULL,
    lat     double precision NOT NULL,
    lon     double precision NOT NULL,
    address text NOT NULL DEFAULT ''
);

CREATE TABLE store_products (
    store_id   integer NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    product_id integer NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    price      double precision NOT NULL,
    PRIMARY KEY (store_id, product_id)
);

CREATE TABLE reviews (
    id         integer PRIMARY KEY,
    product_id integer NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    rating     integer NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment    text NOT NULL DEFAULT '',
    created_at text NOT NULL DEFAULT ''
);

CREATE TABLE product_terms (
    term       text NOT NULL,
    product_id integer NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    PRIMARY KEY (term, product_id)
);

CREATE INDEX idx_store_products_product ON store_products (product_id);
CREATE INDEX idx_reviews_product ON reviews (product_id);
