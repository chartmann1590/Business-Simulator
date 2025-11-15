import { useState, useEffect } from 'react'
import ChatView from '../components/ChatView'
import EmailView from '../components/EmailView'
import CalendarView from '../components/CalendarView'

function Communications() {
  const [activeTab, setActiveTab] = useState('teams')
  const [emails, setEmails] = useState([])
  const [chats, setChats] = useState([])
  const [employees, setEmployees] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchData = async () => {
    try {
      const [emailsRes, chatsRes, employeesRes] = await Promise.all([
        fetch('/api/emails?limit=100'),
        fetch('/api/chats?limit=200'),
        fetch('/api/employees')
      ])
      
      const emailsData = emailsRes.ok ? await emailsRes.json() : []
      const chatsData = chatsRes.ok ? await chatsRes.json() : []
      const employeesData = employeesRes.ok ? await employeesRes.json() : []
      
      setEmails(emailsData || [])
      setChats(chatsData || [])
      setEmployees(employeesData || [])
      setLoading(false)
    } catch (error) {
      console.error('Error fetching communications:', error)
      setEmails([])
      setChats([])
      setEmployees([])
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="text-center py-12">Loading communications...</div>
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
          </nav>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden px-6 py-4">
        {activeTab === 'teams' ? (
          <ChatView chats={chats} employees={employees} />
        ) : activeTab === 'outlook' ? (
          <EmailView emails={emails} employees={employees} />
        ) : (
          <CalendarView employees={employees} />
        )}
      </div>
    </div>
  )
}

export default Communications

