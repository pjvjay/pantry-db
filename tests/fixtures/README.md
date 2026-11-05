# Test fixtures for scripts/cnf-subset.py

Every food, value and measure in these files is **invented**. They exist only
to test how the script reads a download and what it refuses; none of them is
nutrition data.

- `cnf_mini/` uses the Canadian Nutrient File's CSV file and header names
  (FOOD NAME, NUTRIENT NAME, NUTRIENT AMOUNT, CONVERSION FACTOR, MEASURE
  NAME). The names were written from the CNF 2015 documentation as
  remembered, not copied from a download, which has not been approved.
  `FOOD NAME.csv` is cp1252 on purpose, to exercise the encoding fallback, and
  `NUTRIENT NAME.csv` lists the kJ energy row before the kcal one and gives
  each nutrient a NutrientID unlike its code, so the script must choose by
  unit and by code.
- `fdc_mini/` uses FoodData Central's CSV names (food, nutrient,
  food_nutrient). Its three foods carry energy as nutrient 2047, 2048 and
  1008 in different combinations, to test the order of preference.
- `picks.json` in each folder is the picks file the tests build from.
