import { useEffect } from 'react'
import EmployeeAvatar from './EmployeeAvatar'

function RoomDetailModal({ room, isOpen, onClose, onEmployeeClick }) {
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

