import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import FeedbackBar from "../components/FeedbackBar.jsx";

export default function TopicLiteraturePage({ autonomous, onComplete }) {
  const navigate = useNavigate();
  const [topic, setTopic] = useState("");
  const [output, setOutput] = useState("");
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  async function handleRun(feedback = null) {
    if (!topic.trim()) return;
    setOutput("");
    setDone(false);
    setRunning(true);
    setError("");
    setStatus("Researching...");

    try {
      // Step 1 — Run PI agent behind the scenes
      const piResponse = await fetch("http://localhost:8000/api/stages/pi/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: topic,
          feedback: feedback
        })
      });

      if (!piResponse.ok) {
        throw new Error(`PI agent error: ${piResponse.status}`);
      }

      const piData = await piResponse.json();
      const piOutput = piData.output || "";

      // Step 2 — Run Literature agent with PI output
      setStatus("Generating literature review...");
      const litResponse = await fetch("http://localhost:8000/api/stages/literature/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: topic,
          pi_output: piOutput,
          feedback: feedback
        })
      });

      if (!litResponse.ok) {
        throw new Error(`Literature agent error: ${litResponse.status}`);
      }

      const litData = await litResponse.json();
      const fullOutput = litData.output || "";
      setOutput(fullOutput);
      onComplete(fullOutput);
      setDone(true);
      setStatus("");
    } catch (err) {
      setError(`Something went wrong: ${err.message}`);
      setStatus("");
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    if (done && autonomous) {
      const timer = setTimeout(() => {
        navigate("/research-question");
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [done, autonomous]);

  return (
    <div className="stage-page">
      <h1>Topic & Literature</h1>
      <p>Enter your research topic. We'll search academic databases and identify research gaps automatically.</p>

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
          {running ? "Running..." : "Run"}
        </button>
      </div>

      {status && <p className="auto-note">{status}</p>}

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
          <button className="start-button" style={{ marginTop: "16px" }} onClick={() => navigate("/research-question")}>
            Continue to Research Question →
          </button>
        </>
      )}

      {done && autonomous && (
        <p className="auto-note">Autonomous mode — continuing automatically...</p>
      )}
    </div>
  );
}