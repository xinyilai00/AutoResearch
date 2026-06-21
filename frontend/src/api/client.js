const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function getPipelineStatus() {
  const response = await fetch(`${API_BASE_URL}/api/pipeline/status`);
  if (!response.ok) {
    throw new Error(`Status request failed: ${response.status}`);
  }
  return response.json();
}

export async function startPipeline(topic) {
  const response = await fetch(`${API_BASE_URL}/api/pipeline/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });
  if (!response.ok) {
    throw new Error(`Pipeline request failed: ${response.status}`);
  }
  return response.json();
}
