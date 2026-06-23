RESEARCH QUESTION:
Under what market conditions does NLP-based sentiment analysis provide statistically significant incremental predictive power for US equity returns beyond what is achievable using pure time-series deep learning models on OHLCV data alone?

HYPOTHESIS:
NLP-based sentiment features provide statistically significant incremental predictive power for next-day US equity returns beyond a pure OHLCV deep learning baseline primarily during high-volatility regimes and periods of elevated news flow, while offering no significant improvement during low-volatility, trending market conditions where price-volume dynamics already capture the dominant return-predictive signal.

EXPERIMENT DESIGN:
The experiment follows a controlled, two-stage comparative design. In Stage 1, a time-series deep learning baseline (LSTM and Transformer architectures) is trained exclusively on daily OHLCV (Open, High, Low, Close, Volume) data for a universe of US large-cap equities to predict next-day directional returns. In Stage 2, NLP-derived sentiment features — extracted from financial news headlines using a pre-trained FinBERT model — are appended as additional input features to the identical architecture, and predictive performance is compared out-of-sample. The comparison is then stratified by market regime (high-volatility vs. low-volatility, trending vs. mean-reverting, crisis vs. calm periods), with regimes classified using rolling realized volatility of the S&P 500 and the CBOE VIX index level. Statistical significance of the incremental predictive power is assessed using the Diebold-Mariano test for equal predictive accuracy applied to out-of-sample forecast errors within each regime. Walk-forward expanding-window validation is used throughout to prevent look-ahead bias. The experiment covers the period from January 2018 through December 2024 to encompass diverse market conditions including the 2020 pandemic crash, the 2022 bear market, and multiple bull-market phases.

PUBLIC DATA SOURCES:
- **Yahoo Finance OHLCV daily data (via yfinance)**: Daily Open, High, Low, Close, and Adjusted Close prices plus trading volume for US equities. This is the foundational price-volume dataset for both the baseline and augmented models. Relevant for constructing OHLCV feature matrices and computing next-day returns as the target variable. Status: TO_VERIFY — yfinance is a widely used public Python library providing free access to Yahoo Finance data; the Experiment Agent must verify data availability, completeness, and any rate-limiting constraints for the target universe and date range.

- **Financial PhraseBank (Malo et al., 2014)**: A publicly available dataset of 4,840 English-language financial news sentences annotated by 16 human annotators with sentiment labels (positive, negative, neutral) at multiple agreement thresholds. Hosted on the UCI Machine Learning Repository and also available via Hugging Face Datasets (takala/financial_phrasebank). This dataset provides labeled training data for calibrating or validating the financial sentiment extraction pipeline. Status: TO_VERIFY — the Experiment Agent must verify the exact download URL, file format, license (CC BY-NC-SA 3.0), and schema before use.

- **FinBERT pre-trained model (Araci, 2019)**: A BERT-based model pre-trained on a large financial domain corpus and fine-tuned for financial sentiment classification, available on Hugging Face (ProsusAI/finbert). This model serves as the primary NLP sentiment extraction pipeline, converting financial news headlines into numerical sentiment scores (positive, negative, neutral probabilities). Status: TO_VERIFY — the Experiment Agent must verify model availability, license (Apache 2.0), and inference requirements on Hugging Face before execution.

- **All-the-News dataset (Kaggle)**: A publicly available dataset on Kaggle containing approximately 1.4 million news articles from major US publications (including Reuters, Bloomberg, CNBC, and others) spanning 2015-2020+. This provides the raw text corpus from which daily sentiment features are extracted and temporally aligned with OHLCV data. Status: TO_VERIFY — the Experiment Agent must verify the exact Kaggle dataset URL, file format, date range coverage, license, and whether the dataset includes publication timestamps sufficient for daily alignment with market data.

- **FRED (Federal Reserve Economic Data) VIX and macro indicators**: The CBOE VIX index (ticker VIXCLS) and related macro-financial indicators are available as daily CSV files from the FRED public API (https://fred.stlouisfed.org/). The VIX is used as a primary market regime classifier (high-volatility vs. low-volatility). Status: TO_VERIFY — the Experiment Agent must verify API access or direct CSV download availability for the VIX series covering 2018-2024.

- **S&P 500 index OHLCV data (via yfinance, ticker ^GSPC)**: Used to compute market-level features including rolling realized volatility for regime classification. Same source and verification status as the equity OHLCV data above.

DATA COLLECTION PLAN:
The Experiment Agent should execute the following data collection pipeline:

1. **OHLCV Data**: Use the Python yfinance library to download daily OHLCV data for a selected universe of 30-50 S&P 500 constituent stocks (or the full S&P 500 if computationally feasible) covering January 2015 through December 2024. The extra lead time (2015-2017) provides warm-up data for computing lagged features and rolling statistics. Store as per-ticker CSV files with columns: Date, Open, High, Low, Close, Adj Close, Volume.

2. **Financial News Headlines**: Download the All-the-News dataset from Kaggle (requires a free Kaggle account and API key, or manual download). Filter articles to those published on trading days and relevant to the target equity universe. Extract headline text and publication date. If All-the-News proves insufficient in date range or coverage, supplement with the Reuters TR News dataset or the publicly available portion of the DJIA headline dataset from Kaggle (https://www.kaggle.com/datasets/aaron7sun/stocknews), which contains combined Reddit and news headlines aligned with Dow Jones stock movements from 2008-2016. The Experiment Agent must verify which headline dataset provides the best temporal coverage and alignment.

3. **Sentiment Feature Extraction**: Apply the FinBERT model (ProsusAI/finbert from Hugging Face) to each headline to produce per-headline sentiment scores (positive, negative, neutral probabilities). Aggregate daily sentiment per stock by computing the mean, standard deviation, and count of sentiment scores for all headlines mentioning that stock on each trading day. This produces a daily sentiment feature table aligned with the OHLCV data.

4. **Market Regime Indicators**: Download the VIX daily close from FRED (series VIXCLS) as a CSV file. Compute rolling 20-day realized volatility of the S&P 500 from the downloaded ^GSPC OHLCV data. Classify each trading day into regimes: high-volatility (VIX above 75th percentile or realized volatility above median) vs. low-volatility, and trending (absolute 20-day return above median) vs. mean-reverting.

5. **Feature Engineering**: Construct the OHLCV feature matrix including: daily log returns, 5-day and 20-day rolling returns, RSI (14-day), MACD, Bollinger Band width, volume change ratios, and day-of-week indicators. For the augmented model, append the aggregated daily sentiment features (mean positive score, mean negative score, sentiment disagreement, headline count).

METHODOLOGY:

**Models**:
- Baseline Model (OHLCV-only): An LSTM network with 2 layers (64 and 32 hidden units) taking a 20-day lookback window of OHLCV-derived features as input, outputting a predicted next-day log return. A Transformer-based variant (2-layer, 4-head temporal Transformer) is also trained as a second baseline for robustness.
- Augmented Model (OHLCV + Sentiment): The identical LSTM/Transformer architecture with sentiment features concatenated to the OHLCV feature vector at each time step.
- Sentiment-only Model: The same architecture trained on sentiment features alone, to isolate the standalone predictive contribution of sentiment.

**Baselines**:
- Naive baseline: Predict next-day return as today's return (random walk).
- Majority-class baseline: For the classification variant (directional return), predict the historical majority class.
- Mean-prediction baseline: For the regression variant, predict the historical mean return.

**Training and Validation**:
- Walk-forward expanding-window validation: Train on all data up to time T, validate on T+1 through T+60 (approximately 3 months), then expand the training window by 60 days and repeat. This prevents look-ahead bias and simulates real-world deployment.
- The first training window covers January 2015 through December 2017 (3 years). Testing spans January 2018 through December 2024 (7 years), yielding approximately 14 walk-forward folds.

**Market Regime Stratification**:
- After obtaining out-of-sample predictions from all folds, partition test-set predictions by the market regime label active on each test day.
- Compute predictive performance metrics separately within each regime.

**Statistical Tests**:
- Diebold-Mariano (DM) test applied to paired out-of-sample forecast errors (baseline vs. augmented) within each regime to test whether the difference in predictive accuracy is statistically significant at the 5% level.
- Newey-West adjusted standard errors to account for serial correlation in forecast errors.
- Bonferroni correction applied across multiple regime comparisons to control family-wise error rate.

**Performance Metrics**:
- Regression: Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), R-squared, Information Coefficient (rank correlation between predicted and actual returns).
- Classification (directional): Accuracy, Precision, Recall, F1-score, Area Under ROC Curve (AUC-ROC).
- Economic significance: Annualized Sharpe ratio of a simple long-short portfolio that goes long on stocks with the highest predicted returns and short on the lowest, computed separately per regime.

KEY VARIABLES:
- Independent variables: (1) OHLCV-derived technical features (daily returns, rolling returns, RSI, MACD, Bollinger Band width, volume ratios, day-of-week dummies); (2) NLP sentiment features (daily mean positive score, mean negative score, sentiment disagreement/standard deviation, headline count); (3) Market regime indicator (high-vol/low-vol, trending/mean-reverting, crisis/calm).
- Dependent variables: (1) Next-day log return of each stock (regression target); (2) Next-day directional return sign (classification target: 1 if positive, 0 if negative).
- Control variables: (1) Stock fixed effects (ticker identity); (2) Market capitalization tier; (3) Sector classification (GICS); (4) Day-of-week and month-of-year calendar effects; (5) Overall market return (S&P 500 daily return) to control for market-wide movements.

SUCCESS CRITERIA:
- The augmented model (OHLCV + Sentiment) achieves a statistically significant improvement over the OHLCV-only baseline as measured by the Diebold-Mariano test (p < 0.05) on out-of-sample forecast errors in at least one market regime.
- The incremental improvement is regime-dependent: the DM test rejects the null of equal predictive accuracy in high-volatility regimes but fails to reject in low-volatility regimes, supporting the hypothesis that sentiment adds value primarily during stressed market conditions.
- The augmented model achieves an out-of-sample Information Coefficient (rank correlation between predicted and actual returns) that is at least 10% higher than the baseline in high-volatility regimes.
- A simple long-short portfolio constructed from augmented model predictions achieves a Sharpe ratio at least 0.2 higher than the baseline portfolio in high-volatility regimes, after accounting for a 10 basis-point per-trade transaction cost assumption.

FEASIBILITY CHECK:
This experiment is feasible using only public data and open-source tools, with the following considerations:

1. **OHLCV data** is freely accessible via yfinance for any US-listed equity. No API key or payment is required, though rate limits may apply for large batch downloads. The Experiment Agent should implement retry logic and batched downloads.

2. **Financial news headlines** represent the primary feasibility risk. The All-the-News Kaggle dataset covers 2015-2020 and may not extend to 2024. The Experiment Agent must verify the actual date range and, if necessary, supplement with the DJIA headline dataset from Kaggle (aaron7sun/stocknews, covering 2008-2016) or construct a smaller-scale experiment covering only the overlapping date range. If no single public headline dataset covers 2018-2024 adequately, the experiment scope should be reduced to 2015-2020 using All-the-News, which still encompasses the 2020 pandemic crash as a high-volatility regime.

3. **FinBERT** is freely available on Hugging Face (ProsusAI/finbert) under Apache 2.0 license. Inference can be run on a single GPU or even CPU for headline-length text. The Experiment Agent must verify that the model loads correctly and produces valid sentiment outputs.

4. **VIX data** from FRED is freely downloadable as CSV without authentication.

5. **Compute requirements** are moderate: training LSTM/Transformer models on 30-50 stocks over 7 years of daily data with walk-forward validation is feasible on a single GPU (e.g., T4 or V100) within a few hours.

6. The Experiment Agent must verify all dataset licenses permit research use and must confirm file schemas match the expected column names before proceeding with feature engineering.

LIMITATIONS AND RISKS:
- **News headline coverage gap**: Public headline datasets may not cover the full 2018-2024 period. If the All-the-News dataset ends in 2020, the experiment cannot test sentiment value during the 2022 bear market or 2023-2024 AI-driven rally, limiting the diversity of market regimes examined. Mitigation: restrict the experiment to the available date range and clearly report the covered regimes.
- **Sentiment extraction quality**: FinBERT, while domain-adapted, may produce noisy sentiment scores on short headlines or sarcastic/ironic financial commentary. Misclassified sentiment attenuates the measured incremental value, potentially leading to a Type II error (failing to detect true incremental predictability). Mitigation: validate FinBERT outputs against the Financial PhraseBank labeled set and report inter-annotator agreement metrics.
- **Survivorship bias**: Using current S&P 500 constituents introduces survivorship bias, as delisted or demoted stocks are excluded. This may overstate predictive performance. Mitigation: acknowledge this limitation and, if feasible, use a fixed historical constituent list.
- **Causality vs. correlation**: The experiment measures predictive association, not causal impact of sentiment on returns. Observed incremental predictive power may reflect confounding variables (e.g., earnings announcement timing) rather than genuine sentiment-driven return predictability.
- **Transaction cost sensitivity**: The economic significance results depend on the assumed transaction cost level. Higher costs may eliminate the practical value of any incremental predictability, even if statistically significant.
- **Model architecture sensitivity**: Results may be sensitive to hyperparameter choices (lookback window, hidden units, learning rate). The Experiment Agent should conduct a limited hyperparameter sensitivity analysis or use a fixed, literature-standard configuration and report it transparently.
- **Multiple testing**: Testing across multiple regimes, stocks, and model variants inflates the risk of false positives. The Bonferroni correction partially addresses this but may be overly conservative.

EXPERIMENT EXECUTION SPEC:
{
  "runner_type": "NEEDS_NEW_RUNNER",
  "task_type": "regression",
  "dataset_url": "TO_VERIFY",
  "dataset_urls": [
    "TO_VERIFY",
    "https://www.kaggle.com/datasets/aaron7sun/stocknews",
    "https://huggingface.co/datasets/takala/financial_phrasebank",
    "https://fred.stlouisfed.org/series/VIXCLS"
  ],
  "dataset_name": "Multi-source: Yahoo Finance OHLCV + Kaggle financial news headlines + FinBERT sentiment + FRED VIX",
  "target_column": "next_day_log_return",
  "feature_columns": [
    "daily_log_return",
    "return_5d",
    "return_20d",
    "rsi_14",
    "macd",
    "bollinger_width",
    "volume_ratio",
    "day_of_week",
    "sentiment_pos_mean",
    "sentiment_neg_mean",
    "sentiment_disagreement",
    "headline_count"
  ],
  "baseline": "mean_prediction",
  "success_metric": "rmse",
  "success_threshold": 0.0,
  "threshold_direction": "less_or_equal",
  "notes_for_experiment_agent": "This experiment requires a custom runner because it involves: (1) downloading OHLCV data programmatically via yfinance for 30-50 US equity tickers; (2) downloading and parsing financial news headline datasets from Kaggle (aaron7sun/stocknews or All-the-News); (3) running FinBERT inference (ProsusAI/finbert from Hugging Face) on headlines to generate daily sentiment features; (4) downloading VIX data from FRED; (5) constructing aligned daily feature matrices by merging OHLCV features with aggregated sentiment features per stock per date; (6) training LSTM and Transformer time-series models with walk-forward expanding-window validation; (7) stratifying out-of-sample results by market regime (high-vol vs. low-vol based on VIX percentile); (8) running Diebold-Mariano statistical tests on paired forecast errors per regime. The Experiment Agent should first verify that yfinance returns complete OHLCV data for the target tickers and date range, then verify that the Kaggle headline dataset covers the needed period and contains parseable date and headline columns. FinBERT must be loaded from Hugging Face and validated against the Financial PhraseBank labeled set before applying it to the full headline corpus. The target variable is the next-day log return computed as log(Close_t+1 / Close_t). The experiment must use walk-forward validation with no look-ahead bias. Regime classification uses VIX above/below the 75th percentile of the training-period VIX distribution. Report Diebold-Mariano test statistics and p-values per regime as the primary result."
}
