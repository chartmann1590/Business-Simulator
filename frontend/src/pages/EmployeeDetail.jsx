import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getAvatarPath } from '../utils/avatarMapper'
import EmployeeChatModal from '../components/EmployeeChatModal'
import PerformanceAwardModal from '../components/PerformanceAwardModal'
import EmployeeScreenModal from '../components/EmployeeScreenModal'
import RecentFiles from '../components/RecentFiles'
import { formatDate, formatTime, formatDateTime, formatDateWithWeekday, formatDateShort } from '../utils/timezone'

function EmployeeDetail() {
  const { id } = useParams()
  const [employee, setEmployee] = useState(null)
  const [emails, setEmails] = useState([])
  const [chats, setChats] = useState([])
  const [reviews, setReviews] = useState([])
  const [meetings, setMeetings] = useState([])
  const [loading, setLoading] = useState(true)
  const [showChatModal, setShowChatModal] = useState(false)
  const [timeUntilReview, setTimeUntilReview] = useState(null)
  const [thoughts, setThoughts] = useState(null)
  const [loadingThoughts, setLoadingThoughts] = useState(false)
  const [showAwardModal, setShowAwardModal] = useState(false)
  const [showScreenModal, setShowScreenModal] = useState(false)

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
      const [employeeRes, emailsRes, chatsRes, reviewsRes, meetingsRes] = await Promise.all([
        fetch(`/api/employees/${id}`),
        fetch(`/api/employees/${id}/emails`),
        fetch(`/api/employees/${id}/chats`),
        fetch(`/api/employees/${id}/reviews`),
        fetch(`/api/employees/${id}/meetings`)
      ])
      const employeeData = await employeeRes.json()
      const emailsData = await emailsRes.json()
      const chatsData = await chatsRes.json()
      const reviewsData = await reviewsRes.json()
      const meetingsDataRaw = await meetingsRes.json()
      // Handle wrapped response (PowerShell/API might wrap arrays)
      const meetingsData = Array.isArray(meetingsDataRaw) ? meetingsDataRaw : (meetingsDataRaw?.value || meetingsDataRaw || [])
      // Debug: Check award status
      if (employeeData.has_performance_award) {
        console.log('Employee has award:', employeeData.name, employeeData.has_performance_award)
      }
      // Debug: Check meetings
      console.log(`Fetched ${meetingsData?.length || 0} meetings for employee ${id}:`, meetingsData)
      console.log('Meetings data type:', typeof meetingsData, 'Is array:', Array.isArray(meetingsData))
      setEmployee(employeeData)
      setEmails(emailsData)
      setChats(chatsData)
      setReviews(reviewsData || [])
      setMeetings(meetingsData || [])
      console.log('Set meetings state to:', meetingsData)
      setLoading(false)
    } catch (error) {
      console.error('Error fetching employee:', error)
      // Set empty array for reviews if there's an error
      setReviews([])
      setMeetings([])
      setLoading(false)
    }
  }

  const fetchThoughts = useCallback(async () => {
    setLoadingThoughts(true)
    try {
      const response = await fetch(`/api/employees/${id}/thoughts`)
      if (response.ok) {
        const data = await response.json()
        setThoughts(data.thoughts)
      } else {
        console.error('Error fetching thoughts:', response.statusText)
        setThoughts("Unable to generate thoughts at this time.")
      }
    } catch (error) {
      console.error('Error fetching thoughts:', error)
      setThoughts("Unable to generate thoughts at this time.")
    } finally {
      setLoadingThoughts(false)
    }
  }, [id])

  // Fetch thoughts only once when employee profile first loads (when id changes)
  // Only fetch for non-terminated employees
  useEffect(() => {
    // Reset thoughts when employee ID changes
    setThoughts(null)
    setLoadingThoughts(false)
    
    // Fetch thoughts only once when the employee ID changes, and only if employee is not terminated
    if (id && employee && !employee.fired_at && employee.status !== 'fired') {
      fetchThoughts()
    }
    
    // Cleanup: don't refetch when component unmounts or id changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, employee]) // Depend on employee to check termination status

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
                  Hired: {formatDate(employee.hired_at)}
                </p>
              )}
              {employee.birthday_month && employee.birthday_day && (
                <p className="text-xs text-gray-400 mt-1">
                  Birthday: {formatDateShort(new Date(2000, employee.birthday_month - 1, employee.birthday_day))}
                </p>
              )}
              {(employee.fired_at || employee.status === 'fired') && (
                <div className="mt-1">
                  <p className="text-xs text-red-600">
                    Terminated: {employee.fired_at ? formatDate(employee.fired_at) : 'Date not available'}
                  </p>
                  {employee.termination_reason && (
                    <p className="text-xs text-red-700 mt-1 italic font-medium">
                      Reason: {employee.termination_reason}
                    </p>
                  )}
                </div>
              )}
              {employee.has_performance_award === true && (
                <div 
                  onClick={() => setShowAwardModal(true)}
                  className="mt-3 flex items-center gap-2 bg-gradient-to-r from-yellow-50 to-amber-50 border-2 border-yellow-300 rounded-lg px-4 py-2 cursor-pointer hover:from-yellow-100 hover:to-amber-100 transition-colors"
                >
                  <span className="text-3xl">🏆</span>
                  <div className="flex-1">
                    <p className="text-sm font-bold text-yellow-800">Performance Award Winner</p>
                    <p className="text-xs text-yellow-600">
                      Highest performance review rating
                      {employee.performance_award_wins > 0 && (
                        <span className="ml-2 font-semibold">
                          • {employee.performance_award_wins} time{employee.performance_award_wins !== 1 ? 's' : ''} winner
                        </span>
                      )}
                    </p>
                  </div>
                  <svg className="w-5 h-5 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              )}
              {employee.performance_award_wins > 0 && !employee.has_performance_award && (
                <div className="mt-3 flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-4 py-2">
                  <span className="text-2xl">🏆</span>
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-gray-700">Award History</p>
                    <p className="text-xs text-gray-600">
                      {employee.performance_award_wins} time{employee.performance_award_wins !== 1 ? 's' : ''} winner
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
              employee.role === 'CEO' ? 'bg-purple-100 text-purple-800' :
              employee.role === 'Manager' ? 'bg-blue-100 text-blue-800' :
              'bg-gray-100 text-gray-800'
            }`}>
              {employee.role}
            </span>
            {employee.activity_state === 'working' && employee.status === 'active' && (
              <button
                onClick={() => setShowScreenModal(true)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg flex items-center gap-2 transition-colors"
                title="View Employee Screen"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
                <span>View Screen</span>
              </button>
            )}
            {employee.has_performance_award === true && (
              <button
                onClick={() => setShowAwardModal(true)}
                className="text-2xl hover:scale-110 transition-transform cursor-pointer"
                title="View Performance Award Details"
              >
                🏆
              </button>
            )}
          </div>
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

        {/* Calendar/Meetings Section - Always visible */}
        <div className="mb-6 bg-white rounded-lg border border-gray-200 p-6" data-testid="calendar-section">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            Calendar & Meetings ({meetings && Array.isArray(meetings) ? meetings.length : 0})
          </h3>
          {meetings && Array.isArray(meetings) && meetings.length > 0 ? (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {meetings.map((meeting) => {
                const startTime = meeting.start_time ? new Date(meeting.start_time) : null
                const endTime = meeting.end_time ? new Date(meeting.end_time) : null
                const isPast = startTime && startTime < new Date()
                const isUpcoming = startTime && startTime >= new Date()
                const isInProgress = meeting.status === 'in_progress'
                
                const getStatusColor = () => {
                  if (meeting.status === 'completed') return 'bg-gray-100 text-gray-700 border-gray-300'
                  if (meeting.status === 'cancelled') return 'bg-red-50 text-red-700 border-red-300'
                  if (isInProgress) return 'bg-blue-100 text-blue-700 border-blue-300'
                  if (isUpcoming) return 'bg-green-50 text-green-700 border-green-300'
                  return 'bg-gray-50 text-gray-700 border-gray-300'
                }
                
                return (
                  <div key={meeting.id} className={`border-l-4 rounded p-4 ${getStatusColor()}`}>
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <h4 className="font-semibold text-gray-900 mb-1">{meeting.title}</h4>
                        {meeting.description && (
                          <p className="text-sm text-gray-600 mb-2">{meeting.description}</p>
                        )}
                        <div className="flex flex-wrap gap-4 text-xs text-gray-600">
                          {startTime && (
                            <div className="flex items-center gap-1">
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                              </svg>
                              <span>
                                {formatDateWithWeekday(startTime)}
                                {' '}
                                {formatTime(startTime)}
                                {endTime && ` - ${formatTime(endTime)}`}
                              </span>
                            </div>
                          )}
                          {meeting.organizer_name && (
                            <div className="flex items-center gap-1">
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                              </svg>
                              <span>Organizer: {meeting.organizer_name}</span>
                            </div>
                          )}
                        </div>
                        {meeting.attendee_names && meeting.attendee_names.length > 0 && (
                          <div className="mt-2 text-xs text-gray-600">
                            <span className="font-medium">Attendees:</span> {meeting.attendee_names.join(', ')}
                          </div>
                        )}
                      </div>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        meeting.status === 'completed' ? 'bg-gray-200 text-gray-800' :
                        meeting.status === 'cancelled' ? 'bg-red-200 text-red-800' :
                        meeting.status === 'in_progress' ? 'bg-blue-200 text-blue-800' :
                        'bg-green-200 text-green-800'
                      }`}>
                        {meeting.status === 'in_progress' ? 'In Progress' :
                         meeting.status === 'completed' ? 'Completed' :
                         meeting.status === 'cancelled' ? 'Cancelled' :
                         'Scheduled'}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <p className="text-sm">No meetings scheduled</p>
            </div>
          )}
        </div>

        {/* AI-Generated Thoughts - Only show for non-terminated employees */}
        {!employee.fired_at && employee.status !== 'fired' && (
          <div className="mb-6 bg-gradient-to-r from-purple-50 to-blue-50 rounded-lg p-6 border border-purple-200">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                What {employee.name} is Thinking
              </h3>
              <button
                onClick={fetchThoughts}
                disabled={loadingThoughts}
                className="text-sm text-purple-600 hover:text-purple-800 disabled:text-gray-400 flex items-center gap-1"
                title="Refresh thoughts"
              >
                <svg className={`w-4 h-4 ${loadingThoughts ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                {loadingThoughts ? 'Generating...' : 'Refresh'}
              </button>
            </div>
            {loadingThoughts ? (
              <div className="flex items-center gap-2 text-gray-600">
                <svg className="animate-spin h-5 w-5 text-purple-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>Generating thoughts...</span>
              </div>
            ) : thoughts ? (
              <p className="text-gray-700 leading-relaxed italic">"{thoughts}"</p>
            ) : (
              <p className="text-gray-500">Click refresh to generate thoughts.</p>
            )}
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

      {/* Termination Notice - Prominent section for terminated employees */}
      {(employee.fired_at || employee.status === 'fired') && (
        <div className="bg-red-50 border-l-4 border-red-500 rounded-lg p-6 mb-6 shadow">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0">
              <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-red-900 mb-2">Employee Terminated</h3>
              <div className="space-y-2">
                {employee.fired_at && (
                  <p className="text-sm text-red-800">
                    <span className="font-medium">Termination Date:</span> {formatDate(employee.fired_at)} at {formatTime(employee.fired_at)}
                  </p>
                )}
                {employee.termination_reason ? (
                  <div>
                    <p className="text-sm font-medium text-red-800 mb-1">Termination Reason:</p>
                    <p className="text-sm text-red-700 leading-relaxed">{employee.termination_reason}</p>
                  </div>
                ) : (
                  <p className="text-sm text-red-700 italic">Termination reason not available.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

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
                            (Was scheduled for {formatDateTime(employee.next_review.scheduled_at)})
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
                    Scheduled date: {formatDateTime(employee.next_review.scheduled_at)}
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

      {/* Performance Award History */}
      {(employee.performance_award_wins > 0 || (employee.award_history && employee.award_history.length > 0)) && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <span className="text-2xl">🏆</span>
            Performance Award History
            {employee.performance_award_wins > 0 && (
              <span className="text-sm font-normal text-gray-600 ml-2">
                ({employee.performance_award_wins} total win{employee.performance_award_wins !== 1 ? 's' : ''})
              </span>
            )}
          </h3>
          {employee.award_history && employee.award_history.length > 0 ? (
            <div className="space-y-4">
              {employee.award_history.map((award, index) => (
                <div key={award.id} className="border-l-4 border-yellow-400 pl-4 py-3 bg-gradient-to-r from-yellow-50 to-transparent rounded-r-lg">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <p className="text-gray-900 font-medium mb-1">{award.description}</p>
                      {award.rating && (
                        <p className="text-sm text-gray-600">
                          Rating: <span className="font-semibold text-green-600">{award.rating.toFixed(1)}/5.0</span>
                        </p>
                      )}
                    </div>
                    <div className="text-right ml-4">
                      <p className="text-xs text-gray-500">
                        {award.timestamp ? formatDate(award.timestamp) : 'N/A'}
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        {award.timestamp ? formatTime(award.timestamp) : ''}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <p className="text-sm">No award history available yet.</p>
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
                        {review.review_date ? formatDate(review.review_date) : 'N/A'}
                        {review.review_period_start && review.review_period_end && (
                          <span className="ml-2">
                            ({formatDate(review.review_period_start)} - {formatDate(review.review_period_end)})
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
                    {formatDateTime(decision.timestamp)}
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

      {/* Recent Files */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h3 className="text-xl font-semibold text-gray-900 mb-4">Recent Files</h3>
        <RecentFiles employeeId={parseInt(id)} />
      </div>

      {/* Recent Activities */}
      {employee.activities && employee.activities.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="text-xl font-semibold text-gray-900 mb-4">Recent Activities</h3>
          <div className="space-y-3">
            {employee.activities.map((activity) => (
              <div key={activity.id} className="border-l-4 border-blue-500 pl-4 py-2">
                <p className="text-gray-900">{activity.description}</p>
                <p className="text-xs text-gray-500 mt-1">
                  {formatDateTime(activity.timestamp)}
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
                    {formatDateTime(email.timestamp)}
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
                    {formatDateTime(chat.timestamp)}
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

      {/* Award Modal - Available for all employees with award */}
      {employee && employee.has_performance_award === true && (
        <PerformanceAwardModal
          employeeId={parseInt(id)}
          employee={employee}
          isOpen={showAwardModal}
          onClose={() => setShowAwardModal(false)}
        />
      )}

      {/* Screen View Modal */}
      {employee && employee.activity_state === 'working' && employee.status === 'active' && (
        <EmployeeScreenModal
          employeeId={parseInt(id)}
          isOpen={showScreenModal}
          onClose={() => setShowScreenModal(false)}
        />
      )}
    </div>
  )
}

export default EmployeeDetail

