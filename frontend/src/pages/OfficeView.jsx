import { useState, useEffect, useCallback } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import OfficeLayout from '../components/OfficeLayout'
import RoomDetailModal from '../components/RoomDetailModal'
import { useNavigate } from 'react-router-dom'

function OfficeView() {
  const [officeData, setOfficeData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [employees, setEmployees] = useState([])
  const [selectedRoom, setSelectedRoom] = useState(null)
  const [selectedFloor, setSelectedFloor] = useState(1)  // Default to floor 1
  const navigate = useNavigate()
  
  // Get WebSocket messages for real-time updates
  const wsMessages = useWebSocket()
  
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
  
  // Handle WebSocket location updates - trigger a refresh
  useEffect(() => {
    const hasLocationUpdate = wsMessages.some(msg => msg.type === 'location_update')
    if (hasLocationUpdate) {
      // Refresh office layout to get updated positions
      fetchOfficeLayout()
    }
  }, [wsMessages, fetchOfficeLayout])
  
  const handleEmployeeClick = (employee) => {
    navigate(`/employees/${employee.id}`)
  }
  
  const handleRoomClick = (room) => {
    setSelectedRoom(room)
  }
  
  const handleCloseRoomModal = () => {
    setSelectedRoom(null)
  }
  
  if (loading && !officeData) {
    return (
      <div className="px-4 py-6">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-500">Loading office layout...</p>
        </div>
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
              {officeData?.total_employees || 0} active employees across {officeData?.rooms?.length || 0} rooms
              {hasTerminated && ` • ${officeData?.total_terminated || 0} terminated`}
            </p>
          </div>
          
          {/* Floor Selector */}
          <div className="flex items-center space-x-2">
            <span className="text-sm font-medium text-gray-700">Floor:</span>
            <div className="flex bg-gray-100 rounded-lg p-1">
              {availableFloors.map((floor) => (
                <button
                  key={floor}
                  onClick={() => setSelectedFloor(floor)}
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

