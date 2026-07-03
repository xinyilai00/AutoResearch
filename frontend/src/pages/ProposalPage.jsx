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
  const [repoInfo, setRepoInfo] = useState(null);
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

  function updateRepoInfoFromState(state) {
    const metadata = state?.metadata || {};
    const name = metadata.selected_repo_name || metadata.selected_repo_id;
    const url = metadata.selected_repo_url;
    const reason = metadata.selected_repo_reason;
    const candidates = metadata.repo_candidates || [];
    const grades = metadata.repo_grades || [];

    if (name || url || candidates.length || grades.length) {
      setRepoInfo({ name, url, reason, candidates, grades });
    }
  }


  function normalizeRepoUrl(url) {
    return (url || "").trim().replace(/\.git$/, "").replace(/\/$/, "");
  }

  function repoUrlFromProposal(text) {
    const match = (text || "").match(/^Repo:\s*(.+)$/m);
    return match ? normalizeRepoUrl(match[1]) : "";
  }

  async function fetchProgressLines() {
    try {
      const r = await fetch("http://localhost:8000/api/progress");
      const data = await r.json();
      const lines = data.lines || [];
      setProgressLines((previous) => (lines.length > 0 ? lines : running ? previous : []));
    } catch {}
  }

  async function fetchRunState() {
    try {
      const r = await fetch("http://localhost:8000/api/runs/latest");
      const state = await r.json();
      updateRepoInfoFromState(state);
    } catch {}
  }

  useEffect(() => {
    if (running) {
      setProgressLines(["[Proposal Stage] Starting repo pipeline..."]);
      setRepoInfo(null);
      fetchProgressLines();
      fetchRunState();
      progressIntervalRef.current = setInterval(() => {
        fetchProgressLines();
        fetchRunState();
      }, 750);
    } else {
      clearInterval(progressIntervalRef.current);
    }
    return () => clearInterval(progressIntervalRef.current);
  }, [running]);

  useEffect(() => {
    if (!running && (done || proposalOutput)) {
      fetchProgressLines();
      fetchRunState();
    }
  }, [done, proposalOutput, running]);

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
    setProgressLines(["[Proposal Stage] Starting repo pipeline..."]);
    setRepoInfo(null);

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
      updateRepoInfoFromState(data.state);
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

  const outputRepoUrl = repoUrlFromProposal(output);
  const selectedRepoUrl = normalizeRepoUrl(repoInfo?.url);
  const hasRepoMismatch = Boolean(outputRepoUrl && selectedRepoUrl && outputRepoUrl !== selectedRepoUrl);

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

        {hasRepoMismatch && (
          <div className="warning-box">
            This proposal output belongs to {outputRepoUrl}, but the selected repo is {selectedRepoUrl}. Rerun Proposal to regenerate it for the selected repo.
          </div>
        )}

        {output && !hasRepoMismatch && (
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

      {(running || done || progressLines.length > 0 || repoInfo) && (
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
            Repo Pipeline
          </div>
          {done && !running && (
            <div style={{ color: "#68d391", marginBottom: "8px" }}>● Proposal complete</div>
          )}
          {repoInfo && (
            <div style={{
              borderBottom: "1px solid rgba(160, 174, 192, 0.2)",
              marginBottom: "12px",
              paddingBottom: "12px",
              lineHeight: "1.5",
            }}>
              <div style={{ color: "#e2e8f0", fontWeight: 600 }}>Selected Repo</div>
              <div style={{ color: "#68d391", wordBreak: "break-word" }}>
                {repoInfo.name || "Selected repository"}
              </div>
              {repoInfo.url && (
                <a href={repoInfo.url} target="_blank" rel="noreferrer" style={{ color: "#63b3ed", wordBreak: "break-word" }}>
                  {repoInfo.url}
                </a>
              )}
              {repoInfo.reason && (
                <div style={{ color: "#a0aec0", marginTop: "6px" }}>{repoInfo.reason}</div>
              )}
              {repoInfo.candidates?.length > 0 && (
                <div style={{ color: "#a0aec0", marginTop: "6px" }}>
                  Candidates found: {repoInfo.candidates.length}
                </div>
              )}
              {repoInfo.grades?.length > 0 && (
                <div style={{ color: "#a0aec0" }}>
                  Repos graded: {repoInfo.grades.length}
                </div>
              )}
              {repoInfo.candidates?.length > 0 && (
                <div style={{ marginTop: "10px" }}>
                  <div style={{ color: "#e2e8f0", fontWeight: 600, marginBottom: "4px" }}>10 Candidates</div>
                  {repoInfo.candidates.slice(0, 10).map((candidate, index) => (
                    <div key={`${candidate.name || candidate.repo || candidate.url || index}`} style={{
                      color: "#a0aec0",
                      lineHeight: "1.5",
                      overflowWrap: "anywhere",
                    }}>
                      {index + 1}. {candidate.name || candidate.repo || candidate.url || "Unnamed repo"}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {progressLines.length === 0 && running && (
            <div style={{ color: "#63b3ed", lineHeight: "1.5" }}>Waiting for the first repo pipeline update...</div>
          )}
          {progressLines.length === 0 && !running && !repoInfo && (
            <div style={{ color: "#a0aec0", lineHeight: "1.5" }}>No repo pipeline log is available yet.</div>
          )}
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