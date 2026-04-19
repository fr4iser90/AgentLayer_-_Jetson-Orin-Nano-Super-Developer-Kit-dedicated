import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Production build → apps/frontend/dist (served by FastAPI at /app)
export default defineConfig({
  plugins: [react()],
  base: "/app/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/auth": { target: "http://127.0.0.1:8080", changeOrigin: true },
      "/v1": { target: "http://127.0.0.1:8080", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:8080", changeOrigin: true },
      "/openapi.json": { target: "http://127.0.0.1:8080", changeOrigin: true },
    },
  },
});
