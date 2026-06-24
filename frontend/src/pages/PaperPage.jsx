import React, { useState, useEffect, useRef } from "react";
import FeedbackBar from "../components/FeedbackBar.jsx";

const PHASE_LABELS = ["Drafting paper...", "Polishing paper..."];
const PHASE_DURATION_MS = 300000;

export default function PaperPage({ autonomous, experimentOutput, paperOutput, onComplete }) {
  const [output, setOutput] = useState(paperOutput || "");
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(!!paperOutput);
  const [error, setError] = useState("");
  const [phaseIndex, setPhaseIndex] = useState(0);
  const phaseTimerRef = useRef(null);

  useEffect(() => {
    setOutput(paperOutput || "");
    setDone(!!paperOutput);
  }, [paperOutput]);

  useEffect(() => {
    return () => {
      if (phaseTimerRef.current) clearTimeout(phaseTimerRef.current);
    };
  }, []);

  async function handleRun(feedback = null) {
    setOutput("");
    setDone(false);
    setRunning(true);
    setError("");
    setPhaseIndex(0);

    phaseTimerRef.current = setTimeout(() => setPhaseIndex(1), PHASE_DURATION_MS);

    try {
      const res = await fetch("http://localhost:8000/api/stages/paper/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback: feedback || undefined }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Paper stage failed");
      }

      const data = await res.json();
      const text = data.output || "";
      setOutput(text);
      onComplete(text);
      setDone(true);
    } catch (e) {
      setError(e.message);
    } finally {
      clearTimeout(phaseTimerRef.current);
      setRunning(false);
      setPhaseIndex(0);
    }
  }

  return (
    <div className="stage-page">
      <h1>Paper Agent</h1>
      <p>Writes and polishes a full academic research paper based on all previous stage outputs.</p>

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
            {running ? PHASE_LABELS[phaseIndex] : done ? "Rerun" : "Run Paper Agent"}
          </button>
        </div>
      )}

      {error && <div className="error-box">{error}</div>}

      {output && (
        <div className="output-box">
          <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{output}</div>
        </div>
      )}

      {done && !autonomous && (
        <FeedbackBar onRerun={(feedback) => handleRun(feedback)} disabled={running} />
      )}

      {done && autonomous && (
        <p className="auto-note">Autonomous mode — continuing automatically...</p>
      )}
    </div>
  );
}