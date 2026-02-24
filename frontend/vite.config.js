import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import path from "path";
import { visualizer } from "rollup-plugin-visualizer";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    svelte(),
    // Bundle analyzer - generates stats.html after build
    visualizer({
      filename: "dist/stats.html",
      open: false,
      gzipSize: true,
      brotliSize: true,
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      $lib: path.resolve(__dirname, "./src/lib"),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8082",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    cssCodeSplit: true, // Enable CSS code splitting per chunk
    cssTarget: "esnext", // Modern CSS features support
    minify: "esbuild", // Fast minification with tree-shaking
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // Separate large workflow editor CSS into dedicated chunk
          if (id.includes("WorkflowEditor.svelte")) {
            return "workflow-editor";
          }
          // Separate large project detail CSS into dedicated chunk
          if (id.includes("projects/[id]/+page.svelte")) {
            return "project-detail";
          }
          // Separate prediction capture page CSS
          if (id.includes("predictions/capture/+page.svelte")) {
            return "prediction-capture";
          }
          // Vendor chunk for node_modules
          if (id.includes("node_modules")) {
            return "vendor";
          }
        },
      },
    },
  },
});
