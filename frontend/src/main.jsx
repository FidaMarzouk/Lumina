import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Fonts are bundled (the wordmark's Fraunces, Mynerve and Handlee in fonts.js, Poppins for help numbers), not loaded from a font CDN, so no request leaves the app.
import '@fontsource-variable/fraunces/full.css'
import './fonts.js'
import '@fontsource/poppins/600.css'      // plain face, only for help lines and numbers
import './styles/globals.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
