import { useEffect, useState } from 'react'

// A preference kept in this browser only. Storage can be unavailable (private mode), so every
// access is guarded and the default is used instead.
export function usePersisted(key, initial) {
  const [value, setValue] = useState(() => {
    try {
      const raw = window.localStorage.getItem(key)
      return raw === null ? initial : JSON.parse(raw)
    } catch {
      return initial
    }
  })
  useEffect(() => {
    try { window.localStorage.setItem(key, JSON.stringify(value)) } catch { /* not persisted */ }
  }, [key, value])
  return [value, setValue]
}
