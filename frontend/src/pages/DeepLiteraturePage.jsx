import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import FeedbackBar from "../components/FeedbackBar.jsx";

export default function DeepLiteraturePage({ autonomous, selectedQuestion, deepLitOutput, onComplete }) {
  const navigate = useNavigate();
  const [output, setOutput] = useState(deepLitOutput || "");
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(!!deepLitOutput);
  const [error, setError] = useState("");
  const [citationLinks, setCitationLinks] = useState([]);
  const citationIntervalRef = useRef(null);
  const abortControllerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      clearInterval(citationIntervalRef.current);
    };
  }, []);

  useEffect(() => {
    setOutput(deepLitOutput || "");
    setDone(!!deepLitOutput);
  }, [deepLitOutput]);


  async function fetchCitationLinks() {
    try {
      const response = await fetch("http://localhost:8000/api/runs/latest");
      const state = await response.json();
      setCitationLinks(state?.metadata?.deep_literature_citations || []);
    } catch {}
  }

  useEffect(() => {
    if (running) {
      fetchCitationLinks();
      citationIntervalRef.current = setInterval(fetchCitationLinks, 750);
    } else {
      clearInterval(citationIntervalRef.current);
    }
    return () => clearInterval(citationIntervalRef.current);
  }, [running]);

  useEffect(() => {
    if (!running && (done || deepLitOutput)) {
      fetchCitationLinks();
    }
  }, [done, deepLitOutput, running]);

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
    setCitationLinks([]);

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
      fetchCitationLinks();
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
    <div style={{ display: "flex", gap: "24px", alignItems: "flex-start" }}>
      <div className="stage-page" style={{ flex: 1, minWidth: 0 }}>
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
              onClick={running ? () => abortControllerRef.current?.abort() : () => handleRun()}
            >
              {running ? "Stop" : done ? "Rerun" : "Run Literature Review"}
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

      {(running || done || citationLinks.length > 0) && (
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
            Literature Citations
          </div>
          {running && citationLinks.length === 0 && (
            <div style={{ color: "#63b3ed", lineHeight: "1.5" }}>Searching citation sources...</div>
          )}
          {done && !running && (
            <div style={{ color: "#68d391", marginBottom: "8px" }}>● Literature complete</div>
          )}
          {citationLinks.length === 0 && !running && (
            <div style={{ color: "#a0aec0", lineHeight: "1.5" }}>No citation links are available yet.</div>
          )}
          {citationLinks.map((citation, index) => (
            <div key={`${citation.url || citation.title || index}`} style={{
              borderBottom: "1px solid rgba(160, 174, 192, 0.18)",
              marginBottom: "10px",
              paddingBottom: "10px",
              lineHeight: "1.45",
            }}>
              <div style={{ color: "#e2e8f0", fontWeight: 600, overflowWrap: "anywhere" }}>
                {index + 1}. {citation.citation || citation.title || "Citation"}
              </div>
              <a href={citation.url} target="_blank" rel="noreferrer" style={{ color: "#63b3ed", overflowWrap: "anywhere" }}>
                {citation.title || citation.url}
              </a>
              <div style={{ color: "#a0aec0", marginTop: "4px" }}>
                {[citation.source, citation.year].filter(Boolean).join(" · ")}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}