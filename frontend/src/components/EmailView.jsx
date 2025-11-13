import { useState } from 'react'
import { getAvatarPath } from '../utils/avatarMapper'

function EmailView({ emails, employees }) {
  const [selectedEmail, setSelectedEmail] = useState(null)
  const [filter, setFilter] = useState('all') // all, unread

  const getEmployee = (id) => {
    return employees.find(emp => emp.id === id) || { name: 'Unknown', id: id }
  }

  const filteredEmails = filter === 'unread' 
    ? emails.filter(e => !e.read)
    : emails

  const formatDate = (timestamp) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now - date
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    
    if (days === 0) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } else if (days === 1) {
      return 'Yesterday'
    } else if (days < 7) {
      return date.toLocaleDateString([], { weekday: 'short' })
    } else {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
    }
  }

  return (
    <div className="flex h-full bg-white rounded-lg overflow-hidden">
      {/* Outlook-style Email List */}
      <div className="w-96 border-r border-gray-200 flex flex-col bg-white">
        {/* Toolbar */}
        <div className="p-3 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-lg font-semibold text-gray-900">Inbox</h3>
            <span className="text-xs text-gray-500">{filteredEmails.length} {filteredEmails.length === 1 ? 'item' : 'items'}</span>
          </div>
          <div className="flex space-x-1">
            <button
              onClick={() => setFilter('all')}
              className={`px-3 py-1 text-xs rounded-md transition-colors ${
                filter === 'all' 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setFilter('unread')}
              className={`px-3 py-1 text-xs rounded-md transition-colors ${
                filter === 'unread' 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              Unread
            </button>
          </div>
        </div>
        
        {/* Email List */}
        <div className="flex-1 overflow-y-auto">
          {filteredEmails.length === 0 ? (
            <div className="p-8 text-center text-gray-400">
              <p className="text-sm">No emails found</p>
            </div>
          ) : (
            filteredEmails.map(email => {
              const sender = getEmployee(email.sender_id)
              const isUnread = !email.read
              const isSelected = selectedEmail?.id === email.id
              
              return (
                <div
                  key={email.id}
                  onClick={() => setSelectedEmail(email)}
                  className={`px-4 py-3 border-b border-gray-100 cursor-pointer transition-colors ${
                    isSelected 
                      ? 'bg-blue-50 border-l-4 border-l-blue-500' 
                      : isUnread 
                        ? 'bg-gray-50 hover:bg-gray-100' 
                        : 'hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-start space-x-3">
                    <div className="flex-shrink-0 mt-1">
                      {isUnread ? (
                        <div className="w-2 h-2 bg-blue-600 rounded-full"></div>
                      ) : (
                        <div className="w-2 h-2"></div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <p className={`text-sm truncate ${
                          isUnread ? 'font-semibold text-gray-900' : 'text-gray-700'
                        }`}>
                          {sender.name}
                        </p>
                        <span className="text-xs text-gray-500 flex-shrink-0 ml-2">
                          {formatDate(email.timestamp)}
                        </span>
                      </div>
                      <p className={`text-sm truncate mb-1 ${
                        isUnread ? 'font-semibold text-gray-900' : 'text-gray-600'
                      }`}>
                        {email.subject}
                      </p>
                      <p className="text-xs text-gray-500 line-clamp-2">
                        {email.body.substring(0, 80)}...
                      </p>
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* Outlook-style Reading Pane */}
      <div className="flex-1 flex flex-col bg-white">
        {selectedEmail ? (
          <>
            {/* Email Header */}
            <div className="p-6 border-b border-gray-200 bg-white">
              <div className="mb-4">
                <h2 className="text-2xl font-semibold text-gray-900 mb-2">
                  {selectedEmail.subject}
                </h2>
                <div className="flex items-center space-x-2 text-sm text-gray-500">
                  <span>{formatDate(selectedEmail.timestamp)}</span>
                  <span>•</span>
                  <span>{new Date(selectedEmail.timestamp).toLocaleDateString()}</span>
                </div>
              </div>
              
              <div className="flex items-start space-x-3 pt-4 border-t border-gray-200">
                <img
                  src={getAvatarPath(getEmployee(selectedEmail.sender_id))}
                  alt={getEmployee(selectedEmail.sender_id).name}
                  className="w-10 h-10 rounded-full object-cover flex-shrink-0"
                  onError={(e) => {
                    e.target.src = '/avatars/office_char_01_manager.png'
                  }}
                />
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <div>
                      <p className="text-sm font-semibold text-gray-900">
                        {getEmployee(selectedEmail.sender_id).name}
                      </p>
                      <p className="text-xs text-gray-500">
                        {getEmployee(selectedEmail.sender_id).title}
                      </p>
                    </div>
                  </div>
                  <div className="text-xs text-gray-600 mt-2">
                    <p><span className="font-medium">From:</span> {getEmployee(selectedEmail.sender_id).name}</p>
                    <p><span className="font-medium">To:</span> {getEmployee(selectedEmail.recipient_id).name}</p>
                    <p><span className="font-medium">Date:</span> {new Date(selectedEmail.timestamp).toLocaleString()}</p>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Email Body */}
            <div className="flex-1 overflow-y-auto p-6 bg-gray-50">
              <div className="bg-white rounded-lg shadow-sm p-6 max-w-4xl">
                <div className="prose max-w-none">
                  <p className="text-gray-700 whitespace-pre-wrap leading-relaxed text-sm">
                    {selectedEmail.body}
                  </p>
                </div>
              </div>
            </div>
            
            {/* Action Bar */}
            <div className="px-6 py-4 border-t border-gray-200 bg-white">
              <div className="flex items-center space-x-2">
                <button className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors">
                  Reply
                </button>
                <button className="px-4 py-2 bg-gray-100 text-gray-700 text-sm rounded-md hover:bg-gray-200 transition-colors">
                  Reply All
                </button>
                <button className="px-4 py-2 bg-gray-100 text-gray-700 text-sm rounded-md hover:bg-gray-200 transition-colors">
                  Forward
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center bg-gray-50">
            <div className="text-center">
              <svg className="w-20 h-20 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              <p className="text-sm text-gray-400">Select an email to read</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default EmailView

