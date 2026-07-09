import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, NavLink, useLocation } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage.jsx";
import TopicLiteraturePage from "./pages/TopicLiteraturePage.jsx";
import ResearchQuestionPage from "./pages/ResearchQuestionPage.jsx";
import DeepLiteraturePage from "./pages/DeepLiteraturePage.jsx";
import ProposalPage from "./pages/ProposalPage.jsx";
import ExperimentPage from "./pages/ExperimentPage.jsx";
import PaperPage from "./pages/PaperPage.jsx";
import HistoryPage from "./pages/HistoryPage.jsx";
import "./styles/app.css";

const stages = [
  { label: "Dashboard", path: "/" },
  { label: "Topic & Literature", path: "/topic" },
  { label: "Research Question", path: "/research-question" },
  { label: "Literature Review", path: "/deep-literature" },
  { label: "Proposal", path: "/proposal" },
  { label: "Experiment", path: "/experiment" },
  { label: "Paper", path: "/paper" },
  { label: "History", path: "/history", under: "Paper" },
];

const PIPELINE_STAGES = [
  "/topic",
  "/research-question",
  "/deep-literature",
  "/proposal",
  "/experiment",
  "/paper",
];

function DownloadModal({ onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Download Paper</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <p className="modal-subtitle">Choose a format to download your paper.</p>
        <div className="modal-options">
          <button className="modal-option-btn" onClick={() => window.open("http://localhost:8000/api/download/pdf", "_blank")}>
            <span className="modal-option-icon">📄</span>
            <span className="modal-option-label">PDF</span>
            <span className="modal-option-desc">Best for sharing and printing</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function Sidebar({ onDownloadClick }) {
  return (
    <nav className="sidebar">
      <div className="sidebar-title">Auto-Scientist</div>
      <ul>
        {stages.map((stage) => (
          <li key={stage.path} className={stage.under ? "sidebar-subitem" : ""}>
            <NavLink
              to={stage.path}
              end={stage.path === "/"}
              className={({ isActive }) =>
                `${isActive ? "sidebar-link active" : "sidebar-link"}${stage.under ? " nested" : ""}`
              }
            >
              {stage.label}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="sidebar-bottom">
        <button className="download-btn" onClick={onDownloadClick}>
          Download Paper
        </button>
      </div>
    </nav>
  );
}

function Layout({ children, onDownloadClick, canSaveRun, onSaveRun, saveRunStatus, onClearRun, clearRunStatus }) {
  const location = useLocation();
  const stageIndex = PIPELINE_STAGES.indexOf(location.pathname);
  const isStage = stageIndex !== -1;

  return (
    <div className="layout">
      <Sidebar onDownloadClick={onDownloadClick} />
      <main className="content">
        {isStage && (
          <div className="stage-header">
            <div className="stage-header-main">
              <div className="stage-progress">
                {PIPELINE_STAGES.map((_, i) => (
                  <div
                    key={i}
                    className={`stage-pip ${i < stageIndex ? "done" : i === stageIndex ? "active" : ""}`}
                  />
                ))}
              </div>
              <div className="stage-counter">
                Stage {stageIndex + 1} of {PIPELINE_STAGES.length}
              </div>
            </div>
            <div className="stage-save-area">
              {(saveRunStatus || clearRunStatus) && (
                <span className="stage-save-status">{clearRunStatus || saveRunStatus}</span>
              )}
              <button
                className="stage-clear-button"
                onClick={onClearRun}
                title="Clear the current pipeline and start over"
              >
                Clear run
              </button>
              <button
                className="stage-save-button"
                onClick={onSaveRun}
                disabled={!canSaveRun}
                title={canSaveRun ? "Save current run" : "Run Topic & Literature first"}
              >
                Save current run
              </button>
            </div>
          </div>
        )}
        {children}
      </main>
    </div>
  );
}

function App() {
  const [autonomous, setAutonomous] = useState(false);
  const [topic, setTopic] = useState("");
  const [litOutput, setLitOutput] = useState("");
  const [questions, setQuestions] = useState([]);
  const [selectedQuestion, setSelectedQuestion] = useState("");
  const [deepLitOutput, setDeepLitOutput] = useState("");
  const [proposalOutput, setProposalOutput] = useState("");
  const [experimentOutput, setExperimentOutput] = useState("");
  const [paperOutput, setPaperOutput] = useState("");
  const [showDownload, setShowDownload] = useState(false);
  const [saveRunStatus, setSaveRunStatus] = useState("");
  const [clearRunStatus, setClearRunStatus] = useState("");

  function completeLitOutput(output) {
    setLitOutput(output);
    setQuestions([]);
    setSelectedQuestion("");
    setDeepLitOutput("");
    setProposalOutput("");
    setExperimentOutput("");
    setPaperOutput("");
  }

  function completeSelectedQuestion(question) {
    setSelectedQuestion(question);
    setDeepLitOutput("");
    setProposalOutput("");
    setExperimentOutput("");
    setPaperOutput("");
  }

  function completeDeepLitOutput(output) {
    setDeepLitOutput(output);
    setProposalOutput("");
    setExperimentOutput("");
    setPaperOutput("");
  }

  function completeProposalOutput(output) {
    setProposalOutput(output);
    setExperimentOutput("");
    setPaperOutput("");
  }

  function completeExperimentOutput(output) {
    setExperimentOutput(output);
    setPaperOutput("");
  }

  async function saveCurrentRun() {
    if (!litOutput) return;
    setSaveRunStatus("Saving...");
    try {
      const label = window.prompt("Name this run", "");
      const res = await fetch("http://localhost:8000/api/runs/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label: label || undefined }),
      });
      if (!res.ok) {
        let detail = `Save failed (${res.status})`;
        try {
          const data = await res.json();
          detail = data.detail ? `${detail}: ${data.detail}` : detail;
        } catch {
          // Keep the status-only message when the backend does not return JSON.
        }
        throw new Error(detail);
      }
      setSaveRunStatus("Saved");
      setTimeout(() => setSaveRunStatus(""), 2000);
    } catch (e) {
      setSaveRunStatus(e.message);
      setTimeout(() => setSaveRunStatus(""), 3000);
    }
  }

  async function clearCurrentRun() {
    const confirmed = window.confirm(
      "Clear the current pipeline? This will remove the latest working outputs from Topic & Literature through Paper. Saved History runs will not be deleted."
    );
    if (!confirmed) return;

    setClearRunStatus("Clearing...");
    try {
      const res = await fetch("http://localhost:8000/api/runs/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_dir: "paper_runs/latest" }),
      });
      if (!res.ok) {
        let detail = `Clear failed (${res.status})`;
        try {
          const data = await res.json();
          detail = data.detail ? `${detail}: ${data.detail}` : detail;
        } catch {
          // Keep the status-only message when the backend does not return JSON.
        }
        throw new Error(detail);
      }
      setTopic("");
      setLitOutput("");
      setQuestions([]);
      setSelectedQuestion("");
      setDeepLitOutput("");
      setProposalOutput("");
      setExperimentOutput("");
      setPaperOutput("");
      setSaveRunStatus("");
      setClearRunStatus("Cleared");
      setTimeout(() => setClearRunStatus(""), 2000);
    } catch (e) {
      setClearRunStatus(e.message);
      setTimeout(() => setClearRunStatus(""), 3500);
    }
  }

  return (
    <BrowserRouter>
      <Layout
        onDownloadClick={() => setShowDownload(true)}
        canSaveRun={!!litOutput}
        onSaveRun={saveCurrentRun}
        saveRunStatus={saveRunStatus}
        onClearRun={clearCurrentRun}
        clearRunStatus={clearRunStatus}
      >
        <Routes>
  <Route path="/" element={<DashboardPage autonomous={autonomous} setAutonomous={setAutonomous} />} />
  <Route path="/topic" element={
    <TopicLiteraturePage
      autonomous={autonomous}
      topic={topic}
      onTopicSet={setTopic}
      litOutput={litOutput}
      onComplete={completeLitOutput}
    />}
  />
  <Route path="/research-question" element={
    <ResearchQuestionPage
      autonomous={autonomous}
      topic={topic}
      litOutput={litOutput}
      questions={questions}
      onQuestionsGenerated={setQuestions}
      selectedQuestion={selectedQuestion}
      onComplete={completeSelectedQuestion}
    />}
  />
  <Route path="/deep-literature" element={
    <DeepLiteraturePage
      autonomous={autonomous}
      selectedQuestion={selectedQuestion}
      deepLitOutput={deepLitOutput}
      onComplete={completeDeepLitOutput}
    />}
  />
  <Route path="/proposal" element={
    <ProposalPage
      autonomous={autonomous}
      deepLitOutput={deepLitOutput}
      proposalOutput={proposalOutput}
      onComplete={completeProposalOutput}
    />}
  />
  <Route path="/experiment" element={
    <ExperimentPage
      autonomous={autonomous}
      proposalOutput={proposalOutput}
      experimentOutput={experimentOutput}
      onComplete={completeExperimentOutput}
    />}
  />
  <Route path="/paper" element={
    <PaperPage
      autonomous={autonomous}
      experimentOutput={experimentOutput}
      paperOutput={paperOutput}
      onComplete={setPaperOutput}
    />}
  />
  <Route path="/history" element={<HistoryPage />} />
</Routes>
        {showDownload && <DownloadModal onClose={() => setShowDownload(false)} />}
      </Layout>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")).render(<App />);