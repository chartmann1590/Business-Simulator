import { useState, useEffect } from 'react'
import ChatView from '../components/ChatView'
import EmailView from '../components/EmailView'
import CalendarView from '../components/CalendarView'
import SharedDriveView from '../components/SharedDriveView'
import { apiGet } from '../utils/api'

function Communications() {
  // Check for tab in URL params or default to 'teams'
  const urlParams = new URLSearchParams(window.location.search)
  const initialTab = urlParams.get('tab') || 'teams'
  const [activeTab, setActiveTab] = useState(initialTab)
  const [emails, setEmails] = useState([])
  const [chats, setChats] = useState([])
  const [employees, setEmployees] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  // Update URL when tab changes
  useEffect(() => {
    const url = new URL(window.location)
    if (activeTab === 'teams') {
      url.searchParams.delete('tab')
    } else {
      url.searchParams.set('tab', activeTab)
    }
    window.history.replaceState({}, '', url)
  }, [activeTab])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [emailsResult, chatsResult, employeesResult] = await Promise.all([
        apiGet('/api/emails?limit=100'),
        apiGet('/api/chats?limit=200'),
        apiGet('/api/employees')
      ])
      
      // ALWAYS set data - use whatever we got (fresh or cached)
      setEmails(Array.isArray(emailsResult.data) ? emailsResult.data : [])
      setChats(Array.isArray(chatsResult.data) ? chatsResult.data : [])
      setEmployees(Array.isArray(employeesResult.data) ? employeesResult.data : [])
    } catch (error) {
      console.error('Error fetching communications:', error)
      // Even on error, data might be in cache, so components will show it
      setEmails([])
      setChats([])
      setEmployees([])
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-500">Loading communications...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col">
      <div className="px-6 py-4 border-b border-gray-200 bg-white">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Communications</h2>
        
        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('teams')}
              className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'teams'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Teams
            </button>
            <button
              onClick={() => setActiveTab('outlook')}
              className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'outlook'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Outlook
            </button>
            <button
              onClick={() => setActiveTab('calendar')}
              className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'calendar'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Calendar
            </button>
            <button
              onClick={() => setActiveTab('share-drive')}
              className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'share-drive'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Share Drive
            </button>
          </nav>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden px-6 py-4">
        {activeTab === 'teams' ? (
          <ChatView chats={chats} employees={employees} onRefresh={fetchData} />
        ) : activeTab === 'outlook' ? (
          <EmailView emails={emails} employees={employees} />
        ) : activeTab === 'calendar' ? (
          <CalendarView employees={employees} />
        ) : (
          <SharedDriveView />
        )}
      </div>
    </div>
  )
}

export default Communications

