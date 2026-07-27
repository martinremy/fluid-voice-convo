import { defineConfig } from "vite";

export default defineConfig({
  server: {
    proxy: {
      "/offer": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
  },
});
