import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getAvatarPath } from '../utils/avatarMapper'

function EmployeeDetail() {
  const { id } = useParams()
  const [employee, setEmployee] = useState(null)
  const [emails, setEmails] = useState([])
  const [chats, setChats] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchEmployee()
    const interval = setInterval(fetchEmployee, 10000)
    return () => clearInterval(interval)
  }, [id])

  const fetchEmployee = async () => {
    try {
      const [employeeRes, emailsRes, chatsRes] = await Promise.all([
        fetch(`/api/employees/${id}`),
        fetch(`/api/employees/${id}/emails`),
        fetch(`/api/employees/${id}/chats`)
      ])
      const employeeData = await employeeRes.json()
      const emailsData = await emailsRes.json()
      const chatsData = await chatsRes.json()
      setEmployee(employeeData)
      setEmails(emailsData)
      setChats(chatsData)
      setLoading(false)
    } catch (error) {
      console.error('Error fetching employee:', error)
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="text-center py-12">Loading employee details...</div>
  }

  if (!employee) {
    return <div className="text-center py-12">Employee not found</div>
  }

  return (
    <div className="px-4 py-6">
      <Link to="/employees" className="text-blue-600 hover:text-blue-800 mb-4 inline-block">
        ← Back to Employees
      </Link>
      
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-start space-x-4">
            <img
              src={getAvatarPath(employee)}
              alt={employee.name}
              className="w-24 h-24 rounded-full object-cover flex-shrink-0"
              onError={(e) => {
                e.target.src = '/avatars/office_char_01_manager.png'
              }}
            />
            <div>
              <h2 className="text-3xl font-bold text-gray-900">{employee.name}</h2>
              <p className="text-xl text-gray-600 mt-2">{employee.title}</p>
              <p className="text-sm text-gray-500 mt-1">{employee.department}</p>
              {employee.hired_at && (
                <p className="text-xs text-gray-400 mt-1">
                  Hired: {new Date(employee.hired_at).toLocaleDateString()}
                </p>
              )}
              {employee.fired_at && (
                <p className="text-xs text-red-600 mt-1">
                  Terminated: {new Date(employee.fired_at).toLocaleDateString()}
                </p>
              )}
            </div>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${
            employee.role === 'CEO' ? 'bg-purple-100 text-purple-800' :
            employee.role === 'Manager' ? 'bg-blue-100 text-blue-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {employee.role}
          </span>
        </div>

        {employee.backstory && (
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Backstory</h3>
            <p className="text-gray-700 leading-relaxed">{employee.backstory}</p>
          </div>
        )}

        {employee.personality_traits && employee.personality_traits.length > 0 && (
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Personality Traits</h3>
            <div className="flex flex-wrap gap-2">
              {employee.personality_traits.map((trait, idx) => (
                <span key={idx} className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm">
                  {trait}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <span className="text-sm text-gray-500">Status</span>
            <p className="text-lg font-medium text-gray-900">{employee.status}</p>
          </div>
          <div>
            <span className="text-sm text-gray-500">Hierarchy Level</span>
            <p className="text-lg font-medium text-gray-900">{employee.hierarchy_level}</p>
          </div>
        </div>
      </div>

      {/* Recent Decisions */}
      {employee.decisions && employee.decisions.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="text-xl font-semibold text-gray-900 mb-4">Recent Decisions</h3>
          <div className="space-y-4">
            {employee.decisions.map((decision) => (
              <div key={decision.id} className="border-l-4 border-purple-500 pl-4">
                <div className="flex items-center justify-between mb-2">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    decision.decision_type === 'strategic' ? 'bg-purple-100 text-purple-800' :
                    decision.decision_type === 'tactical' ? 'bg-blue-100 text-blue-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {decision.decision_type}
                  </span>
                  <span className="text-xs text-gray-500">
                    {new Date(decision.timestamp).toLocaleString()}
                  </span>
                </div>
                <p className="text-gray-900 font-medium mb-1">{decision.description}</p>
                {decision.reasoning && (
                  <p className="text-sm text-gray-600">{decision.reasoning}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Activities */}
      {employee.activities && employee.activities.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="text-xl font-semibold text-gray-900 mb-4">Recent Activities</h3>
          <div className="space-y-3">
            {employee.activities.map((activity) => (
              <div key={activity.id} className="border-l-4 border-blue-500 pl-4 py-2">
                <p className="text-gray-900">{activity.description}</p>
                <p className="text-xs text-gray-500 mt-1">
                  {new Date(activity.timestamp).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Communications */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Emails */}
        {emails.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-xl font-semibold text-gray-900 mb-4">Recent Emails</h3>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {emails.slice(0, 10).map((email) => (
                <div key={email.id} className="border-l-4 border-green-500 pl-4 py-2">
                  <p className="text-sm font-medium text-gray-900">{email.subject}</p>
                  <p className="text-xs text-gray-600 mt-1">
                    {email.sender_id === parseInt(id) ? `To: ${email.recipient_name}` : `From: ${email.sender_name}`}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {new Date(email.timestamp).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Chats */}
        {chats.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-xl font-semibold text-gray-900 mb-4">Recent Chats</h3>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {chats.slice(0, 10).map((chat) => (
                <div key={chat.id} className="border-l-4 border-purple-500 pl-4 py-2">
                  <p className="text-sm text-gray-900">{chat.message}</p>
                  <p className="text-xs text-gray-600 mt-1">
                    {chat.sender_id === parseInt(id) ? `To: ${chat.recipient_name}` : `From: ${chat.sender_name}`}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {new Date(chat.timestamp).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default EmployeeDetail

