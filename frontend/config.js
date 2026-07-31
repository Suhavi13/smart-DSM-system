// Chooses the API base URL for local static servers and deployed same-origin hosting.
const localFrontendPorts = new Set(["5500", "5501", "5173"]);
const isSeparateLocalFrontend =
  ["localhost", "127.0.0.1"].includes(window.location.hostname) &&
  localFrontendPorts.has(window.location.port);

window.APP_CONFIG = Object.freeze({
  // In cloud deployment the FastAPI app serves this frontend, so both use the
  // same origin. Local static servers continue to call port 8000.
  API_BASE_URL: isSeparateLocalFrontend
    ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
    : `${window.location.origin}/api/v1`,
});
