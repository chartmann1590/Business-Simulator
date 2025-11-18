import { useEffect, useState, useRef } from 'react'
import EmployeeAvatar from './EmployeeAvatar'
import ChatBubble from './ChatBubble'

function RoomDetailModal({ room, isOpen, onClose, onEmployeeClick }) {
  const [conversations, setConversations] = useState([])
  const [currentMessageIndices, setCurrentMessageIndices] = useState({})
  const conversationIntervalRef = useRef(null)

  useEffect(() => {
    // Close on Escape key
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = 'unset'
    }
  }, [isOpen, onClose])

  // Fetch conversations when room opens
  useEffect(() => {
    if (!isOpen || !room) {
      setConversations([])
      setCurrentMessageIndices({})
      if (conversationIntervalRef.current) {
        clearInterval(conversationIntervalRef.current)
        conversationIntervalRef.current = null
      }
      return
    }

    const roomEmployees = room.employees || []
    if (roomEmployees.length < 2) {
      setConversations([])
      return
    }

    // Fetch conversations
    const fetchConversations = async () => {
      try {
        const employeeIds = roomEmployees.map(emp => emp.id)
        const response = await fetch('/api/room/conversations', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            room_id: room.id,
            employee_ids: employeeIds
          })
        })
        
        if (response.ok) {
          const data = await response.json()
          setConversations(data.conversations || [])
          // Initialize message indices
          const indices = {}
          data.conversations?.forEach((conv, idx) => {
            indices[idx] = 0
          })
          setCurrentMessageIndices(indices)
        }
      } catch (error) {
        console.error('Error fetching conversations:', error)
      }
    }

    fetchConversations()

    // Refresh conversations every 15 seconds
    conversationIntervalRef.current = setInterval(fetchConversations, 15000)

    return () => {
      if (conversationIntervalRef.current) {
        clearInterval(conversationIntervalRef.current)
        conversationIntervalRef.current = null
      }
    }
  }, [isOpen, room])

  // Cycle through messages in conversations
  useEffect(() => {
    if (!isOpen || conversations.length === 0) {
      return
    }

    const messageInterval = setInterval(() => {
      setCurrentMessageIndices(prev => {
        const newIndices = { ...prev }
        conversations.forEach((conv, idx) => {
          const maxMessages = conv.messages?.length || 0
          if (maxMessages > 0) {
            const current = prev[idx] || 0
            // Advance to next message, or reset to 0 if at the end
            newIndices[idx] = (current + 1) % maxMessages
          }
        })
        return newIndices
      })
    }, 4000) // Change message every 4 seconds

    return () => clearInterval(messageInterval)
  }, [isOpen, conversations])

  if (!isOpen || !room) return null

  const roomEmployees = room.employees || []
  
  // Better positioning for larger view
  const getEmployeePosition = (employeeIndex, totalInRoom) => {
    if (totalInRoom === 0) return { x: 50, y: 50 }
    
    // Use a grid layout for better distribution
    const cols = Math.ceil(Math.sqrt(totalInRoom))
    const rows = Math.ceil(totalInRoom / cols)
    const row = Math.floor(employeeIndex / cols)
    const col = employeeIndex % cols
    
    // Position in percentage with better spacing
    const padding = 20
    const x = padding + (col * (100 - 2 * padding) / Math.max(1, cols - 1))
    const y = padding + (row * (100 - 2 * padding) / Math.max(1, rows - 1))
    
    return { 
      x: cols === 1 ? 50 : Math.min(80, Math.max(20, x)), 
      y: rows === 1 ? 50 : Math.min(80, Math.max(20, y))
    }
  }

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-75 p-4"
      onClick={onClose}
    >
      <div 
        className="bg-white rounded-lg shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 bg-gray-50">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{room.name}</h2>
            <p className="text-sm text-gray-600 mt-1">
              {roomEmployees.length} {roomEmployees.length === 1 ? 'employee' : 'employees'}
              {room.capacity && ` • Capacity: ${room.capacity}`}
            </p>
            {/* Show meeting information for conference rooms */}
            {room.meeting_info && room.meeting_info.length > 0 && (
              <div className="mt-3 p-4 bg-blue-50 rounded-lg border-2 border-blue-300 shadow-sm">
                <div className="flex items-center mb-2">
                  <svg className="w-5 h-5 text-blue-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  <h3 className="text-base font-bold text-blue-900">Meeting in Progress</h3>
                </div>
                {room.meeting_info.map((meeting, idx) => (
                  <div key={idx} className="mb-3 last:mb-0">
                    <p className="text-sm font-semibold text-blue-900 mb-2 leading-relaxed">
                      {meeting.description}
                    </p>
                    {meeting.participants && meeting.participants.length > 0 && (
                      <div className="flex items-start">
                        <span className="text-xs font-medium text-blue-700 mr-2">Attendees:</span>
                        <span className="text-xs text-blue-600 flex-1">
                          {meeting.participants.join(', ')}
                        </span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors text-2xl font-bold"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        {/* Room View */}
        <div className="flex-1 relative overflow-hidden bg-gray-100" style={{ minHeight: '500px' }}>
          {/* Room background image - larger and more visible */}
          <div className="absolute inset-0">
            <img
              src={room.image_path}
              alt={room.name}
              className="w-full h-full object-contain"
              onError={(e) => {
                e.target.style.display = 'none'
              }}
            />
          </div>
          
          {/* Room overlay with employees */}
          <div className="absolute inset-0">
            {/* Employees */}
            {roomEmployees.map((employee, index) => (
              <EmployeeAvatar
                key={employee.id}
                employee={employee}
                position={getEmployeePosition(index, roomEmployees.length)}
                onEmployeeClick={onEmployeeClick}
              />
            ))}
            
            {/* Chat bubbles for conversations */}
            {conversations.map((conversation, convIndex) => {
              // Find employee positions
              const emp1Index = roomEmployees.findIndex(e => e.id === conversation.employee1_id)
              const emp2Index = roomEmployees.findIndex(e => e.id === conversation.employee2_id)
              
              if (emp1Index === -1 || emp2Index === -1) return null
              
              const emp1Pos = getEmployeePosition(emp1Index, roomEmployees.length)
              const emp2Pos = getEmployeePosition(emp2Index, roomEmployees.length)
              
              // Get current message index for this conversation
              const currentMsgIndex = currentMessageIndices[convIndex] || 0
              const messages = conversation.messages || []
              
              if (messages.length === 0) return null
              
              // Show only the current message for each conversation
              const currentMessage = messages[currentMsgIndex]
              if (!currentMessage) return null
              
              const isEmp1 = currentMessage.speaker === conversation.employee1_name
              const employeePos = isEmp1 ? emp1Pos : emp2Pos
              
              // Position bubble above the employee, slightly offset
              const bubblePos = {
                x: employeePos.x + (isEmp1 ? -8 : 8),
                y: employeePos.y - 25
              }
              
              return (
                <ChatBubble
                  key={`${convIndex}-${currentMsgIndex}`}
                  message={currentMessage.text}
                  speaker={currentMessage.speaker}
                  employeeId={isEmp1 ? conversation.employee1_id : conversation.employee2_id}
                  position={bubblePos}
                  isVisible={true}
                />
              )
            })}
            
            {/* Empty state */}
            {roomEmployees.length === 0 && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center">
                  <div className="text-gray-400 text-lg mb-2">No employees in this room</div>
                  <div className="text-gray-300 text-sm">Employees will appear here when they enter</div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Employee List */}
        {roomEmployees.length > 0 && (
          <div className="border-t border-gray-200 bg-gray-50 p-4 max-h-48 overflow-y-auto">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Employees in this room:</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {roomEmployees.map((employee) => (
                <div
                  key={employee.id}
                  onClick={() => onEmployeeClick && onEmployeeClick(employee)}
                  className="flex items-center space-x-2 p-2 rounded-lg hover:bg-white cursor-pointer transition-colors"
                >
                  <img
                    src={employee.avatar_path || '/avatars/office_char_01_manager.png'}
                    alt={employee.name}
                    className="w-10 h-10 rounded-full object-cover"
                    onError={(e) => {
                      e.target.src = '/avatars/office_char_01_manager.png'
                    }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 truncate">{employee.name}</div>
                    <div className="text-xs text-gray-500 truncate">{employee.title}</div>
                    {employee.activity_state && (
                      <div className="text-xs text-gray-400 capitalize">{employee.activity_state}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default RoomDetailModal

