import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import FeedbackBar from "../components/FeedbackBar.jsx";

async function mockRunProposalAgent(deepLitOutput, feedback, onChunk) {
  const fakeOutput = `HYPOTHESIS:
Combining HRV, sleep quality, and activity metrics in a multivariate LSTM model will predict next-day athletic performance decrements with greater accuracy (AUC > 0.80) than any single-metric baseline model when evaluated using within-subject cross-validation.

RATIONALE:
Prior literature consistently shows multivariate models outperform single-metric approaches by 12-18%. However, no study has applied within-subject cross-validation to properly account for individual athlete variability. This experiment directly addresses that gap using the publicly available PMDATA dataset.

EXPERIMENT DESIGN:
The experiment will use the PMDATA dataset containing 16 athletes monitored over 5 months with daily wearable sensor readings and self-reported wellness scores. Data will be preprocessed to extract three feature streams: HRV metrics, sleep quality scores, and daily activity levels.

Four models will be trained and compared: (1) HRV-only LSTM baseline, (2) sleep-only LSTM baseline, (3) activity-only LSTM baseline, and (4) multivariate LSTM combining all three streams. Each model will be evaluated using leave-one-athlete-out cross-validation to ensure individual-level generalizability.

Performance will be measured using AUC, F1 score, and precision-recall curves. Statistical significance of differences between models will be assessed using paired t-tests with Bonferroni correction.

KEY VARIABLES:
- Independent: HRV metrics, sleep quality scores, daily activity levels
- Dependent: Next-day performance decrement (binary classification)
- Controlled: Dataset, evaluation protocol, model architecture, training epochs

DATASETS:
- PMDATA: Primary dataset for training and evaluation
- LifeSnaps: Secondary dataset for transfer learning validation

METHODOLOGY:
- LSTM Networks: Primary model architecture for sequential wearable data
- Random Forest: Baseline comparison model for feature importance validation
- Within-subject cross-validation: Evaluation protocol to test individual-level prediction

SUCCESS CRITERIA:
- Multivariate LSTM achieves AUC > 0.80 on within-subject evaluation
- Multivariate model statistically outperforms all single-metric baselines (p < 0.05)
- Results replicate across at least 12 of 16 athletes in the dataset

POTENTIAL FAILURE MODES:
- Insufficient data per athlete: Mitigation — apply data augmentation techniques
- Class imbalance in performance decrements: Mitigation — use SMOTE oversampling
- Overfitting to individual athletes: Mitigation — strict train/test separation per fold
${feedback ? `\n\nRefined based on feedback: "${feedback}"` : ""}`;

  const words = fakeOutput.split(" ");
  for (const word of words) {
    await new Promise((resolve) => setTimeout(resolve, 50));
    onChunk(word + " ");
  }
}

export default function ProposalPage({ autonomous, deepLitOutput, onComplete }) {
  const navigate = useNavigate();
  const [output, setOutput] = useState("");
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);

  async function handleRun(feedback = null) {
    setOutput("");
    setDone(false);
    setRunning(true);

    let fullOutput = "";
    await mockRunProposalAgent(deepLitOutput, feedback, (chunk) => {
      fullOutput += chunk;
      setOutput((prev) => prev + chunk);
    });

    onComplete(fullOutput);
    setRunning(false);
    setDone(true);
  }

  useEffect(() => {
    if (done && autonomous) {
      const timer = setTimeout(() => {
        navigate("/experiment");
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [done, autonomous]);

  return (
    <div className="stage-page">
      <h1>Proposal Agent</h1>
      <p>Designs a concrete, computationally feasible research proposal based on the deep literature review.</p>

      {!deepLitOutput && (
        <div className="warning-box">
          No deep literature output found. Please complete the Deep Literature stage first.
        </div>
      )}

      {deepLitOutput && (
        <div className="input-row">
          <button
            className="run-button"
            onClick={() => handleRun()}
            disabled={running}
          >
            {running ? "Running..." : "Run Proposal Agent"}
          </button>
        </div>
      )}

      {output && (
        <div className="output-box">
          <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{output}</div>
        </div>
      )}

      {done && !autonomous && (
        <>
          <FeedbackBar onRerun={(feedback) => handleRun(feedback)} disabled={running} />
          <button className="start-button" style={{ marginTop: "16px" }} onClick={() => navigate("/experiment")}>
            Continue to Experiment →
          </button>
        </>
      )}

      {done && autonomous && (
        <p className="auto-note">Autonomous mode — continuing automatically...</p>
      )}
    </div>
  );
}