import { useState, useEffect, useRef } from 'react'
import { formatDateTime, formatTime } from '../utils/timezone'

function EmployeeScreenView({ employeeId }) {
  const [screenData, setScreenData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [mousePosition, setMousePosition] = useState({ x: 50, y: 50 })
  const [typingText, setTypingText] = useState('')
  const typingIntervalRef = useRef(null)
  const mouseAnimationRef = useRef(null)

  const fetchScreenData = async () => {
    try {
      const response = await fetch(`/api/employees/${employeeId}/screen-view`)
      if (!response.ok) {
        let errorMessage = 'Failed to fetch screen data'
        try {
          const errorData = await response.json()
          errorMessage = errorData.detail || errorData.message || errorMessage
        } catch (e) {
          // If response is not JSON, use status text
          errorMessage = `HTTP ${response.status}: ${response.statusText || errorMessage}`
        }
        throw new Error(errorMessage)
      }
      const data = await response.json()
      setScreenData(data)
      setError(null)

      // Update mouse position
      if (data.screen_activity?.mouse_position) {
        animateMouseTo(data.screen_activity.mouse_position)
      }

      // Handle typing animation for text content
      if (data.screen_activity?.action === 'composing' || data.screen_activity?.action === 'editing') {
        startTypingAnimation(data.screen_activity.content)
      }
    } catch (err) {
      console.error('Error fetching screen data:', err)
      setError(err.message)
      setLoading(false)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchScreenData()
    const interval = setInterval(fetchScreenData, 10000) // Reduced from 2.5s to 10s to prevent timeouts
    return () => {
      clearInterval(interval)
      if (typingIntervalRef.current) {
        clearInterval(typingIntervalRef.current)
      }
      if (mouseAnimationRef.current) {
        cancelAnimationFrame(mouseAnimationRef.current)
      }
    }
  }, [employeeId])

  const animateMouseTo = (targetPos) => {
    const startX = mousePosition.x
    const startY = mousePosition.y
    const targetX = targetPos.x
    const targetY = targetPos.y
    const duration = 1000 // 1 second animation
    const startTime = Date.now()

    const animate = () => {
      const elapsed = Date.now() - startTime
      const progress = Math.min(elapsed / duration, 1)

      // Easing function
      const ease = 1 - Math.pow(1 - progress, 3)

      const currentX = startX + (targetX - startX) * ease
      const currentY = startY + (targetY - startY) * ease

      setMousePosition({ x: currentX, y: currentY })

      if (progress < 1) {
        mouseAnimationRef.current = requestAnimationFrame(animate)
      }
    }

    if (mouseAnimationRef.current) {
      cancelAnimationFrame(mouseAnimationRef.current)
    }
    mouseAnimationRef.current = requestAnimationFrame(animate)
  }

  const startTypingAnimation = (content) => {
    if (typingIntervalRef.current) {
      clearInterval(typingIntervalRef.current)
    }

    let textToType = ''
    if (content.body) {
      textToType = content.body
    } else if (content.message) {
      textToType = content.message
    } else if (content.document_content) {
      textToType = content.document_content.substring(0, 200)
    }

    if (textToType) {
      let currentIndex = 0
      setTypingText('')

      typingIntervalRef.current = setInterval(() => {
        if (currentIndex < textToType.length) {
          setTypingText(textToType.substring(0, currentIndex + 1))
          currentIndex++
        } else {
          clearInterval(typingIntervalRef.current)
        }
      }, 30) // Type one character every 30ms
    }
  }

  if (loading && !screenData) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900 text-white">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
          <p>Loading screen view...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900 text-white">
        <div className="text-center">
          <p className="text-red-400 mb-2">Error: {error}</p>
          <button
            onClick={fetchScreenData}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (!screenData) {
    return null
  }

  const activity = screenData.screen_activity || {}
  const application = activity.application || 'outlook'
  const action = activity.action || 'viewing'
  const content = activity.content || {}
  const windowState = activity.window_state || 'active'
  const actualData = screenData.actual_data || { emails: [], chats: [], files: [] }

  // Render application window based on type
  const renderApplicationWindow = () => {
    switch (application) {
      case 'outlook':
        return (
          <div className="bg-white rounded-lg shadow-2xl overflow-hidden" style={{ width: '800px', height: '600px' }}>
            {/* Title Bar */}
            <div className="bg-blue-600 text-white px-4 py-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg font-semibold">Outlook</span>
                {action === 'composing' && <span className="text-sm opacity-90">- New Message</span>}
              </div>
              <div className="flex gap-1">
                <button className="w-6 h-6 hover:bg-blue-700 rounded flex items-center justify-center">−</button>
                <button className="w-6 h-6 hover:bg-blue-700 rounded flex items-center justify-center">□</button>
                <button className="w-6 h-6 hover:bg-red-600 rounded flex items-center justify-center">×</button>
              </div>
            </div>

            {/* Email Content */}
            <div className="p-6 h-full overflow-y-auto bg-gray-50">
              {action === 'composing' ? (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">To:</label>
                    <input
                      type="text"
                      value={content.recipient || 'Colleague'}
                      readOnly
                      className="w-full px-3 py-2 border border-gray-300 rounded bg-white"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Subject:</label>
                    <input
                      type="text"
                      value={content.subject || 'Work Update'}
                      readOnly
                      className="w-full px-3 py-2 border border-gray-300 rounded bg-white"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Message:</label>
                    <textarea
                      value={typingText || content.body || ''}
                      readOnly
                      className="w-full px-3 py-2 border border-gray-300 rounded bg-white h-64 resize-none"
                    />
                    {(action === 'composing' && typingText.length < (content.body?.length || 0)) && (
                      <span className="inline-block w-2 h-4 bg-blue-600 ml-1 animate-pulse"></span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                      Send
                    </button>
                    <button className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300">
                      Save Draft
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Show actual email if available, otherwise use generated content */}
                  {actualData.emails && actualData.emails.length > 0 && action === 'viewing' ? (
                    actualData.emails.slice(0, 1).map((email, idx) => (
                      <div key={email.id || idx} className="space-y-4">
                        <div className="border-b pb-4">
                          <h3 className="text-lg font-semibold text-gray-900">{email.subject || 'Email Subject'}</h3>
                          <p className="text-sm text-gray-600 mt-1">
                            From: {email.sender_name || 'Colleague'} • To: {email.recipient_name || 'You'}
                          </p>
                          <p className="text-xs text-gray-500 mt-1">
                            {email.timestamp ? formatDateTime(email.timestamp) : ''}
                          </p>
                        </div>
                        <div className="text-gray-700 whitespace-pre-wrap">
                          {email.body || 'Email content...'}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="space-y-4">
                      <div className="border-b pb-4">
                        <h3 className="text-lg font-semibold text-gray-900">{content.subject || 'Email Subject'}</h3>
                        <p className="text-sm text-gray-600 mt-1">
                          From: {content.sender || content.sender_name || 'Colleague'} • To: {content.recipient || content.recipient_name || 'You'}
                        </p>
                      </div>
                      <div className="text-gray-700 whitespace-pre-wrap">
                        {content.body || 'Email content...'}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )

      case 'teams':
        return (
          <div className="bg-white rounded-lg shadow-2xl overflow-hidden" style={{ width: '600px', height: '700px' }}>
            {/* Title Bar */}
            <div className="bg-purple-600 text-white px-4 py-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg font-semibold">Microsoft Teams</span>
                <span className="text-sm opacity-90">- {content.conversation_with || 'Colleague'}</span>
              </div>
              <div className="flex gap-1">
                <button className="w-6 h-6 hover:bg-purple-700 rounded flex items-center justify-center">−</button>
                <button className="w-6 h-6 hover:bg-purple-700 rounded flex items-center justify-center">□</button>
                <button className="w-6 h-6 hover:bg-red-600 rounded flex items-center justify-center">×</button>
              </div>
            </div>

            {/* Chat Content */}
            <div className="flex flex-col h-full">
              <div className="flex-1 overflow-y-auto p-4 bg-gray-50 space-y-3">
                {/* Show actual chat messages if available, otherwise use generated content */}
                {actualData.chats && actualData.chats.length > 0 && action === 'viewing' ? (
                  actualData.chats.slice().reverse().map((chat, idx) => {
                    const isEmployee = chat.sender_id === screenData.employee_id || chat.sender_name === screenData.employee_name
                    return (
                      <div key={chat.id || idx} className={`flex ${isEmployee ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-xs px-4 py-2 rounded-lg ${isEmployee
                            ? 'bg-blue-600 text-white'
                            : 'bg-white border border-gray-200 text-gray-900'
                          }`}>
                          <p className="text-sm font-medium mb-1">{chat.sender_name || 'Colleague'}</p>
                          <p className="text-sm">{chat.message || ''}</p>
                          <p className="text-xs opacity-70 mt-1">
                            {chat.timestamp ? formatTime(chat.timestamp) : ''}
                          </p>
                        </div>
                      </div>
                    )
                  })
                ) : content.messages && Array.isArray(content.messages) ? (
                  content.messages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.sender === screenData.employee_name ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-xs px-4 py-2 rounded-lg ${msg.sender === screenData.employee_name
                          ? 'bg-blue-600 text-white'
                          : 'bg-white border border-gray-200 text-gray-900'
                        }`}>
                        <p className="text-sm font-medium mb-1">{msg.sender || 'Colleague'}</p>
                        <p className="text-sm">{msg.text || msg.message || ''}</p>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="space-y-3">
                    <div className="flex justify-start">
                      <div className="max-w-xs px-4 py-2 rounded-lg bg-white border border-gray-200">
                        <p className="text-sm font-medium mb-1">{content.conversation_with || 'Colleague'}</p>
                        <p className="text-sm">{content.message || 'Hey, how is the project going?'}</p>
                      </div>
                    </div>
                    {action === 'composing' && (
                      <div className="flex justify-end">
                        <div className="max-w-xs px-4 py-2 rounded-lg bg-blue-600 text-white">
                          <p className="text-sm font-medium mb-1">{screenData.employee_name}</p>
                          <p className="text-sm">{typingText || content.message || ''}</p>
                          {typingText.length < (content.message?.length || 0) && (
                            <span className="inline-block w-2 h-4 bg-white ml-1 animate-pulse"></span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                {action === 'composing' && (
                  <div className="flex items-center gap-2 text-gray-500 text-sm px-4">
                    <span>{screenData.employee_name} is typing...</span>
                  </div>
                )}
              </div>

              {/* Message Input */}
              <div className="border-t border-gray-200 p-4 bg-white">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={typingText || content.message || ''}
                    readOnly
                    placeholder="Type a message..."
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg"
                  />
                  <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                    Send
                  </button>
                </div>
              </div>
            </div>
          </div>
        )

      case 'browser':
        return (
          <div className="bg-white rounded-lg shadow-2xl overflow-hidden" style={{ width: '900px', height: '650px' }}>
            {/* Title Bar */}
            <div className="bg-gray-100 px-4 py-2 flex items-center justify-between border-b">
              <div className="flex items-center gap-2 flex-1">
                <div className="flex gap-1">
                  <button className="w-3 h-3 rounded-full bg-red-500"></button>
                  <button className="w-3 h-3 rounded-full bg-yellow-500"></button>
                  <button className="w-3 h-3 rounded-full bg-green-500"></button>
                </div>
                <input
                  type="text"
                  value={content.url || 'https://example.com'}
                  readOnly
                  className="flex-1 px-3 py-1 bg-white border border-gray-300 rounded text-sm"
                />
              </div>
              <div className="flex gap-1 ml-2">
                <button className="w-6 h-6 hover:bg-gray-200 rounded flex items-center justify-center">−</button>
                <button className="w-6 h-6 hover:bg-gray-200 rounded flex items-center justify-center">□</button>
                <button className="w-6 h-6 hover:bg-red-600 rounded flex items-center justify-center">×</button>
              </div>
            </div>

            {/* Browser Content */}
            <div className="p-6 h-full overflow-y-auto bg-white">
              <h1 className="text-2xl font-bold text-gray-900 mb-4">{content.page_title || 'Web Page'}</h1>
              {/* Render HTML content if available, otherwise show plain text */}
              {content.page_content && content.page_content.includes('<') ? (
                <div
                  className="text-gray-700 leading-relaxed prose max-w-none"
                  dangerouslySetInnerHTML={{ __html: content.page_content }}
                />
              ) : (
                <div className="text-gray-700 leading-relaxed whitespace-pre-wrap">
                  {content.page_content || content.body || 'Loading page content...'}
                </div>
              )}
            </div>
          </div>
        )

      case 'sharedrive':
        return (
          <div className="bg-white rounded-lg shadow-2xl overflow-hidden" style={{ width: '800px', height: '600px' }}>
            {/* Title Bar */}
            <div className="bg-green-600 text-white px-4 py-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg font-semibold">Share Drive</span>
                {content.file_name && <span className="text-sm opacity-90">- {content.file_name}</span>}
              </div>
              <div className="flex gap-1">
                <button className="w-6 h-6 hover:bg-green-700 rounded flex items-center justify-center">−</button>
                <button className="w-6 h-6 hover:bg-green-700 rounded flex items-center justify-center">□</button>
                <button className="w-6 h-6 hover:bg-red-600 rounded flex items-center justify-center">×</button>
              </div>
            </div>

            {/* File Explorer or Document Viewer */}
            <div className="flex h-full">
              {action === 'viewing' && !content.document_content ? (
                <div className="w-64 border-r border-gray-200 bg-gray-50 p-4 overflow-y-auto">
                  <h3 className="font-semibold text-gray-900 mb-3">Folders</h3>
                  <div className="space-y-1">
                    <div className="px-3 py-2 hover:bg-gray-200 rounded cursor-pointer flex items-center gap-2">
                      <span>📁</span>
                      <span>Documents</span>
                    </div>
                    <div className="px-3 py-2 hover:bg-gray-200 rounded cursor-pointer flex items-center gap-2">
                      <span>📁</span>
                      <span>Projects</span>
                    </div>
                    <div className="px-3 py-2 hover:bg-gray-200 rounded cursor-pointer flex items-center gap-2">
                      <span>📁</span>
                      <span>Shared</span>
                    </div>
                  </div>
                  <h3 className="font-semibold text-gray-900 mb-3 mt-4">Files</h3>
                  <div className="space-y-1">
                    {actualData.files && actualData.files.length > 0 ? (
                      actualData.files.map((file, idx) => (
                        <div key={file.id || idx} className="px-3 py-2 hover:bg-gray-200 rounded cursor-pointer flex items-center gap-2">
                          <span>📄</span>
                          <span className="text-sm">{file.file_name || 'Document'}</span>
                        </div>
                      ))
                    ) : content.files && Array.isArray(content.files) ? (
                      content.files.map((file, idx) => (
                        <div key={idx} className="px-3 py-2 hover:bg-gray-200 rounded cursor-pointer flex items-center gap-2">
                          <span>📄</span>
                          <span className="text-sm">{file.name || file}</span>
                        </div>
                      ))
                    ) : (
                      <div className="px-3 py-2 hover:bg-gray-200 rounded cursor-pointer flex items-center gap-2">
                        <span>📄</span>
                        <span className="text-sm">{content.file_name || 'Document.docx'}</span>
                      </div>
                    )}
                  </div>
                </div>
              ) : null}

              <div className="flex-1 p-6 overflow-y-auto bg-gray-50">
                {/* Show actual file content if available, otherwise use generated content */}
                {actualData.files && actualData.files.length > 0 && action === 'viewing' ? (
                  actualData.files.slice(0, 1).map((file, idx) => (
                    <div key={file.id || idx} className="bg-white p-6 rounded shadow-sm">
                      <h2 className="text-xl font-semibold text-gray-900 mb-4">
                        {file.file_name || 'Document'}
                      </h2>
                      <p className="text-sm text-gray-500 mb-4">
                        Type: {file.file_type || 'Unknown'} • Updated: {file.updated_at ? formatDateTime(file.updated_at) : 'Unknown'}
                      </p>
                      <div className="text-gray-700 leading-relaxed whitespace-pre-wrap">
                        {file.content || content.document_content || 'Document content...'}
                      </div>
                    </div>
                  ))
                ) : content.document_content ? (
                  <div className="bg-white p-6 rounded shadow-sm">
                    <h2 className="text-xl font-semibold text-gray-900 mb-4">
                      {content.file_name || 'Document'}
                    </h2>
                    <div className="text-gray-700 leading-relaxed whitespace-pre-wrap">
                      {typingText || content.document_content || 'Document content...'}
                    </div>
                    {action === 'editing' && typingText.length < (content.document_content?.length || 0) && (
                      <span className="inline-block w-2 h-4 bg-blue-600 ml-1 animate-pulse"></span>
                    )}
                  </div>
                ) : (
                  <div className="text-center text-gray-500 py-12">
                    <p>Select a file to view</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="relative w-full h-full bg-gradient-to-br from-blue-900 via-blue-800 to-indigo-900 flex items-center justify-center overflow-hidden">
      {/* Desktop Background */}
      <div className="absolute inset-0 bg-gradient-to-br from-blue-50 to-indigo-100 opacity-20"></div>

      {/* Desktop Icons */}
      <div className="absolute top-8 left-8 space-y-3 z-10">
        <div className="flex flex-col items-center gap-1 cursor-pointer hover:bg-white hover:bg-opacity-20 p-2 rounded">
          <div className="w-10 h-10 bg-yellow-400 rounded flex items-center justify-center text-xl">📁</div>
          <span className="text-white text-xs text-center">My Documents</span>
        </div>
        <div className="flex flex-col items-center gap-1 cursor-pointer hover:bg-white hover:bg-opacity-20 p-2 rounded">
          <div className="w-10 h-10 bg-green-500 rounded flex items-center justify-center text-xl">💾</div>
          <span className="text-white text-xs text-center">Share Drive</span>
        </div>
        <div className="flex flex-col items-center gap-1 cursor-pointer hover:bg-white hover:bg-opacity-20 p-2 rounded">
          <div className="w-10 h-10 bg-gray-600 rounded flex items-center justify-center text-xl">🗑️</div>
          <span className="text-white text-xs text-center">Recycle Bin</span>
        </div>
      </div>

      {/* Application Window - Scaled to fit */}
      <div className="absolute inset-0 flex items-center justify-center p-4 pb-16">
        <div className="relative w-full h-full flex items-center justify-center" style={{ maxWidth: '95%', maxHeight: '85%' }}>
          <div className="transform scale-75 origin-center">
            {windowState === 'active' && renderApplicationWindow()}
          </div>
        </div>
      </div>

      {/* Mouse Cursor */}
      <div
        className="absolute pointer-events-none z-50"
        style={{
          left: `${mousePosition.x}%`,
          top: `${mousePosition.y}%`,
          transform: 'translate(-50%, -50%)'
        }}
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path
            d="M3 3L10.07 19.97L12.58 12.58L19.97 10.07L3 3Z"
            fill="black"
            stroke="white"
            strokeWidth="1"
          />
        </svg>
      </div>

      {/* Taskbar */}
      <div className="absolute bottom-0 left-0 right-0 bg-gray-800 text-white px-4 py-2 flex items-center justify-between shadow-lg">
        <div className="flex items-center gap-2">
          <button className="px-3 py-1 bg-blue-600 rounded text-sm font-semibold">Start</button>
          <div className="flex items-center gap-1 px-2 py-1 bg-gray-700 rounded">
            {application === 'outlook' && <span className="text-xs">📧 Outlook</span>}
            {application === 'teams' && <span className="text-xs">💬 Teams</span>}
            {application === 'browser' && <span className="text-xs">🌐 Browser</span>}
            {application === 'sharedrive' && <span className="text-xs">📁 Share Drive</span>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs">{formatTime(new Date())}</span>
        </div>
      </div>
    </div>
  )
}

export default EmployeeScreenView

