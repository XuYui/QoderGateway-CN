import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../src/qoder2api/static',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        landing: resolve(__dirname, 'index.html'),
        console: resolve(__dirname, 'console.html'),
        docs: resolve(__dirname, 'docs.html'),
      },
    },
  }
})
