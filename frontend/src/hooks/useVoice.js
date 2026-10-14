import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchSpeech, serverVoiceAvailable } from '../api/voice.js'

// Split a reply into speakable chunks. The first sentence goes alone so speech starts quickly;
// later sentences are merged up to `max` characters to keep the prosody natural.
export function chunkText(text, max = 240) {
  const clean = text
    .replace(/https?:\/\/\S+/g, '')
    .replace(/[*_#`>~|]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  const sentences = (clean.match(/[^.!?…]+(?:[.!?…]+["')\]]*|$)/g) || []).map(s => s.trim()).filter(Boolean)
  const out = []
  for (const s of sentences) {
    const pieces = s.length <= max ? [s] : (s.match(new RegExp(`.{1,${max}}(?:\\s|$)`, 'g')) || [s]).map(p => p.trim())
    for (const p of pieces) {
      const last = out.length > 1 || (out.length === 1 && out[0].length < 40) ? out[out.length - 1] : null
      if (last && last.length + p.length + 1 <= max) out[out.length - 1] = `${last} ${p}`
      else out.push(p)
    }
  }
  return out
}

// Browser fallback: prefer the "natural"/"neural" voices Edge and Chrome ship, matched to the chosen voice.
const NAMES = {
  female: ['aria', 'jenny', 'ava', 'emma', 'sonia', 'libby', 'michelle', 'samantha', 'zira', 'susan', 'hazel', 'karen', 'moira', 'tessa'],
  male:   ['guy', 'andrew', 'brian', 'ryan', 'christopher', 'eric', 'davis', 'david', 'mark', 'daniel', 'george', 'alex', 'fred'],
}
function pickBrowserVoice(gender) {
  const voices = window.speechSynthesis.getVoices().filter(v => v.lang?.toLowerCase().startsWith('en'))
  const score = v => {
    const n = v.name.toLowerCase()
    return (/natural|neural|online/.test(n) ? 4 : 0) + (NAMES[gender].some(k => n.includes(k)) ? 2 : 0) + (v.lang === 'en-US' ? 1 : 0)
  }
  return voices.sort((a, b) => score(b) - score(a))[0] ?? null
}


export function useVoice({ gender }) {
  const [speaking, setSpeaking] = useState(false)
  const [serverVoice, setServerVoice] = useState(null)   // null = unknown, then true / false

  const ctxRef = useRef(null)
  const outRef = useRef(null)          // analyser on the speech output
  const srcRef = useRef(null)          // the buffer source currently playing
  const micRef = useRef(null)          // { stream, node, analyser } while the mic is open
  const micWantedRef = useRef(false)
  const runRef = useRef(0)             // bumping this cancels the running speech queue
  const abortRef = useRef(null)
  const browserSpeakingRef = useRef(false)
  const levelRef = useRef(0)
  const sampleRef = useRef(null)
  const genderRef = useRef(gender)
  const serverRef = useRef(serverVoice)
  useEffect(() => { genderRef.current = gender }, [gender])
  useEffect(() => { serverRef.current = serverVoice }, [serverVoice])

  useEffect(() => { serverVoiceAvailable().then(setServerVoice) }, [])

  const ensureContext = useCallback(() => {
    if (!ctxRef.current) {
      const Ctx = window.AudioContext || window.webkitAudioContext
      if (!Ctx) return null
      const ctx = new Ctx()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 1024
      analyser.connect(ctx.destination)
      ctxRef.current = ctx
      outRef.current = analyser
    }
    if (ctxRef.current.state === 'suspended') ctxRef.current.resume().catch(() => {})
    return ctxRef.current
  }, [])

  // Call from a click or key press: browsers only allow audio that a user gesture started.
  const unlock = useCallback(() => { ensureContext() }, [ensureContext])

  const cancel = useCallback(() => {
    runRef.current += 1
    abortRef.current?.abort()
    abortRef.current = null
    try { srcRef.current?.stop() } catch { /* already stopped */ }
    srcRef.current = null
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    browserSpeakingRef.current = false
    setSpeaking(false)
  }, [])

  const speakWithServer = useCallback(async (chunks, run, progress) => {
    const ctx = ensureContext()
    if (!ctx) throw new Error('no audio context')
    const ac = new AbortController()
    abortRef.current = ac
    const load = text => fetchSpeech(text, genderRef.current, ac.signal).then(b => ctx.decodeAudioData(b))
    let next = load(chunks[0])
    for (let i = 0; i < chunks.length; i++) {
      const buffer = await next
      if (run !== runRef.current) return
      next = i + 1 < chunks.length ? load(chunks[i + 1]) : null
      next?.catch(() => {})            // a cancelled prefetch must not surface as an unhandled rejection
      if (ctx.state !== 'running') await ctx.resume().catch(() => {})
      if (ctx.state !== 'running') return   // no user gesture yet: stay quiet rather than hang
      setSpeaking(true)
      await new Promise(resolve => {
        const src = ctx.createBufferSource()
        src.buffer = buffer
        src.connect(outRef.current)
        src.onended = resolve
        srcRef.current = src
        src.start()
      })
      srcRef.current = null
      progress.done = i + 1
      if (run !== runRef.current) return
    }
  }, [ensureContext])

  const speakWithBrowser = useCallback((chunks, run) => new Promise(resolve => {
    if (!('speechSynthesis' in window) || !chunks.length) return resolve()
    const voice = pickBrowserVoice(genderRef.current)
    chunks.forEach((text, i) => {
      const u = new SpeechSynthesisUtterance(text)
      if (voice) u.voice = voice
      u.rate = 0.95
      u.onstart = () => { if (run === runRef.current) { browserSpeakingRef.current = true; setSpeaking(true) } }
      if (i === chunks.length - 1) u.onend = u.onerror = () => { browserSpeakingRef.current = false; resolve() }
      window.speechSynthesis.speak(u)
    })
  }), [])

  const speak = useCallback(async text => {
    cancel()
    const run = runRef.current
    const chunks = chunkText(text || '')
    if (!chunks.length) return
    const progress = { done: 0 }
    try {
      if (serverRef.current === false) throw Object.assign(new Error('server voice off'), { fallback: true })
      await speakWithServer(chunks, run, progress)
    } catch (err) {
      if (run !== runRef.current || err.name === 'AbortError') return
      if (err.status === 503 || err.fallback) setServerVoice(false)
      await speakWithBrowser(chunks.slice(progress.done), run)
    } finally {
      if (run === runRef.current) setSpeaking(false)
    }
  }, [cancel, speakWithServer, speakWithBrowser])

  // Mic level for the orb while the person is talking (speech recognition itself runs in InputBar).
  const startMic = useCallback(async () => {
    micWantedRef.current = true
    if (micRef.current || !navigator.mediaDevices?.getUserMedia) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const ctx = ensureContext()
      if (!micWantedRef.current || !ctx) { stream.getTracks().forEach(t => t.stop()); return }
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 1024
      const node = ctx.createMediaStreamSource(stream)
      node.connect(analyser)
      micRef.current = { stream, node, analyser }
    } catch { /* no permission: the orb shows a gentle pulse instead */ }
  }, [ensureContext])

  const stopMic = useCallback(() => {
    micWantedRef.current = false
    const mic = micRef.current
    if (!mic) return
    mic.node.disconnect()
    mic.stream.getTracks().forEach(t => t.stop())
    micRef.current = null
  }, [])

  // Smoothed loudness in [0, 1] for the orb: fast attack, slow release.
  const getLevel = useCallback(() => {
    let raw = 0
    const analyser = micRef.current?.analyser ?? (srcRef.current ? outRef.current : null)
    if (analyser) {
      const buf = sampleRef.current?.length === analyser.fftSize ? sampleRef.current : (sampleRef.current = new Float32Array(analyser.fftSize))
      analyser.getFloatTimeDomainData(buf)
      let sum = 0
      for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i]
      raw = Math.min(1, Math.sqrt(sum / buf.length) * 7)
    } else if (browserSpeakingRef.current || micWantedRef.current) {
      const t = performance.now() / 1000          // browser speech exposes no audio: approximate a voice envelope
      raw = 0.22 + 0.25 * Math.abs(Math.sin(t * 5.1) * Math.sin(t * 1.7))
    }
    levelRef.current += (raw - levelRef.current) * (raw > levelRef.current ? 0.4 : 0.08)
    return levelRef.current
  }, [])

  useEffect(() => () => { cancel(); stopMic(); ctxRef.current?.close().catch(() => {}) }, [cancel, stopMic])

  return { speak, cancel, unlock, speaking, serverVoice, getLevel, startMic, stopMic }
}

