import { request } from './client.js'

// A save Lumina prepared in the conversation is only written when the person presses Save (POST /actions/{id}/confirm).
export const confirmAction = (token, id) =>
  request(`/actions/${encodeURIComponent(id)}/confirm`, { method: 'POST', token })

export const cancelAction = (token, id) =>
  request(`/actions/${encodeURIComponent(id)}/cancel`, { method: 'POST', token })

// Where each kind of save can be found (and deleted) afterwards.
export const SAVED_WHERE = {
  journal_save: 'your journal',
  sleep_log: 'your sleep log',
  mood_log: 'your mood log',
  jar_add: 'your jar',
}
