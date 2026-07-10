import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import FeedbackBar from "../components/FeedbackBar.jsx";
import { API_BASE_URL } from "../api/client.js";

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
    const res = await fetch(`${API_BASE_URL}/api/stages/experiment/run`, {        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          proposal: proposalOutput,
          feedback: feedback || undefined
        }),
        signal: abortControllerRef.current.signal,
      });

      let data = {};
      try {
        data = await res.json();
      } catch {
        const text = await res.text().catch(() => "");
        throw new Error(text || `Experiment server returned ${res.status} without JSON.`);
      }

      if (!res.ok || data.status === "redesign_needed") {
        throw new Error(data.detail || data.output || "Experiment stage failed.");
      }

      setOutput(data.output || "");
      onComplete(data.output || "");
      setDone(true);
    } catch (e) {
      if (e.name !== "AbortError") {
        const message = e.message === "Load failed" || e instanceof TypeError
          ? `Could not reach the experiment backend at ${API_BASE_URL}. Check that the server backend is running and reachable on port 8000.`
          : e.message;
        setError(message);
      }
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
          <button
            className="run-button"
            onClick={running ? () => abortControllerRef.current?.abort() : () => handleRun()}
          >
            {running ? "Stop" : done ? "Rerun" : "Run Experiment Agent"}
          </button>
        </div>
      )}

      {error && <div className="error-box">{error}</div>}

      {running && (
        <div className="status-indicator">
          <div className="spinner"></div>
          <p>Running experiment — training on CPU may take 15-20 minutes.</p>
          <p style={{
            color: "#fc8181",
            fontWeight: 700,
            fontSize: "16px",
            border: "2px solid #fc8181",
            borderRadius: "8px",
            padding: "10px",
            marginTop: "8px",
          }}>
            ⚠️ DO NOT LEAVE OR RELOAD THIS PAGE WHILE THE EXPERIMENT IS RUNNING.
          </p>
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