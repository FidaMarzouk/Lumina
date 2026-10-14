import { useCallback, useEffect, useState } from 'react'
import * as account from '../api/account.js'

const KEY = 'lumina.token'

function readToken() {
  try { return window.localStorage.getItem(KEY) } catch { return null }
}

function writeToken(token) {
  try {
    if (token) window.localStorage.setItem(KEY, token)
    else window.localStorage.removeItem(KEY)
  } catch { /* not persisted: the person stays signed in for this tab only */ }
}

// The signed-in account. status: 'checking' (validating a stored token) | 'guest' | 'signed-in'.
export function useAuth() {
  const [token, setToken] = useState(readToken)
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState(() => (readToken() ? 'checking' : 'guest'))

  const signIn = useCallback(({ token: t, user: u }) => {
    writeToken(t)
    setToken(t)
    setUser(u)
    setStatus('signed-in')
  }, [])

  const forget = useCallback(() => {
    writeToken(null)
    setToken(null)
    setUser(null)
    setStatus('guest')
  }, [])

  // A stored token may have expired or been revoked: check it once on load.
  useEffect(() => {
    if (status !== 'checking' || !token) return
    let live = true
    account.fetchMe(token)
      .then(u => { if (live) { setUser(u); setStatus('signed-in') } })
      .catch(err => { if (live) { if (err.status === 401) forget(); else setStatus('guest') } })
    return () => { live = false }
  }, [status, token, forget])

  const register = useCallback(async fields => signIn(await account.register(fields)), [signIn])
  const login = useCallback(async fields => signIn(await account.login(fields)), [signIn])

  const logout = useCallback(async () => {
    try { if (token) await account.logout(token) } catch { /* the token is dropped locally either way */ }
    forget()
  }, [token, forget])

  const update = useCallback(async changes => setUser(await account.updateSettings(token, changes)), [token])
  const exportData = useCallback(() => account.exportData(token), [token])

  const deleteAccount = useCallback(async password => {
    await account.deleteAccount(token, password)
    forget()
  }, [token, forget])

  return { token: status === 'signed-in' ? token : null, user, status, register, login, logout, update, exportData,
           deleteAccount }
}
