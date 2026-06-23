import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import FeedbackBar from "../components/FeedbackBar.jsx";

export default function DeepLiteraturePage({ autonomous, selectedQuestion, deepLitOutput, onComplete }) {
  const navigate = useNavigate();
  const [output, setOutput] = useState(deepLitOutput || "");
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(!!deepLitOutput);
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
    setOutput(deepLitOutput || "");
    setDone(!!deepLitOutput);
  }, [deepLitOutput]);

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
      const response = await fetch("http://localhost:8000/api/stages/deep_literature/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ research_question: selectedQuestion, feedback: feedback }),
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
      const timer = setTimeout(() => navigate("/proposal"), 1500);
      return () => clearTimeout(timer);
    }
  }, [done, autonomous]);

  return (
    <div className="stage-page">
      <h1>Literature Review</h1>
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
              {running ? "Running..." : done ? "Rerun" : "Run Literature Review"}
            </button>
          </div>
        </>
      )}

      {running && (
        <div className="status-indicator">
          <div className="spinner"></div>
          <p>Running targeted literature review...</p>
        </div>
      )}

      {error && <div className="warning-box">{error}</div>}

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