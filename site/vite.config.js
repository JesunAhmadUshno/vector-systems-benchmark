import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// The site reads ../results/*.json and the repo's Markdown at build time, so every number on the page is generated, never typed.
export default defineConfig({
  base: '/vector-systems-benchmark/',
  plugins: [react()],
  server: { fs: { allow: ['..'] } },
});
