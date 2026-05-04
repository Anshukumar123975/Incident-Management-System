import { useState, useEffect } from 'react'
import LiveFeed from './components/LiveFeed'
import IncidentDetail from './components/IncidentDetail'
import { getHealth } from './api'

export default function App() {
  const [selected, setSelected]     = useState(null)
  const [health, setHealth]         = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth({ status: 'unreachable' }))
    const t = setInterval(() => {
      getHealth().then(setHealth).catch(() => setHealth({ status: 'unreachable' }))
    }, 30000)
    return () => clearInterval(t)
  }, [])

  const handleUpdated = () => setRefreshKey(k => k + 1)

  const healthColor =
    health?.status === 'ok'         ? 'text-green-400' :
    health?.status === 'degraded'   ? 'text-yellow-400' :
    health?.status === 'unreachable'? 'text-red-400' : 'text-gray-400'

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      {/* Top nav */}
      <header className="bg-gray-900 border-b border-gray-700 px-6 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <span className="font-bold text-white tracking-wide">IMS</span>
          <span className="text-gray-500 text-sm">Incident Management System</span>
        </div>

        <div className="flex items-center gap-4 text-xs">
          {health && (
            <div className="flex items-center gap-4 text-xs text-gray-500">
              <span className={`font-medium ${healthColor}`}>
                {health.status?.toUpperCase()}
              </span>
              {health.postgres !== undefined && (
                <>
                  <span className={health.postgres ? 'text-green-500' : 'text-red-500'}>
                    PG {health.postgres ? '✓' : '✗'}
                  </span>
                  <span className={health.mongo ? 'text-green-500' : 'text-red-500'}>
                    Mongo {health.mongo ? '✓' : '✗'}
                  </span>
                  <span className={health.redis ? 'text-green-500' : 'text-red-500'}>
                    Redis {health.redis ? '✓' : '✗'}
                  </span>
                </>
              )}
            </div>
          )}
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="text-gray-500 hover:text-white transition-colors"
          >
            API Docs ↗
          </a>
          <a
            href="http://localhost:8000/metrics"
            target="_blank"
            rel="noreferrer"
            className="text-gray-500 hover:text-white transition-colors"
          >
            Metrics ↗
          </a>
        </div>
      </header>

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel — Live feed */}
        <div className="w-96 flex-shrink-0 border-r border-gray-700 overflow-y-auto">
          <LiveFeed
            key={refreshKey}
            onSelect={setSelected}
            selectedId={selected?.id}
          />
        </div>

        {/* Right panel — Incident detail */}
        <div className="flex-1 overflow-y-auto">
          <IncidentDetail
            incident={selected}
            onClose={() => setSelected(null)}
            onUpdated={handleUpdated}
          />
        </div>
      </div>
    </div>
  )
}