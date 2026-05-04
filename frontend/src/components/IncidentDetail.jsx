import { useState, useEffect } from 'react'
import { getIncident, getTimeline, updateStatus } from '../api'
import { formatDistanceToNow, format } from 'date-fns'
import RCAForm from './RCAForm'

const STATUS_FLOW = ['OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED']

const NEXT_STATUS = {
  OPEN:          'INVESTIGATING',
  INVESTIGATING: 'RESOLVED',
  RESOLVED:      'CLOSED',
  CLOSED:        null,
}

const STATUS_STYLES = {
  OPEN:          'bg-red-900 text-red-300 border-red-700',
  INVESTIGATING: 'bg-yellow-900 text-yellow-300 border-yellow-700',
  RESOLVED:      'bg-blue-900 text-blue-300 border-blue-700',
  CLOSED:        'bg-green-900 text-green-300 border-green-700',
}

const SEVERITY_COLORS = { P0: 'text-red-400', P1: 'text-orange-400', P2: 'text-yellow-400' }

export default function IncidentDetail({ incident, onClose, onUpdated }) {
  const [detail, setDetail]     = useState(null)
  const [timeline, setTimeline] = useState([])
  const [loading, setLoading]   = useState(true)
  const [transitioning, setTransitioning] = useState(false)
  const [showRCA, setShowRCA]   = useState(false)
  const [error, setError]       = useState(null)
  const [activeTab, setActiveTab] = useState('signals')

  useEffect(() => {
    if (!incident?.id) return
    setLoading(true)
    setShowRCA(false)
    setError(null)

    Promise.all([
      getIncident(incident.id),
      getTimeline(incident.id),
    ]).then(([det, tl]) => {
      setDetail(det)
      setTimeline(tl.events || [])
    }).catch(() => {
      setError('Failed to load incident details')
    }).finally(() => setLoading(false))
  }, [incident?.id])

  const handleTransition = async () => {
    const next = NEXT_STATUS[detail.work_item.status]
    if (!next) return

    // CLOSED requires RCA — show form instead
    if (next === 'CLOSED') {
      setShowRCA(true)
      return
    }

    setTransitioning(true)
    try {
      await updateStatus(incident.id, next)
      const [det, tl] = await Promise.all([
        getIncident(incident.id),
        getTimeline(incident.id),
      ])
      setDetail(det)
      setTimeline(tl.events || [])
      onUpdated?.()
    } catch (e) {
      setError(e.response?.data?.detail || 'Transition failed')
    } finally {
      setTransitioning(false)
    }
  }

  const handleRCASuccess = async (rcaResult) => {
    setShowRCA(false)
    const [det, tl] = await Promise.all([
      getIncident(incident.id),
      getTimeline(incident.id),
    ])
    setDetail(det)
    setTimeline(tl.events || [])
    onUpdated?.()
  }

  if (!incident) return (
    <div className="flex items-center justify-center h-full text-gray-500">
      <div className="text-center">
        <div className="text-5xl mb-4">←</div>
        <p>Select an incident to view details</p>
      </div>
    </div>
  )

  if (loading) return (
    <div className="flex items-center justify-center h-full text-gray-500">
      Loading incident...
    </div>
  )

  if (error) return (
    <div className="m-6 p-4 bg-red-900/30 border border-red-700 rounded text-red-400">
      {error}
    </div>
  )

  const wi     = detail?.work_item
  const sty    = STATUS_STYLES[wi?.status] || STATUS_STYLES.OPEN
  const sevCol = SEVERITY_COLORS[wi?.severity] || 'text-yellow-400'
  const next   = NEXT_STATUS[wi?.status]

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-700">
        <div className="flex items-start justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`font-bold text-lg ${sevCol}`}>{wi?.severity}</span>
              <h2 className="text-white font-bold text-lg">{wi?.component_id}</h2>
              <span className={`text-xs px-2 py-0.5 rounded border font-medium ${sty}`}>
                {wi?.status}
              </span>
            </div>
            <p className="text-gray-400 text-sm mt-1">
              {wi?.component_type} · {wi?.signal_count} signals ·{' '}
              started {wi?.start_time && formatDistanceToNow(new Date(wi.start_time), { addSuffix: true })}
            </p>
            {wi?.mttr_seconds && (
              <p className="text-green-400 text-sm mt-1 font-medium">
                MTTR: {Math.floor(wi.mttr_seconds / 60)}m {Math.floor(wi.mttr_seconds % 60)}s
              </p>
            )}
          </div>

          <div className="flex items-center gap-2 flex-shrink-0 ml-4">
            {next && (
              <button
                onClick={handleTransition}
                disabled={transitioning}
                className="text-sm px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors disabled:opacity-50"
              >
                {transitioning ? 'Updating...' : `→ ${next}`}
              </button>
            )}
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white text-xl px-2"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Status progress bar */}
        <div className="flex gap-1 mt-3">
          {STATUS_FLOW.map((s, i) => {
            const currentIdx = STATUS_FLOW.indexOf(wi?.status)
            const isPast     = i < currentIdx
            const isCurrent  = i === currentIdx
            return (
              <div key={s} className="flex-1">
                <div className={`h-1 rounded-full transition-all ${
                  isCurrent ? 'bg-blue-500' : isPast ? 'bg-green-600' : 'bg-gray-700'
                }`} />
                <p className={`text-xs mt-1 text-center ${
                  isCurrent ? 'text-blue-400' : isPast ? 'text-green-600' : 'text-gray-600'
                }`}>{s}</p>
              </div>
            )
          })}
        </div>
      </div>

      {/* RCA Form overlay */}
      {showRCA && (
        <div className="flex-1 overflow-y-auto p-6">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-white font-semibold">Submit Root Cause Analysis</h3>
            <button onClick={() => setShowRCA(false)} className="text-gray-400 hover:text-white">
              Cancel
            </button>
          </div>
          <RCAForm workItemId={incident.id} onSuccess={handleRCASuccess} />
        </div>
      )}

      {/* Tabs */}
      {!showRCA && (
        <>
          <div className="flex border-b border-gray-700 px-6">
            {['signals', 'timeline'].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-3 px-4 text-sm font-medium capitalize transition-colors border-b-2 ${
                  activeTab === tab
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-white'
                }`}
              >
                {tab} {tab === 'signals' ? `(${detail?.signals?.length || 0})` : `(${timeline.length})`}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {/* Signals tab */}
            {activeTab === 'signals' && (
              <div className="space-y-2">
                {(detail?.signals || []).length === 0 && (
                  <p className="text-gray-500 text-sm text-center py-8">No signals yet</p>
                )}
                {(detail?.signals || []).map((sig, i) => (
                  <div key={i} className="bg-gray-900 rounded p-3 border border-gray-700">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-red-400 text-xs font-mono font-bold">
                        {sig.error_code}
                      </span>
                      <span className="text-gray-500 text-xs">
                        {sig.received_at && format(new Date(sig.received_at), 'HH:mm:ss.SSS')}
                      </span>
                    </div>
                    <p className="text-gray-300 text-sm">{sig.message}</p>
                    {sig.payload && (
                      <pre className="text-xs text-gray-500 mt-2 overflow-x-auto">
                        {JSON.stringify(sig.payload, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Timeline tab */}
            {activeTab === 'timeline' && (
              <div className="relative">
                <div className="absolute left-3 top-0 bottom-0 w-px bg-gray-700" />
                <div className="space-y-4">
                  {timeline.length === 0 && (
                    <p className="text-gray-500 text-sm text-center py-8 ml-8">No events yet</p>
                  )}
                  {timeline.map((event, i) => (
                    <div key={i} className="flex gap-4 ml-2">
                      <div className="w-3 h-3 rounded-full bg-blue-500 flex-shrink-0 mt-1 z-10" />
                      <div className="flex-1 bg-gray-900 rounded p-3 border border-gray-700">
                        <div className="flex items-center justify-between">
                          <span className="text-blue-400 text-xs font-medium">
                            {event.event_type}
                          </span>
                          <span className="text-gray-500 text-xs">
                            {event.created_at && format(new Date(event.created_at), 'MMM d, HH:mm:ss')}
                          </span>
                        </div>
                        {(event.old_value || event.new_value) && (
                          <p className="text-gray-300 text-sm mt-1">
                            {event.old_value && <span className="text-gray-500">{event.old_value}</span>}
                            {event.old_value && event.new_value && <span className="text-gray-600"> → </span>}
                            {event.new_value && <span className="text-white">{event.new_value}</span>}
                          </p>
                        )}
                        {event.note && (
                          <p className="text-gray-500 text-xs mt-1">{event.note}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}