// Local frontend dev server settings.
import { defineConfig } from "vite";

export default defineConfig({
  server: {
    host: "localhost",
    port: 5500,
    strictPort: true,
  },
});
