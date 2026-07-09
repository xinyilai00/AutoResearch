import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../api/client.js";

export default function ResearchQuestionPage({ autonomous, topic, litOutput, questions, onQuestionsGenerated, selectedQuestion, onComplete }) {
  const navigate = useNavigate();
  const [candidates, setCandidates] = useState([]);
  const [selected, setSelected] = useState(selectedQuestion || "");
  const [custom, setCustom] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const abortControllerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) abortControllerRef.current.abort();
    };
  }, []);

  useEffect(() => {
    if (litOutput && topic && candidates.length === 0 && !selectedQuestion) {
      generateQuestions();
    }
  }, [litOutput, topic]);

  async function generateQuestions() {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;

    setLoading(true);
    setError("");
    setCandidates([]);
    setSelected("");
    setCustom("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/stages/research_questions/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: topic, literature: litOutput }),
        signal: signal
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);
      const data = await response.json();
      let parsed = [];
      try {
        parsed = JSON.parse(data.output || "[]");
        if (!Array.isArray(parsed)) parsed = [String(parsed)];
      } catch (e) {
        const text = (data.output || "").trim();
        parsed = text ? [text] : [];
      }
      setCandidates(parsed);
      onQuestionsGenerated(parsed);
    } catch (err) {
      if (err.name === "AbortError") return;
      setError(`Something went wrong: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm() {
    const finalQuestion = custom.trim() || selected;
    if (!finalQuestion) return;

    try {
      await fetch(`${API_BASE_URL}/api/stages/research_question/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ research_question: finalQuestion })
      });
    } catch (err) {
      console.error("Failed to save research question:", err);
    }

    onComplete(finalQuestion);
    navigate("/deep-literature");
  }

  useEffect(() => {
    if (candidates.length > 0 && autonomous) {
      setSelected(candidates[0]);
      handleConfirm();
    }
  }, [candidates, autonomous]);

  const finalQuestion = custom.trim() || selected;

  return (
    <div className="stage-page">
      <h1>Research Question</h1>
      <p>Select one of the generated research questions, or write your own below.</p>

      {!litOutput && (
        <div className="warning-box">
          No literature output found. Please run the Topic & Literature stage first.
        </div>
      )}

      {loading && (
        <div className="status-indicator">
          <div className="spinner"></div>
          <p>Generating research questions...</p>
        </div>
      )}

      {error && <div className="warning-box">{error}</div>}

      {candidates.length > 0 && !loading && (
        <div style={{ marginTop: "16px" }}>
          {candidates.map((q, i) => (
            <div
              key={i}
              onClick={() => { setSelected(q); setCustom(""); }}
              style={{
                padding: "12px 16px",
                marginBottom: "12px",
                border: selected === q && !custom.trim() ? "2px solid #6d3fc0" : "1px solid #ddd",
                borderRadius: "10px",
                cursor: "pointer",
                background: selected === q && !custom.trim() ? "#f3eeff" : "#fff",
                fontSize: "13.5px",
                lineHeight: "1.55",
                color: "#1a1a1a",
                transition: "border 0.15s, background 0.15s",
              }}
            >
              {q}
            </div>
          ))}

          <div style={{ marginTop: "20px" }}>
            <p style={{ marginBottom: "8px", fontWeight: 500, fontSize: "14px" }}>Or write your own:</p>
            <textarea
              rows={3}
              style={{
                width: "100%",
                padding: "10px 14px",
                borderRadius: "8px",
                border: "1px solid #ddd",
                fontSize: "14px",
                fontFamily: "inherit",
                lineHeight: "1.5",
                resize: "vertical",
                outline: "none",
                boxSizing: "border-box",
              }}
              placeholder="Type a custom research question..."
              value={custom}
              onChange={(e) => { setCustom(e.target.value); setSelected(""); }}
            />
          </div>
        </div>
      )}

      {candidates.length > 0 && !loading && !autonomous && (
        <div style={{ display: "flex", gap: "16px", marginTop: "20px" }}>
          <button className="run-button" style={{ fontSize: "13px" }} onClick={generateQuestions}>
            Regenerate
          </button>
          <button
            className="start-button"
            style={{ fontSize: "13px" }}
            onClick={handleConfirm}
            disabled={!finalQuestion}
          >
            Confirm & Continue →
          </button>
        </div>
      )}

      {candidates.length > 0 && autonomous && (
        <p className="auto-note">Autonomous mode — continuing automatically...</p>
      )}
    </div>
  );
}