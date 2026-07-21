import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import electron from 'vite-plugin-electron';
import renderer from 'vite-plugin-electron-renderer';
import { fileURLToPath, URL } from 'node:url';

// Vite drives both the React renderer and the Electron main/preload builds.
// `npm run dev` starts the renderer dev server and (via vite-plugin-electron)
// compiles main/preload and launches Electron automatically.
export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  plugins: [
    react(),
    electron([
      {
        // Main process. Output is forced to CommonJS regardless of the
        // package's module type — Electron's main/preload loaders are most
        // reliably tested against CJS; ESM preload support is newer and has
        // had version-dependent quirks that can silently break contextBridge.
        entry: 'electron/main.ts',
        vite: {
          build: {
            outDir: 'dist-electron',
            rollupOptions: {
              output: { format: 'cjs', entryFileNames: '[name].js' },
            },
          },
        },
      },
      {
        // Preload — runs in the renderer with limited Node access.
        entry: 'electron/preload.ts',
        onstart(args) {
          args.reload();
        },
        vite: {
          build: {
            outDir: 'dist-electron',
            rollupOptions: {
              output: { format: 'cjs', entryFileNames: '[name].js' },
            },
          },
        },
      },
    ]),
    renderer(),
  ],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: false,
  },
  build: {
    outDir: 'dist',
  },
});
