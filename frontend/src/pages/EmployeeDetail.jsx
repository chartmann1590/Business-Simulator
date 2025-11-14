import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getAvatarPath } from '../utils/avatarMapper'
import EmployeeChatModal from '../components/EmployeeChatModal'

function EmployeeDetail() {
  const { id } = useParams()
  const [employee, setEmployee] = useState(null)
  const [emails, setEmails] = useState([])
  const [chats, setChats] = useState([])
  const [reviews, setReviews] = useState([])
  const [loading, setLoading] = useState(true)
  const [showChatModal, setShowChatModal] = useState(false)
  const [timeUntilReview, setTimeUntilReview] = useState(null)

  useEffect(() => {
    fetchEmployee()
    const interval = setInterval(fetchEmployee, 10000)
    return () => clearInterval(interval)
  }, [id])

  // Update countdown timer every second
  useEffect(() => {
    if (!employee?.next_review?.scheduled_at) return

    const updateCountdown = () => {
      const scheduledTime = new Date(employee.next_review.scheduled_at)
      const now = new Date()
      const diff = scheduledTime - now

      if (diff <= 0) {
        setTimeUntilReview({ hours: 0, minutes: 0, seconds: 0, overdue: true })
        return
      }

      const hours = Math.floor(diff / (1000 * 60 * 60))
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
      const seconds = Math.floor((diff % (1000 * 60)) / 1000)

      setTimeUntilReview({ hours, minutes, seconds, overdue: false })
    }

    updateCountdown()
    const countdownInterval = setInterval(updateCountdown, 1000)
    return () => clearInterval(countdownInterval)
  }, [employee?.next_review?.scheduled_at])

  // Close chat modal when employee changes
  useEffect(() => {
    setShowChatModal(false)
  }, [id])

  const fetchEmployee = async () => {
    try {
      const [employeeRes, emailsRes, chatsRes, reviewsRes] = await Promise.all([
        fetch(`/api/employees/${id}`),
        fetch(`/api/employees/${id}/emails`),
        fetch(`/api/employees/${id}/chats`),
        fetch(`/api/employees/${id}/reviews`)
      ])
      const employeeData = await employeeRes.json()
      const emailsData = await emailsRes.json()
      const chatsData = await chatsRes.json()
      const reviewsData = await reviewsRes.json()
      setEmployee(employeeData)
      setEmails(emailsData)
      setChats(chatsData)
      setReviews(reviewsData || [])
      setLoading(false)
    } catch (error) {
      console.error('Error fetching employee:', error)
      // Set empty array for reviews if there's an error
      setReviews([])
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

      {/* Next Review Countdown */}
      {employee.next_review && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="text-xl font-semibold text-gray-900 mb-4">Next Performance Review</h3>
          {employee.next_review.eligible ? (
            <div className="space-y-4">
              {employee.next_review.manager_name && (
                <div className="flex items-center gap-3 mb-4">
                  <div className="flex-1">
                    <p className="text-sm text-gray-600 mb-1">Review will be conducted by:</p>
                    <p className="text-lg font-semibold text-gray-900">
                      {employee.next_review.manager_name}
                      {employee.next_review.manager_title && (
                        <span className="text-sm font-normal text-gray-600 ml-2">
                          ({employee.next_review.manager_title})
                        </span>
                      )}
                    </p>
                  </div>
                </div>
              )}
              
              {employee.next_review.scheduled_at && (
                <div className="border-t border-gray-200 pt-4">
                  <p className="text-sm text-gray-600 mb-3">Scheduled for:</p>
                  {timeUntilReview ? (
                    <div className="flex items-center gap-6">
                      {timeUntilReview.overdue ? (
                        <div className="flex items-center gap-2">
                          <span className="text-2xl font-bold text-red-600">Overdue</span>
                          <span className="text-sm text-gray-500">
                            (Was scheduled for {new Date(employee.next_review.scheduled_at).toLocaleString()})
                          </span>
                        </div>
                      ) : (
                        <>
                          <div className="text-center">
                            <div className="text-4xl font-bold text-blue-600">{String(timeUntilReview.hours).padStart(2, '0')}</div>
                            <div className="text-xs text-gray-500 mt-1">Hours</div>
                          </div>
                          <div className="text-2xl font-bold text-gray-400">:</div>
                          <div className="text-center">
                            <div className="text-4xl font-bold text-blue-600">{String(timeUntilReview.minutes).padStart(2, '0')}</div>
                            <div className="text-xs text-gray-500 mt-1">Minutes</div>
                          </div>
                          <div className="text-2xl font-bold text-gray-400">:</div>
                          <div className="text-center">
                            <div className="text-4xl font-bold text-blue-600">{String(timeUntilReview.seconds).padStart(2, '0')}</div>
                            <div className="text-xs text-gray-500 mt-1">Seconds</div>
                          </div>
                        </>
                      )}
                    </div>
                  ) : (
                    <p className="text-gray-600">Calculating...</p>
                  )}
                  <p className="text-xs text-gray-500 mt-3">
                    Scheduled date: {new Date(employee.next_review.scheduled_at).toLocaleString()}
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-4">
              <p className="text-gray-600">{employee.next_review.reason || "This employee is not eligible for performance reviews."}</p>
            </div>
          )}
        </div>
      )}

      {/* Performance Reviews */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h3 className="text-xl font-semibold text-gray-900 mb-4">Performance Reviews</h3>
        {reviews && reviews.length > 0 ? (
          <div className="space-y-6">
            {reviews.map((review) => {
              const getRatingColor = (rating) => {
                if (rating >= 4.5) return 'text-green-600 bg-green-50'
                if (rating >= 4.0) return 'text-green-600 bg-green-50'
                if (rating >= 3.0) return 'text-yellow-600 bg-yellow-50'
                if (rating >= 2.0) return 'text-orange-600 bg-orange-50'
                return 'text-red-600 bg-red-50'
              }
              
              const getRatingLabel = (rating) => {
                if (rating >= 4.5) return 'Excellent'
                if (rating >= 4.0) return 'Very Good'
                if (rating >= 3.0) return 'Good'
                if (rating >= 2.0) return 'Needs Improvement'
                return 'Poor'
              }
              
              return (
                <div key={review.id} className="border border-gray-200 rounded-lg p-5 hover:shadow-md transition-shadow">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <div className="flex items-center gap-3 mb-2">
                        <span className={`px-3 py-1 rounded-full text-sm font-semibold ${getRatingColor(review.overall_rating)}`}>
                          {review.overall_rating.toFixed(1)}/5.0 - {getRatingLabel(review.overall_rating)}
                        </span>
                        <span className="text-sm text-gray-500">
                          Reviewed by {review.manager_name}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400">
                        {review.review_date ? new Date(review.review_date).toLocaleDateString() : 'N/A'}
                        {review.review_period_start && review.review_period_end && (
                          <span className="ml-2">
                            ({new Date(review.review_period_start).toLocaleDateString()} - {new Date(review.review_period_end).toLocaleDateString()})
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                  
                  {/* Rating Breakdown */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    {review.performance_rating && (
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Performance</p>
                        <p className="text-lg font-semibold text-gray-900">{review.performance_rating.toFixed(1)}</p>
                      </div>
                    )}
                    {review.productivity_rating && (
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Productivity</p>
                        <p className="text-lg font-semibold text-gray-900">{review.productivity_rating.toFixed(1)}</p>
                      </div>
                    )}
                    {review.teamwork_rating && (
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Teamwork</p>
                        <p className="text-lg font-semibold text-gray-900">{review.teamwork_rating.toFixed(1)}</p>
                      </div>
                    )}
                    {review.communication_rating && (
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Communication</p>
                        <p className="text-lg font-semibold text-gray-900">{review.communication_rating.toFixed(1)}</p>
                      </div>
                    )}
                  </div>
                  
                  {/* Comments */}
                  {review.comments && (
                    <div className="mb-3">
                      <p className="text-sm font-medium text-gray-700 mb-1">Comments</p>
                      <p className="text-sm text-gray-600 leading-relaxed">{review.comments}</p>
                    </div>
                  )}
                  
                  {/* Strengths and Areas for Improvement */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {review.strengths && (
                      <div>
                        <p className="text-sm font-medium text-green-700 mb-1">Strengths</p>
                        <p className="text-sm text-gray-600">{review.strengths}</p>
                      </div>
                    )}
                    {review.areas_for_improvement && (
                      <div>
                        <p className="text-sm font-medium text-orange-700 mb-1">Areas for Improvement</p>
                        <p className="text-sm text-gray-600">{review.areas_for_improvement}</p>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="text-lg font-medium text-gray-700 mb-2">No Performance Reviews Yet</p>
            <p className="text-sm text-gray-500">
              {employee.role === 'CEO' || employee.role === 'Manager' || employee.role === 'CTO' || employee.role === 'COO' || employee.role === 'CFO' 
                ? 'Executives and managers do not receive performance reviews.'
                : 'Performance reviews are conducted periodically by managers. Reviews will appear here once they are completed.'}
            </p>
          </div>
        )}
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

      {/* Floating Action Button for Chat - Only for non-terminated employees */}
      {!employee.fired_at && employee.status !== 'fired' && (
        <>
          <button
            onClick={() => setShowChatModal(true)}
            className="fixed bottom-8 right-8 bg-blue-600 hover:bg-blue-700 text-white rounded-full p-4 shadow-lg transition-all hover:scale-110 z-50 flex items-center justify-center"
            style={{ width: '56px', height: '56px' }}
            title="Chat with employee"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </button>

          {/* Chat Modal */}
          {showChatModal && (
            <EmployeeChatModal
              employeeId={parseInt(id)}
              employee={employee}
              isOpen={showChatModal}
              onClose={() => setShowChatModal(false)}
            />
          )}
        </>
      )}
    </div>
  )
}

export default EmployeeDetail

