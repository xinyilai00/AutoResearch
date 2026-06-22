import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import FeedbackBar from "../components/FeedbackBar.jsx";

export default function PiPage({ autonomous, onComplete }) {
  const navigate = useNavigate();
  const [topic, setTopic] = useState("");
  const [output, setOutput] = useState("");
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  async function handleRun(feedback = null) {
    if (!topic.trim()) return;
    setOutput("");
    setDone(false);
    setRunning(true);
    setError("");

    try {
      const response = await fetch("http://localhost:8000/api/stages/pi/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: topic,
          feedback: feedback
        })
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const data = await response.json();
      const fullOutput = data.output || "";
      setOutput(fullOutput);
      onComplete(fullOutput);
      setDone(true);
    } catch (err) {
      setError(`Something went wrong: ${err.message}`);
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    if (done && autonomous) {
      const timer = setTimeout(() => {
        navigate("/literature");
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [done, autonomous]);

  return (
    <div className="stage-page">
      <h1>PI Agent</h1>
      <p>Enter your research topic. The PI agent will generate structured search queries for the literature review.</p>

      <div className="input-row">
        <input
          className="topic-input"
          type="text"
          placeholder="e.g. transformer efficiency in NLP"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          disabled={running}
        />
        <button
          className="run-button"
          onClick={() => handleRun()}
          disabled={running || !topic.trim()}
        >
          {running ? "Running..." : "Run PI Agent"}
        </button>
      </div>

      {error && (
        <div className="warning-box">
          {error}
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
          <button className="start-button" style={{ marginTop: "16px" }} onClick={() => navigate("/literature")}>
            Continue to Literature →
          </button>
        </>
      )}

      {done && autonomous && (
        <p className="auto-note">Autonomous mode — continuing automatically...</p>
      )}
    </div>
  );
}