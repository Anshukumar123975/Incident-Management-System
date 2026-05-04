import { useState } from 'react'
import { submitRCA } from '../api'

const CATEGORIES = ['INFRA', 'CODE', 'CONFIG', 'DEPENDENCY', 'NETWORK', 'UNKNOWN']

export default function RCAForm({ workItemId, onSuccess }) {
  const [form, setForm] = useState({
    root_cause_category: '',
    fix_applied:         '',
    prevention_steps:    '',
    incident_start:      '',
    incident_end:        '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError]           = useState(null)
  const [result, setResult]         = useState(null)

  const isValid =
    form.root_cause_category &&
    form.fix_applied.trim().length >= 10 &&
    form.prevention_steps.trim().length >= 10 &&
    form.incident_start &&
    form.incident_end &&
    new Date(form.incident_end) > new Date(form.incident_start)

  const handleSubmit = async () => {
    if (!isValid) return
    setSubmitting(true)
    setError(null)

    try {
      const payload = {
        work_item_id:        workItemId,
        root_cause_category: form.root_cause_category,
        fix_applied:         form.fix_applied,
        prevention_steps:    form.prevention_steps,
        incident_start:      new Date(form.incident_start).toISOString(),
        incident_end:        new Date(form.incident_end).toISOString(),
      }
      const res = await submitRCA(payload)
      setResult(res)
      onSuccess?.(res)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to submit RCA')
    } finally {
      setSubmitting(false)
    }
  }

  if (result) {
    const mttrMin = result.mttr_seconds ? Math.floor(result.mttr_seconds / 60) : 0
    const mttrSec = result.mttr_seconds ? Math.floor(result.mttr_seconds % 60) : 0
    return (
      <div className="bg-green-900/30 border border-green-700 rounded-lg p-6 text-center">
        <div className="text-4xl mb-3">✓</div>
        <h3 className="text-green-400 font-bold text-lg mb-1">Incident Closed</h3>
        <p className="text-gray-300 text-sm mb-3">RCA submitted successfully</p>
        <div className="bg-gray-900 rounded-lg p-4 inline-block">
          <p className="text-gray-400 text-xs uppercase tracking-wide mb-1">MTTR</p>
          <p className="text-white text-2xl font-bold">{mttrMin}m {mttrSec}s</p>
          <p className="text-gray-500 text-xs mt-1">Mean Time To Repair</p>
        </div>
        <div className="mt-4 text-left text-sm space-y-2">
          <div className="flex gap-2">
            <span className="text-gray-500 w-32 flex-shrink-0">Root Cause:</span>
            <span className="text-white">{result.root_cause_category}</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-3 bg-red-900/30 border border-red-700 rounded text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Root cause category */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Root Cause Category <span className="text-red-400">*</span>
        </label>
        <select
          value={form.root_cause_category}
          onChange={e => setForm(f => ({ ...f, root_cause_category: e.target.value }))}
          className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="">Select category...</option>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {/* Incident start/end */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Incident Start <span className="text-red-400">*</span>
          </label>
          <input
            type="datetime-local"
            value={form.incident_start}
            onChange={e => setForm(f => ({ ...f, incident_start: e.target.value }))}
            className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Incident End <span className="text-red-400">*</span>
          </label>
          <input
            type="datetime-local"
            value={form.incident_end}
            onChange={e => setForm(f => ({ ...f, incident_end: e.target.value }))}
            className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Validation hint for dates */}
      {form.incident_start && form.incident_end &&
       new Date(form.incident_end) <= new Date(form.incident_start) && (
        <p className="text-red-400 text-xs">End time must be after start time</p>
      )}

      {/* Fix applied */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Fix Applied <span className="text-red-400">*</span>
          <span className="text-gray-500 font-normal ml-2">(min 10 chars)</span>
        </label>
        <textarea
          rows={3}
          value={form.fix_applied}
          onChange={e => setForm(f => ({ ...f, fix_applied: e.target.value }))}
          placeholder="Describe what fix was applied to resolve the incident..."
          className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none resize-none"
        />
        <p className="text-xs text-gray-600 mt-0.5">{form.fix_applied.length} chars</p>
      </div>

      {/* Prevention steps */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Prevention Steps <span className="text-red-400">*</span>
          <span className="text-gray-500 font-normal ml-2">(min 10 chars)</span>
        </label>
        <textarea
          rows={3}
          value={form.prevention_steps}
          onChange={e => setForm(f => ({ ...f, prevention_steps: e.target.value }))}
          placeholder="Steps to prevent this incident from recurring..."
          className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none resize-none"
        />
        <p className="text-xs text-gray-600 mt-0.5">{form.prevention_steps.length} chars</p>
      </div>

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={!isValid || submitting}
        className={`w-full py-2.5 rounded font-medium text-sm transition-all ${
          isValid && !submitting
            ? 'bg-blue-600 hover:bg-blue-500 text-white cursor-pointer'
            : 'bg-gray-700 text-gray-500 cursor-not-allowed'
        }`}
      >
        {submitting ? 'Submitting RCA...' : 'Submit RCA & Close Incident'}
      </button>

      {!isValid && (
        <p className="text-xs text-gray-500 text-center">
          All fields required · Fix and Prevention must be at least 10 characters
        </p>
      )}
    </div>
  )
}