// Initializes the Firebase Web SDK from the public project configuration.
import { getApps, initializeApp } from "https://www.gstatic.com/firebasejs/12.16.0/firebase-app.js";
import {
  browserLocalPersistence,
  getAuth,
  setPersistence,
} from "https://www.gstatic.com/firebasejs/12.16.0/firebase-auth.js";

const config = window.APP_CONFIG;
if (!config) {
  throw new Error("config.js must be loaded before Firebase modules.");
}

const firebaseConfig = config.FIREBASE_CONFIG || {};
const requiredKeys = ["apiKey", "authDomain", "projectId", "appId"];
const missingKeys = requiredKeys.filter((key) => {
  const value = String(firebaseConfig[key] || "").trim();
  return !value || value.includes("YOUR_") || value.includes("PASTE_");
});

if (missingKeys.length > 0) {
  throw new Error(
    `Complete FIREBASE_CONFIG in frontend/config.js. Missing: ${missingKeys.join(", ")}.`
  );
}

const firebaseApp = getApps()[0] || initializeApp(firebaseConfig);
export const firebaseAuth = getAuth(firebaseApp);

// Keep the user signed in across refreshes. Firebase still refreshes short-lived
// ID tokens automatically and the API verifies every token server-side.
export const firebaseReady = setPersistence(
  firebaseAuth,
  browserLocalPersistence
);
