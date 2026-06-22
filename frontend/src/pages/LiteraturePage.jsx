import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import FeedbackBar from "../components/FeedbackBar.jsx";

async function mockRunLiteratureAgent(piOutput, feedback, onChunk) {
  const fakeOutput = `SUMMARY OF EXISTING WORK:
The existing literature on ${piOutput.split("\n")[0]} spans several decades of research. Studies have primarily focused on computational approaches using publicly available datasets. Key findings suggest that transformer-based models outperform traditional methods in most benchmarks, though efficiency remains a concern at scale.

A secondary body of work has examined the role of data augmentation and transfer learning in improving model generalization. These studies consistently report gains of 10-20% over baseline methods when combining multiple techniques.

GAPS:
1. Limited research on real-time inference optimization for edge devices
2. Lack of studies combining pruning and quantization simultaneously
3. No comprehensive benchmark comparing all major efficiency techniques
4. Underexplored: efficiency tradeoffs in multilingual transformer models
5. Missing longitudinal studies on model degradation over time
${feedback ? `\n\nRefined based on feedback: "${feedback}"` : ""}`;

  const words = fakeOutput.split(" ");
  for (const word of words) {
    await new Promise((resolve) => setTimeout(resolve, 60));
    onChunk(word + " ");
  }
}

export default function LiteraturePage({ autonomous, piOutput, onComplete }) {
  const navigate = useNavigate();
  const [output, setOutput] = useState("");
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);

  async function handleRun(feedback = null) {
    setOutput("");
    setDone(false);
    setRunning(true);

    let fullOutput = "";
    await mockRunLiteratureAgent(piOutput, feedback, (chunk) => {
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
        navigate("/research-question");
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [done, autonomous]);

  return (
    <div className="stage-page">
      <h1>Literature Agent</h1>
      <p>Searches academic databases and identifies research gaps based on the PI output.</p>

      {!piOutput && (
        <div className="warning-box">
          No PI output found. Please run the PI stage first.
        </div>
      )}

      {piOutput && (
        <div className="input-row">
          <button
            className="run-button"
            onClick={() => handleRun()}
            disabled={running}
          >
            {running ? "Running..." : "Run Literature Agent"}
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
          <button className="start-button" style={{ marginTop: "16px" }} onClick={() => navigate("/research-question")}>
            Continue to Research Question →
          </button>
        </>
      )}

      {done && autonomous && (
        <p className="auto-note">Autonomous mode — continuing automatically...</p>
      )}
    </div>
  );
}