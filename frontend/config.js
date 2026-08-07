// Runtime settings shared by local Vite and the containerized Nginx frontend.
//
// The browser always calls the frontend's own origin. During local development,
// Vite proxies /api/v1 requests to the five FastAPI services. In Docker,
// Nginx performs the same routing with Docker Compose service names.
window.APP_CONFIG = Object.freeze({
  // Firebase Web SDK configuration is public client configuration. Server-side
  // service-account credentials must never be added to this file.
  FIREBASE_CONFIG: Object.freeze({
    apiKey: "AIzaSyAxNTc3TmejhFI7Uaxk95c1pix2pwDK2-o",
    authDomain: "gbtac-dsm.firebaseapp.com",
    projectId: "gbtac-dsm",
    storageBucket: "gbtac-dsm.firebasestorage.app",
    messagingSenderId: "1079470552977",
    appId: "1:1079470552977:web:ef2cf0cf967d3e18228c30",
  }),

  API_BASE_URL: `${window.location.origin}/api/v1`,
});
