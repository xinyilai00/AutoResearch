import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import FeedbackBar from "../components/FeedbackBar.jsx";

async function mockRunExperimentAgent(proposalOutput, feedback, onChunk, signal) {
  const fakeOutput = `EXPERIMENT EXECUTION SUMMARY:
The experiment was conducted using the PMDATA dataset containing 16 athletes monitored over 5 months. All data preprocessing, model training, and evaluation were completed using Python with scikit-learn and TensorFlow libraries.

DATA PREPROCESSING:
- Raw wearable sensor data cleaned and normalized using z-score standardization
- Missing values imputed using forward-fill method (< 3% of total data)
- Feature extraction produced 12 HRV metrics, 4 sleep quality scores, and 6 activity metrics
- Final dataset: 2,847 athlete-day samples across 16 athletes

MODEL TRAINING:
- All four models trained using leave-one-athlete-out cross-validation (16 folds)
- LSTM models trained for 100 epochs with early stopping (patience=10)
- Random Forest trained with 500 estimators and max depth of 10
- Training completed in approximately 4.2 hours on standard CPU hardware

RESULTS:
- HRV-only LSTM: AUC 0.71, F1 0.68
- Sleep-only LSTM: AUC 0.69, F1 0.65
- Activity-only LSTM: AUC 0.64, F1 0.61
- Multivariate LSTM: AUC 0.83, F1 0.79

STATISTICAL ANALYSIS:
- Multivariate LSTM significantly outperforms all single-metric baselines (p < 0.01)
- Results replicated across 14 of 16 athletes
- Effect size (Cohen's d) = 0.82, indicating large practical significance

ERRORS AND EDGE CASES:
- 2 athletes showed anomalous patterns — flagged for exclusion in sensitivity analysis
- Class imbalance addressed successfully using SMOTE (minority class ratio improved from 0.23 to 0.45)
${feedback ? `\n\nRefined based on feedback: "${feedback}"` : ""}`;

  const words = fakeOutput.split(" ");
  for (const word of words) {
    if (signal?.aborted) return;
    await new Promise((resolve) => setTimeout(resolve, 50));
    if (signal?.aborted) return;
    onChunk(word + " ");
  }
}

export default function ExperimentPage({ autonomous, proposalOutput, experimentOutput, onComplete }) {
  const navigate = useNavigate();
  const [output, setOutput] = useState(experimentOutput || "");
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(!!experimentOutput);
  const [error, setError] = useState("");
  const abortControllerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  useEffect(() => {
    setOutput(experimentOutput || "");
    setDone(!!experimentOutput);
  }, [experimentOutput]);

  async function handleRun(feedback = null) {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;

    setOutput("");
    setDone(false);
    setRunning(true);
    setError("");

    let fullOutput = "";
    await mockRunExperimentAgent(proposalOutput, feedback, (chunk) => {
      if (signal.aborted) return;
      fullOutput += chunk;
      setOutput((prev) => prev + chunk);
    }, signal);

    if (!signal.aborted) {
      onComplete(fullOutput);
      setDone(true);
    }
    setRunning(false);
  }

  useEffect(() => {
    if (done && autonomous) {
      const timer = setTimeout(() => navigate("/paper"), 1500);
      return () => clearTimeout(timer);
    }
  }, [done, autonomous]);

  return (
    <div className="stage-page">
      <h1>Experiment Agent</h1>
      <p>Executes the proposed experiment and records results.</p>

      {!proposalOutput && (
        <div className="warning-box">
          No proposal output found. Please complete the Proposal stage first.
        </div>
      )}

      {proposalOutput && (
        <div className="input-row">
          <button
            className="run-button"
            onClick={() => handleRun()}
            disabled={running}
          >
            {running ? "Running..." : done ? "Rerun" : "Run Experiment Agent"}
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
          <button className="start-button" style={{ marginTop: "16px" }} onClick={() => navigate("/paper")}>
            Continue to Paper →
          </button>
        </>
      )}

      {done && autonomous && (
        <p className="auto-note">Autonomous mode — continuing automatically...</p>
      )}
    </div>
  );
}