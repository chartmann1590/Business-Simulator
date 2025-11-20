import { useEffect, useRef } from 'react'
import { getAvatarPath } from '../utils/avatarMapper'

// Helper function to format room names for display
function formatRoomName(roomName) {
  if (!roomName) return 'Unknown'
  return roomName
    .replace(/_/g, ' ')
    .replace(/\s*floor\d+\s*/gi, '')
    .replace(/\s+/g, ' ')
    .trim()
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

function EmployeeAvatar({ employee, position = { x: 0, y: 0 }, onEmployeeClick, onScreenView }) {
  const isWalking = employee.activity_state === 'walking'
  const activityState = employee.activity_state || 'idle'
  const prevPositionRef = useRef(position)
  const isMovingRef = useRef(false)
  
  // Track position changes for smooth transitions
  useEffect(() => {
    const prevPos = prevPositionRef.current
    const hasMoved = prevPos.x !== position.x || prevPos.y !== position.y
    
    if (hasMoved) {
      isMovingRef.current = true
      prevPositionRef.current = position
      
      // Reset moving flag after animation
      const timer = setTimeout(() => {
        isMovingRef.current = false
      }, 500)
      
      return () => clearTimeout(timer)
    }
  }, [position])
  
  // Activity indicator icons
  const getActivityIcon = () => {
    switch (activityState) {
      case 'working':
        return '💼'
      case 'meeting':
        return '🤝'
      case 'break':
        return '☕'
      case 'walking':
        return '🚶'
      case 'training':
        return '📚'
      default:
        return null
    }
  }
  
  const activityIcon = getActivityIcon()
  const isMoving = isMovingRef.current || isWalking
  
  return (
    <div
      className={`absolute transition-all duration-500 ease-in-out cursor-pointer group ${
        isMoving ? 'animate-pulse' : ''
      }`}
      style={{
        left: `${position.x}%`,
        top: `${position.y}%`,
        transform: 'translate(-50%, -50%)',
        zIndex: 10,
        transition: 'left 0.5s ease-in-out, top 0.5s ease-in-out'
      }}
      onClick={() => onEmployeeClick && onEmployeeClick(employee)}
      title={`${employee.name} - ${employee.title}\n${activityState}${isWalking && employee.target_room ? `\nWalking to: ${formatRoomName(employee.target_room)}` : ''}`}
    >
      <div className="relative">
        <img
          src={getAvatarPath(employee)}
          alt={employee.name}
          className={`w-12 h-12 rounded-full border-2 border-white shadow-lg object-cover transition-transform duration-300 ${
            isMoving ? 'animate-bounce scale-110' : 'hover:scale-110'
          }`}
          onError={(e) => {
            e.target.src = '/avatars/office_char_01_manager.png'
          }}
        />
        {activityIcon && (
          <div className="absolute -top-1 -right-1 bg-white rounded-full p-1 shadow-md text-xs animate-pulse">
            {activityIcon}
          </div>
        )}
        {/* Walking destination badge - visible when walking */}
        {isWalking && employee.target_room && (
          <div className="absolute -bottom-8 left-1/2 transform -translate-x-1/2 bg-yellow-500 text-white text-[10px] font-semibold px-2 py-1 rounded-full shadow-lg whitespace-nowrap z-30 border-2 border-yellow-600">
            🚶 → {formatRoomName(employee.target_room)}
          </div>
        )}
        {/* Screen View Button - Only show when working */}
        {activityState === 'working' && employee.status === 'active' && onScreenView && (
          <div
            className="absolute -bottom-1 -right-1 bg-blue-600 hover:bg-blue-700 rounded-full p-1.5 shadow-lg cursor-pointer z-30 opacity-0 group-hover:opacity-100 transition-opacity"
            onClick={(e) => {
              e.stopPropagation()
              onScreenView(employee)
            }}
            title="View Screen"
          >
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          </div>
        )}
        {/* Tooltip */}
        <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20">
          <div className="bg-gray-900 text-white text-xs rounded py-1 px-2 whitespace-nowrap">
            <div className="font-semibold">{employee.name}</div>
            <div className="text-gray-300">{employee.title}</div>
            <div className="text-gray-400 capitalize">{activityState}</div>
            {isWalking && employee.target_room && (
              <div className="text-yellow-400 mt-1">
                Walking to: {formatRoomName(employee.target_room)}
              </div>
            )}
            {activityState === 'working' && employee.status === 'active' && (
              <div className="text-blue-400 mt-1">Click screen icon to view</div>
            )}
          </div>
          <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-1">
            <div className="border-4 border-transparent border-t-gray-900"></div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default EmployeeAvatar


