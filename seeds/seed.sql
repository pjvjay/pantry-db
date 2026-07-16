-- GENERATED FILE — do not edit by hand.
-- Regenerate with: python3 scripts/gen-seed-sql.py
-- Applied on every migration run; written to be idempotent.

BEGIN;

-- ─── products ───
INSERT INTO products (id, name, description, price, category) VALUES (1, 'Wheat Bread 1', 'Whole-grain wheat sandwich loaf, 675g, sliced', 5.0, 'bread') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (2, 'Wheat Bread 2', 'Basic wheat sandwich loaf, 450g, sliced, store brand', 3.0, 'bread') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (3, 'Dark Chocolate Cadbury', '70% cocoa dark chocolate bar, 100g', 5.0, 'chocolate') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (4, 'Milk Chocolate Cadbury', 'Milk chocolate bar, smooth and creamy, 100g', 10.0, 'chocolate') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (5, 'Nestles PBJ', 'Peanut butter and grape jelly swirl in a single jar, 340g', 8.0, 'spread') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (6, 'Canadian Peanut Butter Cream', 'Smooth peanut butter, no jelly, 500g', 3.0, 'spread') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (7, 'Sourdough Loaf', 'Artisanal sourdough, 600g, whole loaf uncut', 6.5, 'bread') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (8, 'Basmati Rice 2kg', 'Long-grain basmati rice, 2kg bag, produced in India', 12.0, 'grain') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (9, 'Long Grain White Rice 1kg', 'Standard long-grain white rice, 1kg bag', 4.5, 'grain') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (10, 'Boneless Skinless Chicken Breast', 'Fresh chicken breast, boneless & skinless, ~500g package', 8.99, 'meat') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (11, 'Chicken Thighs Bone-In', 'Bone-in, skin-on chicken thighs, ~700g', 6.49, 'meat') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (12, 'Yellow Onion', 'Fresh yellow cooking onion, 1 bulb (~200g)', 0.99, 'produce') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (13, 'Fresh Garlic', 'One bulb of fresh garlic (~50g)', 0.79, 'produce') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (14, 'Roma Tomato', 'Fresh Roma tomatoes, 500g pack', 2.99, 'produce') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (15, 'Canned Diced Tomatoes', 'Diced tomatoes in juice, canned, 796ml', 1.99, 'pantry') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (16, 'Extra Virgin Olive Oil 500ml', 'Cold-pressed extra virgin olive oil, 500ml', 9.99, 'oil') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (17, 'Canola Oil 1L', 'Neutral canola cooking oil, 1L', 4.49, 'oil') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (18, 'Butter Salted 454g', 'Salted butter, 454g, from grass-fed cows', 6.99, 'dairy') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (19, 'Whole Milk 1L', '3.25% homogenized milk, 1L carton', 2.99, 'dairy') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (20, 'Plain Greek Yogurt 750g', 'Plain Greek yogurt, unsweetened, 750g tub', 5.99, 'dairy') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (21, 'Spaghetti Pasta 500g', 'Dry spaghetti pasta, 500g box', 2.49, 'pantry') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (22, 'Ground Beef Lean', 'Lean ground beef, ~450g package, fresh', 7.99, 'meat') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (23, 'Cheddar Cheese Block 300g', 'Sharp aged cheddar cheese, 300g block', 5.99, 'dairy') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (24, 'Mozzarella Shredded 200g', 'Shredded mozzarella for pizza / pasta, 200g', 4.99, 'dairy') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (25, 'Fresh Ginger', 'Fresh ginger root, sold by weight, priced per 100g', 1.29, 'produce') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (26, 'Cumin Ground 100g', 'Ground cumin spice, 100g jar', 3.49, 'spice') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (27, 'Turmeric Ground 100g', 'Ground turmeric spice, 100g jar', 3.99, 'spice') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (28, 'Coriander Ground 100g', 'Ground coriander spice, 100g jar', 3.49, 'spice') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (29, 'Garam Masala 100g', 'Traditional Indian spice blend, 100g', 4.99, 'spice') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;
INSERT INTO products (id, name, description, price, category) VALUES (30, 'Frozen Broccoli 500g', 'Frozen broccoli florets, 500g bag', 3.49, 'produce') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, category = EXCLUDED.category;

-- ─── recipes ───
INSERT INTO recipes (slug, name, servings) VALUES ('pbj_sandwich', 'Peanut Butter & Jelly Sandwich', 2) ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, servings = EXCLUDED.servings;
INSERT INTO recipes (slug, name, servings) VALUES ('spaghetti_bolognese', 'Spaghetti Bolognese', 4) ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, servings = EXCLUDED.servings;
INSERT INTO recipes (slug, name, servings) VALUES ('chicken_curry', 'Simple Chicken Curry', 4) ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, servings = EXCLUDED.servings;
INSERT INTO recipes (slug, name, servings) VALUES ('grilled_cheese', 'Grilled Cheese Sandwich', 1) ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, servings = EXCLUDED.servings;
INSERT INTO recipes (slug, name, servings) VALUES ('veggie_stirfry', 'Vegetable Stir Fry', 2) ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, servings = EXCLUDED.servings;

-- ─── recipe_ingredients (delete + re-insert per recipe) ───
DELETE FROM recipe_ingredients WHERE recipe_slug = 'pbj_sandwich';
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('pbj_sandwich', 1, 'Peanut Butter and Jelly Jam', 'spread');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('pbj_sandwich', 2, 'Wheat Bread', 'bread');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('pbj_sandwich', 3, 'White Chocolate', 'chocolate');
DELETE FROM recipe_ingredients WHERE recipe_slug = 'spaghetti_bolognese';
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('spaghetti_bolognese', 1, 'Spaghetti', 'pantry');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('spaghetti_bolognese', 2, 'Ground Beef', 'meat');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('spaghetti_bolognese', 3, 'Yellow Onion', 'produce');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('spaghetti_bolognese', 4, 'Garlic', 'produce');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('spaghetti_bolognese', 5, 'Canned Tomatoes', 'pantry');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('spaghetti_bolognese', 6, 'Olive Oil', 'oil');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('spaghetti_bolognese', 7, 'Mozzarella', 'dairy');
DELETE FROM recipe_ingredients WHERE recipe_slug = 'chicken_curry';
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('chicken_curry', 1, 'Chicken Thighs', 'meat');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('chicken_curry', 2, 'Basmati Rice', 'grain');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('chicken_curry', 3, 'Yellow Onion', 'produce');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('chicken_curry', 4, 'Garlic', 'produce');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('chicken_curry', 5, 'Ginger', 'produce');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('chicken_curry', 6, 'Garam Masala', 'spice');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('chicken_curry', 7, 'Turmeric', 'spice');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('chicken_curry', 8, 'Diced Tomatoes', 'pantry');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('chicken_curry', 9, 'Canola Oil', 'oil');
DELETE FROM recipe_ingredients WHERE recipe_slug = 'grilled_cheese';
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('grilled_cheese', 1, 'Sliced Bread', 'bread');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('grilled_cheese', 2, 'Cheddar Cheese', 'dairy');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('grilled_cheese', 3, 'Butter', 'dairy');
DELETE FROM recipe_ingredients WHERE recipe_slug = 'veggie_stirfry';
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('veggie_stirfry', 1, 'Broccoli', 'produce');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('veggie_stirfry', 2, 'Basmati Rice', 'grain');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('veggie_stirfry', 3, 'Garlic', 'produce');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('veggie_stirfry', 4, 'Ginger', 'produce');
INSERT INTO recipe_ingredients (recipe_slug, line_no, name, category) VALUES ('veggie_stirfry', 5, 'Canola Oil', 'oil');

COMMIT;
