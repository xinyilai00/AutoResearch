import React, { useState } from "react";

export default function FeedbackBar({ onRerun, disabled }) {
  const [feedback, setFeedback] = useState("");

  function handleSubmit() {
    if (!feedback.trim()) return;
    onRerun(feedback.trim());
    setFeedback("");
  }

  return (
    <div className="feedback-bar">
      <input
        className="feedback-input"
        type="text"
        placeholder="Type feedback to refine this stage..."
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
        disabled={disabled}
        onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
      />
      <button
        className="feedback-button"
        onClick={handleSubmit}
        disabled={disabled || !feedback.trim()}
      >
        Rerun
      </button>
    </div>
  );
}