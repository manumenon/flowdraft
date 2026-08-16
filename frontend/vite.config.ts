// Imported from 'vitest/config' rather than 'vite' so the `test` block below
// is typed (it re-exports Vite's own `defineConfig` merged with Vitest's
// `UserConfig['test']` — Vitest reads this file directly, no separate
// vitest.config.ts needed).
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  worker: {
    format: 'es', // Compiles Web Workers as ES Modules
    // layoutCore.ts (imported by layout.worker.ts) imports real elkjs for its
    // Node-callable path (layout-cli.ts / vitest); elkjs's constructor has a
    // guarded, never-actually-invoked `require('web-worker')` for a Node-only
    // fallback that isn't installed and isn't needed here (the browser Worker
    // path never takes that branch). Externalize it so the worker bundler
    // doesn't try to resolve it — same fix already applied to layout-cli.ts's
    // esbuild bundle via --external:web-worker.
    rollupOptions: {
      external: ['web-worker'],
    },
  },
  build: {
    // Same "web-worker" externalization as the `worker` block above, but for
    // the MAIN app bundle: useFlowLayout.ts now imports resolveLabelPositions
    // directly from layoutCore.ts (not just via layout.worker.ts), which
    // pulls elkjs's guarded, never-invoked `require('web-worker')` Node
    // fallback into the main build's module graph too. Without this, the
    // production `vite build` fails outright ("Rolldown failed to resolve
    // import 'web-worker'") since only the worker chunk's bundler had this
    // external configured.
    rollupOptions: {
      external: ['web-worker'],
    },
  },
  server: {
    port: 3000,
  },
  test: {
    // Quality checks are pure geometry over layoutCore.ts's Node-callable
    // output — no DOM needed, so 'node' is the cheapest correct environment.
    environment: 'node',
  },
});
