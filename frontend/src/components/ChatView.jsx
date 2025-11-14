import { useState, useEffect } from 'react'
import { getAvatarPath } from '../utils/avatarMapper'

function ChatView({ chats, employees }) {
  const [selectedChat, setSelectedChat] = useState(null)
  const [groupedChats, setGroupedChats] = useState({})

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
    
    // Convert participants Sets to Arrays
    Object.keys(grouped).forEach(key => {
      grouped[key].participants = Array.from(grouped[key].participants)
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

  // Format time to show actual date and time (never "just now")
  const formatTime = (timestamp) => {
    const date = new Date(timestamp)
    
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return new Date().toLocaleString()
    }
    
    // Always show full date and time
    const now = new Date()
    const options = {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }
    
    // Include year if different from current year
    if (date.getFullYear() !== now.getFullYear()) {
      options.year = 'numeric'
    }
    
    return date.toLocaleString([], options)
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
            const otherId = conv.participants.find(id => id !== conv.participants[0])
            const other = getEmployee(otherId || conv.participants[0])
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
            
            {/* Messages Area - newest messages at top */}
            <div className="flex-1 overflow-y-auto p-6 bg-gray-50">
              <div className="space-y-4">
                {currentConversation.messages.map((chat, index) => {
                  const sender = getEmployee(chat.sender_id)
                  // Since messages are sorted newest first, check next message (index + 1) for grouping
                  const nextChat = index < currentConversation.messages.length - 1 ? currentConversation.messages[index + 1] : null
                  const showAvatar = !nextChat || nextChat.sender_id !== chat.sender_id
                  const isMe = chat.sender_id === currentConversation.participants[0]
                  
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
              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  placeholder="Type a new message"
                  className="flex-1 px-4 py-2 bg-gray-100 border border-gray-200 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  disabled
                />
                <button className="p-2 text-blue-600 hover:bg-blue-50 rounded-full transition-colors">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                </button>
              </div>
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

