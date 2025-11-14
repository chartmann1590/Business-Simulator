import { getAvatarPath } from '../utils/avatarMapper'

function EmployeeAvatar({ employee, position = { x: 0, y: 0 }, onEmployeeClick }) {
  const isWalking = employee.activity_state === 'walking'
  const activityState = employee.activity_state || 'idle'
  
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
      default:
        return null
    }
  }
  
  const activityIcon = getActivityIcon()
  
  return (
    <div
      className={`absolute transition-all duration-500 ease-in-out cursor-pointer group ${
        isWalking ? 'animate-pulse' : ''
      }`}
      style={{
        left: `${position.x}%`,
        top: `${position.y}%`,
        transform: 'translate(-50%, -50%)',
        zIndex: 10
      }}
      onClick={() => onEmployeeClick && onEmployeeClick(employee)}
      title={`${employee.name} - ${employee.title}\n${activityState}`}
    >
      <div className="relative">
        <img
          src={getAvatarPath(employee)}
          alt={employee.name}
          className={`w-12 h-12 rounded-full border-2 border-white shadow-lg object-cover ${
            isWalking ? 'animate-bounce' : ''
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
        {/* Tooltip */}
        <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20">
          <div className="bg-gray-900 text-white text-xs rounded py-1 px-2 whitespace-nowrap">
            <div className="font-semibold">{employee.name}</div>
            <div className="text-gray-300">{employee.title}</div>
            <div className="text-gray-400 capitalize">{activityState}</div>
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


