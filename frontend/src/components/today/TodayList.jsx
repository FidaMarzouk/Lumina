import { Hl } from '../ui/Marks'

// "Today I will": a short list written for the person from what they keep. Nothing on it is a task they set;
// each line is an invitation, and the ones already done today are struck through.
function TodayList({ next, pick, loggedSleep, loggedMood, wroteToday, onStartJourney, onTalk, onLogSleep, onLogMood, onWrite }) {
  const items = []
  if (next?.kind === 'journey_step') {
    items.push({ key: 'step', star: true, from: `${next.journey_title.toLowerCase()} · step ${next.step_index + 1}`,
                 onClick: () => onStartJourney(next.journey_id),
                 text: <>Pick up <Hl on>{next.title.toLowerCase()}</Hl></> })
  } else if (next?.kind === 'journey_suggestion') {
    items.push({ key: 'step', star: true, from: 'a trail you might like', onClick: () => onStartJourney(next.journey_id),
                 text: <>Try <Hl on>{next.journey_title.toLowerCase()}</Hl></> })
  } else {
    items.push({ key: 'talk', star: true, from: 'no agenda', onClick: onTalk, text: <>Talk about <Hl on>whatever</Hl> is on my mind</> })
  }
  if (pick) items.push({ key: 'jar', from: 'from your jar', text: <>Try <Hl on>{pick.text}</Hl> again</> })
  items.push({ key: 'sleep', done: loggedSleep, from: '10 seconds', onClick: onLogSleep, text: <>Log <Hl on>last night</Hl></> })
  items.push({ key: 'mood', done: loggedMood, from: 'one tap', onClick: onLogMood, text: <>Mark today’s <Hl on>inner weather</Hl></> })
  items.push({ key: 'write', done: wroteToday, from: 'a line is enough', onClick: onWrite, text: <>Write a <Hl on>line</Hl> in my journal</> })

  return (
    <section className="todo" aria-labelledby="todo-h">
      <h2 id="todo-h" className="todo-title">Today<br /><Hl on>I will:</Hl></h2>
      <ul className="todo-list">
        {items.map(i => (
          <li key={i.key} className={i.done ? 'is-done' : ''}>
            {i.star && <span className="todo-star hand" aria-hidden="true">★</span>}
            {i.onClick && !i.done
              ? <button type="button" className="todo-item" onClick={i.onClick}>{i.text}</button>
              : <span className="todo-item">{i.text}</span>}
            <span className="todo-from hand">{i.done ? 'done' : i.from}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default TodayList
