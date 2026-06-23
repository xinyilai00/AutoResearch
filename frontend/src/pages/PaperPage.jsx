import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import FeedbackBar from "../components/FeedbackBar.jsx";

async function mockRunPaperAgent(experimentOutput, feedback, onChunk, signal) {
  const fakeOutput = `# Predicting Athletic Performance Decrements Using Multivariate Wearable Sensor Data

## Abstract
This study investigates whether combining HRV, sleep, and activity metrics improves next-day athletic performance prediction over single-metric baselines.

## Introduction
Wearable sensors have enabled continuous monitoring of athlete physiological states, yet individual-level prediction remains underexplored.

## Review
Existing literature shows multivariate models outperform single-metric approaches by 12-18%, though within-subject evaluation is rarely applied.

## Methodology
A leave-one-athlete-out cross-validation was applied to the PMDATA dataset across four LSTM model configurations.

## Results
The multivariate LSTM achieved AUC 0.83, significantly outperforming all single-metric baselines (p < 0.01).

## Discussion
Results confirm the hypothesis and suggest sleep quality is the strongest individual predictor when combined with HRV metrics.

## Conclusion
Multivariate wearable models can reliably predict next-day performance decrements at the individual athlete level.

## References
TODO: Add verified citations from the Citations stage.
${feedback ? `\n\nRefined based on feedback: "${feedback}"` : ""}`;

  const words = fakeOutput.split(" ");
  for (const word of words) {
    if (signal?.aborted) return;
    await new Promise((resolve) => setTimeout(resolve, 50));
    if (signal?.aborted) return;
    onChunk(word + " ");
  }
}

export default function PaperPage({ autonomous, experimentOutput, paperOutput, onComplete }) {
  const navigate = useNavigate();
  const [output, setOutput] = useState(paperOutput || "");
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(!!paperOutput);
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
    setOutput(paperOutput || "");
    setDone(!!paperOutput);
  }, [paperOutput]);

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
    await mockRunPaperAgent(experimentOutput, feedback, (chunk) => {
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
      const timer = setTimeout(() => navigate("/review"), 1500);
      return () => clearTimeout(timer);
    }
  }, [done, autonomous]);

  return (
    <div className="stage-page">
      <h1>Paper Agent</h1>
      <p>Writes a full academic research paper based on all previous stage outputs.</p>

      {!experimentOutput && (
        <div className="warning-box">
          No experiment output found. Please complete the Experiment stage first.
        </div>
      )}

      {experimentOutput && (
        <div className="input-row">
          <button
            className="run-button"
            onClick={() => handleRun()}
            disabled={running}
          >
            {running ? "Running..." : done ? "Rerun" : "Run Paper Agent"}
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
          <button className="start-button" style={{ marginTop: "16px" }} onClick={() => navigate("/review")}>
            Continue to Review →
          </button>
        </>
      )}

      {done && autonomous && (
        <p className="auto-note">Autonomous mode — continuing automatically...</p>
      )}
    </div>
  );
}