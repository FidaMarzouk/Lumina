// Shared JSON request helper. Backend base URL: empty in development (Vite proxies the API to :8000),
// set VITE_API_URL for a build.
export const API_BASE = import.meta.env.VITE_API_URL ?? ''

export async function request(path, { method = 'GET', body, token, keepalive = false } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  const response = await fetch(`${API_BASE}${path}`, {
    method, headers, keepalive, body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (!response.ok) {
    let detail = ''
    try {
      const data = await response.json()
      // FastAPI validation errors arrive as a list; show the first message.
      detail = typeof data.detail === 'string' ? data.detail
        : Array.isArray(data.detail) ? (data.detail[0]?.msg ?? '').replace(/^Value error, /, '') : ''
    } catch { /* not JSON */ }
    const err = new Error(detail ? `Server: ${detail}` : `HTTP ${response.status}`)
    err.status = response.status
    err.detail = detail
    throw err
  }
  return response.status === 204 ? null : response.json()
}
