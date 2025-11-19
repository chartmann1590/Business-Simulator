import EmployeeAvatar from './EmployeeAvatar'

function OfficeLayout({ rooms, employees, pets = [], onEmployeeClick, onRoomClick, onScreenView }) {
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
        
        const roomOccupancy = roomEmployees.length
        const roomCapacity = room.capacity || 999
        const isFull = roomOccupancy >= roomCapacity
        const occupancyPercentage = roomCapacity > 0 ? (roomOccupancy / roomCapacity) * 100 : 0
        
        return (
          <div
            key={room.id}
            onClick={() => onRoomClick && onRoomClick(room)}
            className="relative bg-white rounded-lg shadow-md overflow-hidden border-2 border-gray-200 hover:border-blue-400 transition-all duration-300 cursor-pointer hover:scale-105 hover:shadow-xl group"
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
              
              {/* Employee count badge with capacity indicator */}
              <div className="absolute top-2 right-2 flex items-center space-x-1">
                {roomEmployees.length > 0 && (
                  <div className={`text-xs font-semibold px-2 py-1 rounded-full ${
                    isFull 
                      ? 'bg-red-600 text-white' 
                      : occupancyPercentage >= 80 
                        ? 'bg-yellow-600 text-white' 
                        : 'bg-blue-600 text-white'
                  }`}>
                    {roomEmployees.length}{roomCapacity < 999 && `/${roomCapacity}`}
                  </div>
                )}
                {roomEmployees.length === 0 && roomCapacity < 999 && (
                  <div className="bg-gray-400 text-white text-xs font-semibold px-2 py-1 rounded-full">
                    0/{roomCapacity}
                  </div>
                )}
              </div>
              
              {/* Capacity indicator bar */}
              {roomCapacity < 999 && (
                <div className="absolute bottom-0 left-0 right-0 h-1 bg-gray-200">
                  <div 
                    className={`h-full transition-all duration-300 ${
                      isFull 
                        ? 'bg-red-500' 
                        : occupancyPercentage >= 80 
                          ? 'bg-yellow-500' 
                          : 'bg-green-500'
                    }`}
                    style={{ width: `${Math.min(100, occupancyPercentage)}%` }}
                  />
                </div>
              )}
              
              {/* Hover info overlay */}
              <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-20 transition-all duration-300 pointer-events-none" />
              <div className="absolute bottom-2 left-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
                <div className="bg-black bg-opacity-75 text-white text-xs px-2 py-1 rounded">
                  {roomCapacity < 999 ? (
                    <div>
                      <div className="font-semibold">{room.name}</div>
                      <div className="text-gray-300">
                        {roomOccupancy} / {roomCapacity} ({Math.round(occupancyPercentage)}%)
                        {isFull && ' • Full'}
                      </div>
                    </div>
                  ) : (
                    <div className="font-semibold">{room.name}</div>
                  )}
                </div>
              </div>
              
              {/* Employees */}
              {roomEmployees.map((employee, index) => (
                <EmployeeAvatar
                  key={employee.id}
                  employee={employee}
                  position={getEmployeePosition(index, roomEmployees.length)}
                  onEmployeeClick={onEmployeeClick}
                  onScreenView={onScreenView}
                />
              ))}
              
              {/* Pets in this room */}
              {pets.filter(pet => pet.current_room === room.id && pet.floor === room.floor).map((pet, index) => {
                const totalInRoom = roomEmployees.length + pets.filter(p => p.current_room === room.id && p.floor === room.floor).length
                const petIndex = roomEmployees.length + index
                const position = getEmployeePosition(petIndex, totalInRoom)
                return (
                  <div
                    key={pet.id}
                    className="absolute z-20"
                    style={{
                      left: `${position.x}%`,
                      top: `${position.y}%`,
                      transform: 'translate(-50%, -50%)'
                    }}
                    title={`${pet.name} the ${pet.pet_type}`}
                  >
                    <img
                      src={pet.avatar_path}
                      alt={pet.name}
                      className="w-10 h-10 rounded-full border-2 border-yellow-400 shadow-lg object-cover"
                      onError={(e) => {
                        e.target.style.display = 'none'
                      }}
                    />
                  </div>
                )
              })}
              
              {/* Empty state */}
              {roomEmployees.length === 0 && pets.filter(pet => pet.current_room === room.id && pet.floor === room.floor).length === 0 && (
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

