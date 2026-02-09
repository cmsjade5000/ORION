import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Local dev: Vite on :5173, API on :8787.
// Production: `npm run build` then `npm start` serves the static build + API from Express.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8787",
        changeOrigin: true,
      },
    },
  },
});
