import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'

function ProjectDetail() {
  const { id } = useParams()
  const [project, setProject] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchProject()
    const interval = setInterval(fetchProject, 10000)
    return () => clearInterval(interval)
  }, [id])

  const fetchProject = async () => {
    try {
      const response = await fetch(`/api/projects/${id}`)
      const data = await response.json()
      setProject(data)
      setLoading(false)
    } catch (error) {
      console.error('Error fetching project:', error)
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="text-center py-12">Loading project details...</div>
  }

  if (!project) {
    return <div className="text-center py-12">Project not found</div>
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800'
      case 'active': return 'bg-blue-100 text-blue-800'
      case 'planning': return 'bg-yellow-100 text-yellow-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="px-4 py-6">
      <Link to="/projects" className="text-blue-600 hover:text-blue-800 mb-4 inline-block">
        ← Back to Projects
      </Link>
      
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h2 className="text-3xl font-bold text-gray-900">{project.name}</h2>
            {project.description && (
              <p className="text-gray-600 mt-2">{project.description}</p>
            )}
          </div>
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(project.status)}`}>
            {project.status}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div>
            <span className="text-sm text-gray-500">Budget</span>
            <p className="text-lg font-medium text-gray-900">${project.budget.toLocaleString()}</p>
          </div>
          <div>
            <span className="text-sm text-gray-500">Revenue</span>
            <p className="text-lg font-medium text-green-600">${project.revenue.toLocaleString()}</p>
          </div>
          <div>
            <span className="text-sm text-gray-500">Priority</span>
            <p className="text-lg font-medium text-gray-900 capitalize">{project.priority}</p>
          </div>
          <div>
            <span className="text-sm text-gray-500">Progress</span>
            <p className="text-lg font-medium text-gray-900">{project.progress.toFixed(0)}%</p>
          </div>
        </div>

        <div className="mb-6">
          <div className="w-full bg-gray-200 rounded-full h-4">
            <div
              className="bg-blue-600 h-4 rounded-full transition-all"
              style={{ width: `${project.progress}%` }}
            ></div>
          </div>
        </div>

        {project.deadline && (
          <div className="text-sm text-gray-600">
            <span className="font-medium">Deadline: </span>
            {new Date(project.deadline).toLocaleDateString()}
          </div>
        )}
      </div>

      {/* Tasks */}
      {project.tasks && project.tasks.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-xl font-semibold text-gray-900 mb-4">Tasks</h3>
          <div className="space-y-3">
            {project.tasks.map((task) => (
              <div key={task.id} className="border-l-4 border-blue-500 pl-4 py-2">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-gray-900 font-medium">{task.description}</p>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    task.status === 'completed' ? 'bg-green-100 text-green-800' :
                    task.status === 'in_progress' ? 'bg-blue-100 text-blue-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {task.status}
                  </span>
                </div>
                <div className="flex items-center text-xs text-gray-500 mt-1">
                  <span>Created: {new Date(task.created_at).toLocaleString()}</span>
                  {task.completed_at && (
                    <span className="ml-4">Completed: {new Date(task.completed_at).toLocaleString()}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default ProjectDetail

