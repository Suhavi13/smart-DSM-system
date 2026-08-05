// Firebase Authentication helpers shared by sign-in, signup, reset, and protected pages.
import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signOut as firebaseSignOut,
  updateProfile,
} from "https://www.gstatic.com/firebasejs/12.16.0/firebase-auth.js";

import { firebaseAuth, firebaseReady } from "./firebase-client.js";

const config = window.APP_CONFIG;
if (!config) {
  throw new Error("config.js must be loaded before auth.js.");
}

const apiBaseUrl = String(config.API_BASE_URL || "").replace(/\/$/, "");
if (!apiBaseUrl) {
  throw new Error("Set API_BASE_URL in frontend/config.js.");
}

function waitForInitialAuthState() {
  return new Promise((resolve, reject) => {
    let unsubscribe = () => {};
    unsubscribe = onAuthStateChanged(
      firebaseAuth,
      (user) => {
        unsubscribe();
        resolve(user);
      },
      (error) => {
        unsubscribe();
        reject(error);
      }
    );
  });
}

const initialAuthState = firebaseReady.then(waitForInitialAuthState);

async function readResponseBody(response) {
  const text = await response.text().catch(() => "");
  if (!text) return {};

  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

function getApiErrorMessage(body, fallback) {
  if (typeof body.detail === "string" && body.detail.trim()) {
    return body.detail;
  }
  return fallback;
}

function firebaseErrorMessage(error, fallback) {
  const messages = {
    "auth/email-already-in-use": "An account already exists for this email.",
    "auth/invalid-credential": "Invalid email or password.",
    "auth/invalid-email": "Enter a valid email address.",
    "auth/missing-password": "Enter your password.",
    "auth/network-request-failed": "Unable to reach Firebase. Check your connection.",
    "auth/operation-not-allowed": "Email/password sign-in is not enabled in Firebase.",
    "auth/too-many-requests": "Too many attempts. Try again later.",
    "auth/unauthorized-domain": "This website domain is not authorized in Firebase.",
    "auth/user-disabled": "This account has been disabled.",
    "auth/user-not-found": "If the account exists, check the email for next steps.",
    "auth/weak-password": "Choose a stronger password with at least 8 characters.",
  };
  return messages[error?.code] || error?.message || fallback;
}

function makeAuthError(error, fallback) {
  const wrapped = new Error(firebaseErrorMessage(error, fallback));
  wrapped.code = error?.code;
  return wrapped;
}

export async function signIn(email, password) {
  try {
    await firebaseReady;
    await signInWithEmailAndPassword(
      firebaseAuth,
      String(email || "").trim(),
      password
    );
    return await getCurrentUser();
  } catch (error) {
    if (error?.status) throw error;
    throw makeAuthError(error, "Sign-in failed.");
  }
}

export async function signUp(displayName, email, password) {
  try {
    await firebaseReady;
    const credential = await createUserWithEmailAndPassword(
      firebaseAuth,
      String(email || "").trim(),
      password
    );

    const normalizedName = String(displayName || "").trim().replace(/\s+/g, " ");
    if (normalizedName) {
      await updateProfile(credential.user, { displayName: normalizedName });
      await credential.user.getIdToken(true);
    }

    return await getCurrentUser();
  } catch (error) {
    if (error?.status) throw error;
    throw makeAuthError(error, "Account creation failed.");
  }
}

export async function requestPasswordReset(email) {
  try {
    await firebaseReady;
    await sendPasswordResetEmail(
      firebaseAuth,
      String(email || "").trim()
    );
  } catch (error) {
    throw makeAuthError(error, "Unable to send the password-reset email.");
  }
}

export async function signOut() {
  try {
    await firebaseSignOut(firebaseAuth);
  } finally {
    window.APP_USER = null;
    window.location.replace("index.html");
  }
}

export async function apiFetch(path, options = {}) {
  await initialAuthState;
  const firebaseUser = firebaseAuth.currentUser;
  if (!firebaseUser) {
    const error = new Error("Authentication is required.");
    error.status = 401;
    throw error;
  }

  const idToken = await firebaseUser.getIdToken();
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${idToken}`);

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return fetch(`${apiBaseUrl}${normalizedPath}`, {
    ...options,
    headers,
  });
}

export async function getCurrentUser() {
  const response = await apiFetch("/auth/me", {
    headers: { Accept: "application/json" },
  });
  const body = await readResponseBody(response);

  if (!response.ok) {
    const error = new Error(
      getApiErrorMessage(
        body,
        `Unable to load the signed-in user (${response.status}).`
      )
    );
    error.status = response.status;
    throw error;
  }

  return body;
}

export async function requireSignedInUser() {
  try {
    return await getCurrentUser();
  } catch (error) {
    if (error.status === 401) {
      await firebaseSignOut(firebaseAuth).catch(() => {});
      window.APP_USER = null;
      window.location.replace("index.html");
      return null;
    }
    throw error;
  }
}
