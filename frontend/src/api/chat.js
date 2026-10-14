import { request } from './client.js'

// `session` ({ token, sessionId }) is set for signed-in conversations, so Lumina can remember and guide.
// `weather` is the inner-weather check-in, if one was picked: context for the reply's tone.
export async function sendMessage(userMessage, conversationHistory = [], persona = 'listener', session = null, weather = null) {
  return request('/chat', {
    method: 'POST',
    token: session?.token,
    body: {
      message: userMessage,
      persona,
      history: conversationHistory.map(m => ({ role: m.role, text: m.text })),
      ...(session?.sessionId ? { session_id: session.sessionId } : {}),
      ...(weather ? { weather } : {}),
    },
  })
}

export const startSession = (token, mode = 'open', journeyId = null) =>
  request('/sessions', { method: 'POST', token, body: { mode, ...(journeyId ? { journey_id: journeyId } : {}) } })

// keepalive lets the request finish when the page is being closed.
export const endSession = (token, sessionId, keepalive = false) =>
  request(`/sessions/${encodeURIComponent(sessionId)}/end`, { method: 'POST', token, keepalive })
