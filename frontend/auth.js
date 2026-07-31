// Browser-side authentication helpers shared by sign-in, signup, and protected pages.
const config = window.APP_CONFIG;

if (!config) {
  throw new Error("config.js must be loaded before auth.js.");
}

const apiBaseUrl = String(config.API_BASE_URL || "").replace(/\/$/, "");
if (!apiBaseUrl) {
  throw new Error("Set API_BASE_URL in frontend/config.js.");
}

const CSRF_STORAGE_KEY = "gbtacCsrfToken";

function storeCsrfToken(token) {
  if (token) {
    sessionStorage.setItem(CSRF_STORAGE_KEY, token);
  }
}

function clearLocalSession() {
  sessionStorage.removeItem(CSRF_STORAGE_KEY);
  window.APP_USER = null;
}

async function readResponseBody(response) {
  const text = await response.text().catch(() => "");
  if (!text) return {};

  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

function getErrorMessage(body, fallback) {
  if (typeof body.detail === "string" && body.detail.trim()) {
    return body.detail;
  }

  if (Array.isArray(body.detail)) {
    const messages = body.detail
      .map((item) => item?.msg)
      .filter(Boolean);

    if (messages.length > 0) {
      return messages.join(" ");
    }
  }

  if (typeof body.message === "string" && body.message.trim()) {
    return body.message;
  }

  return fallback;
}

export async function signIn(email, password) {
  const response = await fetch(`${apiBaseUrl}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  const body = await readResponseBody(response);
  if (!response.ok) {
    const error = new Error(getErrorMessage(body, "Sign-in failed."));
    error.status = response.status;
    throw error;
  }

  storeCsrfToken(body.csrfToken);
  return body;
}

export async function signUp(displayName, email, password) {
  const response = await fetch(`${apiBaseUrl}/auth/signup`, {
    method: "POST",
    credentials: "include",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ displayName, email, password }),
  });

  const body = await readResponseBody(response);
  if (!response.ok) {
    const error = new Error(getErrorMessage(body, "Account creation failed."));
    error.status = response.status;
    throw error;
  }

  storeCsrfToken(body.csrfToken);
  return body;
}

export async function signOut() {
  try {
    await apiFetch("/auth/logout", { method: "POST" });
  } finally {
    clearLocalSession();
    window.location.replace("index.html");
  }
}

export async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const method = String(options.method || "GET").toUpperCase();

  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfToken = sessionStorage.getItem(CSRF_STORAGE_KEY);
    if (csrfToken) {
      headers.set("X-CSRF-Token", csrfToken);
    }
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return fetch(`${apiBaseUrl}${normalizedPath}`, {
    ...options,
    method,
    headers,
    credentials: "include",
  });
}

export async function getCurrentUser() {
  const response = await apiFetch("/auth/me", {
    headers: { Accept: "application/json" },
  });
  const body = await readResponseBody(response);

  if (!response.ok) {
    const error = new Error(
      getErrorMessage(
        body,
        `Unable to load the signed-in user (${response.status}).`
      )
    );
    error.status = response.status;
    throw error;
  }

  storeCsrfToken(body.csrfToken);
  return body;
}

export async function requireSignedInUser() {
  try {
    return await getCurrentUser();
  } catch (error) {
    if (error.status === 401) {
      clearLocalSession();
      window.location.replace("index.html");
      return null;
    }
    throw error;
  }
}
