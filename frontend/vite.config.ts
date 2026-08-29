import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server never talks to anything but the local backend. `strictPort`
// is deliberate: silently moving to another port would leave the API proxy
// pointing at nothing and produce a blank app with no obvious cause.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8756", changeOrigin: false },
      "/audio": { target: "http://127.0.0.1:8756", changeOrigin: false },
    },
  },
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 900 },
});
