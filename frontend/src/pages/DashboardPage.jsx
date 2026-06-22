import React from "react";
import { useNavigate } from "react-router-dom";

export default function DashboardPage({ autonomous, setAutonomous }) {
  const navigate = useNavigate();

  return (
    <div className="dashboard">
      <h1>Auto-Scientist</h1>
      <p>An autonomous research pipeline. Select a stage from the sidebar, or run the full pipeline below.</p>

      <div className="autonomous-toggle">
        <label>
          <input
            type="checkbox"
            checked={autonomous}
            onChange={() => setAutonomous(!autonomous)}
          />
          {" "}Fully Autonomous Mode
        </label>
        <p className="toggle-description">
          {autonomous
            ? "The pipeline will run all stages automatically after you select a research question."
            : "You will be prompted to review and confirm each stage before the next one runs."}
        </p>
      </div>

      <button className="start-button" onClick={() => navigate("/topic")}>
        Start Pipeline
      </button>
    </div>
  );
}