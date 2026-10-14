// Spoken replies come from the backend's local Kokoro model (POST /tts → audio/wav).
const API_BASE = import.meta.env.VITE_API_URL ?? ''

export async function fetchSpeech(text, voice, signal) {
  const response = await fetch(`${API_BASE}/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice }),
    signal,
  })
  if (!response.ok) {
    const err = new Error(`HTTP ${response.status}`)
    err.status = response.status
    throw err
  }
  return response.arrayBuffer()
}

export async function serverVoiceAvailable() {
  try {
    const response = await fetch(`${API_BASE}/tts/status`)
    return response.ok && (await response.json()).available === true
  } catch {
    return false
  }
}
