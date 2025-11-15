import { useState, useEffect, useCallback, useRef } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import OfficeLayout from '../components/OfficeLayout'
import RoomDetailModal from '../components/RoomDetailModal'
import { useNavigate } from 'react-router-dom'

// Animated number component
function AnimatedNumber({ value, duration = 500 }) {
  const numValue = Number(value) || 0
  const [displayValue, setDisplayValue] = useState(numValue)
  const prevValueRef = useRef(numValue)
  const animationFrameRef = useRef(null)
  
  useEffect(() => {
    if (prevValueRef.current !== numValue) {
      // Cancel any ongoing animation
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
      
      const startValue = prevValueRef.current
      const endValue = numValue
      const startTime = Date.now()
      
      const animate = () => {
        const now = Date.now()
        const elapsed = now - startTime
        const progress = Math.min(elapsed / duration, 1)
        
        // Easing function for smooth animation
        const easeOutQuart = 1 - Math.pow(1 - progress, 4)
        const currentValue = Math.round(startValue + (endValue - startValue) * easeOutQuart)
        
        setDisplayValue(currentValue)
        
        if (progress < 1) {
          animationFrameRef.current = requestAnimationFrame(animate)
        } else {
          setDisplayValue(endValue)
          prevValueRef.current = numValue
        }
      }
      
      animationFrameRef.current = requestAnimationFrame(animate)
    }
    
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [numValue, duration])
  
  return <span>{displayValue}</span>
}

// Loading skeleton component
function LoadingSkeleton() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 p-4">
      {[...Array(10)].map((_, i) => (
        <div
          key={i}
          className="relative bg-gray-200 rounded-lg overflow-hidden border-2 border-gray-200"
          style={{ minHeight: '200px' }}
        >
          <div className="absolute inset-0 animate-pulse">
            <div className="h-full bg-gradient-to-br from-gray-200 via-gray-300 to-gray-200" />
          </div>
          <div className="absolute top-2 left-2 bg-gray-400 h-6 w-24 rounded animate-pulse" />
          <div className="absolute top-2 right-2 bg-gray-400 h-6 w-12 rounded-full animate-pulse" />
        </div>
      ))}
    </div>
  )
}

function OfficeView() {
  const [officeData, setOfficeData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [employees, setEmployees] = useState([])
  const [selectedRoom, setSelectedRoom] = useState(null)
  const [selectedFloor, setSelectedFloor] = useState(1)  // Default to floor 1
  const [soundEnabled, setSoundEnabled] = useState(false) // Muted by default
  const navigate = useNavigate()
  const audioContextRef = useRef(null)
  
  // Get WebSocket messages for real-time updates
  const wsMessages = useWebSocket()
  
  // Simple sound effect generator - defined early so it can be used in useEffects
  const playSound = useCallback((type) => {
    if (!audioContextRef.current) return
    
    try {
      const ctx = audioContextRef.current
      const oscillator = ctx.createOscillator()
      const gainNode = ctx.createGain()
      
      oscillator.connect(gainNode)
      gainNode.connect(ctx.destination)
      
      switch (type) {
        case 'move':
          oscillator.frequency.value = 440
          oscillator.type = 'sine'
          gainNode.gain.setValueAtTime(0.1, ctx.currentTime)
          gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.1)
          oscillator.start(ctx.currentTime)
          oscillator.stop(ctx.currentTime + 0.1)
          break
        case 'click':
          oscillator.frequency.value = 800
          oscillator.type = 'sine'
          gainNode.gain.setValueAtTime(0.05, ctx.currentTime)
          gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.05)
          oscillator.start(ctx.currentTime)
          oscillator.stop(ctx.currentTime + 0.05)
          break
        default:
          break
      }
    } catch (e) {
      // Silently fail if audio context is not available
      console.warn('Sound playback failed:', e)
    }
  }, [])
  
  const fetchOfficeLayout = useCallback(async () => {
    try {
      const response = await fetch('/api/office-layout')
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data = await response.json()
      setOfficeData(data)
      
      // Flatten employees from all rooms into a map for easy lookup
      const employeesMap = new Map()
      if (data.rooms && Array.isArray(data.rooms)) {
        data.rooms.forEach(room => {
          if (room.employees && Array.isArray(room.employees)) {
            room.employees.forEach(emp => {
              employeesMap.set(emp.id, emp)
            })
          }
        })
      }
      setEmployees(Array.from(employeesMap.values()))
      
      setLoading(false)
    } catch (error) {
      console.error('Error fetching office layout:', error)
      setLoading(false)
    }
  }, [])
  
  useEffect(() => {
    fetchOfficeLayout()
    const interval = setInterval(fetchOfficeLayout, 5000) // Refresh every 5 seconds
    return () => clearInterval(interval)
  }, [fetchOfficeLayout])
  
  // Initialize audio context for sound effects
  useEffect(() => {
    if (soundEnabled && !audioContextRef.current) {
      try {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)()
      } catch (e) {
        console.warn('Audio context not supported:', e)
      }
    }
  }, [soundEnabled])
  
  // Handle WebSocket location updates - trigger a refresh
  useEffect(() => {
    const hasLocationUpdate = wsMessages.some(msg => msg.type === 'location_update')
    if (hasLocationUpdate) {
      // Refresh office layout to get updated positions
      fetchOfficeLayout()
      
      // Play sound effect if enabled
      if (soundEnabled && audioContextRef.current) {
        playSound('move')
      }
    }
  }, [wsMessages, fetchOfficeLayout, soundEnabled, playSound])
  
  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Don't handle keyboard shortcuts if user is typing in an input
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return
      }
      
      switch (e.key) {
        case 'ArrowLeft':
          e.preventDefault()
          setSelectedFloor(prev => {
            const floors = officeData?.floors || [1]
            const currentIndex = floors.indexOf(prev)
            return currentIndex > 0 ? floors[currentIndex - 1] : prev
          })
          break
        case 'ArrowRight':
          e.preventDefault()
          setSelectedFloor(prev => {
            const floors = officeData?.floors || [1]
            const currentIndex = floors.indexOf(prev)
            return currentIndex < floors.length - 1 ? floors[currentIndex + 1] : prev
          })
          break
        case 'Escape':
          if (selectedRoom) {
            setSelectedRoom(null)
          }
          break
        default:
          break
      }
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedFloor, officeData, selectedRoom])
  
  const handleRoomClick = (room) => {
    setSelectedRoom(room)
    if (soundEnabled) {
      playSound('click')
    }
  }
  
  const handleEmployeeClick = (employee) => {
    navigate(`/employees/${employee.id}`)
    if (soundEnabled) {
      playSound('click')
    }
  }
  
  const handleCloseRoomModal = () => {
    setSelectedRoom(null)
  }
  
  const handleFloorChange = (floor) => {
    setSelectedFloor(floor)
    if (soundEnabled) {
      playSound('click')
    }
  }
  
  if (loading && !officeData) {
    return (
      <div className="px-4 py-6">
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="h-9 w-48 bg-gray-200 rounded animate-pulse mb-2"></div>
              <div className="h-5 w-64 bg-gray-200 rounded animate-pulse"></div>
            </div>
          </div>
        </div>
        <LoadingSkeleton />
      </div>
    )
  }
  
  if (!officeData || !officeData.rooms) {
    return (
      <div className="px-4 py-6">
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">Unable to load office layout</p>
          <button
            onClick={fetchOfficeLayout}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }
  
  const terminatedEmployees = officeData?.terminated_employees || []
  const hasTerminated = terminatedEmployees.length > 0

  // Get rooms for selected floor
  const roomsForFloor = officeData?.rooms_by_floor?.[selectedFloor] || officeData?.rooms?.filter(r => r.floor === selectedFloor) || []
  const availableFloors = officeData?.floors || [1]

  return (
    <div className="px-4 py-6">
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-3xl font-bold text-gray-900 mb-2">Office View</h2>
            <p className="text-gray-600">
              <AnimatedNumber value={officeData?.total_employees || 0} /> active employees across{' '}
              <AnimatedNumber value={officeData?.rooms?.length || 0} /> rooms
              {hasTerminated && (
                <>
                  {' • '}
                  <AnimatedNumber value={officeData?.total_terminated || 0} /> terminated
                </>
              )}
            </p>
          </div>
          
          {/* Controls */}
          <div className="flex items-center space-x-4">
            {/* Sound Toggle */}
            <button
              onClick={() => setSoundEnabled(!soundEnabled)}
              className={`p-2 rounded-lg transition-colors ${
                soundEnabled
                  ? 'bg-blue-100 text-blue-600 hover:bg-blue-200'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
              title={soundEnabled ? 'Sound enabled (click to disable)' : 'Sound disabled (click to enable)'}
            >
              {soundEnabled ? (
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M9.383 3.076A1 1 0 0110 4v12a1 1 0 01-1.617.793L4.383 13H2a1 1 0 01-1-1V8a1 1 0 011-1h2.383l4.617-3.793a1 1 0 011.383.07zM14.657 2.929a1 1 0 011.414 0A9.972 9.972 0 0119 10a9.972 9.972 0 01-2.929 7.071 1 1 0 01-1.414-1.414A7.971 7.971 0 0017 10c0-2.21-.894-4.208-2.343-5.657a1 1 0 010-1.414zm-2.829 2.828a1 1 0 011.415 0A5.983 5.983 0 0115 10a5.984 5.984 0 01-1.757 4.243 1 1 0 01-1.415-1.415A3.984 3.984 0 0013 10a3.983 3.983 0 00-1.172-2.828 1 1 0 010-1.415z" clipRule="evenodd" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M9.383 3.076A1 1 0 0110 4v12a1 1 0 01-1.617.793L4.383 13H2a1 1 0 01-1-1V8a1 1 0 011-1h2.383l4.617-3.793a1 1 0 011.383.07zM14.657 2.929a1 1 0 011.414 0A9.972 9.972 0 0119 10a9.972 9.972 0 01-2.929 7.071 1 1 0 01-1.414-1.414A7.971 7.971 0 0017 10c0-2.21-.894-4.208-2.343-5.657a1 1 0 010-1.414zm-2.829 2.828a1 1 0 011.415 0A5.983 5.983 0 0115 10a5.984 5.984 0 01-1.757 4.243 1 1 0 01-1.415-1.415A3.984 3.984 0 0013 10a3.983 3.983 0 00-1.172-2.828 1 1 0 010-1.415z" clipRule="evenodd" />
                  <path d="M3.28 2.22a.75.75 0 00-1.06 1.06l14.5 14.5a.75.75 0 101.06-1.06L3.28 2.22z" />
                </svg>
              )}
            </button>
            
            {/* Floor Selector */}
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium text-gray-700">Floor:</span>
              <div className="flex bg-gray-100 rounded-lg p-1">
                {availableFloors.map((floor) => (
                  <button
                    key={floor}
                    onClick={() => handleFloorChange(floor)}
                    className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                      selectedFloor === floor
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-200'
                    }`}
                  >
                    Floor {floor}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Keyboard hint */}
            <div className="text-xs text-gray-500 hidden md:block">
              <kbd className="px-2 py-1 bg-gray-200 rounded">←</kbd> / <kbd className="px-2 py-1 bg-gray-200 rounded">→</kbd> to navigate
            </div>
          </div>
        </div>
      </div>
      
      <OfficeLayout
        rooms={roomsForFloor}
        employees={[]}
        onEmployeeClick={handleEmployeeClick}
        onRoomClick={handleRoomClick}
      />
      
      <RoomDetailModal
        room={selectedRoom}
        isOpen={!!selectedRoom}
        onClose={handleCloseRoomModal}
        onEmployeeClick={handleEmployeeClick}
      />
      
      {hasTerminated && (
        <div className="mt-8 border-t border-gray-200 pt-6">
          <div className="mb-4">
            <h3 className="text-xl font-semibold text-gray-700 mb-2">Terminated Employees</h3>
            <p className="text-sm text-gray-500">
              {terminatedEmployees.length} former employee{terminatedEmployees.length !== 1 ? 's' : ''}
            </p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {terminatedEmployees.map((employee) => (
              <div
                key={employee.id}
                onClick={() => handleEmployeeClick(employee)}
                className="bg-gray-100 rounded-lg p-4 border-2 border-gray-300 hover:border-gray-400 cursor-pointer transition-colors opacity-75"
              >
                <div className="flex items-center space-x-3">
                  {employee.avatar_path ? (
                    <img
                      src={employee.avatar_path}
                      alt={employee.name}
                      className="w-12 h-12 rounded-full object-cover"
                      onError={(e) => {
                        e.target.style.display = 'none'
                        e.target.nextSibling.style.display = 'flex'
                      }}
                    />
                  ) : null}
                  <div className={`w-12 h-12 rounded-full bg-gray-400 flex items-center justify-center text-white font-semibold ${employee.avatar_path ? 'hidden' : 'flex'}`}>
                    {employee.name.split(' ').map(n => n[0]).join('').toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-700 truncate">{employee.name}</p>
                    <p className="text-xs text-gray-500 truncate">{employee.title}</p>
                    {employee.fired_at && (
                      <p className="text-xs text-gray-400 mt-1">
                        Terminated: {new Date(employee.fired_at).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default OfficeView

