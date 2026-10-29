/* ===================================================================
   API client. Uses the real backend when VITE_API_URL is set
   (e.g. http://localhost:8000/api for FastAPI); otherwise falls back
   to the in-memory mock so the UI runs with no backend.
   =================================================================== */
import { api as mockApi } from './mock.js'

const BASE = import.meta.env.VITE_API_URL || ''
const USE_MOCK = !BASE

let token = (() => { try { return localStorage.getItem('vg_token') || '' } catch { return '' } })()
export function setToken(t) {
  token = t || ''
  try { t ? localStorage.setItem('vg_token', t) : localStorage.removeItem('vg_token') } catch { /* ignore */ }
}

function qs(params) {
  const u = new URLSearchParams()
  Object.entries(params || {}).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') u.append(k, v) })
  const s = u.toString()
  return s ? `?${s}` : ''
}

async function http(path, { method = 'GET', body } = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  })
  // Expired/invalid session (not on the login call itself) -> clear and return to login.
  if (res.status === 401 && path !== '/auth/login') {
    try {
      localStorage.removeItem('vg_token')
      localStorage.removeItem('vg_user')
    } catch { /* ignore */ }
    token = ''
    if (!window.__vg_relogin) { window.__vg_relogin = true; window.location.reload() }
    throw new Error('Session expired — please sign in again')
  }
  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.error || e.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

const realApi = {
  login: (email, password) => http('/auth/login', { method: 'POST', body: { email, password } }),
  enquiries: (p) => http(`/enquiries${qs(p)}`),
  createEnquiry: (data) => http('/enquiries', { method: 'POST', body: data }),
  proposals: (p) => http(`/proposals${qs(p)}`),
  getProposal: (id) => http(`/proposals/${id}`),
  updateProposal: (id, patch) => http(`/proposals/${id}`, { method: 'PATCH', body: patch }),
  enquiredBuyers: (id) => http(`/proposals/${id}/enquired-buyers`),
  uploadProposalImages: async (id, formData) => {
    const res = await fetch(`${BASE}/proposals/${id}/upload-images`, {
      method: 'POST',
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: formData,
    })
    if (!res.ok) {
      const e = await res.json().catch(() => ({}))
      throw new Error(e.error || e.detail || `HTTP ${res.status}`)
    }
    return res.json()
  },
  bulkSegment: (buyer_segment, ids) => http('/proposals/bulk-segment', { method: 'POST', body: { buyer_segment, ids } }),
  requestPhoto: (id) => http(`/proposals/${id}/request-photo`, { method: 'POST' }),
  recipients: (id) => http(`/proposals/${id}/recipients`),
  sendProposal: (id) => http(`/proposals/${id}/send`, { method: 'POST' }),
  setProposalState: (id, state) => http(`/proposals/${id}/state`, { method: 'POST', body: { state } }),
  quotations: (p) => http(`/quotations${qs(p)}`),
  quotation: (id) => http(`/quotations/${id}`),
  setFollowup: (id, frequency) => http(`/quotations/${id}/followup`, { method: 'PUT', body: { frequency } }),
  chat: (id) => http(`/quotations/${id}/chat`),
  channels: (purpose) => http(`/config/channels${qs({ purpose })}`),
  saveChannel: (data) => (data.id ? http(`/config/channels/${data.id}`, { method: 'PUT', body: data }) : http('/config/channels', { method: 'POST', body: data })),
  deleteChannel: (id) => http(`/config/channels/${id}`, { method: 'DELETE' }),
  templates: () => http('/config/templates'),
  saveTemplate: (id, data) => http(`/config/templates/${id}`, { method: 'PUT', body: data }),
  createTemplate: (data) => http('/config/templates', { method: 'POST', body: data }),
  users: () => http('/config/users'),
  saveUser: (id, data) => (id ? http(`/config/users/${id}`, { method: 'PUT', body: data }) : http('/config/users', { method: 'POST', body: data })),
  integrations: () => http('/config/integrations'),
  testEmail: () => http('/config/test-email', { method: 'POST' }),
  keywords: () => http('/config/keywords'),
  addKeyword: (word) => http('/config/keywords', { method: 'POST', body: { word } }),
  deleteKeyword: (id) => http(`/config/keywords/${id}`, { method: 'DELETE' }),
  // Machine masters (Make / Model / Machine)
  machineMakes: () => http('/config/machine-makes'),
  saveMachineMake: (data) => (data.id ? http(`/config/machine-makes/${data.id}`, { method: 'PUT', body: data }) : http('/config/machine-makes', { method: 'POST', body: data })),
  models: () => http('/config/models'),
  saveModel: (data) => (data.id ? http(`/config/models/${data.id}`, { method: 'PUT', body: data }) : http('/config/models', { method: 'POST', body: data })),
  machines: () => http('/config/machines'),
  saveMachine: (data) => (data.id ? http(`/config/machines/${data.id}`, { method: 'PUT', body: data }) : http('/config/machines', { method: 'POST', body: data })),
  fetchEmails: () => http('/proposals/fetch-emails', { method: 'POST' }),
  dashboard: () => http('/dashboard'),
}

export const USING_MOCK = USE_MOCK
// When a real backend URL is configured we talk ONLY to it — no silent fallback
// to mock data (that previously made a down backend look like live data).
export const api = USE_MOCK ? mockApi : realApi
