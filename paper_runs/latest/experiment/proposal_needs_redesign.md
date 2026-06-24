# Proposal Needs Redesign

Reason: No CSV datasets could be loaded. Failures: https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/engineered/archive/capology_all_1617_2122_last_updated_05092021.csv: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1028)> | https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/engineered/archive/capology_big5_mls_1617_2122_last_updated_05092021.csv: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1028)> | https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/raw/bundesliga/2016-2017/all_bundesliga_2016-2017.csv: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1028)> | https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/raw/bundesliga/2016-2017/augsburg_bundesliga_2016-2017.csv: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1028)> | https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/raw/bundesliga/2016-2017/bayer-leverkusen_bundesliga_2016-2017.csv: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1028)>

Original proposal:

RESEARCH QUESTION:
Did Messi's 2022 FIFA World Cup victory produce a measurable increase in youth football registration rates across Argentina, as evidenced by publicly available enrollment data from the Argentine Football Association (AFA), provincial sports ministries, and municipal youth leagues?


HYPOTHESIS:
Argentina's victory in the 2022 FIFA World Cup (December 18, 2022) produced a statistically significant, positive structural break in youth football registration rates beginning in the first registration cycle following the victory (Q1 2023), but the effect is concentrated in the 6–12 age cohort, diminishes over subsequent registration cycles, and is more pronounced in provinces with lower baseline registration rates — consistent with an intensification-of-existing-interest mechanism rather than the creation of entirely new participation demand.

EXPERIMENT DESIGN:
The analysis must determine whether a detectable and statistically significant discontinuity in youth football registration trends exists at the point of Argentina's 2022 World Cup victory (December 2022), after controlling for pre-existing secular trends, seasonal registration cycles, demographic shifts, and concurrent economic or policy confounders. It must further characterize the temporal persistence, geographic distribution, and demographic specificity of any observed effect, and adjudicate between two competing interpretations: (a) a sustained structural increase in youth participation driven by victory-inspired engagement, versus (b) a transient spike that reverts to baseline within one to two registration cycles, as the broader mega-event legacy literature would predict (Moussi-Beylie, 2025).

PUBLIC DATA SOURCES:
- eddwebster/football_analytics: 📊⚽  A collection of football analytics projects, data, and analysis by Edd Webster (@eddwebster), including a curated list of publicly available resources published by the football analytics community. Direct files: https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/engineered/archive/capology_all_1617_2122_last_updated_05092021.csv, https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/engineered/archive/capology_big5_mls_1617_2122_last_updated_05092021.csv, https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/raw/bundesliga/2016-2017/all_bundesliga_2016-2017.csv, https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/raw/bundesliga/2016-2017/augsburg_bundesliga_2016-2017.csv, https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/raw/bundesliga/2016-2017/bayer-leverkusen_bundesliga_2016-2017.csv.
- rhit-calviem/Fifa_World_Cup_analysis: Readable public data files were found. Direct files: https://raw.githubusercontent.com/rhit-calviem/Fifa_World_Cup_analysis/main/data/WorldCupMerged.csv, https://raw.githubusercontent.com/rhit-calviem/Fifa_World_Cup_analysis/main/data/final_result.csv, https://raw.githubusercontent.com/rhit-calviem/Fifa_World_Cup_analysis/main/data/goalscorers.csv, https://raw.githubusercontent.com/rhit-calviem/Fifa_World_Cup_analysis/main/data/merged.csv, https://raw.githubusercontent.com/rhit-calviem/Fifa_World_Cup_analysis/main/data/results.csv.
- juanepstein99/MessiEvolution: Readable public data files were found. Direct files: https://raw.githubusercontent.com/juanepstein99/MessiEvolution/main/messi.csv, https://raw.githubusercontent.com/juanepstein99/MessiEvolution/main/messi_headlines.csv.
- Jeffreyjose29/FIFAWorldCupSimulation: Readable public data files were found. Direct files: https://raw.githubusercontent.com/Jeffreyjose29/FIFAWorldCupSimulation/main/Data/Federations.csv, https://raw.githubusercontent.com/Jeffreyjose29/FIFAWorldCupSimulation/main/Data/IntlMatches.csv, https://raw.githubusercontent.com/Jeffreyjose29/FIFAWorldCupSimulation/main/Data/Knockouts.csv, https://raw.githubusercontent.com/Jeffreyjose29/FIFAWorldCupSimulation/main/Data/R16.csv, https://raw.githubusercontent.com/Jeffreyjose29/FIFAWorldCupSimulation/main/Data/ShootOuts.csv.
- julianmancuello/FIFA_World_Cup_2022: Power BI, Jupyter Notebook and Pandas Direct files: https://raw.githubusercontent.com/julianmancuello/FIFA_World_Cup_2022/main/FIFA_dataset/Fifa_world_cup_matches.csv, https://raw.githubusercontent.com/julianmancuello/FIFA_World_Cup_2022/main/FIFA_dataset/Fifa_world_cup_matches_v1.csv, https://raw.githubusercontent.com/julianmancuello/FIFA_World_Cup_2022/main/FBref_matchs/data.csv, https://raw.githubusercontent.com/julianmancuello/FIFA_World_Cup_2022/main/Teams.csv, https://raw.githubusercontent.com/julianmancuello/FIFA_World_Cup_2022/main/WorldCup2022.csv.

DATA COLLECTION PLAN:
The Dataset Agent searched for readable public files and discarded repositories, pages, model artifacts, config files, and unreadable URLs. The Schema Agent inspected the selected direct files when possible. The Experiment Agent should use only the direct dataset URLs in the execution spec.

METHODOLOGY:
Use the selected public data files, schema-inspected target candidates, and the runner specified in EXPERIMENT EXECUTION SPEC. If the target column is AUTO_TARGET or TO_VERIFY, the Experiment Agent may infer a target from loaded tabular data and report that inference in the results.

KEY VARIABLES:
- **Independent variables**:
  - Binary intervention indicator (post-December 2022 = 1, pre = 0) representing the World Cup victory event
  - Time-since-intervention variable (continuous, in months or quarters) to capture decay or persistence of any effect
  - Interaction terms between the intervention indicator and province-level characteristics (baseline registration rate, urbanization level, economic indicators)

- **Dependent variables**:
  - Youth football registration count per registration cycle (monthly or quarterly), by province, age cohort, and gender
  - Youth football registration rate per 1,000 youth-age population, by province (normalizing for demographic changes)

- **Control variables**:
  - Pre-existing secular trend in youth registrations (continuous time variable)
  - Seasonal indicators (quarter or month fixed effects) to account for cyclical registration patterns
  - Provincial youth population size (ages 5–18) as an exposure offset
  - Provincial economic conditions (GDP per capita or unemployment rate, lagged one period)
  - Binary indicators for any concurrent AFA or government youth sport policy changes during the study window
  - Province fixed effects to absorb time-invariant provincial heterogeneity

SUCCESS CRITERIA:
- **Primary criterion**: The ITS model identifies a statistically significant positive level-change coefficient (p < 0.05) at the December 2022 intervention point in the aggregate national youth registration series, after adjusting for trend, seasonality, and confounders — indicating an immediate post-victory registration increase beyond what the pre-existing trajectory would predict.
- **Persistence criterion**: The slope-change coefficient in the post-intervention period is tested to distinguish between a sustained structural shift (significant positive slope change persisting through at least four post-intervention quarters) and a transient spike (significant level change followed by a significant negative slope change returning toward baseline within two to three quarters), with the latter outcome being more consistent with the mega-event legacy skepticism documented by (Moussi-Beylie, 2025).
- **Demographic specificity criterion**: The effect is significantly larger in the youngest age cohort (5–8 or 6–12) than in older adolescent cohorts (13–18), supporting the hypothesis that the victory primarily influenced parental enrollment decisions for young children rather than self-initiated participation by older youth.
- **Geographic heterogeneity criterion**: Provinces with lower pre-victory baseline registration rates exhibit larger relative increases, suggesting the victory activated latent demand in under-participating regions rather than merely amplifying already-saturated markets.
- **Robustness criterion**: The finding holds across at least two independent data sources (e.g., AFA registrations and provincial sports ministry records), reducing the likelihood that observed effects are artifacts of a single administrative system's reporting changes.
- **Null result interpretation**: If no significant level or slope change is detected, this constitutes meaningful evidence that even in a football-saturated culture, a World Cup victory does not translate into measurable grassroots participation increases — a finding that directly extends the critical framework of (Moussi-Beylie, 2025) and challenges the "Podium to Profit" causal pathway proposed by (Chankuna, 2025).

FEASIBILITY CHECK:
The analysis is feasible only to the extent that the listed direct files are readable and contain columns relevant to the hypothesis. If the execution spec uses NEEDS_NEW_RUNNER, the current Experiment Agent should inspect any readable files and report why the full analysis cannot run.

LIMITATIONS AND RISKS:
- Dataset search may miss sources that require credentials or manual download.
- Schema inference can select an imperfect target column when metadata is weak.
- A simple baseline runner cannot replace custom feature engineering, scraping, deep learning, causal inference, or multimodal processing.

EXPERIMENT EXECUTION SPEC:
{
  "runner_type": "universal_tabular_csv",
  "task_type": "auto",
  "dataset_url": "https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/engineered/archive/capology_all_1617_2122_last_updated_05092021.csv",
  "dataset_urls": [
    "https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/engineered/archive/capology_all_1617_2122_last_updated_05092021.csv",
    "https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/engineered/archive/capology_big5_mls_1617_2122_last_updated_05092021.csv",
    "https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/raw/bundesliga/2016-2017/all_bundesliga_2016-2017.csv",
    "https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/raw/bundesliga/2016-2017/augsburg_bundesliga_2016-2017.csv",
    "https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/capology/raw/bundesliga/2016-2017/bayer-leverkusen_bundesliga_2016-2017.csv"
  ],
  "dataset_name": "Direct public data file candidate",
  "target_column": "AUTO_TARGET",
  "feature_columns": [
    "AUTO_NUMERIC"
  ],
  "baseline": "majority_class for classification or mean_prediction for regression",
  "success_metric": "accuracy",
  "success_threshold": 0.0,
  "threshold_direction": "greater_or_equal",
  "notes_for_experiment_agent": "Direct data file candidates were found by the Proposal stage. The Experiment Agent should load the files, inspect schema, and use the selected broad runner."
}
