import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

function RecentFiles({ employeeId }) {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (employeeId) {
      fetchRecentFiles()
    }
  }, [employeeId])

  const fetchRecentFiles = async () => {
    try {
      const response = await fetch(`/api/employees/${employeeId}/recent-files?limit=15`)
      if (response.ok) {
        const data = await response.json()
        setFiles(data)
      }
      setLoading(false)
    } catch (error) {
      console.error('Error fetching recent files:', error)
      setLoading(false)
    }
  }

  const getFileIcon = (fileType) => {
    switch (fileType) {
      case 'word':
        return '📄'
      case 'spreadsheet':
        return '📊'
      case 'powerpoint':
        return '📽️'
      default:
        return '📄'
    }
  }

  const getFileTypeName = (fileType) => {
    switch (fileType) {
      case 'word':
        return 'Word'
      case 'spreadsheet':
        return 'Excel'
      case 'powerpoint':
        return 'PowerPoint'
      default:
        return 'Document'
    }
  }

  if (loading) {
    return <div className="text-sm text-gray-500">Loading recent files...</div>
  }

  if (files.length === 0) {
    return (
      <div className="text-sm text-gray-500">
        No files yet. Files will appear here as they are created or updated.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {files.map(file => (
        <div
          key={file.id}
          className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <div className="flex items-center space-x-3 flex-1 min-w-0">
            <span className="text-2xl flex-shrink-0">{getFileIcon(file.file_type)}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center space-x-2">
                <Link
                  to="/communications?tab=share-drive"
                  className="text-sm font-medium text-blue-600 hover:text-blue-800 truncate"
                  onClick={() => {
                    // Store file ID in sessionStorage to auto-select it in SharedDriveView
                    sessionStorage.setItem('selectedFileId', file.id)
                  }}
                >
                  {file.file_name}
                </Link>
                {file.version_count > 1 && (
                  <span className="text-xs text-gray-500 bg-gray-200 px-2 py-0.5 rounded">
                    {file.version_count} versions
                  </span>
                )}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                <span className="capitalize">{getFileTypeName(file.file_type)}</span>
                {file.project_name && (
                  <span className="ml-2">• {file.project_name}</span>
                )}
                {file.department && (
                  <span className="ml-2">• {file.department}</span>
                )}
              </div>
            </div>
          </div>
          <div className="text-xs text-gray-500 flex-shrink-0 ml-4">
            {file.updated_at ? (
              <div>
                <div>{new Date(file.updated_at).toLocaleDateString()}</div>
                <div className="text-gray-400">{new Date(file.updated_at).toLocaleTimeString()}</div>
              </div>
            ) : (
              'N/A'
            )}
          </div>
        </div>
      ))}
      <div className="text-xs text-gray-500 text-center pt-2">
        <Link
          to="/communications?tab=share-drive"
          className="text-blue-600 hover:text-blue-800"
        >
          View all files in Share Drive →
        </Link>
      </div>
    </div>
  )
}

export default RecentFiles

