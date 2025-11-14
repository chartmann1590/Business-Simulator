import { useState, useEffect, useRef } from 'react'
import { getAvatarPath } from '../utils/avatarMapper'

function EmployeeChat({ employeeId, employee }) {
  const [messages, setMessages] = useState([])
  const [newMessage, setNewMessage] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    fetchMessages()
    const interval = setInterval(fetchMessages, 5000) // Refresh every 5 seconds
    return () => clearInterval(interval)
  }, [employeeId])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const fetchMessages = async () => {
    try {
      const response = await fetch(`/api/employees/${employeeId}/chats`)
      if (response.ok) {
        const data = await response.json()
        // Sort messages oldest first for display
        const sortedMessages = [...data].sort((a, b) => 
          new Date(a.timestamp) - new Date(b.timestamp)
        )
        setMessages(sortedMessages)
        setLoading(false)
      }
    } catch (error) {
      console.error('Error fetching messages:', error)
      setLoading(false)
    }
  }

  const handleSendMessage = async (e) => {
    e.preventDefault()
    if (!newMessage.trim() || sending) return

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
        await fetchMessages()
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

  const formatTime = (timestamp) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now - date
    
    if (diff < 60000) { // Less than 1 minute
      return 'Just now'
    } else if (diff < 3600000) { // Less than 1 hour
      const minutes = Math.floor(diff / 60000)
      return `${minutes}m ago`
    } else if (diff < 86400000) { // Less than 1 day
      const hours = Math.floor(diff / 3600000)
      return `${hours}h ago`
    } else {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    }
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <p className="text-gray-500 text-center">Loading chat...</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow flex flex-col" style={{ height: '600px' }}>
      {/* Chat Header */}
      <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center space-x-3">
          <img
            src={getAvatarPath(employee)}
            alt={employee.name}
            className="w-10 h-10 rounded-full object-cover"
            onError={(e) => {
              e.target.src = '/avatars/office_char_01_manager.png'
            }}
          />
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Chat with {employee.name}</h3>
            <p className="text-xs text-gray-500">Ask how they're doing and what they're working on</p>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 bg-gray-50">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-400">
            <div className="text-center">
              <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              <p className="text-sm">No messages yet. Start a conversation!</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message) => {
              const isYou = message.sender_id === null || message.sender_id === 0 || message.sender_name === 'You'
              const sender = isYou ? { name: 'You', id: 0 } : { name: message.sender_name, id: message.sender_id }
              
              return (
                <div
                  key={message.id}
                  className={`flex ${isYou ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`flex space-x-2 max-w-2xl ${isYou ? 'flex-row-reverse space-x-reverse' : ''}`}>
                    {!isYou && (
                      <img
                        src={getAvatarPath({ id: message.sender_id, name: message.sender_name })}
                        alt={sender.name}
                        className="w-8 h-8 rounded-full object-cover flex-shrink-0"
                        onError={(e) => {
                          e.target.src = '/avatars/office_char_01_manager.png'
                        }}
                      />
                    )}
                    <div className="flex flex-col">
                      <div className={`flex items-center space-x-2 mb-1 ${isYou ? 'flex-row-reverse space-x-reverse' : ''}`}>
                        <span className="text-xs font-semibold text-gray-700">{sender.name}</span>
                        <span className="text-xs text-gray-400">{formatTime(message.timestamp)}</span>
                      </div>
                      <div className={`rounded-2xl px-4 py-2 shadow-sm ${
                        isYou 
                          ? 'bg-blue-500 text-white rounded-tr-none' 
                          : 'bg-white text-gray-900 rounded-tl-none border border-gray-200'
                      }`}>
                        <p className="text-sm leading-relaxed">{message.message}</p>
                      </div>
                    </div>
                    {isYou && (
                      <div className="w-8"></div>
                    )}
                  </div>
                </div>
              )
            })}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="px-6 py-4 border-t border-gray-200 bg-white">
        <form onSubmit={handleSendMessage} className="flex items-center space-x-2">
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Type a message..."
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
    </div>
  )
}

export default EmployeeChat

