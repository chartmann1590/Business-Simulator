import { useState, useEffect } from 'react'
import { getAvatarPath } from '../utils/avatarMapper'
import { formatDateShortTime, formatDateTime } from '../utils/timezone'

function ChatView({ chats, employees, onRefresh }) {
  const [selectedChat, setSelectedChat] = useState(null)
  const [groupedChats, setGroupedChats] = useState({})
  const [newMessage, setNewMessage] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    // Group chats by thread_id to ensure all messages between two employees stay in the same thread
    const grouped = {}
    
    // First pass: group all messages by thread_id (or fallback to sender/recipient pair)
    chats.forEach(chat => {
      // Use thread_id if available, otherwise generate consistent key from sender/recipient pair
      const key = chat.thread_id || [chat.sender_id, chat.recipient_id].sort().join('-')
      if (!grouped[key]) {
        grouped[key] = {
          participants: new Set(),
          messages: []
        }
      }
      grouped[key].participants.add(chat.sender_id)
      grouped[key].participants.add(chat.recipient_id)
      grouped[key].messages.push(chat)
    })
    
    // Convert participants Sets to Arrays and filter out null/undefined
    Object.keys(grouped).forEach(key => {
      grouped[key].participants = Array.from(grouped[key].participants)
        .filter(id => id !== null && id !== undefined)
    })
    
    // Sort messages within each conversation - newest first
    Object.keys(grouped).forEach(key => {
      grouped[key].messages.sort((a, b) => 
        new Date(b.timestamp) - new Date(a.timestamp)
      )
    })
    
    // Sort conversations by most recent message - newest first
    const sortedKeys = Object.keys(grouped).sort((keyA, keyB) => {
      const lastMsgA = grouped[keyA].messages[0] // First message is newest after sort
      const lastMsgB = grouped[keyB].messages[0]
      return new Date(lastMsgB.timestamp) - new Date(lastMsgA.timestamp)
    })
    
    // Create sorted grouped object
    const sortedGrouped = {}
    sortedKeys.forEach(key => {
      sortedGrouped[key] = grouped[key]
    })
    
    setGroupedChats(sortedGrouped)
    
    // Select first conversation by default (most recent)
    const firstKey = sortedKeys[0]
    if (firstKey && !selectedChat) {
      setSelectedChat(firstKey)
    }
  }, [chats])

  const getEmployee = (id) => {
    return employees.find(emp => emp.id === id) || { name: 'Unknown', id: id }
  }

  const currentConversation = selectedChat ? groupedChats[selectedChat] : null

  // Get the employee ID to send to (the one that's not null - manager has sender_id = null)
  const getRecipientEmployeeId = () => {
    if (!currentConversation || !currentConversation.messages || currentConversation.messages.length === 0) {
      // If no messages, try to get from participants
      const validParticipants = currentConversation?.participants?.filter(id => id !== null && id !== undefined) || []
      return validParticipants.length > 0 ? validParticipants[0] : null
    }
    
    // Find the employee ID from existing messages
    // Look for messages where sender_id is null (from manager) - recipient_id is the employee
    // Or messages where recipient_id is null (to manager) - sender_id is the employee
    for (const msg of currentConversation.messages) {
      if (msg.sender_id === null && msg.recipient_id !== null) {
        return msg.recipient_id
      }
      if (msg.recipient_id === null && msg.sender_id !== null) {
        return msg.sender_id
      }
    }
    
    // Fallback: get first valid participant
    const validParticipants = currentConversation.participants.filter(id => id !== null && id !== undefined)
    return validParticipants.length > 0 ? validParticipants[0] : null
  }

  const handleSendMessage = async (e) => {
    e.preventDefault()
    if (!newMessage.trim() || sending) return

    const employeeId = getRecipientEmployeeId()
    if (!employeeId) {
      alert('Cannot determine recipient. Please select a conversation.')
      return
    }

    setSending(true)
    try {
      const response = await fetch('/api/chats/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          employee_id: employeeId,
          message: newMessage.trim()
        })
      })

      if (response.ok) {
        setNewMessage('')
        // Refresh messages
        if (onRefresh) {
          await onRefresh()
        }
      } else {
        const error = await response.json()
        alert(`Error sending message: ${error.detail || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('Error sending message:', error)
      alert('Error sending message. Please try again.')
    } finally {
      setSending(false)
    }
  }

  // Format time to show actual date and time (never "just now")
  const formatTime = (timestamp) => {
    if (!timestamp) return formatDateTime(new Date())
    
    const date = new Date(timestamp)
    if (isNaN(date.getTime())) {
      return formatDateTime(new Date())
    }
    
    // Always show full date and time
    const now = new Date()
    const dateYear = new Date(timestamp).getFullYear()
    const currentYear = now.getFullYear()
    
    // Include year if different from current year
    if (dateYear !== currentYear) {
      return formatDateTime(timestamp)
    }
    
    return formatDateShortTime(timestamp)
  }

  return (
    <div className="flex h-full bg-gray-50 rounded-lg overflow-hidden">
      {/* Teams-style Sidebar */}
      <div className="w-72 bg-white border-r border-gray-200 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-200 bg-gray-50">
          <h3 className="text-lg font-semibold text-gray-900">Chat</h3>
        </div>
        
        {/* Search bar */}
        <div className="p-3 border-b border-gray-200">
          <input
            type="text"
            placeholder="Search"
            className="w-full px-3 py-2 bg-gray-100 border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        
        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto">
          {Object.keys(groupedChats).map(key => {
            const conv = groupedChats[key]
            // Filter out null/undefined and sort participants by ID to ensure consistent ordering
            const validParticipants = conv.participants.filter(id => id !== null && id !== undefined)
            const sortedParticipants = [...validParticipants].sort((a, b) => (a || 0) - (b || 0))
            // Show the second participant (or first if only one) in the sidebar
            const otherId = sortedParticipants[1] || sortedParticipants[0]
            const other = getEmployee(otherId)
            // Messages are sorted newest first, so first message is most recent
            const lastMessage = conv.messages[0]
            
            return (
              <div
                key={key}
                onClick={() => setSelectedChat(key)}
                className={`px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors ${
                  selectedChat === key ? 'bg-blue-50 border-l-4 border-l-blue-500' : ''
                }`}
              >
                <div className="flex items-center space-x-3">
                  <div className="relative">
                    <img
                      src={getAvatarPath(other)}
                      alt={other.name}
                      className="w-12 h-12 rounded-full object-cover"
                      onError={(e) => {
                        e.target.src = '/avatars/office_char_01_manager.png'
                      }}
                    />
                    <div className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 border-2 border-white rounded-full"></div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium truncate ${
                      selectedChat === key ? 'text-blue-600' : 'text-gray-900'
                    }`}>
                      {other.name}
                    </p>
                    {lastMessage && (
                      <p className="text-xs text-gray-500 truncate mt-0.5">
                        {lastMessage.message.substring(0, 35)}...
                      </p>
                    )}
                    {lastMessage && (
                      <p className="text-xs text-gray-400 mt-0.5">
                        {formatTime(lastMessage.timestamp)}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Teams-style Chat Area */}
      <div className="flex-1 flex flex-col bg-white">
        {currentConversation ? (
          <>
            {/* Chat Header */}
            <div className="px-6 py-4 border-b border-gray-200 bg-white">
              <div className="flex items-center space-x-3">
                {currentConversation.participants.map(id => {
                  const emp = getEmployee(id)
                  return (
                    <div key={id} className="flex items-center space-x-2">
                      <img
                        src={getAvatarPath(emp)}
                        alt={emp.name}
                        className="w-10 h-10 rounded-full object-cover"
                        onError={(e) => {
                          e.target.src = '/avatars/office_char_01_manager.png'
                        }}
                      />
                      <div>
                        <span className="text-sm font-semibold text-gray-900">{emp.name}</span>
                        <span className="text-xs text-gray-500 ml-2">Active now</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
            
            {/* Messages Area - oldest messages at top, newest at bottom */}
            <div className="flex-1 overflow-y-auto p-6 bg-gray-50">
              <div className="space-y-4">
                {/* Reverse messages for display: show oldest first, newest last (standard chat UI) */}
                {[...currentConversation.messages].reverse().map((chat, index) => {
                  const sender = getEmployee(chat.sender_id)
                  // Since we reversed the array, check previous message (index - 1) for grouping
                  const reversedMessages = [...currentConversation.messages].reverse()
                  const prevChat = index > 0 ? reversedMessages[index - 1] : null
                  const showAvatar = !prevChat || prevChat.sender_id !== chat.sender_id
                  
                  // Determine message alignment based on sender
                  // Sort participants by ID to ensure consistent ordering (filter nulls first)
                  const validParticipants = currentConversation.participants.filter(id => id !== null && id !== undefined)
                  const sortedParticipants = [...validParticipants].sort((a, b) => (a || 0) - (b || 0))
                  
                  // For display: messages from the first participant (smaller ID) go on right (blue)
                  // Messages from the second participant go on left (white)
                  // This ensures consistent visual distinction between the two participants
                  const firstParticipantId = sortedParticipants[0]
                  const isMe = chat.sender_id === firstParticipantId
                  
                  return (
                    <div
                      key={chat.id}
                      className={`flex ${isMe ? 'justify-end' : 'justify-start'} ${showAvatar ? 'mt-4' : 'mt-1'}`}
                    >
                      <div className={`flex space-x-2 max-w-2xl ${isMe ? 'flex-row-reverse space-x-reverse' : ''}`}>
                        {showAvatar && (
                          <img
                            src={getAvatarPath(sender)}
                            alt={sender.name}
                            className="w-8 h-8 rounded-full object-cover flex-shrink-0"
                            onError={(e) => {
                              e.target.src = '/avatars/office_char_01_manager.png'
                            }}
                          />
                        )}
                        {!showAvatar && <div className="w-8"></div>}
                        <div className="flex flex-col">
                          {showAvatar && (
                            <div className={`flex items-center space-x-2 mb-1 ${isMe ? 'flex-row-reverse space-x-reverse' : ''}`}>
                              <span className="text-xs font-semibold text-gray-700">{sender.name}</span>
                              <span className="text-xs text-gray-400">{formatTime(chat.timestamp)}</span>
                            </div>
                          )}
                          <div className={`rounded-2xl px-4 py-2 shadow-sm ${
                            isMe 
                              ? 'bg-blue-500 text-white rounded-tr-none' 
                              : 'bg-white text-gray-900 rounded-tl-none border border-gray-200'
                          }`}>
                            <p className="text-sm leading-relaxed">{chat.message}</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
            
            {/* Input Area (Teams-style) */}
            <div className="px-6 py-4 border-t border-gray-200 bg-white">
              <form onSubmit={handleSendMessage} className="flex items-center space-x-2">
                <input
                  type="text"
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  placeholder="Type a new message"
                  className="flex-1 px-4 py-2 bg-gray-100 border border-gray-200 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  disabled={sending}
                />
                <button
                  type="submit"
                  disabled={!newMessage.trim() || sending}
                  className="p-2 text-blue-600 hover:bg-blue-50 rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {sending ? (
                    <svg className="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                  )}
                </button>
              </form>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400">
            <div className="text-center">
              <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              <p className="text-sm">Select a conversation to start chatting</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default ChatView

