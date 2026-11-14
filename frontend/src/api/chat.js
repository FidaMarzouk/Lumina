import { API_BASE, request } from './client.js'

// `session` ({ token, sessionId }) is set for signed-in conversations, so Lumina can remember and guide.
// `weather` is the inner-weather check-in, if one was picked: context for the reply's tone.
const chatBody = (userMessage, conversationHistory, persona, session, weather) => ({
  message: userMessage,
  persona,
  history: conversationHistory.map(m => ({ role: m.role, text: m.text })),
  ...(session?.sessionId ? { session_id: session.sessionId } : {}),
  ...(weather ? { weather } : {}),
})

export async function sendMessage(userMessage, conversationHistory = [], persona = 'listener', session = null, weather = null) {
  return request('/chat', {
    method: 'POST',
    token: session?.token,
    body: chatBody(userMessage, conversationHistory, persona, session, weather),
  })
}

// Complete lines of a newline-delimited JSON stream, and the unfinished rest.
export function splitLines(buffer) {
  const parts = buffer.split('\n')
  const rest = parts.pop()
  return [parts.filter(line => line.trim()), rest]
}

/**
 * The same turn as sendMessage, streamed: the reply arrives sentence by sentence (POST /chat/stream).
 * `onEvent` gets each {type: 'delta' | 'replace', text}. Resolves with the final /chat response.
 * Errors before the stream starts carry `status` and `detail` like request(); `started` says whether any
 * event had arrived when it failed.
 */
export async function streamMessage(userMessage, conversationHistory = [], persona = 'listener', session = null,
                                    weather = null, onEvent = () => {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (session?.token) headers.Authorization = `Bearer ${session.token}`
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST', headers, body: JSON.stringify(chatBody(userMessage, conversationHistory, persona, session, weather)),
  })
  if (!response.ok || !response.body) {
    let detail = ''
    try { const data = await response.json(); detail = typeof data.detail === 'string' ? data.detail : '' } catch { /* not JSON */ }
    throw Object.assign(new Error(detail ? `Server: ${detail}` : `HTTP ${response.status}`),
                        { status: response.status, detail, started: false })
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let started = false
  for (;;) {
    const { value, done } = await reader.read()
    if (value) buffer += decoder.decode(value, { stream: true })
    const [lines, rest] = splitLines(done ? buffer + '\n' : buffer)
    buffer = rest
    for (const line of lines) {
      const event = JSON.parse(line)
      started = true
      if (event.type === 'done') return event.response
      if (event.type === 'error') throw Object.assign(new Error(`Server: ${event.detail}`), { started })
      onEvent(event)
    }
    if (done) throw Object.assign(new Error('The reply stopped before it was finished.'), { started })
  }
}

export const startSession = (token, mode = 'open', journeyId = null) =>
  request('/sessions', { method: 'POST', token, body: { mode, ...(journeyId ? { journey_id: journeyId } : {}) } })

// keepalive lets the request finish when the page is being closed.
export const endSession = (token, sessionId, keepalive = false) =>
  request(`/sessions/${encodeURIComponent(sessionId)}/end`, { method: 'POST', token, keepalive })
