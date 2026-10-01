import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/ws": { target: "ws://127.0.0.1:8766", ws: true } } },
  // three.js alone is about 560 kB; it is its own chunk and loads only when the first hologram is shown
  build: { outDir: "dist", chunkSizeWarningLimit: 600 },
  test: { environment: "node" },
});
