import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import FeedbackBar from "../components/FeedbackBar.jsx";

async function mockRunPiAgent(topic, feedback, onChunk) {
  const fakeOutput = `Primary search query: ${topic} machine learning applications

Alternative queries: ${topic} deep learning, ${topic} neural networks, ${topic} artificial intelligence, ${topic} computational methods

Key terms: machine learning, neural networks, deep learning, data analysis, computational methods, prediction, modeling, optimization, evaluation, benchmarking${feedback ? `\n\nRefined based on feedback: "${feedback}"` : ""}`;

  const words = fakeOutput.split(" ");
  for (const word of words) {
    await new Promise((resolve) => setTimeout(resolve, 80));
    onChunk(word + " ");
  }
}

export default function PiPage({ autonomous, onComplete }) {
  const navigate = useNavigate();
  const [topic, setTopic] = useState("");
  const [output, setOutput] = useState("");
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);

  async function handleRun(feedback = null) {
    if (!topic.trim()) return;
    setOutput("");
    setDone(false);
    setRunning(true);

    let fullOutput = "";
    await mockRunPiAgent(topic, feedback, (chunk) => {
      fullOutput += chunk;
      setOutput((prev) => prev + chunk);
    });

    onComplete(fullOutput);
    setRunning(false);
    setDone(true);
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