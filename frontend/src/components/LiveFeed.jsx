import { useState, useEffect, useCallback } from 'react'
import { getIncidents } from '../api'
import { useWebSocket } from '../hooks/useWebSocket'
import { formatDistanceToNow } from 'date-fns'

const SEVERITY_STYLES = {
  P0: {
    badge: 'bg-red-600 text-white',
    row:   'border-l-4 border-red-500 bg-gray-800 hover:bg-gray-750',
    dot:   'bg-red-500 animate-pulse',
    label: 'CRITICAL',
  },
  P1: {
    badge: 'bg-orange-500 text-white',
    row:   'border-l-4 border-orange-400 bg-gray-800 hover:bg-gray-750',
    dot:   'bg-orange-400',
    label: 'HIGH',
  },
  P2: {
    badge: 'bg-yellow-500 text-gray-900',
    row:   'border-l-4 border-yellow-400 bg-gray-800 hover:bg-gray-750',
    dot:   'bg-yellow-400',
    label: 'MEDIUM',
  },
}

const STATUS_STYLES = {
  OPEN:          'bg-red-900 text-red-300',
  INVESTIGATING: 'bg-yellow-900 text-yellow-300',
  RESOLVED:      'bg-blue-900 text-blue-300',
  CLOSED:        'bg-green-900 text-green-300',
}

export default function LiveFeed({ onSelect, selectedId }) {
  const [incidents, setIncidents]   = useState([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)

  const fetchIncidents = useCallback(async () => {
    try {
      const data = await getIncidents()
      setIncidents(data.items || [])
      setLastUpdate(new Date())
      setError(null)
    } catch (e) {
      setError('Failed to load incidents')
    } finally {
      setLoading(false)
    }
  }, [])

  // Initial load
  useEffect(() => { fetchIncidents() }, [fetchIncidents])

  // WebSocket live updates
  const handleWsMessage = useCallback((msg) => {
    if (msg.event || msg.status) {
      fetchIncidents()
    }
  }, [fetchIncidents])

  useWebSocket(handleWsMessage)

  const activeCount = incidents.filter(i => i.status !== 'CLOSED').length
  const p0Count     = incidents.filter(i => i.severity === 'P0' && i.status !== 'CLOSED').length

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">Incident Feed</h1>
            <p className="text-sm text-gray-400 mt-0.5">
              {activeCount} active · {p0Count > 0 && (
                <span className="text-red-400 font-semibold">{p0Count} P0 critical</span>
              )}
              {p0Count === 0 && <span className="text-green-400">No P0 incidents</span>}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {/* Live indicator */}
            <div className="flex items-center gap-1.5 text-xs text-green-400">
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse inline-block" />
              LIVE
            </div>
            <button
              onClick={fetchIncidents}
              className="text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded border border-gray-600 hover:border-gray-400 transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>
        {lastUpdate && (
          <p className="text-xs text-gray-600 mt-1">
            Updated {formatDistanceToNow(lastUpdate, { addSuffix: true })}
          </p>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center h-32 text-gray-500">
            Loading incidents...
          </div>
        )}

        {error && (
          <div className="m-4 p-3 bg-red-900/30 border border-red-700 rounded text-red-400 text-sm">
            {error}
          </div>
        )}

        {!loading && !error && incidents.length === 0 && (
          <div className="flex flex-col items-center justify-center h-48 text-gray-500">
            <div className="text-4xl mb-3">✓</div>
            <p className="font-medium">No incidents</p>
            <p className="text-sm mt-1">All systems operational</p>
          </div>
        )}

        {incidents.map(incident => {
          const sty       = SEVERITY_STYLES[incident.severity] || SEVERITY_STYLES.P2
          const statusSty = STATUS_STYLES[incident.status] || STATUS_STYLES.OPEN
          const isSelected = incident.id === selectedId

          return (
            <div
              key={incident.id}
              onClick={() => onSelect(incident)}
              className={`
                ${sty.row}
                ${isSelected ? 'ring-1 ring-inset ring-blue-500' : ''}
                p-4 mb-1 cursor-pointer transition-all
              `}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3 min-w-0">
                  <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${sty.dot}`} />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${sty.badge}`}>
                        {incident.severity}
                      </span>
                      <span className="text-white font-medium text-sm truncate">
                        {incident.component_id}
                      </span>
                      {incident.is_anomaly && (
                        <span className="text-xs bg-purple-900 text-purple-300 px-2 py-0.5 rounded">
                          ANOMALY
                        </span>
                      )}
                    </div>
                    <p className="text-gray-400 text-xs mt-1">
                      {incident.component_type} · {incident.signal_count} signals
                    </p>
                  </div>
                </div>

                <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${statusSty}`}>
                    {incident.status}
                  </span>
                  <span className="text-xs text-gray-500">
                    {formatDistanceToNow(new Date(incident.created_at), { addSuffix: true })}
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}