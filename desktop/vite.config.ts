import { defineConfig } from 'vite'

// The renderer is a plain page bundled by Vite and loaded from disk by Electron,
// so asset paths are relative. `npm run preview` serves the same page in a browser
// with a mocked bridge (src/renderer/mock.ts) for working on the UI without Electron;
// the frontend's sample BVH is served from its public folder for that.
export default defineConfig({
  root: 'src/renderer',
  base: './',
  publicDir: '../../../frontend/public/samples',
  build: { outDir: '../../dist/renderer', emptyOutDir: true, target: 'esnext' },  // Electron's Chromium supports top-level await
  server: { port: 5174, open: false },
})
