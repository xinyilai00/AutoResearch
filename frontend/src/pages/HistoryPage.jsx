import React, { useEffect, useState } from "react";
import { API_BASE_URL } from "../api/client.js";

export default function HistoryPage() {
  const [savedRuns, setSavedRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [selectedRunIds, setSelectedRunIds] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");

  useEffect(() => {
    loadSavedRuns();
  }, []);

  async function loadSavedRuns() {
    setHistoryLoading(true);
    setHistoryError("");
    try {
      const res = await fetch(`${API_BASE_URL}/api/runs/saved`);
      if (!res.ok) throw new Error("Could not load saved runs.");
      const data = await res.json();
      const runs = data.runs || [];
      setSavedRuns(runs);
      setSelectedRunIds((ids) => ids.filter((id) => runs.some((run) => run.id === id)));
    } catch (e) {
      setHistoryError(e.message);
    } finally {
      setHistoryLoading(false);
    }
  }

  async function openSavedRun(runId) {
    setHistoryError("");
    try {
      const res = await fetch(`${API_BASE_URL}/api/runs/saved/${runId}`);
      if (!res.ok) throw new Error("Could not open saved run.");
      const data = await res.json();
      setSelectedRun(data);
    } catch (e) {
      setHistoryError(e.message);
    }
  }

  function toggleRunSelection(runId) {
    setSelectedRunIds((ids) => (
      ids.includes(runId) ? ids.filter((id) => id !== runId) : [...ids, runId]
    ));
  }

  async function deleteSelectedRuns() {
    const count = selectedRunIds.length;
    if (count === 0) return;
    if (!window.confirm(`Delete ${count} saved run${count === 1 ? "" : "s"}?`)) return;

    setHistoryError("");
    try {
      const results = await Promise.all(selectedRunIds.map(async (runId) => {
        const res = await fetch(`${API_BASE_URL}/api/runs/saved/${runId}`, { method: "DELETE" });
        if (!res.ok) throw new Error("Could not delete one or more saved runs.");
        return runId;
      }));
      setSavedRuns((runs) => runs.filter((run) => !results.includes(run.id)));
      setSelectedRunIds([]);
      if (selectedRun && results.includes(selectedRun.id)) setSelectedRun(null);
    } catch (e) {
      setHistoryError(e.message);
    }
  }

  function statusLabel(statusValue) {
    return statusValue ? statusValue.replaceAll("_", " ") : "not run";
  }

  function filenameSafe(value) {
    return (value || "saved-run")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 80) || "saved-run";
  }

  function downloadSelectedRunPaper() {
    if (!selectedRun) return;
    const paperOutput = selectedRun.stages?.paper?.output || "";
    if (!paperOutput.trim()) return;

    const label = filenameSafe(selectedRun.label || selectedRun.summary?.topic || selectedRun.id);
    const blob = new Blob([paperOutput], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${label}-${selectedRun.id || "version"}.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="stage-page paper-history-page">
      <h1>History</h1>
      <p>Saved pipeline runs, including what worked, what failed, selected repos, outputs, and experiment logs.</p>

      <div className="history-layout">
        <div className="history-panel">
          <div className="history-actions">
            <button className="run-button secondary" onClick={loadSavedRuns}>Refresh</button>
            <button className="history-delete-selected-button" onClick={deleteSelectedRuns} disabled={selectedRunIds.length === 0}>
              Delete selected{selectedRunIds.length ? ` (${selectedRunIds.length})` : ""}
            </button>
          </div>
          {historyLoading && <div className="history-muted">Loading saved runs...</div>}
          {historyError && <div className="error-box">{historyError}</div>}
          {!historyLoading && savedRuns.length === 0 && <div className="warning-box">No saved runs yet.</div>}
          <div className="history-list">
            {savedRuns.map((run) => (
              <div key={run.id} className={selectedRun?.id === run.id ? "history-item active" : "history-item"}>
                <label className="history-select-control" aria-label={`Select ${run.label || "saved run"} for deletion`}>
                  <input
                    type="checkbox"
                    checked={selectedRunIds.includes(run.id)}
                    onChange={() => toggleRunSelection(run.id)}
                  />
                </label>
                <button className="history-open-button" onClick={() => openSavedRun(run.id)}>
                  <span className="history-title">{run.label || "Untitled run"}</span>
                  <span className="history-date">{run.saved_at ? new Date(run.saved_at).toLocaleString() : ""}</span>
                  <span className={run.errors?.length ? "history-badge failed" : "history-badge"}>
                    {run.errors?.length ? `${run.errors.length} issue${run.errors.length === 1 ? "" : "s"}` : "saved"}
                  </span>
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="history-detail">
          {!selectedRun && <div className="history-muted">Select a saved run to inspect its outputs and errors.</div>}
          {selectedRun && (
            <>
              <h2>{selectedRun.label || "Saved run"}</h2>
              <div className="history-meta">
                <div><strong>Saved:</strong> {new Date(selectedRun.saved_at).toLocaleString()}</div>
                <div><strong>Topic:</strong> {selectedRun.summary?.topic || "Unknown"}</div>
                <div><strong>Repo:</strong> {selectedRun.summary?.selected_repo_url ? (
                  <a href={selectedRun.summary.selected_repo_url} target="_blank" rel="noreferrer">{selectedRun.summary.selected_repo_name || selectedRun.summary.selected_repo_url}</a>
                ) : "Not selected"}</div>
              </div>

              {selectedRun.summary?.errors?.length > 0 && (
                <div className="history-errors">
                  <h3>Errors / Could Not Run</h3>
                  {selectedRun.summary.errors.map((err, i) => (
                    <div key={`${err.stage}-${i}`} className="history-error-row"><strong>{err.stage}</strong>: {err.message}</div>
                  ))}
                </div>
              )}

              <div className="history-stage-grid">
                {Object.entries(selectedRun.stages || {})
                  .filter(([stage]) => stage !== "review")
                  .map(([stage, info]) => (
                  <details key={stage} className="history-stage">
                    <summary>
                      <span>{stage.replaceAll("_", " ")}</span>
                      <span className={info.error ? "history-badge failed" : "history-badge"}>{info.error ? "issue" : statusLabel(info.status)}</span>
                    </summary>
                    {info.error && <div className="history-error-row">{info.error}</div>}
                    <pre>{info.output || "No output saved for this stage."}</pre>
                  </details>
                ))}
              </div>

              <div className="history-detail-footer">
                <button
                  className="history-download-version-button"
                  onClick={downloadSelectedRunPaper}
                  disabled={!selectedRun.stages?.paper?.output?.trim()}
                >
                  Download this version
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
