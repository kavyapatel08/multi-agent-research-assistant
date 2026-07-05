/**
 * api.js — Backend communication layer.
 * Reads backend URL from VITE_API_URL env var only.
 * Never exposes any API keys.
 */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Submit a research topic and stream progress + result via SSE.
 *
 * @param {string} topic - The research topic
 * @param {object} callbacks
 * @param {function} callbacks.onProgress - Called with {step, label} on each progress event
 * @param {function} callbacks.onResult   - Called with the final result object
 * @param {function} callbacks.onError    - Called with an error message string
 * @returns {function} abort - Call to cancel the request
 */
export function streamResearch(topic, { onProgress, onResult, onError }) {
  const controller = new AbortController();

  const run = async () => {
    try {
      const response = await fetch(`${API_BASE}/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic }),
        signal: controller.signal,
      });

      if (!response.ok) {
        let errMsg = `Server error: ${response.status}`;
        try {
          const errJson = await response.json();
          errMsg = errJson.detail || errMsg;
        } catch (_) {}
        onError(errMsg);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop(); // incomplete chunk stays in buffer

        for (const part of parts) {
          if (!part.trim()) continue;

          // Parse SSE format: "event: X\ndata: Y"
          const eventMatch = part.match(/^event:\s*(\S+)/m);
          const dataMatch = part.match(/^data:\s*(.+)$/ms);

          if (!eventMatch || !dataMatch) continue;

          const eventType = eventMatch[1];
          let data;
          try {
            data = JSON.parse(dataMatch[1].trim());
          } catch (_) {
            continue;
          }

          if (eventType === "progress" && onProgress) {
            onProgress(data);
          } else if (eventType === "result" && onResult) {
            onResult(data);
          } else if (eventType === "error" && onError) {
            onError(data.message || "An error occurred.");
          }
        }
      }
    } catch (err) {
      if (err.name === "AbortError") return;
      onError(err.message || "Network error. Is the backend running?");
    }
  };

  run();
  return () => controller.abort();
}

/**
 * Health check — returns true if backend is reachable.
 */
export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { method: "GET" });
    return res.ok;
  } catch (_) {
    return false;
  }
}
