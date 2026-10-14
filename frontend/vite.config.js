import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies the API; LUMINA_API points it at a backend other than :8000.
const api = process.env.LUMINA_API ?? 'http://localhost:8000'

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
  }
})
