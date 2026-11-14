// Crisis lines are kept here only (the backend refers to "the lines shown on screen").
export const LINES = [
  { where: 'Tunisia', number: '71 391 000', tel: '71391000' },
  { where: 'United States and Canada', number: '988', tel: '988' },
]

// What the crisis panel says, by the safety layer's crisis_subtype. Never asks the person to declare they are safe.
export const CRISIS_COPY = {
  ideation: {
    title: "You don't have to carry this alone",
    text: "I'm still here, and we can keep talking. If you're in danger or thinking about ending your life, "
      + 'these lines are there for you right now.',
  },
  method: {
    title: 'Please reach out now',
    text: 'If you might act on these thoughts, call one of these lines now or go to the nearest emergency '
      + "department. I'm still here with you.",
  },
  third_party: {
    title: 'If someone else is in danger',
    text: 'If they are in immediate danger, call your local emergency number and try to stay with them. '
      + 'These lines can also help you work out what to do, and they are there for you too.',
  },
}

// When a conversation has had more than one kind of crisis turn, the panel keeps the most urgent wording.
const RANK = { third_party: 1, ideation: 2, method: 3 }
export const moreUrgent = (current, next) => ((RANK[next] ?? 0) > (RANK[current] ?? 0) ? next : current)
