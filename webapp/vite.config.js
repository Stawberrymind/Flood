import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  // GitHub Pages serves this repo's docs/ at /Flood/
  base: '/Flood/',
  plugins: [react(), {
    name: 'neutral-translator-notes',
    apply: 'build',
    // Match the metadata-only cleanup in pipeline/sanitize_web_bundle.py.
    // Doing it during rendering also makes the chunk hashes describe the
    // cleaned content, so publishing no longer needs a separate manual step.
    renderChunk(code) {
      const cleaned = code.replaceAll(
        'Citation 1: OpenAI research paper',
        'Citation 1: a research paper',
      );
      return cleaned === code ? null : {code: cleaned, map: null};
    },
  }],
  build: {outDir: 'dist', chunkSizeWarningLimit: 1200},
})
