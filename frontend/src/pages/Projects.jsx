import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiGet } from '../utils/api'

function Projects() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('active') // 'active' or 'completed'

  useEffect(() => {
    fetchProjects()
    const interval = setInterval(fetchProjects, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchProjects = async () => {
    setLoading(true)
    try {
      const result = await apiGet('/api/projects')
      const projectsArray = Array.isArray(result.data) ? result.data : []
      setProjects(projectsArray)
    } catch (error) {
      console.error('Error fetching projects:', error)
      setProjects([])
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="text-center py-12">Loading projects...</div>
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800'
      case 'active': return 'bg-blue-100 text-blue-800'
      case 'planning': return 'bg-yellow-100 text-yellow-800'
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

  // Filter projects based on active tab and sort by progress (highest first)
  const filteredProjects = projects
    .filter(project => {
      if (activeTab === 'active') {
        return project.status === 'planning' || project.status === 'active'
      } else if (activeTab === 'completed') {
        return project.status === 'completed'
      }
      return true
    })
    .sort((a, b) => {
      // Sort by progress: highest first, then by name for same progress
      const progressA = a.progress || 0
      const progressB = b.progress || 0
      if (progressB !== progressA) {
        return progressB - progressA // Descending order (highest first)
      }
      return (a.name || '').localeCompare(b.name || '')
    })

  console.log('Rendering Projects component, filteredProjects.length:', filteredProjects.length, 'loading:', loading)
  
  return (
    <div className="px-4 py-6">
      <h2 className="text-3xl font-bold text-gray-900 mb-6">Projects</h2>
      
      {/* Tabs */}
      <div className="mb-6 border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('active')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'active'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Active
            <span className="ml-2 bg-gray-100 text-gray-600 py-0.5 px-2.5 rounded-full text-xs font-medium">
              {projects.filter(p => p.status === 'planning' || p.status === 'active').length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('completed')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'completed'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Completed
            <span className="ml-2 bg-gray-100 text-gray-600 py-0.5 px-2.5 rounded-full text-xs font-medium">
              {projects.filter(p => p.status === 'completed').length}
            </span>
          </button>
        </nav>
      </div>
      
      {filteredProjects.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <p className="text-gray-500 text-lg mb-2">
            {activeTab === 'completed' ? 'No completed projects yet' : 'No projects found'}
          </p>
          <p className="text-gray-400 text-sm">
            {activeTab === 'completed' 
              ? 'Completed projects will appear here' 
              : 'Projects will appear here once they are created'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredProjects.map((project) => (
          <Link
            key={project.id}
            to={`/projects/${project.id}`}
            className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow p-6 cursor-pointer"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <div className="flex items-center space-x-2">
                  <h3 className="text-xl font-semibold text-gray-900">{project.name}</h3>
                  {project.is_stalled && (
                    <span className="px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800 animate-pulse">
                      ⚠️ Stalled
                    </span>
                  )}
                </div>
              </div>
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(project.status)}`}>
                {project.status}
              </span>
            </div>
            
            {project.description && (
              <p className="text-sm text-gray-600 mb-4 line-clamp-2">{project.description}</p>
            )}
            
            <div className="space-y-2 mb-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">Progress</span>
                <span className="font-medium text-gray-900">{(project.progress || 0).toFixed(0)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${
                    project.is_stalled ? 'bg-red-500' : 'bg-blue-600'
                  }`}
                  style={{ width: `${project.progress || 0}%` }}
                ></div>
              </div>
              {project.is_stalled && project.last_activity_at && (
                <p className="text-xs text-red-600 mt-1">
                  No activity since {new Date(project.last_activity_at).toLocaleDateString()}
                </p>
              )}
            </div>
            
            <div className="flex items-center justify-between text-sm">
              <div>
                <span className="text-gray-600">Budget: </span>
                <span className="font-medium text-gray-900">${(project.budget || 0).toLocaleString()}</span>
              </div>
              <span className={`px-2 py-1 rounded text-xs font-medium ${getPriorityColor(project.priority || 'medium')}`}>
                {project.priority || 'medium'}
              </span>
            </div>
            
            {(project.revenue || 0) > 0 && (
              <div className="mt-2 text-sm">
                <span className="text-gray-600">Revenue: </span>
                <span className="font-medium text-green-600">${(project.revenue || 0).toLocaleString()}</span>
              </div>
            )}
            {project.status === 'completed' && project.completed_at && (
              <div className="mt-2 text-sm">
                <span className="text-gray-600">Completed: </span>
                <span className="font-medium text-gray-900">
                  {new Date(project.completed_at).toLocaleDateString()}
                </span>
              </div>
            )}
          </Link>
          ))}
        </div>
      )}
    </div>
  )
}

export default Projects
