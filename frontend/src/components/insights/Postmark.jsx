const fmt = (iso, opts) => new Date(iso).toLocaleDateString('en-GB', opts).toUpperCase()

// A dated postmark. `letter`: coral, with wavy cancellation lines, carrying the weekly letter's date range.
// `page` (default): a round forest-green stamp for one journal page (weekday, day and month, year).
function Postmark({ start, end, date, variant = 'page' }) {
  if (variant === 'page') {
    return (
      <svg className="postmark-page" viewBox="0 0 80 80" aria-hidden="true">
        <g fill="none" stroke="var(--forest)" strokeWidth="2.2">
          <circle cx="40" cy="40" r="36" /><circle cx="40" cy="40" r="30" strokeDasharray="3.5 3" strokeWidth="1.8" />
        </g>
        <g fill="var(--forest)" textAnchor="middle" fontWeight="700" fontFamily="var(--text)">
          <text x="40" y="31" fontSize="9" letterSpacing="1">{fmt(date, { weekday: 'short' })}</text>
          <text x="40" y="46" fontSize="13">{fmt(date, { day: 'numeric', month: 'short' })}</text>
          <text x="40" y="58" fontSize="8.5">{fmt(date, { year: 'numeric' })}</text>
        </g>
      </svg>
    )
  }
  const s = start ?? date, e = end ?? date
  const sameMonth = fmt(s, { month: 'short' }) === fmt(e, { month: 'short' })
  const range = s === e ? fmt(e, { day: 'numeric', month: 'short' })
    : sameMonth ? `${fmt(s, { day: 'numeric' })}–${fmt(e, { day: 'numeric', month: 'short' })}`
      : `${fmt(s, { day: 'numeric', month: 'short' })}–${fmt(e, { day: 'numeric', month: 'short' })}`
  return (
    <svg className="postmark" viewBox="0 0 150 80" aria-hidden="true">
      <g fill="none" stroke="var(--coral)" strokeWidth="2">
        <circle cx="40" cy="40" r="34" /><circle cx="40" cy="40" r="28" />
        <path d="M80 26q8-6 16 0t16 0t16 0t16 0M80 40q8-6 16 0t16 0t16 0t16 0M80 54q8-6 16 0t16 0t16 0t16 0" />
      </g>
      <g fill="var(--coral-ink)" textAnchor="middle" fontWeight="600" fontFamily="var(--text)">
        <text x="40" y="33" fontSize="8.5">LUMINA</text>
        <text x="40" y="46" fontSize={range.length > 9 ? 7.5 : 10.5}>{range}</text>
        <text x="40" y="57" fontSize="8">{fmt(e, { year: 'numeric' })}</text>
      </g>
    </svg>
  )
}

export default Postmark
