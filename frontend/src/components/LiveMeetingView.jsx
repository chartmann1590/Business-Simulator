import { useState, useEffect, useRef, useCallback } from 'react'
import { getAvatarPath } from '../utils/avatarMapper'
import { formatTime as formatTimeTZ } from '../utils/timezone'

function LiveMeetingView({ meeting, onClose, employees = [] }) {
  const [meetingData, setMeetingData] = useState(meeting)
  const [liveMessages, setLiveMessages] = useState([])
  const [activeSpeaker, setActiveSpeaker] = useState(null)
  const [bubbleTimestamps, setBubbleTimestamps] = useState({}) // Track when each bubble appeared (UI timestamp)
  const [renderTrigger, setRenderTrigger] = useState(0) // Force re-renders for opacity updates
  const [viewMode, setViewMode] = useState('all') // 'all' or 'speaker' - view all attendees or just the speaker
  const [isAtBottom, setIsAtBottom] = useState(true) // Track if user is scrolled to bottom
  const seenMessageIdsRef = useRef(new Set()) // Track which messages we've already processed
  const transcriptEndRef = useRef(null)
  const transcriptContainerRef = useRef(null) // Ref for the transcript scroll container
  const videoGridRef = useRef(null)

  useEffect(() => {
    if (meeting?.id) {
      fetchMeetingDetails()
      const interval = setInterval(fetchMeetingDetails, 1000) // Refresh every 1 second for live updates
      return () => clearInterval(interval)
    }
  }, [meeting?.id])

  // Check if user is at bottom of transcript
  const checkIfAtBottom = useCallback(() => {
    if (transcriptContainerRef.current) {
      const container = transcriptContainerRef.current
      const threshold = 100 // Consider "at bottom" if within 100px of bottom
      const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < threshold
      setIsAtBottom(isNearBottom)
    }
  }, [])

  // Handle scroll events and check initial position
  useEffect(() => {
    const container = transcriptContainerRef.current
    if (!container) return

    // Check initial position after a brief delay to ensure content is rendered
    const checkInitial = setTimeout(() => {
      checkIfAtBottom()
    }, 100)

    container.addEventListener('scroll', checkIfAtBottom)

    return () => {
      clearTimeout(checkInitial)
      container.removeEventListener('scroll', checkIfAtBottom)
    }
  }, [checkIfAtBottom, liveMessages.length])

  // Scroll transcript to bottom when new messages arrive (only if user is already at bottom)
  useEffect(() => {
    if (transcriptContainerRef.current && isAtBottom) {
      // Use scrollTop instead of scrollIntoView to avoid scrolling the whole page
      const container = transcriptContainerRef.current
      container.scrollTop = container.scrollHeight
    }
  }, [liveMessages, meetingData.live_transcript, isAtBottom])

  // Separate effect for managing active speaker and bubble timestamps
  useEffect(() => {
    if (liveMessages.length === 0) {
      setActiveSpeaker(null)
      setBubbleTimestamps({})
      seenMessageIdsRef.current.clear()
      return
    }

    // Get the most recent message
    const lastMessage = liveMessages[liveMessages.length - 1]
    if (!lastMessage) {
      return
    }

    // Create a unique ID for this message (use message content + timestamp to make it unique)
    const messageId = `${lastMessage.sender_id}-${lastMessage.timestamp}-${lastMessage.message?.substring(0, 20)}`
    
    // Only update timestamp if this is a NEW message we haven't seen before
    if (!seenMessageIdsRef.current.has(messageId)) {
      seenMessageIdsRef.current.add(messageId)
      
      const senderId = lastMessage.sender_id
      const now = Date.now()
      
      // Update timestamp for this speaker's bubble using UI time (ONLY when we first see it)
      // IMPORTANT: Only update if we don't already have a timestamp, or if the existing one is old
      setBubbleTimestamps(prev => {
        const existingTimestamp = prev[senderId]
        // Only update if no timestamp exists, or if existing bubble is already gone (> 6.5 seconds old)
        if (!existingTimestamp || (now - existingTimestamp) / 1000 > 6.5) {
          console.log(`Setting new bubble timestamp for ${senderId} at ${now}`)
          return {
            ...prev,
            [senderId]: now
          }
        }
        // Don't update if bubble is still active
        console.log(`Keeping existing bubble timestamp for ${senderId} (age: ${((now - existingTimestamp) / 1000).toFixed(2)}s)`)
        return prev
      })
      
      // Set active speaker to the person who just spoke
      setActiveSpeaker(senderId)
    }
  }, [liveMessages])

  // Effect to clean up old bubbles based on timestamps and trigger re-renders for opacity
  useEffect(() => {
    const cleanupInterval = setInterval(() => {
      const now = Date.now()
      
      setBubbleTimestamps(prev => {
        const updated = { ...prev }
        let changed = false
        let hasActiveBubbles = false
        
        // Remove bubbles older than 6.5 seconds (based on UI timestamp)
        Object.keys(updated).forEach(senderId => {
          const timestamp = updated[senderId]
          const age = (now - timestamp) / 1000
          if (age > 6.5) {
            delete updated[senderId]
            changed = true
          } else {
            // Bubble is still active
            hasActiveBubbles = true
          }
        })
        
        // Always trigger re-render if there are active bubbles (to update opacity smoothly)
        if (hasActiveBubbles) {
          setRenderTrigger(renderTrigger => renderTrigger + 1)
        }
        
        // Update active speaker - clear if bubble is older than 8 seconds
        setActiveSpeaker(currentSpeaker => {
          if (currentSpeaker === null) return null
          
          const bubbleTimestamp = updated[currentSpeaker]
          if (!bubbleTimestamp) {
            return null
          }
          
          const age = (now - bubbleTimestamp) / 1000
          if (age > 8) {
            return null
          }
          return currentSpeaker
        })
        
        return changed ? updated : prev
      })
    }, 100) // Check every 100ms
    
    return () => clearInterval(cleanupInterval)
  }, [])

  const fetchMeetingDetails = async () => {
    if (!meeting?.id) return
    try {
      const response = await fetch(`/api/meetings/${meeting.id}`)
      if (response.ok) {
        const data = await response.json()
        setMeetingData(data)
        
        // Update live messages from metadata - handle both array and string cases
        let messages = []
        if (data.meeting_metadata?.live_messages) {
          if (Array.isArray(data.meeting_metadata.live_messages)) {
            messages = data.meeting_metadata.live_messages
          } else if (typeof data.meeting_metadata.live_messages === 'string' && data.meeting_metadata.live_messages.trim() !== '') {
            // If it's a string, try to parse it
            try {
              messages = JSON.parse(data.meeting_metadata.live_messages)
            } catch (e) {
              console.warn('Could not parse live_messages:', e)
              messages = []
            }
          }
        }
        setLiveMessages(messages)
        
        // Also update from live_transcript if available (for backwards compatibility)
        if (data.live_transcript && messages.length === 0) {
          // Parse transcript to extract messages if live_messages is empty
          const transcriptLines = data.live_transcript.split('\n').filter(line => line.trim())
          const parsedMessages = []
          const meetingStartTime = data.start_time ? new Date(data.start_time) : new Date()
          
          transcriptLines.forEach(line => {
            // Match pattern like [16:52:42] Quinn Garcia: message text
            const match = line.match(/\[(\d{2}):(\d{2}):(\d{2})\]\s+([^:]+):\s+(.+)/)
            if (match) {
              const [, hours, minutes, seconds, name, message] = match
              const attendee = data.attendees?.find(a => a.name === name.trim())
              if (attendee) {
                // Create a static timestamp based on the meeting start time + the time in the transcript
                const transcriptTime = new Date(meetingStartTime)
                transcriptTime.setHours(parseInt(hours, 10))
                transcriptTime.setMinutes(parseInt(minutes, 10))
                transcriptTime.setSeconds(parseInt(seconds, 10))
                
                parsedMessages.push({
                  sender_id: attendee.id,
                  sender_name: attendee.name,
                  sender_title: attendee.title,
                  message: message.trim(),
                  timestamp: transcriptTime.toISOString() // Static timestamp based on transcript time
                })
              }
            }
          })
          if (parsedMessages.length > 0) {
            setLiveMessages(parsedMessages)
          }
        }
      }
    } catch (error) {
      console.error('Error fetching meeting details:', error)
    }
  }


  const getAttendeeById = (attendeeId) => {
    return meetingData.attendees?.find(a => a.id === attendeeId)
  }

  const getLatestMessageForAttendee = (attendeeId) => {
    // Get the most recent message from this attendee
    const messages = liveMessages.filter(msg => msg.sender_id === attendeeId)
    return messages.length > 0 ? messages[messages.length - 1] : null
  }

  const getGridCols = (count) => {
    if (count <= 1) return 'grid-cols-1'
    if (count <= 2) return 'grid-cols-2'
    if (count <= 4) return 'grid-cols-2'
    if (count <= 6) return 'grid-cols-3'
    return 'grid-cols-4'
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

  const attendees = meetingData.attendees || []
  
  // Filter attendees based on view mode
  let displayedAttendees = attendees
  if (viewMode === 'speaker') {
    // Show only the active speaker, or all if no one is speaking
    if (activeSpeaker) {
      displayedAttendees = attendees.filter(a => a.id === activeSpeaker)
    } else {
      // If no one is speaking, show all (fallback)
      displayedAttendees = attendees
    }
  }
  
  const gridCols = getGridCols(displayedAttendees.length)

  return (
    <div className="h-full flex flex-col bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 p-4 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold mb-1">{meetingData.title}</h2>
            <div className="flex items-center gap-4 text-sm text-gray-400">
              <span>🕐 {formatTimeTZ(meetingData.start_time)}</span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
                Live
              </span>
              <span>👥 {attendees.length} attendees</span>
              {viewMode === 'speaker' && activeSpeaker && (
                <span className="text-blue-400">• Speaker View</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* View Mode Toggle */}
            <div className="flex items-center gap-2 bg-gray-700 rounded-lg p-1">
              <button
                onClick={() => setViewMode('all')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  viewMode === 'all'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:text-white'
                }`}
                title="View all attendees"
              >
                All
              </button>
              <button
                onClick={() => setViewMode('speaker')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  viewMode === 'speaker'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:text-white'
                }`}
                title="View only the active speaker"
              >
                Speaker
              </button>
            </div>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg transition-colors font-medium"
            >
              Leave Meeting
            </button>
          </div>
        </div>
      </div>

      {/* Main Content - Zoom Video Call Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Video Grid Area (Main) */}
        <div className="flex-1 bg-black p-4 overflow-hidden relative" ref={videoGridRef}>
          <div className={`grid ${gridCols} gap-4 h-full`}>
            {displayedAttendees.map(attendee => {
              const latestMessage = getLatestMessageForAttendee(attendee.id)
              const isSpeaking = activeSpeaker === attendee.id
              // Get avatar path using the utility function
              const avatarUrl = getAvatarPath(attendee)
              
              return (
                <div
                  key={attendee.id}
                  className={`relative bg-gray-800 rounded-lg overflow-hidden flex items-center justify-center transition-all ${
                    isSpeaking ? 'ring-4 ring-green-500 ring-opacity-75' : ''
                  }`}
                >
                  {/* Profile Photo/Video Tile */}
                  <div className="w-full h-full flex flex-col items-center justify-center p-4 relative">
                    <img
                      src={avatarUrl}
                      alt={attendee.name}
                      className="w-full h-full object-cover rounded-lg"
                      style={{ display: 'block' }}
                      onError={(e) => {
                        // If image fails to load, hide it and show fallback
                        e.target.style.display = 'none'
                        const fallback = e.target.nextElementSibling
                        if (fallback) {
                          fallback.style.display = 'flex'
                        }
                      }}
                    />
                    <div
                      className="w-full h-full rounded-lg flex items-center justify-center text-6xl font-bold absolute inset-0"
                      style={{
                        display: 'none',
                        background: `linear-gradient(135deg, ${
                          ['#3B82F6', '#8B5CF6', '#EC4899', '#F59E0B', '#10B981', '#EF4444'][attendee.id % 6]
                        } 0%, ${
                          ['#1D4ED8', '#7C3AED', '#DB2777', '#D97706', '#059669', '#DC2626'][attendee.id % 6]
                        } 100%)`
                      }}
                    >
                      {attendee.name.charAt(0).toUpperCase()}
                    </div>
                    
                    {/* Name Overlay */}
                    <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-3">
                      <p className="text-sm font-semibold text-white">{attendee.name}</p>
                      <p className="text-xs text-gray-300">{attendee.title}</p>
                    </div>
                    
                    {/* Microphone Indicator */}
                    <div className="absolute top-3 right-3 flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full ${isSpeaking ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`}></div>
                      {isSpeaking && (
                        <span className="text-xs text-white bg-green-500 px-2 py-1 rounded-full animate-pulse">
                          Speaking
                        </span>
                      )}
                    </div>
                    
                    {/* Speaking Indicator - Animated Border */}
                    {isSpeaking && (
                      <div className="absolute inset-0 border-4 border-green-400 rounded-lg animate-pulse pointer-events-none"></div>
                    )}
                  </div>

                  {/* Chat Bubble - appears when this person speaks, fades away after 6 seconds */}
                  {(() => {
                    const bubbleTimestamp = bubbleTimestamps[attendee.id]
                    if (!latestMessage || !bubbleTimestamp) return null
                    
                    const now = Date.now()
                    const age = (now - bubbleTimestamp) / 1000
                    
                    // Don't show bubble if older than 6.5 seconds
                    if (age > 6.5) return null
                    
                    // Calculate opacity: fade out between 5.5 and 6.5 seconds
                    let opacity = 1
                    if (age > 5.5) {
                      // Fade out over 1 second (from 5.5 to 6.5)
                      opacity = 1 - ((age - 5.5) / 1.0)
                    }
                    
                    return (
                      <div 
                        className="absolute bottom-20 left-1/2 transform -translate-x-1/2 z-20"
                        style={{
                          opacity: opacity,
                          transition: 'opacity 0.1s linear',
                          pointerEvents: opacity < 0.1 ? 'none' : 'auto'
                        }}
                      >
                        <div className={`bg-white text-gray-900 rounded-lg px-4 py-3 shadow-2xl max-w-xs border-2 ${
                          isSpeaking ? 'border-green-400' : 'border-gray-300'
                        }`}>
                          <div className="text-sm font-medium mb-1 text-blue-600 flex items-center gap-2">
                            {isSpeaking && (
                              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                            )}
                            {attendee.name}
                          </div>
                          <div className="text-sm">{latestMessage.message}</div>
                          {/* Arrow pointing down */}
                          <div className="absolute -bottom-2 left-1/2 transform -translate-x-1/2">
                            <div className="w-0 h-0 border-l-8 border-r-8 border-t-8 border-transparent border-t-white"></div>
                          </div>
                        </div>
                      </div>
                    )
                  })()}
                </div>
              )
            })}
          </div>
        </div>

        {/* Transcript Sidebar (Right) */}
        <div className="w-96 bg-gray-900 border-l border-gray-700 flex flex-col flex-shrink-0">
          {/* Header */}
          <div className="p-4 border-b border-gray-700">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
              Live Transcript
            </h3>
            <p className="text-xs text-gray-500 mt-1">Real-time meeting transcript</p>
          </div>

          {/* Transcript Content */}
          <div 
            ref={transcriptContainerRef}
            className="flex-1 overflow-y-auto p-4 bg-gray-950"
          >
            <div className="space-y-2">
              {liveMessages.map((msg, index) => {
                const attendee = getAttendeeById(msg.sender_id)
                const attendeeName = attendee?.name || msg.sender_name || 'Unknown'
                const timestamp = msg.timestamp ? formatTimeTZ(msg.timestamp, true) : ''
                
                return (
                  <div key={index} className="text-sm animate-fade-in">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-blue-400">{attendeeName}</span>
                      {timestamp && (
                        <span className="text-xs text-gray-500">{timestamp}</span>
                      )}
                    </div>
                    <div className="text-gray-200 bg-gray-800 rounded px-3 py-2">
                      {msg.message}
                    </div>
                  </div>
                )
              })}
              
              {/* Fallback: Show live_transcript if live_messages is empty but transcript exists */}
              {liveMessages.length === 0 && meetingData.live_transcript && (() => {
                // Calculate meeting start time once for stable timestamps
                const meetingStartTime = meetingData.start_time ? new Date(meetingData.start_time) : new Date()
                return (
                  <div className="space-y-2">
                    {meetingData.live_transcript.split('\n').filter(line => {
                      const trimmed = line.trim()
                      return trimmed && !trimmed.includes('Meeting started') && trimmed.length > 0
                    }).map((line, index) => {
                      // Parse transcript lines like [16:52:42] Quinn Garcia: message text
                      const match = line.match(/\[(\d{2}):(\d{2}):(\d{2})\]\s+([^:]+):\s+(.+)/)
                      if (match) {
                        const [, hours, minutes, seconds, name, message] = match
                        const attendee = meetingData.attendees?.find(a => a.name === name.trim())
                        // Create static timestamp based on meeting start time + transcript time
                        const transcriptTime = new Date(meetingStartTime)
                        transcriptTime.setHours(parseInt(hours, 10))
                        transcriptTime.setMinutes(parseInt(minutes, 10))
                        transcriptTime.setSeconds(parseInt(seconds, 10))
                        const staticTimestamp = formatTimeTZ(transcriptTime, true)
                        
                        return (
                          <div key={index} className="text-sm animate-fade-in">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-semibold text-blue-400">{name.trim()}</span>
                              <span className="text-xs text-gray-500">{staticTimestamp}</span>
                            </div>
                            <div className="text-gray-200 bg-gray-800 rounded px-3 py-2">
                              {message.trim()}
                            </div>
                          </div>
                        )
                      }
                      // If it doesn't match the pattern, just show the line
                      if (line.trim().length > 0) {
                        return (
                          <div key={index} className="text-sm text-gray-300 py-1">
                            {line}
                          </div>
                        )
                      }
                      return null
                    })}
                  </div>
                )
              })()}
              
              {liveMessages.length === 0 && !meetingData.live_transcript && (
                <div className="text-center text-gray-500 py-8 text-sm">
                  Waiting for discussion to begin...
                </div>
              )}
              <div ref={transcriptEndRef} />
            </div>
          </div>

          {/* Meeting Info Footer */}
          <div className="p-4 border-t border-gray-700 bg-gray-800">
            <div className="text-xs text-gray-400 space-y-1">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                <span>All participants are connected</span>
              </div>
              <div className="text-gray-500">
                {liveMessages.length > 0 
                  ? `${liveMessages.length} message${liveMessages.length !== 1 ? 's' : ''} in transcript`
                  : meetingData.live_transcript 
                    ? `${meetingData.live_transcript.split('\n').filter(l => l.trim() && !l.includes('Meeting started')).length} message${meetingData.live_transcript.split('\n').filter(l => l.trim() && !l.includes('Meeting started')).length !== 1 ? 's' : ''} in transcript`
                    : '0 messages in transcript'
                }
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default LiveMeetingView
