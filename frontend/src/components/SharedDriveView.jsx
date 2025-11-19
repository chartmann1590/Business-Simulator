import { useState, useEffect } from 'react'
import DocumentViewer from './DocumentViewer'

function SharedDriveView() {
  const [structure, setStructure] = useState({})
  const [files, setFiles] = useState([])
  const [selectedFile, setSelectedFile] = useState(null)
  const [expandedNodes, setExpandedNodes] = useState(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [filterDepartment, setFilterDepartment] = useState('')
  const [filterFileType, setFilterFileType] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000) // Refresh every 10 seconds
    return () => clearInterval(interval)
  }, [])

  // Check for selected file ID from sessionStorage (when navigating from employee profile)
  useEffect(() => {
    const selectedFileId = sessionStorage.getItem('selectedFileId')
    if (selectedFileId && files.length > 0) {
      const file = files.find(f => f.id === parseInt(selectedFileId))
      if (file) {
        setSelectedFile(file)
        sessionStorage.removeItem('selectedFileId') // Clear after selecting
      }
    }
  }, [files])

  const fetchData = async () => {
    try {
      const [structureRes, filesRes] = await Promise.all([
        fetch('/api/shared-drive/structure'),
        fetch('/api/shared-drive/files?limit=500')
      ])
      
      if (structureRes.ok) {
        const structureData = await structureRes.json()
        setStructure(structureData)
      }
      
      if (filesRes.ok) {
        const filesData = await filesRes.json()
        setFiles(filesData)
      }
      
      setLoading(false)
    } catch (error) {
      console.error('Error fetching shared drive data:', error)
      setLoading(false)
    }
  }

  const toggleNode = (path) => {
    const newExpanded = new Set(expandedNodes)
    if (newExpanded.has(path)) {
      newExpanded.delete(path)
    } else {
      newExpanded.add(path)
    }
    setExpandedNodes(newExpanded)
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

  const filteredFiles = files.filter(file => {
    const matchesSearch = !searchQuery || 
      file.file_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (file.employee_name && file.employee_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (file.project_name && file.project_name.toLowerCase().includes(searchQuery.toLowerCase()))
    const matchesDepartment = !filterDepartment || file.department === filterDepartment
    const matchesFileType = !filterFileType || file.file_type === filterFileType
    return matchesSearch && matchesDepartment && matchesFileType
  })

  const departments = [...new Set(files.map(f => f.department).filter(Boolean))].sort()

  const renderTree = (data, path = '') => {
    const items = []
    
    for (const [key, value] of Object.entries(data)) {
      const currentPath = path ? `${path}/${key}` : key
      const isExpanded = expandedNodes.has(currentPath)
      
      if (typeof value === 'object' && !Array.isArray(value)) {
        // It's a folder (department, employee, or project)
        items.push(
          <div key={currentPath} className="select-none">
            <div
              className="flex items-center py-1 px-2 hover:bg-gray-100 cursor-pointer"
              onClick={() => toggleNode(currentPath)}
            >
              <span className="mr-2">{isExpanded ? '📂' : '📁'}</span>
              <span className="text-sm font-medium text-gray-700">{key}</span>
            </div>
            {isExpanded && (
              <div className="ml-4 border-l border-gray-200 pl-2">
                {renderTree(value, currentPath)}
              </div>
            )}
          </div>
        )
      } else if (Array.isArray(value)) {
        // It's a list of files
        value.forEach((file, index) => {
          const filePath = `${currentPath}/${file.file_name}`
          items.push(
            <div
              key={`${file.id}-${index}`}
              className={`flex items-center py-2 px-2 hover:bg-blue-50 cursor-pointer rounded ${
                selectedFile?.id === file.id ? 'bg-blue-100' : ''
              }`}
              onClick={() => {
                setSelectedFile(file)
              }}
            >
              <span className="mr-2 text-lg">{getFileIcon(file.file_type)}</span>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-900 truncate">
                  {file.file_name}
                </div>
                <div className="text-xs text-gray-500">
                  v{file.current_version} • {file.updated_at ? new Date(file.updated_at).toLocaleDateString() : 'N/A'}
                </div>
              </div>
            </div>
          )
        })
      }
    }
    
    return items
  }

  if (loading) {
    return <div className="flex items-center justify-center h-full">Loading shared drive...</div>
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header with Search and Filters */}
      <div className="border-b border-gray-200 p-4 bg-white">
        <div className="flex items-center space-x-4 mb-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search files, employees, projects..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <select
            value={filterDepartment}
            onChange={(e) => setFilterDepartment(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Departments</option>
            {departments.map(dept => (
              <option key={dept} value={dept}>{dept}</option>
            ))}
          </select>
          <select
            value={filterFileType}
            onChange={(e) => setFilterFileType(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Types</option>
            <option value="word">Word Documents</option>
            <option value="spreadsheet">Spreadsheets</option>
            <option value="powerpoint">Presentations</option>
          </select>
        </div>
        <div className="text-sm text-gray-600">
          {filteredFiles.length} file{filteredFiles.length !== 1 ? 's' : ''} found
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* File Browser */}
        <div className="w-1/3 border-r border-gray-200 overflow-y-auto bg-gray-50">
          <div className="p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">File Structure</h3>
            {Object.keys(structure).length > 0 ? (
              <div className="space-y-1">
                {renderTree(structure)}
              </div>
            ) : (
              <div className="text-sm text-gray-500">No files yet. Files will appear as employees create them.</div>
            )}
          </div>
          
          {/* Recent Files List */}
          {filteredFiles.length > 0 && (
            <div className="border-t border-gray-200 p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Recent Files</h3>
              <div className="space-y-1">
                {filteredFiles.slice(0, 20).map(file => (
                  <div
                    key={file.id}
                    className={`flex items-center py-2 px-2 hover:bg-blue-50 cursor-pointer rounded ${
                      selectedFile?.id === file.id ? 'bg-blue-100' : ''
                    }`}
                    onClick={() => setSelectedFile(file)}
                  >
                    <span className="mr-2 text-lg">{getFileIcon(file.file_type)}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900 truncate">
                        {file.file_name}
                      </div>
                      <div className="text-xs text-gray-500">
                        {file.employee_name || 'Unknown'} • {file.department || 'General'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Document Viewer */}
        <div className="flex-1 overflow-hidden">
          {selectedFile ? (
            <DocumentViewer file={selectedFile} />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              <div className="text-center">
                <div className="text-4xl mb-4">📁</div>
                <p>Select a file to view</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default SharedDriveView

