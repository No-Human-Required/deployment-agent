import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "VITE_");
  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        // Companion apps/agent BFF (settings, orchestrator, liara, …)
        "/api": {
          target: env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000",
          changeOrigin: true,
        },
        // Liveness / readiness are outside /api on the companion
        "/health": {
          target: env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000",
          changeOrigin: true,
        },
        "/ready": {
          target: env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
  };
});
