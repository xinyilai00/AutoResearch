import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import FeedbackBar from "../components/FeedbackBar.jsx";

export default function ProposalPage({ autonomous, deepLitOutput, proposalOutput, onComplete }) {
  const navigate = useNavigate();
  const [output, setOutput] = useState(proposalOutput || "");
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(!!proposalOutput);
  const [error, setError] = useState("");
  const [progressLines, setProgressLines] = useState([]);
  const abortControllerRef = useRef(null);
  const progressIntervalRef = useRef(null);
  const progressBottomRef = useRef(null);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) abortControllerRef.current.abort();
      clearInterval(progressIntervalRef.current);
    };
  }, []);

  useEffect(() => {
    setOutput(proposalOutput || "");
    setDone(!!proposalOutput);
  }, [proposalOutput]);

  useEffect(() => {
    if (running) {
      setProgressLines([]);
      progressIntervalRef.current = setInterval(async () => {
        try {
          const r = await fetch("http://localhost:8000/api/progress");
          const data = await r.json();
          setProgressLines(data.lines || []);
        } catch {}
      }, 2000);
    } else {
      clearInterval(progressIntervalRef.current);
    }
    return () => clearInterval(progressIntervalRef.current);
  }, [running]);

  useEffect(() => {
    if (progressBottomRef.current) {
      progressBottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [progressLines]);

  async function handleRun(feedback = null) {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;

    setOutput("");
    setDone(false);
    setRunning(true);
    setError("");
    setProgressLines([]);

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
    <div style={{ display: "flex", gap: "24px", alignItems: "flex-start" }}>
      <div className="stage-page" style={{ flex: 1, minWidth: 0 }}>
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
              onClick={running ? () => abortControllerRef.current?.abort() : () => handleRun()}
            >
              {running ? "Stop" : done ? "Rerun" : "Run Proposal Agent"}
            </button>
          </div>
        )}

        {running && (
          <div className="status-indicator">
            <div className="spinner"></div>
            <p>Finding repo and designing research proposal...</p>
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

      {(running || progressLines.length > 0) && (
        <div style={{
          width: "300px",
          flexShrink: 0,
          background: "#1a1a2e",
          borderRadius: "12px",
          padding: "16px",
          fontFamily: "monospace",
          fontSize: "11px",
          color: "#a0aec0",
          overflowY: "auto",
          maxHeight: "80vh",
          position: "sticky",
          top: "24px",
        }}>
          <div style={{ color: "#e2e8f0", fontWeight: 600, marginBottom: "12px", fontSize: "12px" }}>
            Pipeline Progress
          </div>
          {progressLines.map((line, i) => (
            <div key={i} style={{
              marginBottom: "4px",
              lineHeight: "1.5",
              color: line.includes("succeeded") || line.includes("Done") || line.includes("complete") || line.includes("Selected") ? "#68d391" :
                     line.includes("failed") || line.includes("error") || line.includes("Error") || line.includes("aborting") ? "#fc8181" :
                     line.includes("Grading") || line.includes("Fetching") || line.includes("Asking") || line.includes("Generating") ? "#63b3ed" :
                     "#a0aec0"
            }}>
              {line}
            </div>
          ))}
          {running && (
            <div style={{ color: "#63b3ed", marginTop: "8px" }}>● Running...</div>
          )}
          <div ref={progressBottomRef} />
        </div>
      )}
    </div>
  );
}