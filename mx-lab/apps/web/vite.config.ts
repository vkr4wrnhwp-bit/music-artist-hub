import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { viteSingleFile } from 'vite-plugin-singlefile';
import path from 'node:path';

// Single-file build keeps the Phase 1 app fully offline-capable and portable:
// one HTML file runs from disk, a dock laptop, or a private artifact page.
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  resolve: {
    alias: {
      '@mxlab/domain': path.resolve(__dirname, '../../packages/domain/src/index.ts'),
    },
  },
  build: { chunkSizeWarningLimit: 4096 },
});
