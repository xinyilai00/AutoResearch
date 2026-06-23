# Experiment Results

## Status
REDESIGN_NEEDED

## Hypothesis Supported
UNDETERMINED

## Summary
Experiment was not executed: Proposal says this experiment requires a new specialized runner.

## Dataset
- Name: Halloween Candy Cariogenicity Dataset (to be constructed from USDA FoodData Central and Open Food Facts)
- URL/path: https://world.openfoodfacts.org/data/en.openfoodfacts.org.products.csv, https://fdc.nal.usda.gov/download-datasets.html
- Target column: TO_VERIFY

## Method
- Runner type: NEEDS_NEW_RUNNER
- Task type: inspect
- Baseline: sugar_linear_baseline

## Metrics

## Results

## Limitations
- No empirical results were generated.
- The current Experiment Agent can execute universal_tabular_csv and universal_data_file specs only.
- Runner notes: This experiment requires a custom runner because it is a computational simulation study, not a standard ML classification or regression task. The Experiment Agent must: (1) Download candy product nutritional data from USDA FoodData Central API (https://api.nal.usda.gov/fdc/v1/ with free API key from https://fdc.nal.usda.gov/api-guide.html) and/or Open Food Facts CSV. (2) Filter and categorize products into four candy types: chocolate, gummy_sticky, hard, sour. (3) Compile oral physiology parameters from dental literature (salivary flow rates, Stephan curve constants, critical pH 5.5, bacterial fermentation K_m and V_max). (4) Implement a numerical simulation (discrete-time or ODE-based using scipy.integrate) modeling sugar release kinetics, oral sugar concentration, and plaque pH dynamics over a 60-minute window at 1-minute resolution for each candy product. (5) Compute four cariogenicity metrics from simulated pH-time curves: time_below_pH5.5, AUC_pH_deficit, pH_nadir, cumulative_acid_exposure. (6) Perform one-way ANOVA with Tukey HSD post-hoc tests comparing four candy types on each metric. (7) Run sensitivity analysis varying key parameters across plausible ranges. (8) Output: ranked cariogenicity scores by candy type, statistical test results, pH-time curve plots for representative products from each category, and sensitivity analysis results. Required Python packages: numpy, scipy, pandas, matplotlib, statsmodels. No GPU or large-scale compute required.

## Output Files
