import { useState, useEffect, useRef } from 'react'
import { getAvatarPath } from '../utils/avatarMapper'

function BoardroomView({ leadershipTeam, chats, onChatsUpdate }) {
  const [boardroomChats, setBoardroomChats] = useState([])
  const [chatBubbles, setChatBubbles] = useState({}) // { employeeId: { message, timestamp, visibleUntil } }
  const bubbleTimersRef = useRef({})
  const shownMessagesRef = useRef({}) // Track which messages have already been shown { employeeId: lastShownTimestamp }
  const [visibleExecutives, setVisibleExecutives] = useState([]) // Executives currently in the room
  const [timeUntilRotation, setTimeUntilRotation] = useState(30 * 60) // Time in seconds until next rotation
  const rotationIntervalRef = useRef(null)
  const lastRotationTimeRef = useRef(null) // Track when last rotation happened
  const isInitializedRef = useRef(false) // Track if we've done initial selection

  // Auto-generate boardroom discussions periodically
  useEffect(() => {
    if (!visibleExecutives || visibleExecutives.length < 2) {
      console.log('Not enough executives for discussions:', visibleExecutives?.length)
      return
    }

    // Generate discussions every 2 minutes for executives in the room
    const generateDiscussions = async () => {
      try {
        const executiveIds = visibleExecutives.map(e => e.id)
        console.log('Generating boardroom discussions for executives:', executiveIds)
        
        const response = await fetch('/api/boardroom/generate-discussions', { 
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ executive_ids: executiveIds })
        })
        const data = await response.json()
        console.log('Boardroom discussions response:', data)
        if (data.success && onChatsUpdate) {
          // Refresh chats after a short delay
          setTimeout(() => {
            onChatsUpdate()
          }, 2000)
        } else if (!data.success) {
          console.error('Failed to generate discussions:', data.message)
        }
      } catch (error) {
        console.error('Error auto-generating discussions:', error)
      }
    }

    // Initial generation immediately, then again after 10 seconds
    generateDiscussions() // Generate immediately
    const initialTimer = setTimeout(generateDiscussions, 10000)
    
    // Then every 2 minutes
    const interval = setInterval(generateDiscussions, 2 * 60 * 1000)

    return () => {
      clearTimeout(initialTimer)
      clearInterval(interval)
    }
  }, [visibleExecutives, onChatsUpdate])

  // Rotate executives in the room every 30 minutes (CEO always stays)
  // This effect should ONLY run once on mount
  useEffect(() => {
    if (!leadershipTeam || leadershipTeam.length === 0) return
    if (isInitializedRef.current) return // Already initialized, don't run again

    // Store leadership team in ref so we always have the latest
    const leadershipTeamRef = { current: leadershipTeam }

    // Function to select executives for the room (max 7, CEO always included)
    const selectExecutives = (isRotation = false, teamToUse = null) => {
      const maxInRoom = 7
      const team = teamToUse || leadershipTeamRef.current || leadershipTeam
      if (!team || team.length === 0) return
      
      const ceo = team.find(emp => emp.role === 'CEO')
      
      // Get current visible executives using functional update to get latest state
      setVisibleExecutives(currentVisible => {
        const currentCEO = currentVisible.find(e => e.role === 'CEO')
        
        // Always use CEO (from current selection if available, otherwise from leadership team)
        const selectedCEO = currentCEO || ceo
        
        // Get other executives (excluding CEO)
        const others = team.filter(emp => emp.role !== 'CEO' && emp.id !== selectedCEO?.id)
        
        // If rotating, select new 6 executives (excluding current ones except CEO)
        // If initial, just select randomly
        let selectedOthers
        if (isRotation && currentVisible.length > 0) {
          // Exclude current executives (except CEO) from selection
          const currentOtherIds = new Set(
            currentVisible
              .filter(e => e.role !== 'CEO')
              .map(e => e.id)
          )
          const available = others.filter(emp => !currentOtherIds.has(emp.id))
          const shuffled = [...available].sort(() => Math.random() - 0.5)
          selectedOthers = shuffled.slice(0, maxInRoom - 1)
        } else {
          // Initial selection - random
          const shuffled = [...others].sort(() => Math.random() - 0.5)
          selectedOthers = shuffled.slice(0, maxInRoom - 1)
        }
        
        // Combine CEO with selected others
        const selected = selectedCEO 
          ? [selectedCEO, ...selectedOthers]
          : selectedOthers.slice(0, maxInRoom)
        
        // Store in localStorage for persistence
        try {
          localStorage.setItem('boardroom_visible_executives', JSON.stringify(selected.map(e => e.id)))
        } catch (e) {
          console.error('Error saving to localStorage:', e)
        }
        
        // Clear chat bubbles for executives leaving the room
        setChatBubbles(prev => {
          const newBubbles = {}
          const selectedIds = new Set(selected.map(emp => emp.id))
          Object.entries(prev).forEach(([empId, bubble]) => {
            if (selectedIds.has(parseInt(empId))) {
              newBubbles[empId] = bubble
            } else {
              // Clear timer for executives leaving
              if (bubbleTimersRef.current[empId]) {
                clearTimeout(bubbleTimersRef.current[empId])
                delete bubbleTimersRef.current[empId]
              }
            }
          })
          return newBubbles
        })
        
        const now = Date.now()
        lastRotationTimeRef.current = now
        setTimeUntilRotation(30 * 60) // Reset to 30 minutes
        
        // Store rotation time in localStorage
        try {
          localStorage.setItem('boardroom_last_rotation', now.toString())
        } catch (e) {
          console.error('Error saving to localStorage:', e)
        }
        
        return selected
      })
    }

    // Check for persisted state
    try {
      const storedRotationTime = localStorage.getItem('boardroom_last_rotation')
      const storedExecutiveIds = localStorage.getItem('boardroom_visible_executives')
      
      if (storedRotationTime && storedExecutiveIds) {
        const lastRotation = parseInt(storedRotationTime)
        const now = Date.now()
        const elapsed = Math.floor((now - lastRotation) / 1000) // seconds
        const ROTATION_INTERVAL_SEC = 30 * 60 // 30 minutes in seconds
        
        // Check if rotation should have happened
        if (elapsed >= ROTATION_INTERVAL_SEC) {
          // Time has passed - need to rotate
          const rotationsNeeded = Math.floor(elapsed / ROTATION_INTERVAL_SEC)
          // Do the rotation(s)
          selectExecutives(true, leadershipTeam)
          // If multiple rotations needed, do them
          for (let i = 1; i < rotationsNeeded; i++) {
            setTimeout(() => {
              selectExecutives(true, leadershipTeam)
            }, 100)
          }
        } else {
          // Restore previous executives
          const executiveIds = JSON.parse(storedExecutiveIds)
          const restored = leadershipTeam.filter(emp => executiveIds.includes(emp.id))
          if (restored.length > 0) {
            setVisibleExecutives(restored)
            lastRotationTimeRef.current = lastRotation
            const remaining = ROTATION_INTERVAL_SEC - elapsed
            setTimeUntilRotation(remaining)
          } else {
            // Invalid stored data, do fresh selection
            selectExecutives(false, leadershipTeam)
          }
        }
      } else {
        // No stored state - do initial selection
        selectExecutives(false, leadershipTeam)
      }
    } catch (e) {
      console.error('Error loading from localStorage:', e)
      // Fallback to fresh selection
      selectExecutives(false, leadershipTeam)
    }

    isInitializedRef.current = true

    // Set up rotation interval - ONLY ONCE
    const ROTATION_INTERVAL = 30 * 60 * 1000 // Exactly 30 minutes
    rotationIntervalRef.current = setInterval(() => {
      // Update leadership team ref before rotation
      leadershipTeamRef.current = leadershipTeam
      selectExecutives(true, leadershipTeam) // true = this is a rotation
    }, ROTATION_INTERVAL)

    return () => {
      // Only clear on unmount
      if (rotationIntervalRef.current) {
        clearInterval(rotationIntervalRef.current)
        rotationIntervalRef.current = null
      }
      isInitializedRef.current = false
    }
  }, []) // Empty dependency array - only run once on mount

  // Countdown timer for next rotation - checks localStorage for persistence
  useEffect(() => {
    const countdownInterval = setInterval(() => {
      // Check localStorage first (in case page was reloaded)
      try {
        const storedRotationTime = localStorage.getItem('boardroom_last_rotation')
        if (storedRotationTime) {
          const lastRotation = parseInt(storedRotationTime)
          const now = Date.now()
          const elapsed = Math.floor((now - lastRotation) / 1000) // seconds
          const remaining = Math.max(0, (30 * 60) - elapsed) // 30 minutes in seconds
          setTimeUntilRotation(remaining)
          lastRotationTimeRef.current = lastRotation
        } else if (lastRotationTimeRef.current) {
          // Fallback to ref if localStorage not available
          const now = Date.now()
          const elapsed = Math.floor((now - lastRotationTimeRef.current) / 1000) // seconds
          const remaining = Math.max(0, (30 * 60) - elapsed) // 30 minutes in seconds
          setTimeUntilRotation(remaining)
        }
      } catch (e) {
        // If localStorage fails, use ref
        if (lastRotationTimeRef.current) {
          const now = Date.now()
          const elapsed = Math.floor((now - lastRotationTimeRef.current) / 1000) // seconds
          const remaining = Math.max(0, (30 * 60) - elapsed) // 30 minutes in seconds
          setTimeUntilRotation(remaining)
        }
      }
    }, 1000) // Update every second

    return () => clearInterval(countdownInterval)
  }, [])

  // Filter chats to only include messages between visible executives
  useEffect(() => {
    if (!visibleExecutives || visibleExecutives.length === 0 || !chats) {
      setBoardroomChats([])
      return
    }

    const visibleIds = new Set(visibleExecutives.map(emp => emp.id))
    
    // Filter chats where both sender and recipient are in the visible executives
    const filteredChats = chats
      .filter(chat => 
        visibleIds.has(chat.sender_id) && visibleIds.has(chat.recipient_id)
      )
      .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp)) // Oldest first for log
    
    setBoardroomChats(filteredChats)

    // Update chat bubbles for the most recent message from each executive
    const lastMessages = {}
    filteredChats.forEach(chat => {
      if (!lastMessages[chat.sender_id] || 
          new Date(chat.timestamp) > new Date(lastMessages[chat.sender_id].timestamp)) {
        lastMessages[chat.sender_id] = chat
      }
    })

    // Update bubbles with new messages - only show if it's a message we haven't shown before
    Object.entries(lastMessages).forEach(([employeeId, chat]) => {
      // Skip if this executive is not currently in the room
      if (!visibleIds.has(parseInt(employeeId))) {
        return
      }
      const now = Date.now()
      const lastShownTimestamp = shownMessagesRef.current[employeeId]
      
      // Check if this is a truly new message (different timestamp than what we've shown before)
      const isNewMessage = !lastShownTimestamp || chat.timestamp !== lastShownTimestamp
      
      // Only show bubble if it's a new message
      if (!isNewMessage) {
        // This message was already shown, don't show it again
        return
      }
      
      // Check current bubble state using functional update
      setChatBubbles(prev => {
        const existingBubble = prev[employeeId]
        
        // If there's an existing bubble that's still visible, don't replace it yet
        if (existingBubble && existingBubble.visibleUntil > now) {
          // Bubble is still visible, wait for it to expire before showing new one
          return prev
        }
        
        // This is a new message that hasn't been shown - show it for at least 6 seconds
        const visibleUntil = now + 6000
        
        // Mark this message as shown
        shownMessagesRef.current[employeeId] = chat.timestamp
        
        // Clear existing timer for this employee
        if (bubbleTimersRef.current[employeeId]) {
          clearTimeout(bubbleTimersRef.current[employeeId])
        }

        // Set timer to hide bubble after 6 seconds
        const timeToShow = visibleUntil - now
        bubbleTimersRef.current[employeeId] = setTimeout(() => {
          setChatBubbles(prevBubbles => {
            const updated = { ...prevBubbles }
            // Only remove if this is still the same message (timestamp matches)
            if (updated[employeeId] && updated[employeeId].timestamp === chat.timestamp) {
              delete updated[employeeId]
            }
            return updated
          })
          delete bubbleTimersRef.current[employeeId]
        }, timeToShow)

        return {
          ...prev,
          [employeeId]: {
            message: chat.message,
            timestamp: chat.timestamp,
            visibleUntil: visibleUntil
          }
        }
      })
    })
  }, [visibleExecutives, chats])

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      Object.values(bubbleTimersRef.current).forEach(timer => clearTimeout(timer))
    }
  }, [])

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return ''
    try {
      const date = new Date(timestamp)
      if (isNaN(date.getTime())) return ''
      return date.toLocaleString()
    } catch {
      return ''
    }
  }

  const getEmployee = (id) => {
    return leadershipTeam?.find(emp => emp.id === id) || { name: 'Unknown', id }
  }

  // Format name to show first name + last initial
  const formatName = (fullName) => {
    if (!fullName) return 'Unknown'
    const parts = fullName.trim().split(' ')
    if (parts.length === 1) return parts[0]
    const firstName = parts[0]
    const lastInitial = parts[parts.length - 1][0].toUpperCase()
    return `${firstName} ${lastInitial}.`
  }

  // Calculate boardroom mood based on recent chat messages
  const calculateMood = () => {
    if (!boardroomChats || boardroomChats.length === 0) {
      return { mood: 'Neutral', color: 'gray', emoji: '😐', description: 'No recent discussions' }
    }

    // Get recent messages (last 20)
    const recentMessages = boardroomChats.slice(-20).map(chat => chat.message.toLowerCase())
    const allText = recentMessages.join(' ')

    // Positive indicators
    const positiveKeywords = [
      'great', 'excellent', 'good', 'success', 'win', 'achievement', 'progress', 'growth',
      'opportunity', 'excited', 'optimistic', 'confident', 'strong', 'improve', 'better',
      'positive', 'thrilled', 'amazing', 'wonderful', 'fantastic', 'outstanding', 'perfect',
      'agree', 'support', 'approve', 'yes', 'definitely', 'absolutely'
    ]

    // Negative indicators
    const negativeKeywords = [
      'concern', 'worried', 'problem', 'issue', 'risk', 'challenge', 'difficult', 'struggle',
      'fail', 'failure', 'decline', 'drop', 'loss', 'bad', 'poor', 'weak', 'critical',
      'urgent', 'emergency', 'disappointed', 'frustrated', 'concerned', 'uncertain', 'doubt',
      'disagree', 'against', 'no', 'cannot', 'unable', 'error', 'mistake'
    ]

    // Count keyword matches
    let positiveCount = 0
    let negativeCount = 0

    positiveKeywords.forEach(keyword => {
      const regex = new RegExp(`\\b${keyword}\\w*\\b`, 'gi')
      const matches = allText.match(regex)
      if (matches) positiveCount += matches.length
    })

    negativeKeywords.forEach(keyword => {
      const regex = new RegExp(`\\b${keyword}\\w*\\b`, 'gi')
      const matches = allText.match(regex)
      if (matches) negativeCount += matches.length
    })

    // Determine mood
    const score = positiveCount - negativeCount
    const totalKeywords = positiveCount + negativeCount

    if (totalKeywords === 0) {
      return { mood: 'Neutral', color: 'gray', emoji: '😐', description: 'Neutral discussion' }
    }

    if (score > 3) {
      return { mood: 'Very Positive', color: 'green', emoji: '😊', description: 'Highly optimistic atmosphere' }
    } else if (score > 1) {
      return { mood: 'Positive', color: 'green', emoji: '🙂', description: 'Optimistic discussion' }
    } else if (score > -1) {
      return { mood: 'Neutral', color: 'gray', emoji: '😐', description: 'Balanced discussion' }
    } else if (score > -3) {
      return { mood: 'Concerned', color: 'yellow', emoji: '😟', description: 'Some concerns raised' }
    } else {
      return { mood: 'Tense', color: 'red', emoji: '😰', description: 'Serious concerns discussed' }
    }
  }

  const boardroomMood = calculateMood()

  if (!leadershipTeam || leadershipTeam.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">No executives available for the boardroom meeting.</p>
      </div>
    )
  }

  if (visibleExecutives.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Selecting executives for the boardroom meeting...</p>
      </div>
    )
  }

  // Generate positions for executives around a boardroom table
  // This function creates positions in a circle around the table
  const generatePositions = (team) => {
    if (team.length === 0) return []
    
    const positions = []
    const centerX = 50 // 50% from left
    const centerY = 50 // 50% from top
    const radius = 35 // Distance from center
    
    // Always put CEO at top center if available
    const ceoIndex = team.findIndex(emp => emp.role === 'CEO')
    const nonCeoCount = ceoIndex >= 0 ? team.length - 1 : team.length
    
    // Calculate angle step for even distribution (excluding CEO position)
    const angleStep = nonCeoCount > 0 ? (2 * Math.PI) / nonCeoCount : 0
    let currentAngle = -Math.PI / 2 + (angleStep / 2) // Start slightly offset from top
    
    for (let i = 0; i < team.length; i++) {
      // Handle CEO separately
      if (i === ceoIndex) {
        positions.push({ top: '10%', left: '50%', transform: 'translateX(-50%)', index: i })
        continue
      }
      
      // Calculate position on circle
      const x = centerX + radius * Math.cos(currentAngle)
      const y = centerY + radius * Math.sin(currentAngle)
      
      // Adjust for better visual distribution
      let top, left, right, transform
      if (y < 20) {
        // Top area
        top = `${Math.max(5, y - 5)}%`
        left = `${x}%`
        transform = 'translateX(-50%)'
      } else if (y > 80) {
        // Bottom area
        top = `${Math.min(95, y + 5)}%`
        left = `${x}%`
        transform = 'translateX(-50%)'
      } else if (x < 30) {
        // Left side
        top = `${y}%`
        left = `${Math.max(5, x - 5)}%`
        transform = ''
      } else if (x > 70) {
        // Right side
        top = `${y}%`
        right = `${Math.max(5, 100 - x - 5)}%`
        transform = ''
      } else {
        // Middle areas
        top = `${y}%`
        left = `${x}%`
        transform = 'translateX(-50%)'
      }
      
      positions.push({ top, left, right, transform, index: i })
      currentAngle += angleStep
    }
    
    return positions
  }
  
  const positions = generatePositions(visibleExecutives)

  return (
    <div className="space-y-6">
      {/* Boardroom Scene */}
      <div className="bg-gradient-to-br from-amber-50 to-amber-100 rounded-lg shadow-lg p-8 relative overflow-hidden min-h-[600px]">
        {/* Boardroom table */}
        <div className="absolute inset-x-8 top-1/2 transform -translate-y-1/2 h-48 bg-gradient-to-b from-amber-700 to-amber-800 rounded-lg shadow-2xl border-4 border-amber-900"></div>
        
        {/* Executives positioned around the table */}
        {visibleExecutives.map((executive, index) => {
          // Find position for this executive (by index)
          const position = positions.find(p => p.index === index) || positions[0] || { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }
          const bubble = chatBubbles[executive.id]
          
          return (
            <div
              key={executive.id}
              className="absolute"
              style={{
                top: position.top,
                left: position.left,
                right: position.right,
                transform: position.transform
              }}
            >
              {/* Chat bubble */}
              {bubble && (
                <div 
                  className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-64 bg-white rounded-lg shadow-xl p-3 border-2 border-blue-300 z-10 animate-fade-in"
                >
                  <div className="text-xs font-semibold text-gray-700 mb-1">
                    {formatName(executive.name)}
                  </div>
                  <div className="text-sm text-gray-900">
                    {bubble.message}
                  </div>
                  <div className="absolute -bottom-2 left-1/2 transform -translate-x-1/2 w-4 h-4 bg-white border-r-2 border-b-2 border-blue-300 rotate-45"></div>
                </div>
              )}
              
              {/* Executive avatar */}
              <div className="relative">
                <img
                  src={getAvatarPath(executive)}
                  alt={executive.name}
                  className="w-20 h-20 rounded-full object-cover border-4 border-white shadow-lg"
                  onError={(e) => {
                    e.target.src = '/avatars/office_char_08_exec.png'
                  }}
                />
                <div className="absolute -bottom-2 left-1/2 transform -translate-x-1/2 bg-white px-2 py-1 rounded shadow text-xs font-semibold text-gray-800 whitespace-nowrap">
                  {formatName(executive.name)}
                </div>
              </div>
            </div>
          )
        })}
        
        {/* Boardroom label */}
        <div className="absolute top-4 left-4 bg-white/90 px-4 py-2 rounded-lg shadow">
          <h3 className="text-lg font-bold text-gray-900">Executive Boardroom</h3>
        </div>

        {/* Countdown timer */}
        <div className="absolute bottom-4 left-4 bg-white/90 px-4 py-3 rounded-lg shadow border-2 border-blue-400">
          <div className="text-xs font-semibold text-gray-600 mb-1">Next Rotation In:</div>
          <div className="text-2xl font-bold text-blue-600">
            {Math.floor(timeUntilRotation / 60)}:{(timeUntilRotation % 60).toString().padStart(2, '0')}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {Math.floor(timeUntilRotation / 60)} minute{Math.floor(timeUntilRotation / 60) !== 1 ? 's' : ''} remaining
          </div>
        </div>

        {/* Mood indicator */}
        <div className={`absolute top-4 right-4 bg-white/90 px-4 py-3 rounded-lg shadow border-2 ${
          boardroomMood.color === 'green' ? 'border-green-400' :
          boardroomMood.color === 'yellow' ? 'border-yellow-400' :
          boardroomMood.color === 'red' ? 'border-red-400' :
          'border-gray-400'
        }`}>
          <div className="flex items-center space-x-2">
            <span className="text-2xl">{boardroomMood.emoji}</span>
            <div>
              <div className="text-sm font-semibold text-gray-900">Mood: {boardroomMood.mood}</div>
              <div className={`text-xs ${
                boardroomMood.color === 'green' ? 'text-green-600' :
                boardroomMood.color === 'yellow' ? 'text-yellow-600' :
                boardroomMood.color === 'red' ? 'text-red-600' :
                'text-gray-600'
              }`}>{boardroomMood.description}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Chat Log */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Boardroom Discussion Log</h3>
          <p className="text-sm text-gray-500 mt-1">
            Conversations between executives currently in the room ({visibleExecutives.map(e => formatName(e.name)).join(', ')})
          </p>
        </div>
        <div className="px-6 py-4 max-h-[600px] overflow-y-auto">
          {boardroomChats.length === 0 ? (
            <p className="text-gray-500 text-center py-8">No boardroom discussions yet</p>
          ) : (
            <div className="space-y-4">
              {boardroomChats.map((chat) => {
                const sender = getEmployee(chat.sender_id)
                const recipient = getEmployee(chat.recipient_id)
                
                return (
                  <div key={chat.id} className="border-l-4 border-blue-500 pl-4 py-3 bg-gray-50 rounded-r-lg">
                    <div className="flex items-start space-x-3 mb-2">
                      <img
                        src={getAvatarPath(sender)}
                        alt={sender.name}
                        className="w-8 h-8 rounded-full object-cover"
                        onError={(e) => {
                          e.target.src = '/avatars/office_char_08_exec.png'
                        }}
                      />
                      <div className="flex-1">
                        <div className="flex items-center space-x-2 mb-1">
                          <span className="text-sm font-semibold text-gray-900">{formatName(sender.name)}</span>
                          <span className="text-xs text-gray-500">→</span>
                          <span className="text-sm text-gray-700">{formatName(recipient.name)}</span>
                        </div>
                        <div className="text-sm text-gray-700 mb-2">{chat.message}</div>
                        <div className="text-xs text-gray-400">
                          {formatTimestamp(chat.timestamp)}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default BoardroomView

