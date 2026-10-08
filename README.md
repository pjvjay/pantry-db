# pantry-db

Database schema, migrations, and seed data for the
[pantry-platform](https://github.com/pjvjay/pantry-platform) GitOps demo.

This repo owns the **deployed** database's shape. The API
([pantry-api](https://github.com/pjvjay/pantry-api)) never runs DDL in
Kubernetes — its SQLAlchemy models mirror the tables defined here, and this
repo's migration image applies them.

## Layout

```
.
├── migrations/            # numbered DDL, applied exactly once each
│   ├── 0001_init.sql
│   ├── 0002_product_attributes.sql   # NL2SQL: subcategory/tags/unit sizes
│   ├── 0003_stores_reviews_terms.sql # query-plan: stores, per-store prices,
│   │                                 # reviews, brand, product_terms index
│   ├── 0004_product_origins.sql      # one resolved origin per product
│   ├── 0005_origin_evidence.sql      # evidence rows beneath the summary;
│   │                                 # scraped price observations
│   ├── 0006_origin_submissions.sql   # reviewed queue for agent-submitted
│   │                                 # label claims (pending → evidence)
│   └── 0007_recipe_line_amounts.sql  # quantity/unit/note per recipe line
│                                     # (demo house amounts)
├── seeds/
│   ├── products.json      # canonical seed data (edit these)
│   ├── recipes.json
│   └── seed.sql           # GENERATED — idempotent, applied every run;
│                          # stores/prices/reviews/terms are synthesized
│                          # deterministically by gen-seed-sql.py
├── scripts/
│   ├── gen-seed-sql.py    # regenerates seeds/seed.sql from the JSON
│   └── run-migrations.sh  # container entrypoint
├── Dockerfile             # postgres:17-alpine + psql runner
└── .github/workflows/     # CI: build → GHCR → bump tag in pantry-gitops
```

## How it runs in the cluster

The image is executed as an **ArgoCD PreSync Job** (defined in
[pantry-gitops](https://github.com/pjvjay/pantry-gitops)): on every sync,
migrations run *before* the app workloads roll. Pending migrations apply
once (tracked in a `schema_migrations` table); the seed file applies every
run and is written to be idempotent.

```
git push here
  → CI builds ghcr.io/pjvjay/pantry-db-migrate:dev-<sha>
  → CI bumps the tag in pantry-gitops
  → ArgoCD PreSync Job migrates the CNPG Postgres cluster
  → app Deployments roll only after the Job succeeds
```

## Editing the schema

Add a new numbered file — never edit an applied migration:

```bash
$EDITOR migrations/0002_add_products_unit_size.sql
git commit -am "add unit_size to products" && git push
```

## Editing seed data

Edit the JSON, regenerate, commit both:

```bash
$EDITOR seeds/products.json
python3 scripts/gen-seed-sql.py
git commit -am "add new products" && git push
```

CI fails the build if `seed.sql` is stale relative to the JSON.

Every word of a product's name and description becomes a `product_terms`
row (lowercased, naive plural stem), and the planner matches an ingredient
only when the product carries all of its words. Two exceptions, applied
identically by pantry-api: words a description negates ("no salt added",
"no jelly", "without X") are not indexed, and a few irregular plurals stem
to their singular ("leaves" -> leaf, "loaves" -> loaf, "halves" -> half).
Otherwise the stem only drops a final "s" (or the "es" of "-oes"), so
"chillies" is indexed as "chillie" and "chiles" as "chile". So:

- Name and describe products the way recipes phrase them, alternate
  spellings included ("chili, chilli, chillies, chile, chiles";
  "scallions"): a spelling the description lacks does not match.
- Keep incidental words out of descriptions. A product joins the pool of
  every ingredient whose words it contains: "clarified butter" on ghee would
  put ghee in every "butter" pool, and "packed in water" puts a can in the
  pool of a recipe's water (pantry-api skips water and ice before matching,
  but the rule stands for every other word).
- File products by kind: the planner's substitutes for a thin pool are the
  cheapest products of the same subcategory, so whole spices ("whole
  spice"), ground spices and blends ("spice"), dried and fresh herbs, and
  cooking and finishing oils each have their own.
- Append new products with new ids and leave existing rows alone. Store
  prices and reviews are seeded from the id.
- pantry-api keeps its own copy of `seeds/products.json` for its SQLite dev
  DB. Copy the file there as well, or local runs will not see the change.

## Testing locally

```bash
docker run -d --name pantry-pg -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=pantry -p 5544:5432 postgres:17-alpine
docker build -t pantry-db-migrate .
docker run --rm --network host \
  -e DB_HOST=localhost -e DB_PORT=5544 -e DB_NAME=pantry \
  -e DB_USER=postgres -e DB_PASSWORD=dev \
  pantry-db-migrate
```

Re-run the last command — everything reports `skip`/idempotent. That's the
same behavior the cluster Job relies on.
