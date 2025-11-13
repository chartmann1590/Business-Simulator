import EmployeeAvatar from './EmployeeAvatar'

function OfficeLayout({ rooms, employees, onEmployeeClick, onRoomClick }) {
  // Generate random positions for employees within a room
  const getEmployeePosition = (employeeIndex, totalInRoom) => {
    // Distribute employees evenly across the room
    const cols = Math.ceil(Math.sqrt(Math.max(1, totalInRoom)))
    const row = Math.floor(employeeIndex / cols)
    const col = employeeIndex % cols
    
    // Position in percentage (with some padding from edges)
    const padding = 15
    const x = padding + (col * (100 - 2 * padding) / Math.max(1, cols - 1))
    const y = padding + (row * (100 - 2 * padding) / Math.max(1, cols - 1))
    
    return { x: Math.min(85, Math.max(15, x)), y: Math.min(85, Math.max(15, y)) }
  }
  
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 p-4">
      {rooms.map((room) => {
        // Use employees from room data if available, otherwise filter from employees array
        const roomEmployees = room.employees && room.employees.length > 0
          ? room.employees
          : employees.filter(
              emp => (emp.current_room || emp.home_room) === room.id
            )
        
        return (
          <div
            key={room.id}
            onClick={() => onRoomClick && onRoomClick(room)}
            className="relative bg-white rounded-lg shadow-md overflow-hidden border-2 border-gray-200 hover:border-blue-400 transition-colors cursor-pointer"
            style={{ minHeight: '200px' }}
          >
            {/* Room background image */}
            <div className="absolute inset-0 opacity-30">
              <img
                src={room.image_path}
                alt={room.name}
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.target.style.display = 'none'
                }}
              />
            </div>
            
            {/* Room overlay with employees */}
            <div className="relative z-10 h-full min-h-[200px]">
              {/* Room label */}
              <div className="absolute top-2 left-2 bg-black bg-opacity-70 text-white text-xs font-semibold px-2 py-1 rounded">
                {room.name}
              </div>
              
              {/* Employee count badge */}
              {roomEmployees.length > 0 && (
                <div className="absolute top-2 right-2 bg-blue-600 text-white text-xs font-semibold px-2 py-1 rounded-full">
                  {roomEmployees.length}
                </div>
              )}
              
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
                  <div className="text-gray-400 text-sm">Empty</div>
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default OfficeLayout

