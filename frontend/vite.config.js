// Local frontend dev server settings.
import { defineConfig } from "vite";

export default defineConfig({
  build: {
    rollupOptions: {
      // Firebase is loaded from Google's official ESM CDN so the same source
      // works with Vite and a simple static/FastAPI file server.
      external: [/^https:\/\/www\.gstatic\.com\/firebasejs\//],
    },
  },
  server: {
    host: "localhost",
    port: 5500,
    strictPort: true,
  },
});
