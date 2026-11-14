import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies the API; LUMINA_API points it at a backend other than :8000.
// 127.0.0.1, not "localhost": Node tries IPv6 (::1) first, uvicorn listens on IPv4, and anything else holding
// [::]:8000 (e.g. a Docker container) would silently receive the requests instead.
const api = process.env.LUMINA_API ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/chat': api,
      '/tts': api,
      '/auth': api,
      '/users': api,
      '/sessions': api,
      '/journeys': api,
      '/journey': api,
      '/insights': api,
      '/jar': api,
    }
  },
  // npm test: unit tests for the pure logic (no browser, no backend)
  test: { environment: 'node', include: ['src/**/*.test.{js,jsx}'] },
})
