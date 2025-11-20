import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiGet } from '../utils/api'

function Tasks() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    assignment: 'all', // 'all', 'assigned', 'unassigned'
    status: 'all', // 'all', 'pending', 'in_progress', 'completed', 'cancelled'
    priority: 'all', // 'all', 'low', 'medium', 'high'
    project: 'all' // 'all' or specific project id
  })
  const [projects, setProjects] = useState([])

  useEffect(() => {
    fetchTasks()
    fetchProjects()
    const interval = setInterval(() => {
      fetchTasks()
      fetchProjects()
    }, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchTasks = async () => {
    setLoading(true)
    try {
      const result = await apiGet('/api/tasks')
      setTasks(Array.isArray(result.data) ? result.data : [])
    } catch (error) {
      console.error('Error fetching tasks:', error)
      setTasks([])
    } finally {
      setLoading(false)
    }
  }

  const fetchProjects = async () => {
    try {
      const result = await apiGet('/api/projects')
      setProjects(Array.isArray(result.data) ? result.data : [])
    } catch (error) {
      console.error('Error fetching projects:', error)
      setProjects([])
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800'
      case 'in_progress': return 'bg-blue-100 text-blue-800'
      case 'pending': return 'bg-yellow-100 text-yellow-800'
      case 'cancelled': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high': return 'bg-red-100 text-red-800'
      case 'medium': return 'bg-yellow-100 text-yellow-800'
      case 'low': return 'bg-green-100 text-green-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  // Filter tasks based on current filters
  const filteredTasks = tasks.filter(task => {
    // Assignment filter
    if (filters.assignment === 'assigned' && !task.employee_id) {
      return false
    }
    if (filters.assignment === 'unassigned' && task.employee_id) {
      return false
    }

    // Status filter
    if (filters.status !== 'all' && task.status !== filters.status) {
      return false
    }

    // Priority filter
    if (filters.priority !== 'all' && task.priority !== filters.priority) {
      return false
    }

    // Project filter
    if (filters.project !== 'all') {
      const projectId = parseInt(filters.project)
      if (task.project_id !== projectId) {
        return false
      }
    }

    return true
  })

  // Get statistics
  const stats = {
    total: tasks.length,
    assigned: tasks.filter(t => t.employee_id).length,
    unassigned: tasks.filter(t => !t.employee_id).length,
    pending: tasks.filter(t => t.status === 'pending').length,
    inProgress: tasks.filter(t => t.status === 'in_progress').length,
    completed: tasks.filter(t => t.status === 'completed').length
  }

  if (loading) {
    return <div className="text-center py-12">Loading tasks...</div>
  }

  return (
    <div className="px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-3xl font-bold text-gray-900">Tasks</h2>
        <div className="flex items-center space-x-4 text-sm text-gray-600">
          <span>Total: <strong>{stats.total}</strong></span>
          <span>Assigned: <strong className="text-blue-600">{stats.assigned}</strong></span>
          <span>Unassigned: <strong className="text-orange-600">{stats.unassigned}</strong></span>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Assignment Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Assignment
            </label>
            <select
              value={filters.assignment}
              onChange={(e) => setFilters({ ...filters, assignment: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">All Tasks</option>
              <option value="assigned">Assigned</option>
              <option value="unassigned">Unassigned</option>
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Status
            </label>
            <select
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          {/* Priority Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Priority
            </label>
            <select
              value={filters.priority}
              onChange={(e) => setFilters({ ...filters, priority: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">All Priorities</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          {/* Project Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Project
            </label>
            <select
              value={filters.project}
              onChange={(e) => setFilters({ ...filters, project: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">All Projects</option>
              {projects.map(project => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Tasks List */}
      {filteredTasks.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <p className="text-gray-500 text-lg mb-2">No tasks found</p>
          <p className="text-gray-400 text-sm">
            {tasks.length === 0 
              ? 'Tasks will appear here once they are created'
              : 'Try adjusting your filters'}
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Task
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Assigned To
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Project
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Priority
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Progress
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredTasks.map((task) => (
                  <tr key={task.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Link
                        to={`/tasks/${task.id}`}
                        className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline max-w-md block"
                      >
                        {task.description}
                      </Link>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {task.employee ? (
                        <Link
                          to={`/employees/${task.employee.id}`}
                          className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          <div className="font-medium">{task.employee.name}</div>
                          <div className="text-xs text-gray-500">{task.employee.title}</div>
                        </Link>
                      ) : (
                        <span className="text-sm text-orange-600 font-medium">Unassigned</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {task.project ? (
                        <Link
                          to={`/projects/${task.project.id}`}
                          className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          {task.project.name}
                        </Link>
                      ) : (
                        <span className="text-sm text-gray-400">No project</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(task.status)}`}>
                        {task.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getPriorityColor(task.priority)}`}>
                        {task.priority}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full"
                            style={{ width: `${task.progress}%` }}
                          ></div>
                        </div>
                        <span className="text-sm text-gray-600">{Math.round(task.progress)}%</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {task.created_at 
                        ? new Date(task.created_at).toLocaleDateString()
                        : 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default Tasks

