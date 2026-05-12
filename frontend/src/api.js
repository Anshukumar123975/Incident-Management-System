import axios from 'axios'

const API_KEY = import.meta.env.VITE_API_KEY || 'dev-api-key-change-in-production'
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const client = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
  },
})

// ── Incidents ─────────────────────────────────────────────────────────────
export const getIncidents = () => client.get('/incidents').then(r => r.data)

export const getIncident = (id) => client.get(`/incidents/${id}`).then(r => r.data)

export const getTimeline = (id) => client.get(`/incidents/${id}/timeline`).then(r => r.data)

export const updateStatus = (id, status) =>
  client.patch(`/incidents/${id}`, { status }).then(r => r.data)

// ── RCA ───────────────────────────────────────────────────────────────────
export const submitRCA = (data) => client.post('/rca', data).then(r => r.data)

// ── Signals ───────────────────────────────────────────────────────────────
export const ingestSignal = (data) => client.post('/signals', data).then(r => r.data)

// ── Analytics ─────────────────────────────────────────────────────────────
export const getMTTR = (days = 7) =>
  client.get(`/analytics/mttr?window_days=${days}`).then(r => r.data)

// ── Health ────────────────────────────────────────────────────────────────
export const getHealth = () => client.get('/health').then(r => r.data)