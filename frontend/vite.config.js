// Vite serves the browser UI and proxies API paths to independently running
// FastAPI services during Stage 4 local development.
import { resolve } from "node:path";
import { defineConfig } from "vite";

const projectPages = [
  "index.html",
  "signup.html",
  "forgot-password.html",
  "dashboard.html",
  "sensors.html",
  "recommendations.html",
];

const pageInputs = Object.fromEntries(
  projectPages.map((fileName) => [
    fileName.replace(/\.html$/, ""),
    resolve(import.meta.dirname, fileName),
  ])
);

export default defineConfig({
  build: {
    rollupOptions: {
      input: pageInputs,
      // Firebase is loaded from Google's official ESM CDN. Keeping it external
      // avoids copying the SDK into the Vite bundle.
      external: [/^https:\/\/www\.gstatic\.com\/firebasejs\//],
    },
  },

  server: {
    host: "localhost",
    port: 5500,
    strictPort: true,
    proxy: {
      "/api/v1/auth": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      "/api/v1/sensors": {
        target: "http://localhost:8002",
        changeOrigin: true,
      },
      "/api/v1/dashboard": {
        target: "http://localhost:8002",
        changeOrigin: true,
      },
      "/api/v1/external": {
        target: "http://localhost:8003",
        changeOrigin: true,
      },
      "/api/v1/recommendations": {
        target: "http://localhost:8004",
        changeOrigin: true,
      },
      "/api/v1/decisions": {
        target: "http://localhost:8005",
        changeOrigin: true,
      },
    },
  },
});
