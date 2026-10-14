import { useState } from 'react'
import { sendFeedback } from '../../api/personal.js'

// "Does this fit?" as two rubber stamps. The pressed stamp stays inked on the page as a record.
// The answer is used by the next weekly reflection (lumina/insights/weekly.py), so say so once it is saved.
function Stamps({ insight, token, onChange }) {
  const [value, setValue] = useState(insight.feedback)
  const [saved, setSaved] = useState(false)
  const send = async v => {
    const before = value
    setValue(v)
    setSaved(false)
    try {
      await sendFeedback(token, insight.id, v)
      setSaved(true)
      onChange?.(insight.id, v)
    } catch { setValue(before) }
  }
  const linkedPast = insight.kind === 'weekly' && insight.evidence?.echo
  return (
    <div className="feedback-wrap">
      <div className="stamps" role="group" aria-label="Does this fit?">
        {[['fits', 'Rings true'], ['not_quite', 'Not quite me']].map(([v, label]) => (
          <button key={v} type="button" aria-pressed={value === v} className={`stamp ${value === v ? 'is-on' : ''}`}
                  onClick={() => send(v)}>{label}</button>
        ))}
      </div>
      {saved && (
        <p className="feedback-note" role="status">
          {value === 'fits'
            ? 'Noted. Next week’s reflection will build on links like this one.'
            : `Noted. Next week’s reflection won’t offer this reading again${linkedPast ? ', or link back to that conversation' : ''}.`}
        </p>
      )}
    </div>
  )
}

export default Stamps
