// Small wrapper around authenticated API calls that returns useful errors.
import { apiFetch } from "./auth.js";

export async function apiRequest(path, options = {}) {
  const response = await apiFetch(path, options);

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const errorData = await response.json();
      message = errorData.detail || message;
    } catch {
      // Keep the default error message.
    }

    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return response;
}

export async function apiGet(path) {
  const response = await apiRequest(path, {
    headers: { Accept: "application/json" },
  });
  return response.json();
}
