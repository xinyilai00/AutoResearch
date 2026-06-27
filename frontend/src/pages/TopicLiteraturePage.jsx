import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import FeedbackBar from "../components/FeedbackBar.jsx";

export default function TopicLiteraturePage({ autonomous, topic, onTopicSet, litOutput, onComplete, repoUrl, hypothesis }) 
{  const navigate = useNavigate();
  const [localTopic, setLocalTopic] = useState(topic || "");
  const [output, setOutput] = useState(litOutput || "");
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(!!litOutput);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const abortControllerRef = useRef(null);

  // Cancel fetch on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  useEffect(() => {
    setLocalTopic(topic || "");
    setOutput(litOutput || "");
    setDone(!!litOutput);
  }, [topic, litOutput]);

  async function handleRun(feedback = null) {
    if (!localTopic.trim()) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;

    setOutput("");
    setDone(false);
    setRunning(true);
    setError("");
    setStatus("Researching...");

    try {
      const piResponse = await fetch("http://localhost:8000/api/stages/pi/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: localTopic, feedback: feedback, repo_url: repoUrl, hypothesis: hypothesis }),        signal: signal
      });

      if (!piResponse.ok) throw new Error(`PI agent error: ${piResponse.status}`);
      const piData = await piResponse.json();
      const piOutput = piData.output || "";

      setStatus("Generating literature review...");
      const litResponse = await fetch("http://localhost:8000/api/stages/literature/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: localTopic, pi_output: piOutput, feedback: feedback, repo_url: repoUrl, hypothesis: hypothesis }),        signal: signal
      });

      if (!litResponse.ok) throw new Error(`Literature agent error: ${litResponse.status}`);
      const litData = await litResponse.json();
      const fullOutput = litData.output || "";
      setOutput(fullOutput);
      onComplete(fullOutput);
      setDone(true);
      setStatus("");
    } catch (err) {
      if (err.name === "AbortError") {
        setRunning(false);
        setStatus("");
        return;
      }
      setError(`Something went wrong: ${err.message}`);
      setStatus("");
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    if (done && autonomous) {
      const timer = setTimeout(() => navigate("/research-question"), 1500);
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
          value={localTopic}
          onChange={(e) => {
            setLocalTopic(e.target.value);
            onTopicSet(e.target.value);
          }}
          disabled={running}
        />
        <button
          className="run-button"
          onClick={running ? () => abortControllerRef.current?.abort() : () => handleRun()}
          disabled={!localTopic.trim()}
        >
          {running ? "Stop" : done ? "Rerun" : "Run"}
        </button>
      </div>

      {status && (
        <div className="status-indicator">
          <div className="spinner"></div>
          <p>{status}</p>
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