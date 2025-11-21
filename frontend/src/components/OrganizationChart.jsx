import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiGet } from '../utils/api'

const TreeNode = ({ node, level = 0, navigate }) => {
  const [isExpanded, setIsExpanded] = useState(level < 2) // Auto-expand first 2 levels
  const hasChildren = node.children && node.children.length > 0

  const getAvatarPath = (avatarPath) => {
    if (!avatarPath) return '/avatars/office_char_01_manager.png'
    return avatarPath.startsWith('/') ? avatarPath : `/avatars/${avatarPath}`
  }

  const getRoleColor = (role) => {
    switch (role) {
      case 'CEO':
      case 'CTO':
      case 'COO':
      case 'CFO':
        return 'bg-purple-100 text-purple-800 border-purple-300'
      case 'Manager':
        return 'bg-blue-100 text-blue-800 border-blue-300'
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300'
    }
  }

  return (
    <div className="relative">
      {/* Node Card */}
      <div className="flex items-start">
        {/* Expand/Collapse Button */}
        {hasChildren && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="mr-2 mt-3 flex-shrink-0 w-6 h-6 rounded-full border-2 border-gray-400 bg-white hover:bg-gray-50 flex items-center justify-center transition-colors"
          >
            <svg
              className={`w-4 h-4 text-gray-600 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        )}
        {!hasChildren && <div className="w-6 mr-2" />}

        {/* Employee Card */}
        <div
          onClick={() => navigate(`/employees/${node.id}`)}
          className={`flex items-center gap-3 px-4 py-3 border-2 rounded-lg hover:shadow-md transition-all mb-3 cursor-pointer ${getRoleColor(node.role)}`}
          style={{ minWidth: '300px', maxWidth: '400px' }}
        >
          <img
            src={getAvatarPath(node.avatar_path)}
            alt={node.name}
            className="w-12 h-12 rounded-full object-cover border-2 border-white shadow"
            onError={(e) => {
              e.target.src = '/avatars/office_char_01_manager.png'
            }}
          />
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-sm truncate">{node.name}</p>
            <p className="text-xs opacity-75 truncate">{node.title}</p>
            {node.department && (
              <p className="text-xs opacity-60">{node.department}</p>
            )}
            {node.direct_reports_count > 0 && (
              <p className="text-xs opacity-75 mt-1">
                {node.direct_reports_count} direct report{node.direct_reports_count !== 1 ? 's' : ''}
              </p>
            )}
          </div>
          <span className={`px-2 py-1 rounded text-xs font-medium ${getRoleColor(node.role)}`}>
            {node.role}
          </span>
        </div>
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div className="ml-8 border-l-2 border-gray-300 pl-4">
          {node.children.map((child) => (
            <TreeNode key={child.id} node={child} level={level + 1} navigate={navigate} />
          ))}
        </div>
      )}
    </div>
  )
}

const OrganizationChart = () => {
  const navigate = useNavigate()
  const [hierarchy, setHierarchy] = useState(null)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchHierarchy()
  }, [])

  const fetchHierarchy = async () => {
    setLoading(true)
    try {
      const response = await apiGet('/api/company-hierarchy')
      if (response.data) {
        setHierarchy(response.data.hierarchy)
        setStats(response.data.stats)
      }
    } catch (err) {
      console.error('Error fetching hierarchy:', err)
      setError('Failed to load organizational structure')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <p className="text-red-600">{error}</p>
        <button
          onClick={fetchHierarchy}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    )
  }

  if (!hierarchy) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
        <p className="text-yellow-800">No organizational structure available</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4 border border-purple-200">
            <p className="text-sm font-medium text-purple-600">Total Employees</p>
            <p className="text-3xl font-bold text-purple-900 mt-2">{stats.total}</p>
          </div>
          <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4 border border-blue-200">
            <p className="text-sm font-medium text-blue-600">Executives</p>
            <p className="text-3xl font-bold text-blue-900 mt-2">{stats.executives}</p>
          </div>
          <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4 border border-green-200">
            <p className="text-sm font-medium text-green-600">Managers</p>
            <p className="text-3xl font-bold text-green-900 mt-2">{stats.managers}</p>
          </div>
          <div className="bg-gradient-to-br from-gray-50 to-gray-100 rounded-lg p-4 border border-gray-200">
            <p className="text-sm font-medium text-gray-600">Employees</p>
            <p className="text-3xl font-bold text-gray-900 mt-2">{stats.employees}</p>
          </div>
          <div className="bg-gradient-to-br from-amber-50 to-amber-100 rounded-lg p-4 border border-amber-200">
            <p className="text-sm font-medium text-amber-600">Manager Ratio</p>
            <p className="text-3xl font-bold text-amber-900 mt-2">{stats.ratio}</p>
          </div>
        </div>
      )}

      {/* Organization Tree */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-bold text-gray-900">Organizational Structure</h3>
          <button
            onClick={fetchHierarchy}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
        </div>

        <div className="overflow-x-auto">
          <TreeNode node={hierarchy} level={0} navigate={navigate} />
        </div>

        <div className="mt-6 pt-6 border-t border-gray-200">
          <p className="text-sm text-gray-500">
            Click on any employee card to view their detailed profile. Use the expand/collapse buttons to navigate the hierarchy.
          </p>
        </div>
      </div>
    </div>
  )
}

export default OrganizationChart
