import { useState, useEffect, useRef } from 'react'
import { apiGet } from '../utils/api'

// Component to render document in iframe for complete isolation
function DocumentIframe({ content, fileType }) {
  const iframeRef = useRef(null)
  const [iframeHeight, setIframeHeight] = useState('800px')

  useEffect(() => {
    if (!iframeRef.current || !content) return

    const iframe = iframeRef.current
    const iframeDoc = iframe.contentDocument || iframe.contentWindow.document

    // Create a completely isolated HTML document
    const htmlContent = `
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <style>
            * {
              margin: 0;
              padding: 0;
              box-sizing: border-box;
            }
            body {
              font-family: ${fileType === 'word' ? "'Times New Roman', serif" : "'Calibri', Arial, sans-serif"};
              background: #f5f5f5;
              padding: 20px;
              overflow-x: hidden;
            }
            .document-container {
              background: white;
              margin: 0 auto;
              padding: ${fileType === 'word' ? '48px' : fileType === 'spreadsheet' ? '16px' : '16px'};
              max-width: ${fileType === 'word' ? '900px' : fileType === 'spreadsheet' ? '100%' : '1200px'};
              box-shadow: 0 2px 8px rgba(0,0,0,0.1);
              min-height: 100%;
            }
            /* Ensure all document styles are contained */
            .document-container * {
              max-width: 100%;
            }
          </style>
        </head>
        <body>
          <div class="document-container">
            ${content}
          </div>
          <script>
            // Auto-resize iframe to content height
            function resizeIframe() {
              const container = document.querySelector('.document-container');
              const height = container.offsetHeight + 40;
              window.parent.postMessage({ type: 'iframe-resize', height: height }, '*');
            }
            window.addEventListener('load', resizeIframe);
            window.addEventListener('resize', resizeIframe);
            // Use MutationObserver to detect content changes
            const observer = new MutationObserver(resizeIframe);
            observer.observe(document.body, { childList: true, subtree: true });
          </script>
        </body>
      </html>
    `

    iframeDoc.open()
    iframeDoc.write(htmlContent)
    iframeDoc.close()

    // Listen for resize messages from iframe
    const handleMessage = (event) => {
      if (event.data.type === 'iframe-resize') {
        setIframeHeight(`${event.data.height}px`)
      }
    }
    window.addEventListener('message', handleMessage)

    return () => {
      window.removeEventListener('message', handleMessage)
    }
  }, [content, fileType])

  return (
    <div className="w-full h-full">
      <iframe
        ref={iframeRef}
        style={{
          width: '100%',
          height: iframeHeight,
          border: 'none',
          background: 'white',
          display: 'block',
        }}
        title="Document Viewer"
        sandbox="allow-same-origin allow-scripts"
      />
    </div>
  )
}

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
          const result = await apiGet(`/api/shared-drive/files/${file.id}/versions/${versionNumber}`)
          if (result.ok && result.data) {
            setContent(result.data)
            setSelectedVersion(result.data)
          }
        } else {
          // Fetch current version
          const result = await apiGet(`/api/shared-drive/files/${file.id}`)
          if (result.ok && result.data) {
            setContent(result.data)
          }
        }

        // Fetch version history
        const versionsResult = await apiGet(`/api/shared-drive/files/${file.id}/versions`)
        if (versionsResult.ok && versionsResult.data) {
          setVersions(Array.isArray(versionsResult.data) ? versionsResult.data : [])
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
      const result = await apiGet(`/api/shared-drive/files/${file.id}`)
      if (result.ok && result.data) {
        setContent(result.data)
        setSelectedVersion(null)
      }
    } else {
      // Show specific version
      const result = await apiGet(`/api/shared-drive/files/${file.id}/versions/${versionNum}`)
      if (result.ok && result.data) {
        setContent(result.data)
        setSelectedVersion(result.data)
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
        <DocumentIframe 
          content={content.content_html || content.html || ''} 
          fileType={file.file_type}
        />
      </div>
    </div>
  )
}

export default DocumentViewer

