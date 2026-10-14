import { request } from './client.js'

export const register = ({ email, password, displayName, consent }) =>
  request('/auth/register', { method: 'POST', body: { email, password, display_name: displayName, consent } })

export const login = ({ email, password }) =>
  request('/auth/login', { method: 'POST', body: { email, password } })

export const logout = token => request('/auth/logout', { method: 'POST', token })

export const fetchMe = token => request('/auth/me', { token })

export const updateSettings = (token, changes) => request('/users/me', { method: 'PATCH', token, body: changes })

export const exportData = token => request('/users/me/export', { token })

export const deleteAccount = (token, password) =>
  request('/users/me', { method: 'DELETE', token, body: { password } })
