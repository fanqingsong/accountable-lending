import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/lending/",
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api/lending": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
        timeout: 240_000,
      },
    },
  },
});
