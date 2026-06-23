import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import FeedbackBar from "../components/FeedbackBar.jsx";

export default function ExperimentPage({ autonomous, proposalOutput, experimentOutput, onComplete }) {
  const navigate = useNavigate();
  const [output, setOutput] = useState(experimentOutput || "");
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(!!experimentOutput);
  const [error, setError] = useState("");
  const abortControllerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) abortControllerRef.current.abort();
    };
  }, []);

  useEffect(() => {
    setOutput(experimentOutput || "");
    setDone(!!experimentOutput);
  }, [experimentOutput]);

  useEffect(() => {
    if (done && autonomous) {
      const timer = setTimeout(() => navigate("/paper"), 1500);
      return () => clearTimeout(timer);
    }
  }, [done, autonomous]);

  async function handleRun(feedback = null) {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    abortControllerRef.current = new AbortController();

    setOutput("");
    setDone(false);
    setRunning(true);
    setError("");

    try {
      const res = await fetch("http://localhost:8000/api/stages/experiment/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback: feedback || undefined }),
        signal: abortControllerRef.current.signal,
      });

      const data = await res.json();

      if (!res.ok || data.status === "redesign_needed") {
        throw new Error(data.detail || data.output || "Experiment stage failed.");
      }

      setOutput(data.output || "");
      onComplete(data.output || "");
      setDone(true);
    } catch (e) {
      if (e.name !== "AbortError") setError(e.message);
    } finally {
      setRunning(false);
    }
  }

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
          <button className="run-button" onClick={() => handleRun()} disabled={running}>
            {running ? "Running experiment..." : done ? "Rerun" : "Run Experiment Agent"}
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