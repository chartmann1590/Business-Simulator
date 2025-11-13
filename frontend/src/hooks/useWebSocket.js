import { useState, useEffect, useRef } from 'react'

export function useWebSocket() {
  const [activities, setActivities] = useState([])
  const wsRef = useRef(null)

  useEffect(() => {
    // Use the proxy through Vite dev server
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.hostname}:${window.location.port}/ws`
    
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('WebSocket connected')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        // Store all message types (activity, location_update, etc.)
        if (data.type === 'activity' || data.type === 'location_update') {
          setActivities(prev => [data, ...prev].slice(0, 100)) // Keep last 100
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    ws.onclose = () => {
      console.log('WebSocket disconnected')
      // Attempt to reconnect after 3 seconds
      setTimeout(() => {
        if (wsRef.current?.readyState === WebSocket.CLOSED) {
          // Reconnect logic would go here
        }
      }, 3000)
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  return activities
}

