// Chooses the API base URL for local static servers and deployed same-origin hosting.
const localFrontendPorts = new Set(["5500", "5501", "5173"]);
const isSeparateLocalFrontend =
  ["localhost", "127.0.0.1"].includes(window.location.hostname) &&
  localFrontendPorts.has(window.location.port);

window.APP_CONFIG = Object.freeze({
  // Copy this public web configuration from Firebase Console:
  // Project settings > General > Your apps > Web app.
  FIREBASE_CONFIG: Object.freeze({
    apiKey: "AIzaSyAxNTc3TmejhFI7Uaxk95c1pix2pwDK2-o",
    authDomain: "gbtac-dsm.firebaseapp.com",
    projectId: "gbtac-dsm",
    storageBucket: "gbtac-dsm.firebasestorage.app",
    messagingSenderId: "1079470552977",
    appId: "1:1079470552977:web:ef2cf0cf967d3e18228c30",
  }),

  // In cloud deployment the FastAPI app serves this frontend, so both use the
  // same origin. Local static servers continue to call port 8000.
  API_BASE_URL: isSeparateLocalFrontend
    ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
    : `${window.location.origin}/api/v1`,
});
