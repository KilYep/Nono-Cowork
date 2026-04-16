import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    // electron:dev waits on http://127.0.0.1:5173 and main.cjs loads that exact
    // URL — if vite silently falls back to 5174/5175 because the port is busy,
    // the electron window never loads. Fail fast instead.
    port: 5173,
    strictPort: true,
    // Force IPv4 loopback. On Windows + Node 17+, vite otherwise binds only
    // to [::1] (IPv6) while the rest of the stack resolves `localhost` to
    // 127.0.0.1 first — wait-on then loops forever on ECONNREFUSED and
    // electron never launches. To serve on LAN, use `vite --host 0.0.0.0`.
    host: '127.0.0.1',
  },
})
