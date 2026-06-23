import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import FeedbackBar from "../components/FeedbackBar.jsx";

export default function ProposalPage({ autonomous, deepLitOutput, proposalOutput, onComplete }) {
  const navigate = useNavigate();
  const [output, setOutput] = useState(proposalOutput || "");
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(!!proposalOutput);
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
    setOutput(proposalOutput || "");
    setDone(!!proposalOutput);
  }, [proposalOutput]);

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

    try {
      const response = await fetch("http://localhost:8000/api/stages/proposal/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          deep_literature: deepLitOutput,
          feedback: feedback
        }),
        signal: signal
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);
      const data = await response.json();
      const fullOutput = data.output || "";
      setOutput(fullOutput);
      onComplete(fullOutput);
      setDone(true);
    } catch (err) {
      if (err.name === "AbortError") {
        setRunning(false);
        return;
      }
      setError(`Something went wrong: ${err.message}`);
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    if (done && autonomous) {
      const timer = setTimeout(() => navigate("/experiment"), 1500);
      return () => clearTimeout(timer);
    }
  }, [done, autonomous]);

  return (
    <div className="stage-page">
      <h1>Proposal Agent</h1>
      <p>Designs a concrete, computationally feasible research proposal based on the literature review.</p>

      {!deepLitOutput && (
        <div className="warning-box">
          No literature review output found. Please complete the Literature Review stage first.
        </div>
      )}

      {deepLitOutput && (
        <div className="input-row">
          <button
            className="run-button"
            onClick={() => handleRun()}
            disabled={running}
          >
            {running ? "Running..." : done ? "Rerun" : "Run Proposal Agent"}
          </button>
        </div>
      )}

      {running && (
        <div className="status-indicator">
          <div className="spinner"></div>
          <p>Designing research proposal...</p>
        </div>
      )}

      {error && <div className="warning-box">{error}</div>}

      {output && (
        <div className="output-box">
          <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {output.includes("EXPERIMENT EXECUTION SPEC:") 
              ? output.slice(0, output.indexOf("EXPERIMENT EXECUTION SPEC:")).trim()
              : output}
          </div>
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