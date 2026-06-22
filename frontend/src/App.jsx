import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage.jsx";
import TopicLiteraturePage from "./pages/TopicLiteraturePage.jsx";
import ResearchQuestionPage from "./pages/ResearchQuestionPage.jsx";
import DeepLiteraturePage from "./pages/DeepLiteraturePage.jsx";
import ProposalPage from "./pages/ProposalPage.jsx";
import ExperimentPage from "./pages/ExperimentPage.jsx";
import PaperPage from "./pages/PaperPage.jsx";
import ReviewPage from "./pages/ReviewPage.jsx";
import RebuttalPage from "./pages/RebuttalPage.jsx";
import CitationsPage from "./pages/CitationsPage.jsx";
import FilesPage from "./pages/FilesPage.jsx";
import SubmissionPage from "./pages/SubmissionPage.jsx";
import "./styles/app.css";

const stages = [
  { label: "Dashboard", path: "/" },
  { label: "Topic & Literature", path: "/topic" },
  { label: "Research Question", path: "/research-question" },
  { label: "Deep Literature", path: "/deep-literature" },
  { label: "Proposal", path: "/proposal" },
  { label: "Experiment", path: "/experiment" },
  { label: "Paper", path: "/paper" },
  { label: "Review", path: "/review" },
  { label: "Rebuttal", path: "/rebuttal" },
  { label: "Citations", path: "/citations" },
  { label: "Files", path: "/files" },
  { label: "Submission", path: "/submission" },
];

function Sidebar() {
  return (
    <nav className="sidebar">
      <div className="sidebar-title">Auto-Scientist</div>
      <ul>
        {stages.map((stage) => (
          <li key={stage.path}>
            <NavLink
              to={stage.path}
              end={stage.path === "/"}
              className={({ isActive }) =>
                isActive ? "sidebar-link active" : "sidebar-link"
              }
            >
              {stage.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function Layout({ children }) {
  return (
    <div className="layout">
      <Sidebar />
      <main className="content">{children}</main>
    </div>
  );
}

function App() {
  const [autonomous, setAutonomous] = useState(false);

  const [litOutput, setLitOutput] = useState("");
  const [selectedQuestion, setSelectedQuestion] = useState("");
  const [deepLitOutput, setDeepLitOutput] = useState("");
  const [proposalOutput, setProposalOutput] = useState("");
  const [experimentOutput, setExperimentOutput] = useState("");
  const [paperOutput, setPaperOutput] = useState("");
  const [reviewOutput, setReviewOutput] = useState("");

  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<DashboardPage autonomous={autonomous} setAutonomous={setAutonomous} />} />
          <Route path="/topic" element={<TopicLiteraturePage autonomous={autonomous} onComplete={setLitOutput} />} />
          <Route path="/research-question" element={<ResearchQuestionPage autonomous={autonomous} litOutput={litOutput} onComplete={setSelectedQuestion} />} />
          <Route path="/deep-literature" element={<DeepLiteraturePage autonomous={autonomous} selectedQuestion={selectedQuestion} onComplete={setDeepLitOutput} />} />
          <Route path="/proposal" element={<ProposalPage autonomous={autonomous} deepLitOutput={deepLitOutput} onComplete={setProposalOutput} />} />
          <Route path="/experiment" element={<ExperimentPage autonomous={autonomous} proposalOutput={proposalOutput} onComplete={setExperimentOutput} />} />
          <Route path="/paper" element={<PaperPage autonomous={autonomous} experimentOutput={experimentOutput} onComplete={setPaperOutput} />} />
          <Route path="/review" element={<ReviewPage autonomous={autonomous} paperOutput={paperOutput} onComplete={setReviewOutput} />} />
          <Route path="/rebuttal" element={<RebuttalPage autonomous={autonomous} reviewOutput={reviewOutput} />} />
          <Route path="/citations" element={<CitationsPage autonomous={autonomous} />} />
          <Route path="/files" element={<FilesPage autonomous={autonomous} />} />
          <Route path="/submission" element={<SubmissionPage autonomous={autonomous} />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")).render(<App />);