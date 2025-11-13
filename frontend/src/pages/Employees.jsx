import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getAvatarPath } from '../utils/avatarMapper'

function Employees() {
  const [employees, setEmployees] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('active') // 'active', 'terminated', 'all'

  useEffect(() => {
    fetchEmployees()
    const interval = setInterval(fetchEmployees, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchEmployees = async () => {
    try {
      const response = await fetch('/api/employees')
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data = await response.json()
      setEmployees(data || [])
      setLoading(false)
    } catch (error) {
      console.error('Error fetching employees:', error)
      setEmployees([])
      setLoading(false)
    }
  }
  
  // Filter employees based on selected filter
  const filteredEmployees = employees.filter(emp => {
    if (filter === 'active') {
      return emp.status !== 'fired' && !emp.fired_at
    } else if (filter === 'terminated') {
      return emp.status === 'fired' || emp.fired_at
    }
    return true // 'all'
  })
  
  const activeCount = employees.filter(emp => emp.status !== 'fired' && !emp.fired_at).length
  const terminatedCount = employees.filter(emp => emp.status === 'fired' || emp.fired_at).length

  if (loading) {
    return <div className="text-center py-12">Loading employees...</div>
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800'
      case 'busy': return 'bg-yellow-100 text-yellow-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getRoleColor = (role) => {
    switch (role) {
      case 'CEO': return 'bg-purple-100 text-purple-800'
      case 'Manager': return 'bg-blue-100 text-blue-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-3xl font-bold text-gray-900">Employees</h2>
        <div className="flex items-center space-x-4">
          <div className="text-sm text-gray-600">
            <span className="font-medium">{activeCount}</span> active
            {terminatedCount > 0 && (
              <> • <span className="font-medium">{terminatedCount}</span> terminated</>
            )}
          </div>
          <div className="flex bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setFilter('active')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                filter === 'active'
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Active
            </button>
            {terminatedCount > 0 && (
              <button
                onClick={() => setFilter('terminated')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  filter === 'terminated'
                    ? 'bg-white text-blue-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Terminated
              </button>
            )}
            <button
              onClick={() => setFilter('all')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                filter === 'all'
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              All
            </button>
          </div>
        </div>
      </div>
      
      {filteredEmployees.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <p className="text-gray-500 text-lg mb-2">
            {filter === 'active' ? 'No active employees found' :
             filter === 'terminated' ? 'No terminated employees found' :
             'No employees found'}
          </p>
          <p className="text-gray-400 text-sm">Employees will appear here once the simulation starts</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredEmployees.map((employee) => (
          <Link
            key={employee.id}
            to={`/employees/${employee.id}`}
            className={`bg-white rounded-lg shadow hover:shadow-lg transition-shadow p-6 cursor-pointer ${
              (employee.status === 'fired' || employee.fired_at) ? 'opacity-75' : ''
            }`}
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-start space-x-4 flex-1">
                <img
                  src={getAvatarPath(employee)}
                  alt={employee.name}
                  className="w-16 h-16 rounded-full object-cover flex-shrink-0"
                  onError={(e) => {
                    e.target.src = '/avatars/office_char_01_manager.png'
                  }}
                />
                <div className="flex-1 min-w-0">
                  <h3 className="text-xl font-semibold text-gray-900">{employee.name}</h3>
                  <p className="text-sm text-gray-600 mt-1">{employee.title}</p>
                </div>
              </div>
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${getRoleColor(employee.role)}`}>
                {employee.role}
              </span>
            </div>
            
            <div className="space-y-2">
              <div className="flex items-center text-sm text-gray-600">
                <span className="font-medium">Department:</span>
                <span className="ml-2">{employee.department || 'N/A'}</span>
              </div>
              <div className="flex items-center text-sm text-gray-600">
                <span className="font-medium">Status:</span>
                <span className={`ml-2 px-2 py-1 rounded-full text-xs ${getStatusColor(employee.status)}`}>
                  {employee.status}
                </span>
                {(employee.status === 'fired' || employee.fired_at) && (
                  <span className="ml-2 px-2 py-1 rounded-full text-xs bg-red-100 text-red-800">
                    Terminated
                  </span>
                )}
              </div>
              {employee.termination_reason && (
                <div className="text-xs text-red-600 mt-2 italic">
                  {employee.termination_reason}
                </div>
              )}
              {employee.current_task_id && !employee.fired_at && (
                <div className="text-sm text-blue-600 mt-2">
                  Has active task
                </div>
              )}
            </div>
            
            {employee.backstory && (
              <div className="mt-4 pt-4 border-t border-gray-200">
                <p className="text-xs text-gray-500 line-clamp-3">{employee.backstory}</p>
              </div>
            )}
          </Link>
          ))}
        </div>
      )}
    </div>
  )
}

export default Employees

