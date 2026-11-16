// "Today I will": a short list written for the person from what they keep. Nothing on it is a task they set;
// each line is an invitation, and the ones already done today are crossed through.
function TodayList({ next, pick, loggedSleep, wroteToday, onStartJourney, onTalk, onLogSleep, onWrite }) {
  const items = []
  if (next?.kind === 'journey_step') {
    items.push({ key: 'step', star: true, from: `${next.journey_title.toLowerCase()} · step ${next.step_index + 1}`,
                 onClick: () => onStartJourney(next.journey_id), text: <>Pick up <em>{next.title.toLowerCase()}</em></> })
  } else if (next?.kind === 'journey_suggestion') {
    items.push({ key: 'step', star: true, from: 'a trail you might like', onClick: () => onStartJourney(next.journey_id),
                 text: <>Try <em>{next.journey_title.toLowerCase()}</em></> })
  } else {
    items.push({ key: 'talk', star: true, from: 'no agenda', onClick: onTalk, text: <>Talk about whatever is on my mind</> })
  }
  if (pick) items.push({ key: 'jar', from: 'from your jar', text: <>Try <em>{pick.text}</em> again</> })
  items.push({ key: 'sleep', done: loggedSleep, from: 'ten seconds', onClick: onLogSleep, text: <>Note how I slept last night</> })
  items.push({ key: 'write', done: wroteToday, from: 'a line is enough', onClick: onWrite, text: <>Write a line in my journal</> })

  return (
    <section className="card todo" aria-labelledby="todo-h">
      <h2 id="todo-h" className="card-title">Today I will</h2>
      <ul className="todo-list">
        {items.map(i => (
          <li key={i.key} className={i.done ? 'is-done' : ''}>
            <span className="todo-mark" aria-hidden="true">{i.done ? '✓' : i.star ? '★' : '·'}</span>
            {i.onClick && !i.done
              ? <button type="button" className="todo-item" onClick={i.onClick}>{i.text}</button>
              : <span className="todo-item">{i.text}</span>}
            <span className="todo-from">{i.done ? 'done' : i.from}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default TodayList
