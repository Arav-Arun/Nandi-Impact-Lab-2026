import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // NANDI backend. NOTE: port 8000 is taken by an unrelated ASR/TTS service on
      // this machine, so the backend runs on 8137. Change this if you run it elsewhere.
      "/api": { target: "http://localhost:8137", changeOrigin: true, ws: true },
      "/health": { target: "http://localhost:8137", changeOrigin: true },
    },
  },
});
