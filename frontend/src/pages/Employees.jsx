import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getAvatarPath } from '../utils/avatarMapper'

function Employees() {
  const [employees, setEmployees] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('active') // 'active', 'terminated', 'all'
  const [searchQuery, setSearchQuery] = useState('')
  const [departmentFilter, setDepartmentFilter] = useState('all')
  const [roleFilter, setRoleFilter] = useState('all')
  const [titleFilter, setTitleFilter] = useState('all')
  const [reviewFilter, setReviewFilter] = useState('all') // 'all', 'with_reviews', 'without_reviews', 'highest', 'lowest'

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
      // Debug: Check for award holders
      const awardHolders = data.filter(emp => emp.has_performance_award === true)
      if (awardHolders.length > 0) {
        console.log('Award holders found:', awardHolders.map(e => ({ name: e.name, award: e.has_performance_award })))
      }
      setEmployees(data || [])
      setLoading(false)
    } catch (error) {
      console.error('Error fetching employees:', error)
      setEmployees([])
      setLoading(false)
    }
  }
  
  // Filter employees based on selected filters
  let filteredEmployees = employees.filter(emp => {
    // Status filter
    let matchesStatus = true
    if (filter === 'active') {
      matchesStatus = emp.status !== 'fired' && !emp.fired_at
    } else if (filter === 'terminated') {
      matchesStatus = emp.status === 'fired' || emp.fired_at
    }
    
    if (!matchesStatus) return false
    
    // Search query filter (name, title, department)
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      const matchesSearch = 
        (emp.name && emp.name.toLowerCase().includes(query)) ||
        (emp.title && emp.title.toLowerCase().includes(query)) ||
        (emp.department && emp.department.toLowerCase().includes(query))
      if (!matchesSearch) return false
    }
    
    // Department filter
    if (departmentFilter !== 'all') {
      if (emp.department !== departmentFilter) return false
    }
    
    // Role filter
    if (roleFilter !== 'all') {
      if (emp.role !== roleFilter) return false
    }
    
    // Job title filter
    if (titleFilter !== 'all') {
      if (emp.title !== titleFilter) return false
    }
    
    // Review filter
    if (reviewFilter === 'with_reviews') {
      if (!emp.review_count || emp.review_count === 0) return false
    } else if (reviewFilter === 'without_reviews') {
      if (emp.review_count && emp.review_count > 0) return false
    }
    // Note: 'highest' and 'lowest' don't filter, they just sort
    
    return true
  })

  // Sort by rating if highest or lowest filter is selected
  if (reviewFilter === 'highest') {
    // Sort all employees with highest ratings first, employees without ratings last
    filteredEmployees = [...filteredEmployees].sort((a, b) => {
      const ratingA = a.latest_rating ?? -1 // Use -1 for null/undefined so they sort last
      const ratingB = b.latest_rating ?? -1
      return ratingB - ratingA // Descending (highest first)
    })
  } else if (reviewFilter === 'lowest') {
    // Sort all employees with lowest ratings first, employees without ratings last
    filteredEmployees = [...filteredEmployees].sort((a, b) => {
      const ratingA = a.latest_rating ?? 999 // Use 999 for null/undefined so they sort last
      const ratingB = b.latest_rating ?? 999
      return ratingA - ratingB // Ascending (lowest first)
    })
  }
  
  // Get unique departments, roles, and titles for filter dropdowns
  const departments = [...new Set(employees.map(emp => emp.department).filter(Boolean))].sort()
  const roles = [...new Set(employees.map(emp => emp.role).filter(Boolean))].sort()
  const titles = [...new Set(employees.map(emp => emp.title).filter(Boolean))].sort()
  
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
            <span className="font-medium">{filteredEmployees.length}</span> of <span className="font-medium">{employees.length}</span> shown
            {filteredEmployees.length !== employees.length && (
              <span className="ml-2 text-gray-400">({activeCount} active{terminatedCount > 0 ? `, ${terminatedCount} terminated` : ''})</span>
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
      
      {/* Search and Filter Bar */}
      <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4">
          {/* Search Input */}
          <div className="md:col-span-2">
            <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-2">
              Search
            </label>
            <input
              id="search"
              type="text"
              placeholder="Search by name, title, or department..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          
          {/* Department Filter */}
          <div>
            <label htmlFor="department" className="block text-sm font-medium text-gray-700 mb-2">
              Department
            </label>
            <select
              id="department"
              value={departmentFilter}
              onChange={(e) => setDepartmentFilter(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">All Departments</option>
              {departments.map(dept => (
                <option key={dept} value={dept}>{dept}</option>
              ))}
            </select>
          </div>
          
          {/* Role Filter */}
          <div>
            <label htmlFor="role" className="block text-sm font-medium text-gray-700 mb-2">
              Role
            </label>
            <select
              id="role"
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">All Roles</option>
              {roles.map(role => (
                <option key={role} value={role}>{role}</option>
              ))}
            </select>
          </div>
          
          {/* Job Title Filter */}
          <div>
            <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-2">
              Job Title
            </label>
            <select
              id="title"
              value={titleFilter}
              onChange={(e) => setTitleFilter(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">All Titles</option>
              {titles.map(title => (
                <option key={title} value={title}>{title}</option>
              ))}
            </select>
          </div>
          
          {/* Review Filter */}
          <div>
            <label htmlFor="review" className="block text-sm font-medium text-gray-700 mb-2">
              Reviews
            </label>
            <select
              id="review"
              value={reviewFilter}
              onChange={(e) => setReviewFilter(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">All Employees</option>
              <option value="with_reviews">With Reviews</option>
              <option value="without_reviews">Without Reviews</option>
              <option value="highest">Highest Performance</option>
              <option value="lowest">Lowest Performance</option>
            </select>
          </div>
        </div>
        
        {/* Clear Filters Button */}
        {(searchQuery || departmentFilter !== 'all' || roleFilter !== 'all' || titleFilter !== 'all' || reviewFilter !== 'all') && (
          <div className="mt-4 flex justify-end">
            <button
              onClick={() => {
                setSearchQuery('')
                setDepartmentFilter('all')
                setRoleFilter('all')
                setTitleFilter('all')
                setReviewFilter('all')
              }}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:underline"
            >
              Clear all filters
            </button>
          </div>
        )}
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
              {employee.review_count > 0 && (
                <div className="flex items-center text-sm text-gray-600 mt-2">
                  <span className="font-medium">Reviews:</span>
                  <span className="ml-2 px-2 py-1 rounded-full text-xs bg-green-100 text-green-800 font-semibold">
                    {employee.review_count} review{employee.review_count !== 1 ? 's' : ''}
                  </span>
                  {employee.latest_rating && (
                    <span className={`ml-2 px-2 py-1 rounded-full text-xs font-medium ${
                      employee.latest_rating >= 4.5 ? 'bg-green-100 text-green-800' :
                      employee.latest_rating >= 4.0 ? 'bg-green-50 text-green-700' :
                      employee.latest_rating >= 3.0 ? 'bg-yellow-100 text-yellow-800' :
                      employee.latest_rating >= 2.0 ? 'bg-orange-100 text-orange-800' :
                      'bg-red-100 text-red-800'
                    }`}>
                      {employee.latest_rating.toFixed(1)}/5.0
                    </span>
                  )}
                  {employee.latest_review_date && (
                    <span className="ml-2 text-xs text-gray-500">
                      (Latest: {new Date(employee.latest_review_date).toLocaleDateString()})
                    </span>
                  )}
                </div>
              )}
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
              {employee.has_performance_award === true && (
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-2xl">🏆</span>
                  <span className="text-sm font-semibold text-yellow-600 bg-yellow-50 px-3 py-1 rounded-full">
                    Performance Award Winner
                    {employee.performance_award_wins > 0 && (
                      <span className="ml-1 text-xs">
                        ({employee.performance_award_wins} time{employee.performance_award_wins !== 1 ? 's' : ''})
                      </span>
                    )}
                  </span>
                </div>
              )}
              {employee.performance_award_wins > 0 && !employee.has_performance_award && (
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-xl">🏆</span>
                  <span className="text-xs text-gray-600">
                    {employee.performance_award_wins} award win{employee.performance_award_wins !== 1 ? 's' : ''}
                  </span>
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

