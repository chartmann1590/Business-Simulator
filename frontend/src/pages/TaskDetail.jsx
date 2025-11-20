import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { apiGet } from '../utils/api'

function TaskDetail() {
  const { id } = useParams()
  const [task, setTask] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activities, setActivities] = useState([])
  const [loadingActivities, setLoadingActivities] = useState(false)

  useEffect(() => {
    fetchTask()
    fetchActivities()
    const interval = setInterval(() => {
      fetchTask()
      fetchActivities()
    }, 10000)
    return () => clearInterval(interval)
  }, [id])

  const fetchTask = async () => {
    try {
      const result = await apiGet(`/api/tasks/${id}`)
      setTask(result.data || null)
    } catch (error) {
      console.error('Error fetching task:', error)
      setTask(null)
    } finally {
      setLoading(false)
    }
  }

  const fetchActivities = async () => {
    setLoadingActivities(true)
    try {
      const result = await apiGet(`/api/tasks/${id}/activities`)
      setActivities(Array.isArray(result.data) ? result.data : [])
    } catch (error) {
      console.error('Error fetching task activities:', error)
      setActivities([])
    } finally {
      setLoadingActivities(false)
    }
  }

  if (loading) {
    return <div className="text-center py-12">Loading task details...</div>
  }

  if (!task) {
    return <div className="text-center py-12">Task not found</div>
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

  const getActivityIcon = (activityType) => {
    switch (activityType) {
      case 'task_completed': return '✅'
      case 'decision': return '💡'
      default: return '📝'
    }
  }

  return (
    <div className="px-4 py-6">
      <Link to="/tasks" className="text-blue-600 hover:text-blue-800 mb-4 inline-block">
        ← Back to Tasks
      </Link>
      
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-start justify-between mb-6">
          <div className="flex-1">
            <h2 className="text-3xl font-bold text-gray-900 mb-2">{task.description}</h2>
            <div className="flex items-center space-x-3 mt-2">
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(task.status)}`}>
                {task.status.replace('_', ' ')}
              </span>
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${getPriorityColor(task.priority)}`}>
                {task.priority} priority
              </span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          <div>
            <span className="text-sm text-gray-500 block mb-1">Assigned To</span>
            {task.employee ? (
              <Link
                to={`/employees/${task.employee.id}`}
                className="text-lg font-medium text-blue-600 hover:text-blue-800 hover:underline"
              >
                {task.employee.name}
              </Link>
            ) : (
              <span className="text-lg font-medium text-orange-600">Unassigned</span>
            )}
            {task.employee && (
              <p className="text-sm text-gray-500 mt-1">{task.employee.title}</p>
            )}
          </div>
          <div>
            <span className="text-sm text-gray-500 block mb-1">Project</span>
            {task.project ? (
              <Link
                to={`/projects/${task.project.id}`}
                className="text-lg font-medium text-blue-600 hover:text-blue-800 hover:underline"
              >
                {task.project.name}
              </Link>
            ) : (
              <span className="text-lg font-medium text-gray-400">No project</span>
            )}
          </div>
          <div>
            <span className="text-sm text-gray-500 block mb-1">Progress</span>
            <p className="text-lg font-medium text-gray-900">{Math.round(task.progress)}%</p>
          </div>
        </div>

        <div className="mb-6">
          <div className="w-full bg-gray-200 rounded-full h-4">
            <div
              className={`h-4 rounded-full transition-all ${
                task.status === 'completed' ? 'bg-green-600' : 'bg-blue-600'
              }`}
              style={{ width: `${task.progress}%` }}
            ></div>
          </div>
        </div>

        <div className="flex flex-wrap gap-4 text-sm text-gray-600 border-t pt-4">
          {task.created_at && (
            <div>
              <span className="font-medium">Created: </span>
              {new Date(task.created_at).toLocaleString()}
            </div>
          )}
          {task.completed_at && (
            <div>
              <span className="font-medium">Completed: </span>
              {new Date(task.completed_at).toLocaleString()}
            </div>
          )}
        </div>
      </div>

      {/* Work Done / Activities */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-xl font-semibold text-gray-900 mb-4">
          Work Done
        </h3>
        {loadingActivities ? (
          <div className="text-center py-4 text-gray-500">Loading activities...</div>
        ) : activities.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <p className="mb-2">No work activities recorded yet</p>
            <p className="text-sm text-gray-400">
              {task.status === 'pending' 
                ? 'Work activities will appear here once the task is assigned and work begins'
                : 'Activities related to this task will appear here'}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {activities.map((activity) => (
              <div key={activity.id} className="border-l-4 border-blue-500 pl-4 py-3 bg-gray-50 rounded-r">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="text-lg">{getActivityIcon(activity.activity_type)}</span>
                      <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                        {activity.activity_type.replace('_', ' ')}
                      </span>
                    </div>
                    <p className="text-gray-900 font-medium">{activity.description}</p>
                    {activity.employee_name && (
                      <p className="text-sm text-gray-500 mt-1">
                        by <span className="font-medium">{activity.employee_name}</span>
                      </p>
                    )}
                  </div>
                  <span className="text-xs text-gray-500 ml-4 whitespace-nowrap">
                    {new Date(activity.timestamp).toLocaleString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default TaskDetail





