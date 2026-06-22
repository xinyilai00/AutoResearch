import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import FeedbackBar from "../components/FeedbackBar.jsx";

async function mockRunDeepLiteratureAgent(selectedQuestion, feedback, onChunk) {
  const fakeOutput = `RELEVANT METHODOLOGIES:
- LSTM Networks: Used for time-series data prediction with ~78% accuracy in prior fatigue classification studies. Particularly effective for sequential sensor data.
- Random Forest: Applied for feature importance ranking across HRV, sleep, and activity metrics. Computationally lightweight and interpretable.
- Transformer-based models: Recently applied to wearable time-series with promising results but high computational cost.
- Support Vector Machines: Used as baseline classifiers in several benchmark studies with moderate performance.

RELEVANT DATASETS:
- PMDATA: Publicly available dataset of 16 athletes over 5 months with daily wellness scores and wearable sensor data. Most directly relevant to this question.
- LifeSnaps: Fitbit data combined with self-reported wellness metrics across general population. Useful for transfer learning.
- WESAD: Wearable stress and affect detection dataset. Relevant for physiological signal processing methods.

PRIOR QUANTITATIVE RESULTS:
- HRV alone predicts next-day readiness with AUC 0.71 in prior studies
- Multivariate models combining sleep + HRV + activity outperform single-metric models by 12-18%
- LSTM models achieve F1 score of 0.74 on fatigue classification tasks
- Random Forest feature importance consistently ranks sleep quality as the top predictor

WHAT THIS QUESTION STILL NEEDS:
Individual-level prediction versus group-level prediction has not been rigorously tested in the literature. Most existing studies aggregate data across athletes, masking significant within-person variability that is critical for personalized performance monitoring.

A new study must apply within-subject cross-validation or leave-one-out methodology to properly evaluate individual-level prediction accuracy. Current benchmarks are not directly comparable due to inconsistent evaluation protocols across studies.

Furthermore, the combination of multiple wearable modalities in a unified model has not been systematically compared against single-modality approaches using the same dataset and evaluation framework.
${feedback ? `\n\nRefined based on feedback: "${feedback}"` : ""}`;

  const words = fakeOutput.split(" ");
  for (const word of words) {
    await new Promise((resolve) => setTimeout(resolve, 50));
    onChunk(word + " ");
  }
}

export default function DeepLiteraturePage({ autonomous, selectedQuestion, onComplete }) {
  const navigate = useNavigate();
  const [output, setOutput] = useState("");
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);

  async function handleRun(feedback = null) {
    setOutput("");
    setDone(false);
    setRunning(true);

    let fullOutput = "";
    await mockRunDeepLiteratureAgent(selectedQuestion, feedback, (chunk) => {
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
        navigate("/proposal");
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [done, autonomous]);

  return (
    <div className="stage-page">
      <h1>Deep Literature Agent</h1>
      <p>Conducts a targeted literature review focused on your selected research question.</p>

      {!selectedQuestion && (
        <div className="warning-box">
          No research question selected. Please complete the Research Question stage first.
        </div>
      )}

      {selectedQuestion && (
        <>
          <div className="selected-preview" style={{ marginBottom: "20px" }}>
            <strong>Research Question:</strong> {selectedQuestion}
          </div>

          <div className="input-row">
            <button
              className="run-button"
              onClick={() => handleRun()}
              disabled={running}
            >
              {running ? "Running..." : "Run Deep Literature Agent"}
            </button>
          </div>
        </>
      )}

      {output && (
        <div className="output-box">
          <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{output}</div>
        </div>
      )}

      {done && !autonomous && (
        <>
          <FeedbackBar onRerun={(feedback) => handleRun(feedback)} disabled={running} />
          <button className="start-button" style={{ marginTop: "16px" }} onClick={() => navigate("/proposal")}>
            Continue to Proposal →
          </button>
        </>
      )}

      {done && autonomous && (
        <p className="auto-note">Autonomous mode — continuing automatically...</p>
      )}
    </div>
  );
}