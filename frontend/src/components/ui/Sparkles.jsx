import { useEffect, useRef } from 'react'

// The pointer is the logo's star; moving it leaves a few small sparkles that drift and fade, like star dust.
// Mouse and pen only (never on touch), never with reduced motion, nothing while a button is held (scratching
// out in the journal), and the drawing loop runs only while sparkles are alive.
const COLOURS = { day: ['#ea6a33', '#f5b08e', '#f2a65a'], night: ['#f3d58a', '#f2a65a', '#f6edd2'] }
const MAX = 36, EVERY_PX = 22, LIFE_MS = 750

function star(ctx, x, y, r) {
  ctx.beginPath()
  ctx.moveTo(x, y - r)
  ctx.quadraticCurveTo(x + r * 0.12, y - r * 0.12, x + r, y)
  ctx.quadraticCurveTo(x + r * 0.12, y + r * 0.12, x, y + r)
  ctx.quadraticCurveTo(x - r * 0.12, y + r * 0.12, x - r, y)
  ctx.quadraticCurveTo(x - r * 0.12, y - r * 0.12, x, y - r)
  ctx.fill()
}

function Sparkles({ night = false }) {
  const canvas = useRef(null)
  const nightRef = useRef(night)
  useEffect(() => { nightRef.current = night }, [night])

  useEffect(() => {
    const still = window.matchMedia('(prefers-reduced-motion: reduce)')
    const fine = window.matchMedia('(hover: hover) and (pointer: fine)')
    const c = canvas.current
    if (!c) return
    const ctx = c.getContext('2d')
    let sparks = [], frame = 0, last = null
    const size = () => {
      const dpr = window.devicePixelRatio || 1
      c.width = innerWidth * dpr; c.height = innerHeight * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    size()
    const draw = now => {
      ctx.clearRect(0, 0, innerWidth, innerHeight)
      sparks = sparks.filter(s => now - s.born < LIFE_MS)
      for (const s of sparks) {
        const t = (now - s.born) / LIFE_MS
        ctx.globalAlpha = (1 - t) * 0.9
        ctx.fillStyle = s.colour
        star(ctx, s.x + s.dx * t * 14, s.y + s.dy * t * 14 + t * 8, s.r * (1 - t * 0.6))
      }
      ctx.globalAlpha = 1
      frame = sparks.length ? requestAnimationFrame(draw) : 0
    }
    const move = e => {
      if (still.matches || !fine.matches || e.pointerType === 'touch' || e.buttons) { last = null; return }
      if (last && Math.hypot(e.clientX - last.x, e.clientY - last.y) < EVERY_PX) return
      last = { x: e.clientX, y: e.clientY }
      const palette = COLOURS[nightRef.current ? 'night' : 'day']
      sparks.push({ x: e.clientX + (Math.random() - 0.5) * 8, y: e.clientY + (Math.random() - 0.5) * 8,
                    dx: Math.random() - 0.5, dy: Math.random() * 0.6, r: 2.5 + Math.random() * 3.5,
                    colour: palette[Math.floor(Math.random() * palette.length)], born: performance.now() })
      if (sparks.length > MAX) sparks.shift()
      if (!frame) frame = requestAnimationFrame(draw)
    }
    window.addEventListener('pointermove', move, { passive: true })
    window.addEventListener('resize', size)
    return () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('resize', size)
      cancelAnimationFrame(frame)
    }
  }, [])

  return <canvas ref={canvas} className="sparkles" aria-hidden="true" />
}

export default Sparkles
