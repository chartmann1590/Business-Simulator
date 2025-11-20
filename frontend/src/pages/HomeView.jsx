import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import HomeLayout from '../components/HomeLayout'
import { apiGet, apiPost } from '../utils/api'
import { useWebSocket } from '../hooks/useWebSocket'

function HomeView() {
  const [homeData, setHomeData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [employees, setEmployees] = useState([])
  const [selectedEmployeeId, setSelectedEmployeeId] = useState(null)
  const [viewType, setViewType] = useState('interior') // 'interior' or 'exterior'
  const [conversations, setConversations] = useState([])
  const chatLogRef = useRef(null)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const conversationIntervalRef = useRef(null)
  
  // Get WebSocket messages for real-time updates
  const wsMessages = useWebSocket()
  
  // Handle URL parameters for employee navigation
  useEffect(() => {
    const employeeId = searchParams.get('employee')
    
    if (employeeId) {
      const employeeIdNum = parseInt(employeeId, 10)
      if (!isNaN(employeeIdNum)) {
        setSelectedEmployeeId(employeeIdNum)
        // Clear the URL parameter after a short delay
        setTimeout(() => {
          setSearchParams({}, { replace: true })
        }, 1000)
      }
    }
  }, [searchParams, setSearchParams])
  
  // Fetch list of employees with home data
  const fetchEmployees = useCallback(async () => {
    console.log('[HomeView] Fetching employees...')
    try {
      console.log('[HomeView] Making API call to /api/home/employees')
      
      // Add timeout to prevent hanging
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Request timeout')), 10000)
      )
      
      const apiPromise = apiGet('/api/home/employees')
      const result = await Promise.race([apiPromise, timeoutPromise])
      
      console.log('[HomeView] API result:', result)
      console.log('[HomeView] API result.ok:', result?.ok)
      console.log('[HomeView] API result.data:', result?.data)
      
      if (result && result.ok && result.data) {
        const employeesList = Array.isArray(result.data) ? result.data : []
        console.log('[HomeView] Employees loaded:', employeesList.length)
        setEmployees(employeesList)
        
        // Set first employee as default if none selected
        if (employeesList.length > 0) {
          setSelectedEmployeeId(prev => prev || employeesList[0].id)
        }
      } else {
        console.warn('[HomeView] API result not ok or no data', result)
        setEmployees([])
      }
    } catch (error) {
      console.error('[HomeView] Error fetching employees:', error)
      console.error('[HomeView] Error stack:', error.stack)
      setEmployees([])
    }
  }, [])
  
  // Fetch home layout data for selected employee
  const fetchHomeLayout = useCallback(async () => {
    if (!selectedEmployeeId) {
      setHomeData(null)
      setLoading(false)
      return
    }
    
    setLoading(true)
    try {
      const result = await apiGet(`/api/home/layout/${selectedEmployeeId}?view=${viewType}`)
      if (result.ok && result.data) {
        setHomeData(result.data)
      } else {
        setHomeData(null)
      }
    } catch (error) {
      console.error('Error fetching home layout:', error)
      setHomeData(null)
    } finally {
      setLoading(false)
    }
  }, [selectedEmployeeId, viewType])
  
  // Generate home conversations
  const generateConversations = useCallback(async () => {
    if (!selectedEmployeeId) return
    
    try {
      const result = await apiPost('/api/home/conversations', {
        employee_id: selectedEmployeeId
      })
      if (result.ok && result.data && result.data.conversations) {
        setConversations(result.data.conversations)
      }
    } catch (error) {
      console.error('Error generating conversations:', error)
    }
  }, [selectedEmployeeId])
  
  
  // Initial data fetch
  useEffect(() => {
    fetchEmployees()
  }, [fetchEmployees])
  
  // Fetch home layout when employee or view changes
  useEffect(() => {
    fetchHomeLayout()
  }, [fetchHomeLayout])
  
  // Generate conversations when employee changes, then periodically
  useEffect(() => {
    if (!selectedEmployeeId) return
    
    // Generate initial conversations
    generateConversations()
    
    // Set up periodic conversation generation (every 30 seconds)
    conversationIntervalRef.current = setInterval(() => {
      generateConversations()
    }, 30000)
    
    return () => {
      if (conversationIntervalRef.current) {
        clearInterval(conversationIntervalRef.current)
      }
    }
  }, [selectedEmployeeId, generateConversations])
  
  // Auto-scroll chat log to bottom when new conversations arrive
  useEffect(() => {
    if (chatLogRef.current && conversations.length > 0) {
      chatLogRef.current.scrollTop = chatLogRef.current.scrollHeight
    }
  }, [conversations])
  
  // Handle employee selection
  const handleEmployeeChange = (e) => {
    const newEmployeeId = parseInt(e.target.value, 10)
    if (!isNaN(newEmployeeId)) {
      setSelectedEmployeeId(newEmployeeId)
      setConversations([]) // Clear conversations when switching employees
    }
  }
  
  // Handle view type toggle
  const handleViewToggle = () => {
    setViewType(prev => prev === 'interior' ? 'exterior' : 'interior')
    // Conversations will regenerate automatically via useEffect dependency on viewType
  }
  
  // Handle occupant click
  const handleOccupantClick = (occupant) => {
    if (occupant.type === 'employee') {
      navigate(`/employees/${occupant.id}`)
    }
    // Could add more actions for family members or pets
  }
  
  const selectedEmployee = employees.find(e => e.id === selectedEmployeeId)
  
  if (loading && !homeData) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center h-96">
          <div className="text-gray-400">Loading home data...</div>
        </div>
      </div>
    )
  }
  
  return (
    <div className="p-6">
      {/* Header with controls */}
      <div className="mb-6 space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold text-gray-900">Home View</h1>
          <div className="flex items-center space-x-4">
            {/* Employee dropdown */}
            <div className="flex items-center space-x-2">
              <label htmlFor="employee-select" className="text-sm font-medium text-gray-700">
                Employee:
              </label>
              <select
                id="employee-select"
                value={selectedEmployeeId || ''}
                onChange={handleEmployeeChange}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                {employees.map(emp => (
                  <option key={emp.id} value={emp.id}>
                    {emp.name} {emp.family_count > 0 && `(${emp.family_count} family)`} {emp.pet_count > 0 && `[${emp.pet_count} pet${emp.pet_count > 1 ? 's' : ''}]`}
                  </option>
                ))}
              </select>
            </div>
            
            {/* View toggle */}
            <button
              onClick={handleViewToggle}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              {viewType === 'interior' ? 'Show Exterior' : 'Show Interior'}
            </button>
          </div>
        </div>
        
        {/* Employee info */}
        {selectedEmployee && (
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center space-x-4">
              {selectedEmployee.avatar_path && (
                <img
                  src={selectedEmployee.avatar_path}
                  alt={selectedEmployee.name}
                  className="w-16 h-16 rounded-full object-cover border-2 border-blue-400"
                />
              )}
              <div>
                <h2 className="text-xl font-semibold text-gray-900">{selectedEmployee.name}</h2>
                <p className="text-sm text-gray-600">{selectedEmployee.title}</p>
                {selectedEmployee.home_settings && (
                  <p className="text-xs text-gray-500 mt-1">
                    {selectedEmployee.home_settings.home_address}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
      
      {/* Home layout and chat log */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Home layout - takes 2/3 of space */}
        <div className="lg:col-span-2">
          {homeData ? (
            <HomeLayout
              homeData={homeData}
              conversations={conversations}
              onOccupantClick={handleOccupantClick}
            />
          ) : (
            <div className="flex items-center justify-center h-96 bg-gray-50 rounded-lg">
              <div className="text-gray-400">
                {selectedEmployeeId ? 'No home data available for this employee' : 'Please select an employee'}
              </div>
            </div>
          )}
        </div>
        
        {/* Chat log - takes 1/3 of space */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow-md border-2 border-gray-200 flex flex-col" style={{ minHeight: '500px', maxHeight: '800px' }}>
            <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 rounded-t-lg">
              <h2 className="text-lg font-semibold text-gray-900">Home Chat Log</h2>
              <p className="text-xs text-gray-500 mt-1">Conversations in the home</p>
            </div>
            
            <div ref={chatLogRef} className="flex-1 overflow-y-auto p-4 space-y-4" style={{ minHeight: '400px' }}>
              {conversations.length === 0 ? (
                <div className="text-center text-gray-400 py-8">
                  <p className="text-sm">No conversations yet</p>
                  <p className="text-xs mt-1">Conversations will appear here as family members chat</p>
                </div>
              ) : (
                conversations.map((conversation, convIndex) => {
                  const messages = conversation.messages || []
                  if (messages.length === 0) return null
                  
                  // Determine participants
                  let participant1Name = null
                  let participant2Name = null
                  
                  if (conversation.employee_id && conversation.family_member_id) {
                    participant1Name = conversation.employee_name
                    participant2Name = conversation.family_member_name
                  } else if (conversation.family_member1_id && conversation.family_member2_id) {
                    participant1Name = conversation.family_member1_name
                    participant2Name = conversation.family_member2_name
                  }
                  
                  if (!participant1Name || !participant2Name) return null
                  
                  return (
                    <div key={convIndex} className="border-b border-gray-200 pb-4 last:border-b-0 last:pb-0">
                      <div className="mb-2">
                        <p className="text-xs font-semibold text-gray-600">
                          {participant1Name} & {participant2Name}
                        </p>
                      </div>
                      <div className="space-y-2">
                        {messages.map((message, msgIndex) => {
                          const isParticipant1 = message.speaker === participant1Name
                          return (
                            <div
                              key={msgIndex}
                              className={`flex ${isParticipant1 ? 'justify-start' : 'justify-end'}`}
                            >
                              <div className={`max-w-[85%] rounded-lg px-3 py-2 ${
                                isParticipant1
                                  ? 'bg-blue-50 text-gray-900 border border-blue-200'
                                  : 'bg-green-50 text-gray-900 border border-green-200'
                              }`}>
                                <p className="text-xs font-semibold text-gray-700 mb-1">
                                  {message.speaker}
                                </p>
                                <p className="text-sm leading-relaxed">{message.text}</p>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default HomeView

