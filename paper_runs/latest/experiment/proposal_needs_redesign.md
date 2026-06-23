# Proposal Needs Redesign

Reason: Proposal says this experiment requires a new specialized runner.

Original proposal:

RESEARCH QUESTION:
To what extent do different candy types commonly distributed at Halloween (chocolate, gummy/sticky candies, hard candies, sour candies) differ in their predicted cariogenic and erosive potential based on computational modeling of sugar release kinetics, oral retention time, and acidogenic pH profiles?

HYPOTHESIS:
Gummy/sticky candies will exhibit the highest predicted cariogenic potential due to prolonged oral retention time and sustained sugar release, followed by sour candies (which combine high sugar content with exogenous acids that directly lower oral pH), hard candies (prolonged dissolution but lower adhesiveness), and chocolate (rapid clearance due to fat-mediated oral clearance and lower retention on tooth surfaces). The ranking from highest to lowest cariogenic risk is predicted to be: gummy/sticky > sour > hard > chocolate.

EXPERIMENT DESIGN:
This experiment constructs a computational cariogenicity simulation model that integrates publicly available candy nutritional composition data with established oral physiology parameters to predict and compare the cariogenic and erosive potential of four Halloween candy categories. The design proceeds in four phases.

Phase 1 — Data Compilation: A structured dataset of candy products is assembled from USDA FoodData Central and Open Food Facts. Each product is categorized into one of four candy types (chocolate, gummy/sticky, hard candy, sour candy) based on product name, description, and ingredient list. For each product, the following nutritional features are extracted: total sugars (g per 100g), sucrose/glucose/fructose composition where available, total fat, protein, moisture content, and carbohydrate type. A minimum of 15 products per category (60+ total) is targeted to enable meaningful between-group comparisons.

Phase 2 — Parameter Assignment: Each candy type is assigned physical property parameters derived from published food science and dental literature. These include: dissolution rate constant (k_diss, min^-1), adhesiveness index (dimensionless, 0-1 scale), oral retention time estimate (minutes), and initial sugar bolus release fraction. Chocolate is assigned parameters reflecting rapid melting at oral temperature (37 degrees C) and fat-mediated clearance (Bhattacharyya & Joshi, 2022). Gummy/sticky candies receive high adhesiveness and slow dissolution parameters. Hard candies receive slow dissolution but low adhesiveness. Sour candies receive moderate dissolution parameters plus an initial acid bolus representing exogenous organic acids (citric, malic, tartaric).

Phase 3 — Computational Simulation: For each candy product, a numerical simulation models three coupled processes over a 60-minute post-consumption window at 1-minute resolution: (a) sugar release kinetics, modeled as a first-order dissolution process modulated by candy matrix properties and adhesiveness; (b) oral sugar concentration over time, accounting for salivary clearance (unstimulated flow rate approximately 0.3 mL/min, stimulated approximately 1.5 mL/min); and (c) plaque pH dynamics using a modified Stephan curve model that converts available sugar concentration to acid production via bacterial fermentation kinetics (Michaelis-Menten-type), buffered by salivary bicarbonate. The critical demineralization threshold is set at pH 5.5 for enamel.

Phase 4 — Metric Computation and Comparison: For each candy product, four cariogenicity metrics are computed from the simulated pH-time curve: (1) Time below critical pH (minutes where pH < 5.5), (2) Area under the pH deficit curve (integral of [5.5 - pH] over time when pH < 5.5), (3) Minimum pH reached (nadir), and (4) Cumulative acid exposure index (time-weighted average of hydrogen ion concentration above baseline). An erosive potential index is additionally computed for sour candies incorporating the exogenous acid contribution. Between-group differences across the four candy types are tested using one-way ANOVA with post-hoc Tukey HSD tests for each metric, with significance set at alpha = 0.05. Effect sizes are reported as Cohen's d for pairwise comparisons.

PUBLIC DATA SOURCES:
- USDA FoodData Central (https://fdc.nal.usda.gov/): A comprehensive U.S. government nutritional database containing detailed nutrient profiles for thousands of food products including branded and generic candy items. Provides total sugars, sugar subtypes, fat, protein, moisture, and carbohydrate data. CONFIRMED — this is a well-established public government database with API and bulk download access.
- Open Food Facts (https://world.openfoodfacts.org/): A collaborative open food product database with nutritional information for hundreds of thousands of products worldwide, including many branded Halloween candy items. Provides downloadable CSV exports and an API. CONFIRMED — well-established open database with direct data file availability.
- Published oral physiology parameters (salivary flow rates, Stephan curve parameters, critical pH thresholds, bacterial fermentation kinetics): Standard values from the dental caries literature (e.g., unstimulated salivary flow approximately 0.3 mL/min, stimulated approximately 1.5 mL/min, critical enamel pH approximately 5.5, plaque pH recovery time constants). TO_VERIFY — the Experiment Agent must compile specific parameter values from dental caries textbooks and review articles available through PubMed or open-access sources.
- Candy physical property parameters (dissolution rates, adhesiveness indices, melting behavior): Derived from food science literature including rheological characterization of chocolate (Bhattacharyya & Joshi, 2022) and general confectionery science. TO_VERIFY — specific numerical parameter values for each candy type under oral-simulated conditions must be compiled or estimated from food science literature; the literature review found only tangentially relevant data from chocolate rheology studies conducted under non-oral conditions.

DATA COLLECTION PLAN:
The Experiment Agent should proceed as follows:

Step 1 — USDA FoodData Central: Access the USDA FoodData Central API (https://api.nal.usda.gov/fdc/v1/) or download the bulk CSV datasets from https://fdc.nal.usda.gov/download-datasets.html. Search for candy products using keywords: "chocolate candy," "gummy candy," "hard candy," "sour candy," "caramel," "jelly bean," "lollipop," "candy bar," "Halloween candy." Filter results to retain products with complete sugar and macronutrient data. Assign each product to one of four candy type categories.

Step 2 — Open Food Facts: Download the product CSV from https://world.openfoodfacts.org/data/en.openfoodfacts.org.products.csv (large file, approximately 3GB) or use the API to query for candy products. Filter by categories_tags containing "candies," "chocolates," "gummies," etc. Extract nutritional values per 100g. Cross-reference with USDA data where possible.

Step 3 — Parameter Compilation: Search PubMed and Google Scholar for published values on: (a) oral retention time of different candy types, (b) dissolution rates of confections under simulated oral conditions, (c) Stephan curve parameters, (d) salivary clearance rates. Compile a parameter table with point estimates and plausible ranges for sensitivity analysis.

Step 4 — Dataset Construction: Merge nutritional data with candy type assignments and physical property parameters into a single analysis-ready CSV file with columns: product_name, candy_type, total_sugars_g, sucrose_fraction, fat_g, protein_g, moisture_g, dissolution_rate, adhesiveness_index, estimated_retention_min, acid_content (for sour candies).

METHODOLOGY:
Computational Model: A system of ordinary differential equations (ODEs) or a discrete-time numerical simulation models the oral environment post-candy consumption. The model includes three coupled components:

(a) Sugar Release Module: S(t) = S_0 * (1 - exp(-k_diss * t)) * (1 - A * exp(-k_clear * t)), where S_0 is total available sugar, k_diss is the candy-type-specific dissolution rate, A is the adhesiveness-modulated retention factor, and k_clear is the salivary clearance rate.

(b) Oral Sugar Concentration Module: C(t) = S(t) / V_saliva(t), where V_saliva(t) accounts for stimulated salivary volume accumulation over time.

(c) pH Dynamics Module: pH(t) = pH_resting - delta_pH_max * [C(t) / (K_m + C(t))] + recovery(t), where pH_resting is approximately 6.8, delta_pH_max is the maximum achievable pH drop, K_m is the Michaelis-Menten half-saturation constant for bacterial sugar fermentation, and recovery(t) models bicarbonate buffering with an exponential return toward resting pH.

Baselines: The primary baseline is a simple reference model that assigns fixed cariogenicity scores based solely on total sugar content (linear sugar-cariogenicity assumption), without accounting for candy matrix effects, retention time, or acid content. A second baseline uses only candy type category with literature-derived average risk scores.

Validation Scheme: Since no ground-truth clinical cariogenicity dataset exists for these specific candy categories, validation proceeds through: (1) internal consistency checks (e.g., higher sugar products within a category should yield equal or higher cariogenicity scores), (2) face validity against known dental health guidance (e.g., sticky candies are widely recommended against by dental associations), (3) sensitivity analysis varying key parameters (dissolution rate, adhesiveness, salivary flow) across plausible ranges to assess robustness, and (4) comparison of predicted rankings against any available in vitro or in vivo cariogenicity data from the broader dental literature (TO_VERIFY).

Statistical Tests: One-way ANOVA comparing the four candy types on each of the four cariogenicity metrics, followed by Tukey HSD post-hoc pairwise comparisons. Kruskal-Wallis test as a non-parametric alternative if normality assumptions are violated. Cohen's d effect sizes for all pairwise comparisons. Bonferroni correction for multiple comparisons across four metrics.

KEY VARIABLES:
- Independent variables: Candy type (categorical: chocolate, gummy/sticky, hard, sour); total sugar content (continuous, g per serving); candy matrix properties (dissolution rate, adhesiveness index, moisture content)
- Dependent variables: Time below critical pH 5.5 (minutes); area under pH deficit curve (pH-minutes); minimum pH nadir; cumulative acid exposure index; erosive potential index (for sour candies)
- Control variables: Salivary flow rate (held constant at population-average values for base case, varied in sensitivity analysis); oral temperature (37 degrees C); serving size (standardized to typical single-piece or single-serving mass per candy type); resting plaque pH (6.8); bacterial fermentation parameters (K_m, V_max from literature); simulation duration (60 minutes)

SUCCESS CRITERIA:
- The computational model produces distinct, statistically significant (p < 0.05) differences in at least 3 of 4 cariogenicity metrics across the four candy types.
- The predicted cariogenicity ranking is consistent with established dental health guidance: gummy/sticky candies rank highest in cariogenic potential, and chocolate ranks lowest or near-lowest.
- Sensitivity analysis demonstrates that the ranking is robust across at least 80% of plausible parameter variations (i.e., the rank order does not invert when key parameters are varied within their reported ranges).
- The model produces physiologically plausible pH curves (minimum pH between 4.0 and 6.5, recovery to near-resting pH within 30-60 minutes) consistent with published Stephan curve observations.

FEASIBILITY CHECK:
This experiment is feasible using only public data and computational methods. The USDA FoodData Central and Open Food Facts databases are well-established, freely accessible, and contain nutritional data for hundreds of candy products. The computational simulation requires only standard scientific Python libraries (NumPy, SciPy, pandas, matplotlib) and does not require specialized hardware or large-scale compute. The model parameters can be compiled from published oral physiology and food science literature available through PubMed and open-access journals. No human subjects, clinical data, proprietary datasets, or credentialed APIs are required.

Key verification needs before execution: (1) The Experiment Agent must verify that USDA FoodData Central contains sufficient candy products with complete nutritional data across all four categories (at least 15 per category). If one category is underrepresented, Open Food Facts should supplement. (2) The specific ODE parameter values (K_m for bacterial fermentation, salivary clearance constants, adhesiveness indices) must be compiled from dental and food science literature — these were not available in the deep literature review and are marked TO_VERIFY. (3) The candy type categorization scheme must be validated by inspecting actual product listings in the databases.

LIMITATIONS AND RISKS:
- The model is a computational simulation and does not capture the full complexity of in vivo oral conditions, including individual variation in salivary composition, oral microbiome differences, tooth surface topography, and eating behavior (chewing vs. sucking).
- Physical property parameters (dissolution rates, adhesiveness) for candy types under oral conditions are not well-characterized in the retrieved literature and may require estimation from indirect sources or expert judgment, introducing uncertainty.
- The model assumes a single consumption event and does not account for repeated candy consumption over time (as occurs during Halloween), which would compound acid exposure.
- No ground-truth clinical dataset linking specific candy types to caries incidence was found in the literature review, limiting the ability to validate absolute cariogenicity predictions. Validation is restricted to face validity and consistency with known dental guidance.
- The nutritional databases may lack detailed sugar subtype composition (sucrose vs. glucose vs. fructose fractions) for many branded candy products, requiring estimation from generic ingredient lists.
- Sour candy erosive potential depends on specific organic acid types and concentrations (citric, malic, tartaric), which are rarely reported in nutritional databases and may need to be estimated from ingredient lists or food science literature.

EXPERIMENT EXECUTION SPEC:
{
  "runner_type": "NEEDS_NEW_RUNNER",
  "task_type": "inspect",
  "dataset_url": "TO_VERIFY",
  "dataset_urls": [
    "https://world.openfoodfacts.org/data/en.openfoodfacts.org.products.csv",
    "https://fdc.nal.usda.gov/download-datasets.html"
  ],
  "dataset_name": "Halloween Candy Cariogenicity Dataset (to be constructed from USDA FoodData Central and Open Food Facts)",
  "target_column": "TO_VERIFY",
  "feature_columns": ["candy_type", "total_sugars_g", "fat_g", "protein_g", "moisture_g", "dissolution_rate", "adhesiveness_index", "estimated_retention_min"],
  "baseline": "sugar_linear_baseline",
  "success_metric": "custom_cariogenicity_metrics",
  "success_threshold": 0.0,
  "threshold_direction": "greater_or_equal",
  "notes_for_experiment_agent": "This experiment requires a custom runner because it is a computational simulation study, not a standard ML classification or regression task. The Experiment Agent must: (1) Download candy product nutritional data from USDA FoodData Central API (https://api.nal.usda.gov/fdc/v1/ with free API key from https://fdc.nal.usda.gov/api-guide.html) and/or Open Food Facts CSV. (2) Filter and categorize products into four candy types: chocolate, gummy_sticky, hard, sour. (3) Compile oral physiology parameters from dental literature (salivary flow rates, Stephan curve constants, critical pH 5.5, bacterial fermentation K_m and V_max). (4) Implement a numerical simulation (discrete-time or ODE-based using scipy.integrate) modeling sugar release kinetics, oral sugar concentration, and plaque pH dynamics over a 60-minute window at 1-minute resolution for each candy product. (5) Compute four cariogenicity metrics from simulated pH-time curves: time_below_pH5.5, AUC_pH_deficit, pH_nadir, cumulative_acid_exposure. (6) Perform one-way ANOVA with Tukey HSD post-hoc tests comparing four candy types on each metric. (7) Run sensitivity analysis varying key parameters across plausible ranges. (8) Output: ranked cariogenicity scores by candy type, statistical test results, pH-time curve plots for representative products from each category, and sensitivity analysis results. Required Python packages: numpy, scipy, pandas, matplotlib, statsmodels. No GPU or large-scale compute required."
}
