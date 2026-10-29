// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

// The FastAPI engine (api/main.py) has no CORS: the browser calls /api on this server,
// which forwards to the engine, as the Next.js routes did before.
const API_URL = (process.env["ARENA_API_URL"] ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const proxy = {
  "/api": {
    target: API_URL,
    changeOrigin: true,
    timeout: 180_000,
    proxyTimeout: 180_000,
    rewrite: (p: string) => p.replace(/^\/api/, ""),
  },
};

export default defineConfig({
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
  vite: {
    server: { proxy },
    preview: { proxy },
  },
});
