-- 0010_matching_cache — what the matcher asked a model once, kept for good.
--
-- An ingredient name no seed knows is identified by a low-cost model (its
-- product type, form and variant) and its identity string is embedded; both
-- answers are the same every time they are wanted, so each is stored the
-- first time and read from here after. pantry-api has no disk of its own in
-- the deployment, and several instances share one database, so the cache
-- lives here rather than in a file or in memory alone.
--
--   ingredient_identities  one row per described name, keyed by a hash of the
--                          prompt version, the model, the catalog's type list
--                          and the normalized name, so a changed prompt or
--                          catalog makes new rows instead of reusing stale ones
--     status               'auto' (the model's answer), 'reviewed' (a person
--                          confirmed it) or 'overridden' (a person corrected
--                          it); a reviewed or overridden row is never replaced
--   embedding_cache        one row per embedded text, keyed by a hash of the
--                          model, its dimensions and the text; the vector is
--                          a JSON array of floats (text), so SQLite tests and
--                          Postgres hold it the same way
--   matching_usage         how many model requests were made per UTC day and
--                          kind ('embed_texts', 'describe_calls'), so every
--                          instance counts against the same free-tier budget
--
-- Timestamps are ISO-8601 text written by pantry-api, as every table here
-- keeps them. Mirrored by IngredientIdentityRow, EmbeddingCacheRow and
-- MatchingUsageRow in pantry-api/pantry_planner/db.py (same columns,
-- nullability and defaults; the CHECK lives here).

CREATE TABLE ingredient_identities (
    key                 text PRIMARY KEY,
    name                text NOT NULL,
    normalized          text NOT NULL,
    product_type        text NOT NULL,
    form                text NOT NULL DEFAULT '',
    variant             text NOT NULL DEFAULT '',
    look_alikes         text NOT NULL DEFAULT '[]',
    identity            text NOT NULL,
    model               text NOT NULL,
    prompt_version      integer NOT NULL,
    catalog_fingerprint text NOT NULL,
    status              text NOT NULL DEFAULT 'auto'
                        CHECK (status IN ('auto', 'reviewed', 'overridden')),
    created_at          text NOT NULL DEFAULT ''
);
CREATE INDEX ingredient_identities_normalized ON ingredient_identities (normalized);

CREATE TABLE embedding_cache (
    key        text PRIMARY KEY,
    model      text NOT NULL,
    dims       integer NOT NULL,
    text       text NOT NULL,
    vector     text NOT NULL,
    created_at text NOT NULL DEFAULT ''
);

CREATE TABLE matching_usage (
    day   text NOT NULL,
    kind  text NOT NULL,
    count integer NOT NULL DEFAULT 0,
    PRIMARY KEY (day, kind)
);
