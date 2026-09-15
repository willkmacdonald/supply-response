import {resolve} from "node:path";
import {defineConfig} from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      {find: /^\.\/auth\/msal$/, replacement: resolve(import.meta.dirname, "e2e/mockMsal.ts")},
      {find: /^\.\/msal$/, replacement: resolve(import.meta.dirname, "e2e/mockMsal.ts")},
    ],
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
