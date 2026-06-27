import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

export default function ResearchQuestionPage({ autonomous, topic, litOutput, questions, onQuestionsGenerated, selectedQuestion, onComplete, repoUrl, hypothesis }) {
  const navigate = useNavigate();
  const [question, setQuestion] = useState(selectedQuestion || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const abortControllerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) abortControllerRef.current.abort();
    };
  }, []);

  useEffect(() => {
    setQuestion(selectedQuestion || "");
  }, [selectedQuestion]);

  useEffect(() => {
    if (litOutput && topic && !selectedQuestion) {
      generateQuestion();
    }
  }, [litOutput, topic]);

  async function generateQuestion() {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;

    setLoading(true);
    setError("");
    setQuestion("");

    try {
      const response = await fetch("http://localhost:8000/api/stages/research_questions/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: topic,
          literature: litOutput,
          repo_url: repoUrl,
          hypothesis: hypothesis,
        }),
        signal: signal
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);
      const data = await response.json();
      const q = (data.output || "").trim();
      setQuestion(q);
      onQuestionsGenerated([q]);
    } catch (err) {
      if (err.name === "AbortError") return;
      setError(`Something went wrong: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm() {
    if (!question) return;

    try {
      await fetch("http://localhost:8000/api/stages/research_question/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          research_question: question,
          repo_url: repoUrl,
          hypothesis: hypothesis,
        })
      });
    } catch (err) {
      console.error("Failed to save research question to backend:", err);
    }

    onComplete(question);
    navigate("/deep-literature");
  }

  useEffect(() => {
    if (question && autonomous) {
      handleConfirm();
    }
  }, [question, autonomous]);

  return (
    <div className="stage-page">
      <h1>Research Question</h1>
      <p>The pipeline will generate a single research question scoped to the experiment being replicated.</p>

      {!litOutput && (
        <div className="warning-box">
          No literature output found. Please run the Topic & Literature stage first.
        </div>
      )}

      {loading && (
        <div className="status-indicator">
          <div className="spinner"></div>
          <p>Generating research question...</p>
        </div>
      )}

      {error && <div className="warning-box">{error}</div>}

      {question && !loading && (
        <div className="output-box">
          <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{question}</div>
        </div>
      )}

      {question && !loading && !autonomous && (
        <div style={{ display: "flex", gap: "12px", marginTop: "16px" }}>
          <button className="run-button" onClick={generateQuestion}>
            Regenerate
          </button>
          <button className="start-button" onClick={handleConfirm}>
            Confirm & Continue to Literature Review →
          </button>
        </div>
      )}

      {question && autonomous && (
        <p className="auto-note">Autonomous mode — continuing automatically...</p>
      )}
    </div>
  );
}