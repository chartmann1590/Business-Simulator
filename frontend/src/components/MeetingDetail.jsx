import { useState, useEffect } from 'react'

function MeetingDetail({ meeting, onClose, employees = [] }) {
  const [meetingData, setMeetingData] = useState(meeting)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (meeting?.id) {
      fetchMeetingDetails()
      const interval = setInterval(fetchMeetingDetails, 5000) // Refresh every 5 seconds
      return () => clearInterval(interval)
    }
  }, [meeting?.id])

  const fetchMeetingDetails = async () => {
    if (!meeting?.id) return
    try {
      setLoading(true)
      const response = await fetch(`/api/meetings/${meeting.id}`)
      if (response.ok) {
        const data = await response.json()
        setMeetingData(data)
      }
    } catch (error) {
      console.error('Error fetching meeting details:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatTime = (timeString) => {
    if (!timeString) return ''
    const date = new Date(timeString)
    return date.toLocaleString('en-US', { 
      weekday: 'short',
      month: 'short', 
      day: 'numeric',
      hour: '2-digit', 
      minute: '2-digit' 
    })
  }

  const getStatusBadge = (status) => {
    const badges = {
      scheduled: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Scheduled' },
      in_progress: { bg: 'bg-green-100', text: 'text-green-800', label: '🔴 In Progress' },
      completed: { bg: 'bg-gray-100', text: 'text-gray-800', label: 'Completed' },
      cancelled: { bg: 'bg-red-100', text: 'text-red-800', label: 'Cancelled' }
    }
    const badge = badges[status] || badges.scheduled
    return (
      <span className={`px-3 py-1 rounded-full text-sm font-medium ${badge.bg} ${badge.text}`}>
        {badge.label}
      </span>
    )
  }

  const formatOutline = (outline) => {
    if (!outline) return ''
    
    // Handle if outline is a JSON string
    try {
      const parsed = JSON.parse(outline)
      if (typeof parsed === 'object') {
        // Convert object to formatted string
        return formatOutlineObject(parsed)
      }
    } catch (e) {
      // Not JSON, continue with string processing
    }
    
    // Replace literal \n with actual newlines
    let formatted = outline.replace(/\\n/g, '\n')
    
    // Replace other escape sequences
    formatted = formatted.replace(/\\t/g, '\t')
    formatted = formatted.replace(/\\"/g, '"')
    formatted = formatted.replace(/\\'/g, "'")
    
    return formatted
  }

  const formatOutlineObject = (obj, indent = 0) => {
    let result = ''
    const indentStr = '  '.repeat(indent)
    
    for (const [key, value] of Object.entries(obj)) {
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        result += `${indentStr}${key}\n`
        result += formatOutlineObject(value, indent + 1)
      } else if (Array.isArray(value)) {
        result += `${indentStr}${key}\n`
        value.forEach(item => {
          result += `${indentStr}  • ${item}\n`
        })
      } else {
        result += `${indentStr}${key}: ${value}\n`
      }
    }
    
    return result
  }

  const formatAgenda = (agenda) => {
    if (!agenda) return ''
    
    // Replace literal \n with actual newlines
    let formatted = agenda.replace(/\\n/g, '\n')
    formatted = formatted.replace(/\\t/g, '\t')
    
    return formatted
  }

  if (!meetingData) {
    return (
      <div className="text-center py-12">
        <p>Meeting not found</p>
        <button onClick={onClose} className="mt-4 text-blue-600 hover:underline">
          Go back
        </button>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="border-b border-gray-200 p-6 bg-white sticky top-0 z-10 shadow-sm">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h2 className="text-2xl font-bold text-gray-900">{meetingData.title}</h2>
              {getStatusBadge(meetingData.status)}
            </div>
            <p className="text-gray-600 mb-3">{meetingData.description}</p>
            <div className="flex items-center gap-4 text-sm text-gray-500">
              <span>🕐 {formatTime(meetingData.start_time)} - {formatTime(meetingData.end_time)}</span>
              <span>👤 Organized by {meetingData.organizer_name}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors font-medium flex items-center gap-2"
            title="Close meeting details"
          >
            <span>✕</span>
            <span>Close</span>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Attendees */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Attendees</h3>
            <div className="flex flex-wrap gap-2">
              {meetingData.attendees?.map(attendee => (
                <div
                  key={attendee.id}
                  className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-lg"
                >
                  {attendee.avatar_path ? (
                    <img
                      src={`/avatars/${attendee.avatar_path}`}
                      alt={attendee.name}
                      className="w-8 h-8 rounded-full"
                      onError={(e) => {
                        e.target.style.display = 'none'
                        e.target.nextSibling.style.display = 'flex'
                      }}
                    />
                  ) : null}
                  <span
                    className="w-8 h-8 rounded-full bg-blue-500 text-white flex items-center justify-center text-sm font-medium"
                    style={{ display: attendee.avatar_path ? 'none' : 'flex' }}
                  >
                    {attendee.name.charAt(0)}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{attendee.name}</p>
                    <p className="text-xs text-gray-500">{attendee.title}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Agenda */}
          {meetingData.agenda && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Agenda</h3>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="text-sm text-gray-700 space-y-2">
                  {formatAgenda(meetingData.agenda).split('\n').map((line, index) => {
                    if (!line.trim()) return <div key={index} className="h-2" />
                    // Check if line starts with a number or bullet
                    const isBullet = /^[\d•\-\*]/.test(line.trim())
                    return (
                      <div 
                        key={index} 
                        className={isBullet ? 'pl-4' : ''}
                        style={{ 
                          marginLeft: isBullet && /^\s+/.test(line) ? '1rem' : '0',
                          fontWeight: /^[IVX]+\./.test(line.trim()) ? '600' : 'normal'
                        }}
                      >
                        {line.trim()}
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Outline */}
          {meetingData.outline && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Meeting Outline</h3>
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <div className="text-sm text-gray-700 space-y-1 font-sans">
                  {formatOutline(meetingData.outline).split('\n').map((line, index) => {
                    if (!line.trim()) return <div key={index} className="h-2" />
                    
                    // Detect different outline levels
                    const trimmed = line.trim()
                    const isMainTopic = /^[IVX]+\./.test(trimmed) // Roman numerals
                    const isSubTopic = /^[A-Z]\./.test(trimmed) // Letters
                    const isSubSubTopic = /^\d+\./.test(trimmed) // Numbers
                    const isBullet = /^[•\-\*]/.test(trimmed)
                    
                    let className = ''
                    let style = {}
                    
                    if (isMainTopic) {
                      className = 'font-semibold text-gray-900 mt-3 mb-1'
                      style = { fontSize: '0.95rem' }
                    } else if (isSubTopic) {
                      className = 'font-medium text-gray-800 ml-4 mt-2 mb-1'
                      style = { fontSize: '0.9rem' }
                    } else if (isSubSubTopic) {
                      className = 'text-gray-700 ml-8 mt-1'
                      style = { fontSize: '0.875rem' }
                    } else if (isBullet) {
                      className = 'text-gray-700 ml-6'
                    } else {
                      // Regular text - check for indentation
                      const leadingSpaces = line.match(/^\s*/)[0].length
                      className = 'text-gray-700'
                      style = { marginLeft: `${Math.min(leadingSpaces * 0.5, 3)}rem` }
                    }
                    
                    return (
                      <div key={index} className={className} style={style}>
                        {trimmed}
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Transcript */}
          {meetingData.status === 'completed' && meetingData.transcript && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Meeting Transcript</h3>
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 max-h-96 overflow-y-auto">
                <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans">
                  {meetingData.transcript}
                </pre>
              </div>
            </div>
          )}

          {meetingData.status === 'scheduled' && (
            <div className="text-center py-8 text-gray-500">
              <p>This meeting hasn't started yet.</p>
              <p className="text-sm mt-2">Agenda and outline will be available once the meeting begins.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default MeetingDetail

