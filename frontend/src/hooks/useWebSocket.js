import { useEffect, useRef, useCallback } from 'react'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/feed'

export function useWebSocket(onMessage) {
  const ws = useRef(null)
  const reconnectTimer = useRef(null)
  const isMounted = useRef(true)

  const connect = useCallback(() => {
    if (!isMounted.current) return

    try {
      ws.current = new WebSocket(WS_URL)

      ws.current.onopen = () => {
        console.log('[WebSocket] Connected')
        if (reconnectTimer.current) {
          clearTimeout(reconnectTimer.current)
          reconnectTimer.current = null
        }
      }

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type !== 'heartbeat') {
            onMessage(data)
          }
        } catch (e) {
          // ignore malformed messages
        }
      }

      ws.current.onclose = () => {
        console.log('[WebSocket] Disconnected — reconnecting in 3s')
        if (isMounted.current) {
          reconnectTimer.current = setTimeout(connect, 3000)
        }
      }

      ws.current.onerror = (err) => {
        console.error('[WebSocket] Error:', err)
        ws.current?.close()
      }
    } catch (e) {
      console.error('[WebSocket] Failed to connect:', e)
      if (isMounted.current) {
        reconnectTimer.current = setTimeout(connect, 3000)
      }
    }
  }, [onMessage])

  useEffect(() => {
    isMounted.current = true
    connect()
    return () => {
      isMounted.current = false
      clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [connect])
}