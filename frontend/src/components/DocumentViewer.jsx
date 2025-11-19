import { useState, useEffect } from 'react'

function DocumentViewer({ file, versionNumber = null }) {
  const [content, setContent] = useState(null)
  const [versions, setVersions] = useState([])
  const [selectedVersion, setSelectedVersion] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!file) return

    const fetchContent = async () => {
      setLoading(true)
      try {
        if (versionNumber) {
          // Fetch specific version
          const response = await fetch(`/api/shared-drive/files/${file.id}/versions/${versionNumber}`)
          if (response.ok) {
            const data = await response.json()
            setContent(data)
            setSelectedVersion(data)
          }
        } else {
          // Fetch current version
          const response = await fetch(`/api/shared-drive/files/${file.id}`)
          if (response.ok) {
            const data = await response.json()
            setContent(data)
          }
        }

        // Fetch version history
        const versionsResponse = await fetch(`/api/shared-drive/files/${file.id}/versions`)
        if (versionsResponse.ok) {
          const versionsData = await versionsResponse.json()
          setVersions(versionsData)
        }
      } catch (error) {
        console.error('Error fetching file content:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchContent()
  }, [file, versionNumber])

  const handleVersionChange = async (versionNum) => {
    if (versionNum === file.current_version) {
      // Show current version
      const response = await fetch(`/api/shared-drive/files/${file.id}`)
      if (response.ok) {
        const data = await response.json()
        setContent(data)
        setSelectedVersion(null)
      }
    } else {
      // Show specific version
      const response = await fetch(`/api/shared-drive/files/${file.id}/versions/${versionNum}`)
      if (response.ok) {
        const data = await response.json()
        setContent(data)
        setSelectedVersion(data)
      }
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center p-8">Loading document...</div>
  }

  if (!content) {
    return <div className="p-8 text-gray-500">Document not found</div>
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
        return 'Word Document'
      case 'spreadsheet':
        return 'Excel Spreadsheet'
      case 'powerpoint':
        return 'PowerPoint Presentation'
      default:
        return 'Document'
    }
  }

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="border-b border-gray-200 p-4 bg-gray-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">{getFileIcon(file.file_type)}</span>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{file.file_name}</h2>
              <p className="text-sm text-gray-500">
                {getFileTypeName(file.file_type)} • Version {selectedVersion ? selectedVersion.version_number : file.current_version}
                {selectedVersion && <span className="text-orange-600 ml-2">(Previous Version)</span>}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            {versions.length > 0 && (
              <select
                value={selectedVersion ? selectedVersion.version_number : file.current_version}
                onChange={(e) => handleVersionChange(parseInt(e.target.value))}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value={file.current_version}>Current (v{file.current_version})</option>
                {versions.map((v) => (
                  <option key={v.id} value={v.version_number}>
                    Version {v.version_number} - {v.created_at ? new Date(v.created_at).toLocaleDateString() : 'N/A'}
                  </option>
                ))}
              </select>
            )}
            <span className="text-xs text-gray-500 bg-gray-200 px-2 py-1 rounded">Read Only</span>
          </div>
        </div>
        {selectedVersion && selectedVersion.change_summary && (
          <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-md">
            <p className="text-sm text-blue-900">
              <strong>Change Summary:</strong> {selectedVersion.change_summary}
            </p>
            <p className="text-xs text-blue-700 mt-1">
              Updated by {selectedVersion.created_by_name || 'Unknown'} on{' '}
              {selectedVersion.created_at ? new Date(selectedVersion.created_at).toLocaleString() : 'N/A'}
            </p>
          </div>
        )}
        <div className="mt-2 text-xs text-gray-500">
          {file.employee_name && <span>Created by: {file.employee_name}</span>}
          {file.last_updated_by_name && (
            <span className="ml-4">Last updated by: {file.last_updated_by_name}</span>
          )}
          {file.updated_at && (
            <span className="ml-4">
              Updated: {new Date(file.updated_at).toLocaleString()}
            </span>
          )}
        </div>
      </div>

      {/* Document Content */}
      <div className="flex-1 overflow-auto p-8 bg-gray-100">
        <style>{`
          .document-content {
            font-family: 'Calibri', 'Arial', sans-serif;
            line-height: 1.6;
            color: #333;
            background: #ffffff;
          }
          
          /* Word Document Styling */
          .document-content h1 {
            font-family: 'Times New Roman', serif;
            font-size: 18pt;
            font-weight: bold;
            margin-top: 1em;
            margin-bottom: 0.5em;
            color: #000000;
          }
          .document-content h2 {
            font-family: 'Times New Roman', serif;
            font-size: 14pt;
            font-weight: bold;
            margin-top: 1em;
            margin-bottom: 0.5em;
            color: #000000;
          }
          .document-content h3 {
            font-family: 'Times New Roman', serif;
            font-size: 12pt;
            font-weight: bold;
            margin-top: 1em;
            margin-bottom: 0.5em;
            color: #000000;
          }
          .document-content p {
            margin-bottom: 12pt;
            text-align: justify;
            font-size: 12pt;
            line-height: 1.5;
          }
          .document-content ul, .document-content ol {
            margin-left: 36pt;
            margin-bottom: 12pt;
          }
          .document-content li {
            margin-bottom: 6pt;
            font-size: 12pt;
          }
          
          /* Spreadsheet Styling */
          .document-content table {
            width: 100%;
            border-collapse: collapse;
            margin: 1em 0;
            font-family: 'Arial', sans-serif;
            font-size: 11pt;
          }
          .document-content th {
            background-color: #366092 !important;
            color: white !important;
            font-weight: bold;
            padding: 8px;
            text-align: left;
            border: 1px solid #d0d0d0;
          }
          .document-content td {
            border: 1px solid #d0d0d0;
            padding: 8px;
            background-color: white;
          }
          .document-content tr:nth-child(even) td {
            background-color: #f2f2f2 !important;
          }
          .document-content tr:last-child td {
            font-weight: bold;
          }
          
          /* PowerPoint Styling */
          .document-content .slide {
            background: #ffffff;
            padding: 60px;
            margin: 30px auto;
            max-width: 960px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            font-family: 'Calibri', 'Arial', sans-serif;
            min-height: 600px;
            page-break-after: always;
          }
          .document-content .slide h1 {
            font-family: 'Calibri', 'Arial', sans-serif;
            font-size: 36pt;
            font-weight: bold;
            color: #2F5597;
            margin-bottom: 40px;
          }
          .document-content .slide ul {
            font-size: 20pt;
            line-height: 1.8;
            margin-left: 40px;
            color: #333;
          }
          .document-content .slide li {
            margin-bottom: 20px;
            font-size: 20pt;
          }
          .document-content .slide p {
            font-size: 20pt;
            line-height: 1.8;
            margin-bottom: 20px;
          }
        `}</style>
        <div
          className={`mx-auto bg-white shadow-lg ${
            file.file_type === 'word'
              ? 'max-w-4xl p-12'
              : file.file_type === 'spreadsheet'
              ? 'w-full overflow-x-auto p-4'
              : 'max-w-5xl p-4'
          }`}
          style={{
            fontFamily: file.file_type === 'word' ? "'Times New Roman', serif" : "'Calibri', Arial, sans-serif",
            minHeight: '100%',
          }}
        >
          <div
            dangerouslySetInnerHTML={{ __html: content.content_html || content.html || '' }}
            className="document-content"
          />
        </div>
      </div>
    </div>
  )
}

export default DocumentViewer

