import { cpSync } from "node:fs";
import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const outputDirectory = resolve(__dirname, "../representation");

export default defineConfig({
  base: "/assets/representation/",
  plugins: [
    react(),
    {
      name: "copy-cascade-runtime",
      closeBundle() {
        cpSync(
          resolve(
            __dirname,
            "node_modules/cascade-core/dist/cascade-worker.js",
          ),
          resolve(outputDirectory, "cascade-worker.js"),
        );
        cpSync(
          resolve(
            __dirname,
            "node_modules/cascade-core/dist/cascadestudio.wasm",
          ),
          resolve(outputDirectory, "cascadestudio.wasm"),
        );
      },
    },
  ],
  resolve: {
    dedupe: ["react", "react-dom"],
    alias: {
      react: resolve(__dirname, "node_modules/react"),
      "react-dom": resolve(__dirname, "node_modules/react-dom"),
    },
  },
  build: {
    outDir: outputDirectory,
    emptyOutDir: true,
    chunkSizeWarningLimit: 1800,
  },
});
