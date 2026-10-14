import { useState } from 'react'
import { useMediaQuery } from '../../hooks/useMediaQuery'
import InsightChain from './InsightChain'
import JournalCalendar from './JournalCalendar'
import Postmark from './Postmark'

const longDay = iso => new Date(iso).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
const year = iso => new Date(iso).getFullYear()
const monthKey = iso => new Date(iso).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })
const TURN_MS = 750
const ORDINAL = ['', 'First', 'Second', 'Third', 'Fourth', 'Fifth']
const sessionThemes = e => (e.kind === 'session' ? (e.evidence?.themes ?? []).filter(t => typeof t === 'string') : [])

// Lumina's margin notes: where a theme on this page has already come up earlier in the same month.
// This is where patterns first show, before they reach Insights.
function marginNotes(entries) {
  return entries.map((e, i) => {
    let best = null
    for (const t of sessionThemes(e)) {
      const n = entries.slice(0, i + 1)
        .filter(x => monthKey(x.created_at) === monthKey(e.created_at) && sessionThemes(x).includes(t)).length
      if (n >= 2 && (!best || n > best.n)) best = { t, n }
    }
    return best && {
      short: `${best.n === 2 ? '2nd' : best.n === 3 ? '3rd' : `${best.n}th`} time`,
      text: `${ORDINAL[best.n] ?? `${best.n}th`} time ${best.t} came up this month.`,
    }
  })
}

// A pressed sprig for the empty part of the page, picked by the page's first theme.
const SPRIGS = [
  'M34 50c-12-2-18-10-18-17 10 0 17 7 18 17z M35 38c12-2 18-10 18-17-10 0-17 7-18 17z M34 24c-9-2-13-8-13-13 8 0 12 5 13 13z',
  'M34 54c-10-4-14-12-12-18 8 2 12 9 12 18z M35 44c10-4 14-12 12-18-8 2-12 9-12 18z M35 30c-6-5-7-12-4-16 5 3 6 9 4 16z',
  'M34 52c-13 0-19-6-20-12 9-1 16 4 20 12z M35 40c13 0 19-6 20-12-9-1-16 4-20 12z M35 26c-8-3-11-9-10-14 7 1 10 7 10 14z',
]
function Sprig({ seed = '' }) {
  const i = [...seed].reduce((a, c) => a + c.charCodeAt(0), 0) % SPRIGS.length
  return (
    <svg className="jpage-sprig" viewBox="0 0 70 70" aria-hidden="true">
      <path d="M35 66 C 33 50, 37 32, 34 8" fill="none" stroke="var(--forest)" strokeWidth="2" strokeLinecap="round" />
      <path d={SPRIGS[i]} fill="var(--mint)" opacity=".7" />
    </svg>
  )
}

// One page: a reflection written after a conversation, or a weekly letter.
function Page({ entry, note, number, total, renderFeedback }) {
  const themes = sessionThemes(entry)
  const echo = entry.kind === 'weekly' ? entry.evidence?.echo : null
  // The title Lumina wrote when it summarised the conversation; pages from before titles existed are named
  // after their main theme (themes such as "work stress and burnout" already read as a phrase).
  const title = entry.kind === 'weekly' ? 'A weekly letter'
    : entry.evidence?.title ?? (themes.length ? `On ${themes[0]}` : 'After a conversation')
  return (
    <article className="jpage" aria-label={`Page ${number}: ${longDay(entry.created_at)} ${year(entry.created_at)}`}>
      {entry.feedback === 'fits' && <span className="jpage-tape" title="You marked this page “Rings true”" />}
      {note && <span className="jpage-margin hand" aria-hidden="true">{note.short} ↓</span>}
      <header className="jpage-head">
        <Postmark date={entry.created_at} />
        <h3 className="jpage-title">
          <time className="sr-only" dateTime={entry.created_at}>{longDay(entry.created_at)} {year(entry.created_at)}: </time>
          {title}
        </h3>
      </header>
      <div className="jpage-text">{entry.text.split(/\n+/).map((p, i) => <p key={i}>{p}</p>)}</div>
      {entry.evidence?.chain && <InsightChain insight={entry.evidence.chain} title="The link that day" />}
      {echo && <p className="jpage-echo">Linked back to a conversation from {echo.then}.</p>}
      {themes.length > 0 && <ul className="jpage-tags" aria-label="Themes">{themes.slice(0, 4).map(t => <li key={t}>{t}</li>)}</ul>}
      {note && (
        <p className="jpage-note hand">
          <svg viewBox="0 0 40 30" aria-hidden="true"><path d="M3 4 C 14 6, 22 14, 30 24 M30 24 l-8 -1 M30 24 l1 -8" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
          {note.text}
        </p>
      )}
      <div className="jpage-foot">{renderFeedback(entry)}</div>
      <Sprig seed={themes[0] ?? entry.kind} />
      <span className="jpage-num">{number} / {total}</span>
    </article>
  )
}

/**
 * Past reflections as a notebook folded open at one page: oldest first, opened at the latest.
 * The page turns around the spine; the calendar beside it jumps to any day with a conversation.
 */
function Journal({ entries, renderFeedback }) {
  const reduced = useMediaQuery('(prefers-reduced-motion: reduce)')
  const n = entries.length
  const [at, setAt] = useState(null)                  // index of the page on show; null = the latest
  const [turn, setTurn] = useState(null)              // { dir, from } while a page is turning
  const index = Math.min(n - 1, at ?? n - 1)
  const notes = marginNotes(entries)

  const go = target => {
    if (target < 0 || target >= n || target === index || turn) return
    setAt(target)
    if (!reduced) {
      setTurn({ dir: target > index ? 'next' : 'prev', from: index })
      setTimeout(() => setTurn(null), TURN_MS)
    }
  }

  const page = i => (
    <Page entry={entries[i]} note={notes[i]} number={i + 1} total={n} renderFeedback={renderFeedback} />
  )
  // Turning forward, the old page lifts away over the spine to show the new one underneath;
  // turning back, the earlier page comes back over the one you were reading.
  const under = turn?.dir === 'prev' ? turn.from : index
  const leaf = turn ? (turn.dir === 'next' ? turn.from : index) : null

  return (
    <div className="journal">
      <div className="journal-shelf">
        <div className="notebook">
          <div className="notebook-cover" tabIndex={0}
               onKeyDown={e => { if (e.key === 'ArrowLeft') go(index - 1); if (e.key === 'ArrowRight') go(index + 1) }}
               aria-roledescription="journal" aria-label={`Your journal, page ${index + 1} of ${n}. Use the arrow keys to turn pages.`}>
            <span className="notebook-band" aria-hidden="true" />
            <div className="notebook-block">
              {page(under)}
              {leaf !== null && (
                <div className={`notebook-leaf turn-${turn.dir}`} aria-hidden="true">
                  <div className="leaf-face leaf-front">{page(leaf)}</div>
                  <div className="leaf-face leaf-back"><div className="jpage jpage-back" /></div>
                </div>
              )}
            </div>
          </div>
          <div className="journal-nav">
            <button type="button" className="btn-quiet" onClick={() => go(index - 1)} disabled={index === 0 || !!turn}>Earlier page</button>
            <p className="journal-where">Page {index + 1} of {n}</p>
            <button type="button" className="btn-quiet" onClick={() => go(index + 1)} disabled={index >= n - 1 || !!turn}>Later page</button>
          </div>
        </div>
        <JournalCalendar key={index} entries={entries} current={index} onPick={go} />
      </div>
    </div>
  )
}

export default Journal
