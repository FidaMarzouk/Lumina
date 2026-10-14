import { useState, useCallback, useRef, useEffect } from 'react'
import { endSession, sendMessage, startSession } from '../api/chat.js'
import { withWeather } from '../components/chat/weather.js'

const message = (role, text, extra = {}) => ({ id: crypto.randomUUID(), role, text, isCrisis: false, ...extra })

const greeting = () =>
  message('ai', "Hi, I'm Lumina. I'm here to listen, with no judgement and no rush. How are you feeling today?")

// Guests chat statelessly. When signed in (`token`) and the conversation is open (`active`), each conversation is
// a server session: Lumina opens with the next step waiting, can remember and reflect, and the session is closed
// (summary + next step) on "New chat", on leaving, or when the page is closed.
export function useChat(persona = 'listener', { token = null, active = false } = {}) {
  const [messages, setMessages]         = useState(() => [greeting()])
  const [isTyping, setIsTyping]         = useState(false)
  const [crisisActive, setCrisisActive] = useState(false)
  const [error, setError]               = useState(null)
  // The open signed-in conversation: { mode: 'open' | 'guided', step } (step = the journey step for guided ones).
  const [session, setSession]           = useState(null)

  // Refs mirror state so callbacks always see current values (voice input can fire late).
  const messagesRef = useRef(messages)
  const busyRef     = useRef(false)
  const crisisRef   = useRef(false)
  const sessionRef  = useRef(null)        // { id, token } of the open server session
  const weatherRef  = useRef(null)        // the inner weather picked before the conversation started
  useEffect(() => { messagesRef.current = messages }, [messages])

  // The opening line, retuned to the inner weather if one was picked.
  const opening = useCallback((text, guided) => {
    const w = weatherRef.current
    return w ? message('ai', withWeather(text, w, guided), { base: text, weather: w }) : message('ai', text, { base: text })
  }, [])

  const applySession = useCallback(s => {
    sessionRef.current = { id: s.session_id, token }
    setSession({ mode: s.mode, step: s.mode === 'guided' ? s.next_step : null })
    // Replace the generic greeting with the personal opening, unless the conversation has already started.
    setMessages(prev => (prev.length <= 1 ? [opening(s.opening, s.mode === 'guided')] : prev))
    return sessionRef.current
  }, [token, opening])

  // The kind of session to open next ({ mode: 'guided', journeyId } from the journeys screen); open by default.
  const nextRef = useRef(null)
  const request = useCallback(() => {
    const next = nextRef.current
    return startSession(token, next?.mode ?? 'open', next?.journeyId ?? null)
  }, [token])
  const apply = useCallback(s => { nextRef.current = null; return applySession(s) }, [applySession])

  // On failure chat still works, without memory.
  const openSession = useCallback(() => (token ? request().then(apply).catch(() => null) : Promise.resolve(null)),
                                  [token, request, apply])

  // Resolves once the server has summarised the session (call before logging out: the token must still be valid).
  const closeSession = useCallback((keepalive = false) => {
    const s = sessionRef.current
    sessionRef.current = null
    setSession(null)
    return s ? endSession(s.token, s.id, keepalive).catch(() => { /* best effort */ }) : Promise.resolve()
  }, [])

  useEffect(() => {
    if (!active || !token) return
    let live = true
    request()
      // A session that arrives after the view closed is ended straight away.
      .then(s => { if (live) apply(s); else endSession(token, s.session_id).catch(() => {}) })
      .catch(() => { sessionRef.current = null })
    const onHide = () => closeSession(true)
    window.addEventListener('pagehide', onHide)
    return () => {
      live = false
      window.removeEventListener('pagehide', onHide)
      closeSession(true)
    }
  }, [active, token, request, apply, closeSession])

  const sendUserMessage = useCallback(async (text) => {
    const clean = text.trim()
    // Never send while a reply is pending or the crisis sheet is open (also guards voice input).
    if (!clean || busyRef.current || crisisRef.current) return

    const history = messagesRef.current
    setMessages(prev => [...prev, message('user', clean)])
    busyRef.current = true
    setIsTyping(true)
    setError(null)

    const send = s => sendMessage(clean, history, persona, s && { token: s.token, sessionId: s.id }, weatherRef.current)
    try {
      let response
      try {
        response = await send(sessionRef.current)
      } catch (err) {
        // The session ended on the server (e.g. another tab closed it): continue in a fresh one.
        if (err.status !== 404 || !sessionRef.current) throw err
        sessionRef.current = null
        response = await send(await openSession())
      }
      if (typeof response.reply !== 'string' || !response.reply) throw new Error('Empty reply from server')

      if (response.crisis_flag) {
        crisisRef.current = true
        setCrisisActive(true)
      }
      setMessages(prev => [...prev, message('ai', response.reply,
        { isCrisis: response.crisis_flag, insight: response.insight ?? null })])
    } catch (err) {
      setError(err?.message?.startsWith('Server:') ? err.message.slice(8)
               : "Lumina couldn't be reached. Check that the server is running, then send your message again.")
    } finally {
      busyRef.current = false
      setIsTyping(false)
    }
  }, [persona, openSession])

  // The inner-weather check-in: retunes the opening line, until the person has said anything.
  const setWeather = useCallback(weather => {
    weatherRef.current = weather
    setMessages(prev => {
      if (prev.length !== 1 || prev[0].role !== 'ai') return prev
      const base = prev[0].base ?? prev[0].text
      return [{ ...prev[0], base, weather, text: weather ? withWeather(base, weather, session?.mode === 'guided') : base }]
    })
  }, [session])

  // A line from Lumina that needs no reply from the model (the torn-off question of the day).
  const addLuminaLine = useCallback(text => {
    if (busyRef.current || crisisRef.current) return
    setMessages(prev => [...prev, message('ai', text)])
  }, [])

  // Closes the crisis sheet only; the crisis reply stays visible in the chat.
  const dismissCrisis = useCallback(() => {
    crisisRef.current = false
    setCrisisActive(false)
  }, [])

  // Start a fresh conversation (history, crisis sheet and errors reset; a signed-in session is closed and reopened).
  const resetSession = useCallback(() => {
    crisisRef.current = false
    setCrisisActive(false)
    setError(null)
    weatherRef.current = null
    setMessages([greeting()])
    closeSession()
    if (active && token) openSession()
  }, [active, token, openSession, closeSession])

  // Start a new conversation of a given kind, e.g. { mode: 'guided', journeyId } (the current one is closed).
  const startWith = useCallback(options => {
    nextRef.current = options
    resetSession()
  }, [resetSession])

  return { messages, isTyping, crisisActive, error, session, sendUserMessage, dismissCrisis, resetSession, startWith,
           setWeather, addLuminaLine, endConversation: closeSession }
}
