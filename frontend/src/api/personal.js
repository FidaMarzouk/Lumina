import { request } from './client.js'

// Journeys
export const fetchJourneys = token => request('/journeys', { token }).then(r => r.journeys)
export const fetchNextStep = token => request('/journey/next', { token })
export const completeStep = (token, journeyId, stepId) =>
  request('/journey/steps/complete', { method: 'POST', token, body: { journey_id: journeyId, step_id: stepId } })

// Insights
export const fetchInsights = token => request('/insights?limit=50', { token }).then(r => r.insights)
// Reading the weekly letter never writes one: GET says whether it is ready, due or not yet possible.
export const fetchWeekly = token => request('/insights/weekly', { token })
// Writes this week's letter when it is due (the LLM and the safety checks: several seconds).
export const writeWeekly = token => request('/insights/weekly', { method: 'POST', token })
export const sendFeedback = (token, id, value) =>
  request(`/insights/${encodeURIComponent(id)}/feedback`, { method: 'POST', token, body: { value } })

// Things that helped: kept by the person, or noticed by Lumina and waiting to be kept or dismissed
export const fetchJar = token => request('/jar', { token })
export const addToJar = (token, text) => request('/jar', { method: 'POST', token, body: { text } })
export const keepInJar = (token, id) => request(`/jar/${encodeURIComponent(id)}/keep`, { method: 'POST', token })
export const removeFromJar = (token, id) => request(`/jar/${encodeURIComponent(id)}`, { method: 'DELETE', token })

