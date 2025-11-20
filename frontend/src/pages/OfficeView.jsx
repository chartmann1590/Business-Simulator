import { useState, useEffect, useCallback, useRef } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import OfficeLayout from '../components/OfficeLayout'
import RoomDetailModal from '../components/RoomDetailModal'
import EmployeeScreenModal from '../components/EmployeeScreenModal'
import TrainingDetailModal from '../components/TrainingDetailModal'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiGet } from '../utils/api'

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
  const [weather, setWeather] = useState(null)
  const [pets, setPets] = useState([])
  const [birthdayParties, setBirthdayParties] = useState([])
  const [upcomingBirthdays, setUpcomingBirthdays] = useState([])
  const [screenViewEmployee, setScreenViewEmployee] = useState(null)
  const [trainingViewEmployee, setTrainingViewEmployee] = useState(null)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const audioContextRef = useRef(null)
  
  // Get WebSocket messages for real-time updates
  const wsMessages = useWebSocket()
  
  // Handle URL parameters for employee, pet, and floor navigation
  useEffect(() => {
    const employeeId = searchParams.get('employee')
    const petId = searchParams.get('pet')
    const floorParam = searchParams.get('floor')
    
    if (floorParam) {
      const floorNum = parseInt(floorParam, 10)
      if (!isNaN(floorNum) && floorNum > 0) {
        setSelectedFloor(floorNum)
      }
    }
    
    // If pet ID is provided, try to find their room and select it
    if (petId && pets.length > 0) {
      const petIdNum = parseInt(petId, 10)
      if (!isNaN(petIdNum)) {
        const foundPet = pets.find(p => p.id === petIdNum)
        if (foundPet && foundPet.current_room) {
          // Set the floor to the pet's floor
          if (foundPet.floor) {
            setSelectedFloor(foundPet.floor)
          }
          
          // Find the room where the pet is located
          // Pet's current_room might have floor suffix (e.g., "breakroom_floor2") or just be the base name
          if (officeData && officeData.rooms) {
            // Try exact match first
            let petRoom = officeData.rooms.find(room => 
              room.id === foundPet.current_room && 
              room.floor === foundPet.floor
            )
            
            // If no exact match, try matching base room name (remove floor suffix)
            if (!petRoom) {
              const baseRoomName = foundPet.current_room.replace(/_floor\d+$/, '')
              petRoom = officeData.rooms.find(room => 
                room.id === baseRoomName && 
                room.floor === foundPet.floor
              )
            }
            
            if (petRoom) {
              setSelectedRoom(petRoom)
              // Clear the URL parameter after a short delay to allow the view to update
              setTimeout(() => {
                setSearchParams({}, { replace: true })
              }, 1000)
            }
          }
        }
      }
    }
    
    // If employee ID is provided, try to find their room and select it
    if (employeeId && officeData) {
      const employeeIdNum = parseInt(employeeId, 10)
      if (!isNaN(employeeIdNum)) {
        // Find the employee's room
        for (const room of officeData.rooms || []) {
          if (room.employees && Array.isArray(room.employees)) {
            const foundEmployee = room.employees.find(emp => emp.id === employeeIdNum)
            if (foundEmployee) {
              // Set the floor if not already set
              if (room.floor && !floorParam) {
                setSelectedFloor(room.floor)
              }
              // Select the room to highlight the employee
              setSelectedRoom(room)
              // Clear the URL parameter after a short delay to allow the view to update
              setTimeout(() => {
                setSearchParams({}, { replace: true })
              }, 1000)
              break
            }
          }
        }
      }
    }
  }, [searchParams, officeData, pets, setSearchParams])
  
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
    setLoading(true)
    try {
      const result = await apiGet('/api/office-layout')
      const data = result.data || {}
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
    } catch (error) {
      console.error('Error fetching office layout:', error)
      setOfficeData({})
      setEmployees([])
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchWeatherAndPets = useCallback(async () => {
    try {
      const [weatherResult, petsResult, partiesResult, birthdaysResult] = await Promise.all([
        apiGet('/api/weather'),
        apiGet('/api/pets'),
        apiGet('/api/birthdays/parties'),
        apiGet('/api/birthdays/upcoming?days=90')
      ])
      
      if (weatherResult.ok && weatherResult.data) {
        setWeather(weatherResult.data)
      }
      
      if (petsResult.ok && petsResult.data) {
        setPets(Array.isArray(petsResult.data) ? petsResult.data : [])
      }
      
      if (partiesResult.ok && partiesResult.data) {
        setBirthdayParties(Array.isArray(partiesResult.data) ? partiesResult.data : [])
      }
      
      if (birthdaysResult.ok && birthdaysResult.data) {
        setUpcomingBirthdays(Array.isArray(birthdaysResult.data) ? birthdaysResult.data : [])
      }
    } catch (error) {
      console.error('Error fetching weather/pets/parties/birthdays:', error)
    }
  }, [])
  
  useEffect(() => {
    fetchOfficeLayout()
    fetchWeatherAndPets()
    const interval = setInterval(() => {
      fetchOfficeLayout()
      fetchWeatherAndPets()
    }, 5000) // Refresh every 5 seconds
    return () => clearInterval(interval)
  }, [fetchOfficeLayout, fetchWeatherAndPets])
  
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
    // If employee is in training, show training modal instead of navigating to profile
    if (employee.activity_state === 'training' || 
        (employee.current_room && employee.current_room.includes('training_room'))) {
      setTrainingViewEmployee({ id: employee.id, name: employee.name })
      if (soundEnabled) {
        playSound('click')
      }
    } else {
      navigate(`/employees/${employee.id}`)
      if (soundEnabled) {
        playSound('click')
      }
    }
  }

  const handleScreenView = (employee) => {
    setScreenViewEmployee(employee)
    if (soundEnabled) {
      playSound('click')
    }
  }

  const handleCloseScreenView = () => {
    setScreenViewEmployee(null)
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
            </p>
          </div>
          
          {/* Weather Display */}
          {weather && (
            <div className="mb-4 flex items-center space-x-3 bg-white rounded-lg shadow-sm p-3 border border-gray-200 inline-block">
              <div className="text-3xl">
                {weather.condition === 'sunny' && '☀️'}
                {weather.condition === 'cloudy' && '☁️'}
                {weather.condition === 'rainy' && '🌧️'}
                {weather.condition === 'stormy' && '⛈️'}
                {weather.condition === 'snowy' && '❄️'}
              </div>
              <div>
                <p className="text-lg font-semibold">{Math.round(weather.temperature)}°F</p>
                <p className="text-xs text-gray-600">{weather.description}</p>
              </div>
            </div>
          )}
        </div>
        
        <div className="flex items-center justify-between mb-4">
          <div></div>
          
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
        pets={pets.filter(pet => pet.floor === selectedFloor)}
        onEmployeeClick={handleEmployeeClick}
        onRoomClick={handleRoomClick}
        onScreenView={handleScreenView}
      />
      
      {/* Birthday Parties Section */}
      {birthdayParties.length > 0 && (
        <div className="mt-8 border-t border-gray-200 pt-6">
          <div className="mb-4">
            <h3 className="text-xl font-semibold text-gray-700 mb-2">🎉 Birthday Parties</h3>
            <p className="text-sm text-gray-500">
              Scheduled birthday celebrations
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {birthdayParties.map((party) => {
              const partyDate = new Date(party.party_time || party.celebration_date)
              const isToday = partyDate.toDateString() === new Date().toDateString()
              // Party duration is 1 hour, so check if current time is between start and end
              const partyStart = new Date(party.party_time || party.celebration_date)
              const partyEnd = new Date(partyStart.getTime() + 60 * 60 * 1000) // Add 1 hour
              const now = new Date()
              const isHappening = now >= partyStart && now < partyEnd
              
              const handlePartyClick = () => {
                if (isHappening) {
                  // Navigate to the party room
                  setSelectedFloor(party.party_floor)
                  // Find the room by matching party_room
                  const partyRoomId = party.party_room || 'breakroom'
                  const rooms = officeData?.rooms || []
                  // Try to find the room - match by ID, or by name containing "breakroom" on the correct floor
                  let partyRoom = rooms.find(r => 
                    r.id === partyRoomId && r.floor === party.party_floor
                  )
                  // If not found, try matching base room name without floor suffix
                  if (!partyRoom) {
                    const baseRoomId = partyRoomId.replace('_floor2', '').replace('_floor3', '').replace('_floor4', '')
                    partyRoom = rooms.find(r => 
                      (r.id === baseRoomId || r.id === partyRoomId) && 
                      r.floor === party.party_floor &&
                      (r.name && r.name.toLowerCase().includes('breakroom'))
                    )
                  }
                  // Last resort: find any breakroom on the correct floor
                  if (!partyRoom) {
                    partyRoom = rooms.find(r => 
                      r.floor === party.party_floor &&
                      (r.name && r.name.toLowerCase().includes('breakroom'))
                    )
                  }
                  if (partyRoom) {
                    setSelectedRoom(partyRoom)
                    handleRoomClick(partyRoom)
                  }
                }
              }
              
              return (
                <div
                  key={party.id}
                  onClick={handlePartyClick}
                  className={`bg-white rounded-lg p-4 border-2 transition-colors cursor-pointer ${
                    isHappening
                      ? 'border-pink-400 bg-pink-50 hover:border-pink-500'
                      : 'border-gray-200 hover:border-pink-300'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-semibold text-lg">{party.employee_name}</p>
                      <p className="text-sm text-gray-600">Turning {party.age}!</p>
                    </div>
                    {isHappening && (
                      <span className="text-2xl animate-bounce">🎉</span>
                    )}
                  </div>
                  <div className="space-y-1 text-sm">
                    <p className="text-gray-700">
                      <span className="font-medium">When:</span>{' '}
                      {isToday ? 'Today' : partyDate.toLocaleDateString()} at {partyDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                    <p className="text-gray-700">
                      <span className="font-medium">Where:</span>{' '}
                      {party.room_name} on Floor {party.party_floor}
                    </p>
                    <p className="text-gray-600">
                      <span className="font-medium">Attendees:</span>{' '}
                      {party.attendees_count + 1} people (including {party.employee_name})
                    </p>
                  </div>
                  {isHappening && (
                    <div className="mt-3 pt-3 border-t border-pink-200">
                      <p className="text-sm font-semibold text-pink-600">🎊 Party happening now!</p>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
      
      {/* Office Pets Section */}
      {pets.length > 0 && (
        <div className="mt-8 border-t border-gray-200 pt-6">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-xl font-semibold text-gray-700 mb-2">🐾 Office Pets</h3>
              <p className="text-sm text-gray-500">
                {pets.length} pet{pets.length !== 1 ? 's' : ''} roaming the office
              </p>
            </div>
            <button
              onClick={() => navigate('/pet-care')}
              className="px-4 py-2 bg-gradient-to-r from-yellow-400 to-orange-400 hover:from-yellow-500 hover:to-orange-500 text-white rounded-lg font-medium shadow-md hover:shadow-lg transition-all transform hover:scale-105"
            >
              🎮 Play Pet Care Game
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {pets.map((pet) => (
              <div
                key={pet.id}
                className="bg-white rounded-lg p-4 border-2 border-gray-200 hover:border-yellow-400 transition-colors"
              >
                <div className="text-center">
                  <img
                    src={pet.avatar_path}
                    alt={pet.name}
                    className="w-16 h-16 mx-auto rounded-full object-cover border-2 border-yellow-400 mb-2"
                    onError={(e) => {
                      e.target.style.display = 'none'
                    }}
                  />
                  <p className="font-semibold text-sm">{pet.name}</p>
                  <p className="text-xs text-gray-600 capitalize">{pet.pet_type}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    Floor {pet.floor} • {pet.current_room || 'Unknown'}
                  </p>
                  {pet.personality && (
                    <p className="text-xs text-gray-400 mt-1 italic">{pet.personality}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Upcoming Birthdays Section */}
      {upcomingBirthdays.length > 0 && (
        <div className="mt-8 border-t border-gray-200 pt-6">
          <div className="mb-4">
            <h3 className="text-xl font-semibold text-gray-700 mb-2">🎂 Upcoming Birthdays</h3>
            <p className="text-sm text-gray-500">
              Birthdays in the next 90 days
            </p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {upcomingBirthdays.map((bday) => {
              const birthdayDate = new Date(bday.date)
              const isToday = bday.days_until === 0
              
              return (
                <div
                  key={bday.employee_id}
                  className={`bg-white rounded-lg p-4 border-2 transition-colors ${
                    isToday
                      ? 'border-pink-400 bg-pink-50'
                      : 'border-gray-200 hover:border-pink-200'
                  }`}
                >
                  <div className="text-center">
                    <p className="font-semibold text-sm">{bday.employee_name}</p>
                    <p className="text-xs text-gray-600 mt-1">
                      {isToday ? (
                        <span className="font-semibold text-pink-600">🎉 Today!</span>
                      ) : (
                        <>
                          {bday.days_until} day{bday.days_until !== 1 ? 's' : ''} away
                        </>
                      )}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {birthdayDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
      
      <RoomDetailModal
        room={selectedRoom}
        isOpen={!!selectedRoom}
        onClose={handleCloseRoomModal}
        onEmployeeClick={handleEmployeeClick}
        onScreenView={handleScreenView}
      />

      {/* Employee Screen View Modal */}
      {screenViewEmployee && (
        <EmployeeScreenModal
          employeeId={screenViewEmployee.id}
          isOpen={!!screenViewEmployee}
          onClose={handleCloseScreenView}
        />
      )}

      {/* Training Detail Modal */}
      {trainingViewEmployee && (
        <TrainingDetailModal
          employeeId={trainingViewEmployee.id}
          employeeName={trainingViewEmployee.name}
          isOpen={!!trainingViewEmployee}
          onClose={() => setTrainingViewEmployee(null)}
        />
      )}
      
    </div>
  )
}

export default OfficeView

