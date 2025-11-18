import { useState, useEffect, useCallback } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import BoardroomView from '../components/BoardroomView'
import { formatTimestamp } from '../utils/timezone'
import { useNavigate } from 'react-router-dom'

function Dashboard() {
  const [dashboardData, setDashboardData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')
  const [chats, setChats] = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [suggestionsLoading, setSuggestionsLoading] = useState(false)
  const [suggestionFilter, setSuggestionFilter] = useState('all') // all, pending, reviewed, implemented, rejected
  const activities = useWebSocket()
  const navigate = useNavigate()
  const [currentTime, setCurrentTime] = useState(new Date())
  
  const handleEmployeeClick = (employee) => {
    // Navigate to office view with employee ID and floor as URL parameters
    const params = new URLSearchParams({
      employee: employee.id.toString(),
      floor: (employee.floor || 1).toString()
    })
    navigate(`/office-view?${params.toString()}`)
  }
  
  const formatBreakDuration = (breakStartTime) => {
    if (!breakStartTime) return 'Unknown'
    
    try {
      const breakStart = new Date(breakStartTime)
      const now = currentTime
      const diffMs = now - breakStart
      
      if (diffMs < 0) return 'Just started'
      
      const diffMinutes = Math.floor(diffMs / (1000 * 60))
      const diffHours = Math.floor(diffMinutes / 60)
      const diffDays = Math.floor(diffHours / 24)
      
      if (diffDays > 0) {
        return `${diffDays} day${diffDays > 1 ? 's' : ''} ${diffHours % 24} hour${(diffHours % 24) !== 1 ? 's' : ''}`
      } else if (diffHours > 0) {
        const remainingMinutes = diffMinutes % 60
        if (remainingMinutes > 0) {
          return `${diffHours} hour${diffHours > 1 ? 's' : ''} ${remainingMinutes} minute${remainingMinutes !== 1 ? 's' : ''}`
        }
        return `${diffHours} hour${diffHours > 1 ? 's' : ''}`
      } else if (diffMinutes > 0) {
        return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''}`
      } else {
        return 'Just started'
      }
    } catch (error) {
      return 'Unknown'
    }
  }

  const fetchDashboardData = useCallback(async () => {
    try {
      const response = await fetch('/api/dashboard')
      if (!response.ok) {
        // If response is not OK, try to get error message
        const errorText = await response.text()
        console.error('Error fetching dashboard data:', response.status, errorText)
        // Set default data so the page still renders
        setDashboardData({
          revenue: 0.0,
          profit: 0.0,
          expenses: 0.0,
          active_projects: 0,
          employee_count: 0,
          recent_activities: [],
          goals: [],
          goal_progress: {},
          company_overview: {
            business_name: "TechFlow Solutions",
            mission: "To deliver innovative technology solutions that empower businesses to achieve their goals through cutting-edge software development and consulting services.",
            industry: "Technology & Software Development",
            founded: "2024",
            location: "San Francisco, CA",
            ceo: "Not Assigned",
            total_projects: 0,
            completed_projects: 0,
            active_projects_count: 0,
            total_project_revenue: 0.0,
            average_project_budget: 0.0,
            departments: {},
            role_distribution: {},
            products_services: []
          },
          leadership_insights: {
            leadership_team: [],
            recent_decisions: [],
            recent_activities: [],
            metrics: {
              total_leadership_count: 0,
              ceo_count: 0,
              manager_count: 0,
              strategic_decisions_count: 0,
              projects_led_by_leadership: 0
            }
          }
        })
        setLoading(false)
        return
      }
      const data = await response.json()
      setDashboardData(data)
      setLoading(false)
    } catch (error) {
      console.error('Error fetching dashboard data:', error)
      // Set default data so the page still renders
      setDashboardData({
        revenue: 0.0,
        profit: 0.0,
        expenses: 0.0,
        active_projects: 0,
        employee_count: 0,
        recent_activities: [],
        goals: [],
        goal_progress: {},
        leadership_insights: {
          leadership_team: [],
          recent_decisions: [],
          recent_activities: [],
          metrics: {
            total_leadership_count: 0,
            ceo_count: 0,
            manager_count: 0,
            strategic_decisions_count: 0,
            projects_led_by_leadership: 0
          }
        }
      })
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDashboardData()
    const interval = setInterval(fetchDashboardData, 5000)
    return () => clearInterval(interval)
  }, [fetchDashboardData])
  
  // Update current time every minute to refresh break durations
  useEffect(() => {
    const timeInterval = setInterval(() => {
      setCurrentTime(new Date())
    }, 60000) // Update every minute
    return () => clearInterval(timeInterval)
  }, [])

  // Fetch chats for boardroom
  useEffect(() => {
    const fetchChats = async () => {
      try {
        const response = await fetch('/api/chats?limit=500')
        if (response.ok) {
          const data = await response.json()
          setChats(data || [])
        }
      } catch (error) {
        console.error('Error fetching chats:', error)
        setChats([])
      }
    }

    fetchChats()
    const interval = setInterval(fetchChats, 10000) // Refresh every 10 seconds
    return () => clearInterval(interval)
  }, [])

  // Fetch suggestions
  useEffect(() => {
    const fetchSuggestions = async () => {
      setSuggestionsLoading(true)
      try {
        const statusParam = suggestionFilter !== 'all' ? `?status=${suggestionFilter}` : ''
        const response = await fetch(`/api/suggestions${statusParam}`)
        if (response.ok) {
          const data = await response.json()
          setSuggestions(data || [])
        }
      } catch (error) {
        console.error('Error fetching suggestions:', error)
        setSuggestions([])
      } finally {
        setSuggestionsLoading(false)
      }
    }

    if (activeTab === 'suggestions') {
      fetchSuggestions()
      const interval = setInterval(fetchSuggestions, 10000) // Refresh every 10 seconds
      return () => clearInterval(interval)
    }
  }, [activeTab, suggestionFilter])

  // Update business name in sidebar
  useEffect(() => {
    if (dashboardData?.business_name) {
      const businessNameEl = document.getElementById('business-name')
      if (businessNameEl) {
        businessNameEl.textContent = dashboardData.business_name
      }
    }
  }, [dashboardData])

  // Show loading only on initial load (before we have any data)
  if (loading && dashboardData === null) {
    return (
      <div className="px-4 py-6">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-500">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  // If we have no data after loading, show error
  if (!dashboardData) {
    return (
      <div className="px-4 py-6">
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">Unable to load dashboard data</p>
          <button 
            onClick={() => {
              setLoading(true)
              fetchDashboardData()
            }} 
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  const profitMargin = dashboardData && dashboardData.revenue > 0 
    ? ((dashboardData.profit / dashboardData.revenue) * 100).toFixed(1)
    : 0

  const companyOverview = dashboardData?.company_overview || {}

  return (
    <div className="px-4 py-6">
      <h2 className="text-3xl font-bold text-gray-900 mb-6">Dashboard</h2>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'overview'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('company')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'company'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Company Overview
          </button>
          <button
            onClick={() => setActiveTab('leadership')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'leadership'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Leadership
          </button>
          <button
            onClick={() => setActiveTab('boardroom')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'boardroom'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Boardroom
          </button>
          <button
            onClick={() => setActiveTab('suggestions')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'suggestions'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Employee Suggestions
          </button>
          <button
            onClick={() => setActiveTab('breaks')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'breaks'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Break Tracking
          </button>
        </nav>
      </div>

      {/* Overview Tab Content */}
      {activeTab === 'overview' && (
        <>
          {/* Metrics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Total Revenue</div>
          <div className="mt-2 text-3xl font-bold text-green-600">
            ${dashboardData.revenue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Total Profit</div>
          <div className={`mt-2 text-3xl font-bold ${dashboardData.profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            ${dashboardData.profit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Active Projects</div>
          <div className="mt-2 text-3xl font-bold text-blue-600">
            {dashboardData.active_projects}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Employees</div>
          <div className="mt-2 text-3xl font-bold text-purple-600">
            {dashboardData.employee_count}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Recent Activities */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">Recent Activities</h3>
          </div>
          <div className="px-6 py-4 max-h-96 overflow-y-auto">
            {activities.length === 0 && dashboardData.recent_activities.length === 0 ? (
              <p className="text-gray-500 text-center py-4">No activities yet</p>
            ) : (
              <div className="space-y-4">
                {[...activities, ...dashboardData.recent_activities]
                  .slice(0, 20)
                  .map((activity, idx) => (
                    <div key={idx} className="border-l-4 border-blue-500 pl-4 py-2">
                      <div className="text-sm text-gray-900">{activity.description || activity.activity_type}</div>
                      <div className="text-xs text-gray-500 mt-1">
                        {formatTimestamp(activity.timestamp)}
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>

        {/* Business Goals */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">Business Goals</h3>
          </div>
          <div className="px-6 py-4">
            {dashboardData.goals && dashboardData.goals.length > 0 ? (
              <div className="space-y-4">
                {dashboardData.goals.map((goal, idx) => {
                  const goalKeys = Object.keys(dashboardData.goal_progress || {})
                  const isComplete = goalKeys[idx] ? dashboardData.goal_progress[goalKeys[idx]] : false
                  return (
                    <div key={idx} className="flex items-center justify-between">
                      <span className="text-sm text-gray-700">{goal}</span>
                      <span className={`text-sm font-medium ${isComplete ? 'text-green-600' : 'text-gray-400'}`}>
                        {isComplete ? '✓' : '○'}
                      </span>
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="text-gray-500 text-center py-4">No goals defined yet</p>
            )}
          </div>
        </div>
      </div>
        </>
      )}

      {/* Break Tracking Tab Content */}
      {activeTab === 'breaks' && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                </div>
                <div className="ml-4">
                  <div className="text-sm font-medium text-gray-500">Currently on Break</div>
                  <div className="mt-1 text-3xl font-bold text-orange-600">
                    {dashboardData?.break_tracking?.total_on_break || 0}
                  </div>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                    </svg>
                  </div>
                </div>
                <div className="ml-4">
                  <div className="text-sm font-medium text-gray-500">Total Breaks Today</div>
                  <div className="mt-1 text-3xl font-bold text-blue-600">
                    {dashboardData?.break_tracking?.total_breaks_today || 0}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Employees Currently on Break */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Currently on Break</h3>
            </div>
            <div className="px-6 py-4">
              {dashboardData?.break_tracking?.employees_on_break && dashboardData.break_tracking.employees_on_break.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {dashboardData.break_tracking.employees_on_break.map((employee) => (
                    <div 
                      key={employee.id} 
                      onClick={() => handleEmployeeClick(employee)}
                      className="border border-orange-200 rounded-lg p-4 bg-orange-50 cursor-pointer hover:bg-orange-100 hover:border-orange-300 transition-all duration-200 hover:shadow-md"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <div className="font-semibold text-gray-900">{employee.name}</div>
                          <div className="text-sm text-gray-600">{employee.title}</div>
                          {employee.department && (
                            <div className="text-xs text-gray-500 mt-1">{employee.department}</div>
                          )}
                        </div>
                        <span className="px-2 py-1 text-xs font-medium rounded bg-orange-200 text-orange-800">
                          On Break
                        </span>
                      </div>
                      <div className="mt-3 pt-3 border-t border-orange-200">
                        <div className="flex items-center text-sm text-gray-700 mb-2">
                          <svg className="w-4 h-4 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <span className="font-medium">Duration:</span>
                          <span className="ml-2 text-orange-600 font-semibold">{formatBreakDuration(employee.last_coffee_break)}</span>
                        </div>
                        <div className="flex items-center text-sm text-gray-700">
                          <svg className="w-4 h-4 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                          <span className="font-medium">Room:</span>
                          <span className="ml-2">{(employee.current_room || 'Unknown').replace(/_/g, ' ').replace('breakroom', 'Breakroom')}</span>
                        </div>
                        <div className="flex items-center text-sm text-gray-700 mt-1">
                          <svg className="w-4 h-4 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                          </svg>
                          <span className="font-medium">Floor:</span>
                          <span className="ml-2">{employee.floor || 'N/A'}</span>
                        </div>
                        <div className="mt-2 pt-2 border-t border-orange-200">
                          <div className="flex items-center text-xs text-blue-600">
                            <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                            </svg>
                            Click to view in office
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-center py-8">No employees currently on break</p>
              )}
            </div>
          </div>

          {/* Break Returns - Manager Interventions */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Manager Interventions</h3>
              <p className="text-sm text-gray-500 mt-1">
                Employees returned to work after exceeding 30-minute break limit ({dashboardData?.break_tracking?.total_returns_today || 0} today)
              </p>
            </div>
            <div className="px-6 py-4">
              {dashboardData?.break_tracking?.break_returns && dashboardData.break_tracking.break_returns.length > 0 ? (
                <div className="space-y-3 max-h-64 overflow-y-auto">
                  {dashboardData.break_tracking.break_returns.map((returnItem) => (
                    <div key={returnItem.id} className="border-l-4 border-red-500 bg-red-50 rounded p-3">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-1">
                            <span className="text-sm font-semibold text-gray-900">{returnItem.employee_name}</span>
                            <span className="text-xs text-gray-600">returned by</span>
                            <span className="text-sm font-semibold text-blue-700">{returnItem.manager_name}</span>
                          </div>
                          <div className="text-sm text-gray-700 mb-1">{returnItem.description}</div>
                          {returnItem.break_duration_minutes && (
                            <div className="text-xs text-gray-600">
                              Break duration: {returnItem.break_duration_minutes} minutes
                            </div>
                          )}
                        </div>
                        <div className="text-xs text-gray-500 ml-4">
                          {returnItem.timestamp ? formatTimestamp(returnItem.timestamp) : 'N/A'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-center py-8">No manager interventions today</p>
              )}
            </div>
          </div>

          {/* Daily Break History */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Daily Break History</h3>
              <p className="text-sm text-gray-500 mt-1">Complete break history for all employees today</p>
            </div>
            <div className="px-6 py-4">
              {dashboardData?.break_tracking?.break_history && dashboardData.break_tracking.break_history.length > 0 ? (
                <div className="space-y-4 max-h-[600px] overflow-y-auto">
                  {dashboardData.break_tracking.break_history.map((employeeHistory) => (
                    <div key={employeeHistory.employee_id} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <div className="font-semibold text-gray-900">{employeeHistory.employee_name}</div>
                          <div className="text-sm text-gray-600">
                            {employeeHistory.total_break_count} break{employeeHistory.total_break_count !== 1 ? 's' : ''} today
                          </div>
                        </div>
                      </div>
                      <div className="space-y-2">
                        {employeeHistory.breaks.map((breakItem) => (
                          <div key={breakItem.id} className="flex items-start justify-between bg-gray-50 rounded p-3">
                            <div className="flex-1">
                              <div className="flex items-center space-x-2 mb-1">
                                <span className="text-sm font-medium text-gray-900">
                                  {breakItem.description || 'Break'}
                                </span>
                                <span className="px-2 py-0.5 text-xs font-medium rounded bg-blue-100 text-blue-800">
                                  {breakItem.break_type || 'coffee'}
                                </span>
                              </div>
                              <div className="flex items-center text-xs text-gray-600 mt-1">
                                <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                                </svg>
                                <span>{(breakItem.room || 'Unknown').replace(/_/g, ' ').replace('breakroom', 'Breakroom')}</span>
                              </div>
                            </div>
                            <div className="text-xs text-gray-500 ml-4">
                              {breakItem.timestamp ? formatTimestamp(breakItem.timestamp) : 'N/A'}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-center py-8">No break history for today</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Company Overview Tab Content */}
      {activeTab === 'company' && (
        <div className="space-y-6">
          {/* Company Information Card */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-2xl font-bold text-gray-900 mb-6">Company Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-2">Company Name</h4>
                <p className="text-lg font-semibold text-gray-900">{companyOverview.business_name || 'N/A'}</p>
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-2">Industry</h4>
                <p className="text-lg font-semibold text-gray-900">{companyOverview.industry || 'N/A'}</p>
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-2">Founded</h4>
                <p className="text-lg font-semibold text-gray-900">{companyOverview.founded || 'N/A'}</p>
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-2">Location</h4>
                <p className="text-lg font-semibold text-gray-900">{companyOverview.location || 'N/A'}</p>
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-2">CEO</h4>
                <p className="text-lg font-semibold text-gray-900">{companyOverview.ceo || 'N/A'}</p>
              </div>
            </div>
            <div className="mt-6">
              <h4 className="text-sm font-medium text-gray-500 mb-2">Mission Statement</h4>
              <p className="text-gray-700 leading-relaxed">{companyOverview.mission || 'No mission statement available.'}</p>
            </div>
          </div>

          {/* Business Statistics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-sm font-medium text-gray-500">Total Projects</div>
              <div className="mt-2 text-3xl font-bold text-blue-600">
                {companyOverview.total_projects || 0}
              </div>
              <div className="mt-2 text-sm text-gray-600">
                {companyOverview.completed_projects || 0} completed
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-sm font-medium text-gray-500">Active Projects</div>
              <div className="mt-2 text-3xl font-bold text-green-600">
                {companyOverview.active_projects_count || 0}
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-sm font-medium text-gray-500">Total Project Revenue</div>
              <div className="mt-2 text-3xl font-bold text-purple-600">
                ${(companyOverview.total_project_revenue || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-sm font-medium text-gray-500">Avg Project Budget</div>
              <div className="mt-2 text-3xl font-bold text-orange-600">
                ${(companyOverview.average_project_budget || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </div>
          </div>

          {/* Organization Structure */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900">Departments</h3>
              </div>
              <div className="px-6 py-4">
                {companyOverview.departments && Object.keys(companyOverview.departments).length > 0 ? (
                  <div className="space-y-3">
                    {Object.entries(companyOverview.departments).map(([dept, count]) => (
                      <div key={dept} className="flex items-center justify-between">
                        <span className="text-sm text-gray-700">{dept}</span>
                        <span className="text-sm font-semibold text-gray-900">{count} employees</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500 text-center py-4">No department data available</p>
                )}
              </div>
            </div>

            <div className="bg-white rounded-lg shadow">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900">Role Distribution</h3>
              </div>
              <div className="px-6 py-4">
                {companyOverview.role_distribution && Object.keys(companyOverview.role_distribution).length > 0 ? (
                  <div className="space-y-3">
                    {Object.entries(companyOverview.role_distribution).map(([role, count]) => (
                      <div key={role} className="flex items-center justify-between">
                        <span className="text-sm text-gray-700">{role}</span>
                        <span className="text-sm font-semibold text-gray-900">{count}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500 text-center py-4">No role data available</p>
                )}
              </div>
            </div>
          </div>

          {/* Products & Services */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Products & Services</h3>
              <p className="text-sm text-gray-500 mt-1">Projects representing our products and services</p>
            </div>
            <div className="px-6 py-4">
              {companyOverview.products_services && companyOverview.products_services.length > 0 ? (
                <div className="space-y-4">
                  {companyOverview.products_services.map((product) => (
                    <div key={product.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="text-lg font-semibold text-gray-900">{product.name}</h4>
                        <span className={`px-2 py-1 text-xs font-medium rounded ${
                          product.status === 'completed' ? 'bg-green-100 text-green-800' :
                          product.status === 'active' ? 'bg-blue-100 text-blue-800' :
                          product.status === 'planning' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {product.status}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-3">{product.description}</p>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <span className="text-gray-500">Revenue: </span>
                          <span className="font-semibold text-green-600">
                            ${(product.revenue || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-500">Budget: </span>
                          <span className="font-semibold text-gray-900">
                            ${(product.budget || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </span>
                        </div>
                        {product.created_at && (
                          <div>
                            <span className="text-gray-500">Created: </span>
                            <span className="font-semibold text-gray-900">
                              {new Date(product.created_at).toLocaleDateString()}
                            </span>
                          </div>
                        )}
                        {product.completed_at && (
                          <div>
                            <span className="text-gray-500">Completed: </span>
                            <span className="font-semibold text-gray-900">
                              {new Date(product.completed_at).toLocaleDateString()}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-center py-8">No products or services available yet</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Leadership Tab Content */}
      {activeTab === 'leadership' && (
        <div className="space-y-6">
          {/* Leadership Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-sm font-medium text-gray-500">Leadership Team</div>
              <div className="mt-2 text-3xl font-bold text-blue-600">
                {dashboardData?.leadership_insights?.metrics?.total_leadership_count || 0}
              </div>
              <div className="mt-2 text-sm text-gray-600">
                Total leaders
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-sm font-medium text-gray-500">CEOs</div>
              <div className="mt-2 text-3xl font-bold text-purple-600">
                {dashboardData?.leadership_insights?.metrics?.ceo_count || 0}
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-sm font-medium text-gray-500">Managers</div>
              <div className="mt-2 text-3xl font-bold text-green-600">
                {dashboardData?.leadership_insights?.metrics?.manager_count || 0}
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-sm font-medium text-gray-500">Strategic Decisions</div>
              <div className="mt-2 text-3xl font-bold text-orange-600">
                {dashboardData?.leadership_insights?.metrics?.strategic_decisions_count || 0}
              </div>
              <div className="mt-2 text-sm text-gray-600">
                Recent strategic moves
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-sm font-medium text-gray-500">Reviews In Progress</div>
              <div className="mt-2 text-3xl font-bold text-yellow-600">
                {dashboardData?.leadership_insights?.metrics?.reviews_in_progress || 0}
              </div>
              <div className="mt-2 text-sm text-gray-600">
                Reviews being conducted
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-sm font-medium text-gray-500">Reviews Completed</div>
              <div className="mt-2 text-3xl font-bold text-teal-600">
                {dashboardData?.leadership_insights?.metrics?.reviews_completed || 0}
              </div>
              <div className="mt-2 text-sm text-gray-600">
                Completed reviews
              </div>
            </div>
          </div>

          {/* Leadership Team */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Leadership Team</h3>
              <p className="text-sm text-gray-500 mt-1">The executives and managers driving the company forward</p>
            </div>
            <div className="px-6 py-4">
              {dashboardData?.leadership_insights?.leadership_team && dashboardData.leadership_insights.leadership_team.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {dashboardData.leadership_insights.leadership_team.map((leader) => (
                    <div key={leader.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <h4 className="text-lg font-semibold text-gray-900">{leader.name}</h4>
                          <p className="text-sm text-gray-600">{leader.title}</p>
                        </div>
                        <span className={`px-2 py-1 text-xs font-medium rounded ${
                          leader.role === 'CEO' ? 'bg-purple-100 text-purple-800' :
                          leader.role === 'CTO' ? 'bg-indigo-100 text-indigo-800' :
                          leader.role === 'COO' ? 'bg-green-100 text-green-800' :
                          leader.role === 'CFO' ? 'bg-amber-100 text-amber-800' :
                          leader.role === 'Manager' ? 'bg-blue-100 text-blue-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {leader.role}
                        </span>
                      </div>
                      {leader.department && (
                        <p className="text-sm text-gray-500 mb-2">Department: {leader.department}</p>
                      )}
                      {leader.hired_at && (
                        <p className="text-xs text-gray-400">
                          Hired: {new Date(leader.hired_at).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-center py-8">No leadership team members found</p>
              )}
            </div>
          </div>

          {/* Strategic Decisions and Activities */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Recent Strategic Decisions */}
            <div className="bg-white rounded-lg shadow">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900">Strategic Decisions</h3>
                <p className="text-sm text-gray-500 mt-1">Key decisions shaping the company's future</p>
              </div>
              <div className="px-6 py-4 max-h-96 overflow-y-auto">
                {dashboardData?.leadership_insights?.recent_decisions && dashboardData.leadership_insights.recent_decisions.length > 0 ? (
                  <div className="space-y-4">
                    {dashboardData.leadership_insights.recent_decisions.map((decision) => (
                      <div key={decision.id} className="border-l-4 border-orange-500 pl-4 py-2">
                        <div className="flex items-start justify-between mb-1">
                          <div className="flex-1">
                            <div className="text-sm font-semibold text-gray-900">{decision.employee_name}</div>
                            <div className="text-xs text-gray-500">{decision.employee_role}</div>
                          </div>
                          <span className={`px-2 py-1 text-xs font-medium rounded ${
                            decision.decision_type === 'strategic' ? 'bg-orange-100 text-orange-800' :
                            decision.decision_type === 'tactical' ? 'bg-blue-100 text-blue-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {decision.decision_type}
                          </span>
                        </div>
                        <div className="text-sm text-gray-700 mt-2">{decision.description}</div>
                        {decision.reasoning && (
                          <div className="text-xs text-gray-500 mt-1 italic">"{decision.reasoning}"</div>
                        )}
                        <div className="text-xs text-gray-400 mt-2">
                          {formatTimestamp(decision.timestamp)}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500 text-center py-4">No strategic decisions recorded yet</p>
                )}
              </div>
            </div>

            {/* Recent Leadership Activities */}
            <div className="bg-white rounded-lg shadow">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900">Leadership Activities</h3>
                <p className="text-sm text-gray-500 mt-1">Recent actions and initiatives from leadership</p>
              </div>
              <div className="px-6 py-4 max-h-96 overflow-y-auto">
                {dashboardData?.leadership_insights?.recent_activities && dashboardData.leadership_insights.recent_activities.length > 0 ? (
                  <div className="space-y-4">
                    {dashboardData.leadership_insights.recent_activities.map((activity) => (
                      <div key={activity.id} className="border-l-4 border-blue-500 pl-4 py-2">
                        <div className="flex items-start justify-between mb-1">
                          <div className="flex-1">
                            <div className="text-sm font-semibold text-gray-900">{activity.employee_name}</div>
                            <div className="text-xs text-gray-500">{activity.employee_role}</div>
                          </div>
                          <span className="px-2 py-1 text-xs font-medium rounded bg-blue-100 text-blue-800">
                            {activity.activity_type}
                          </span>
                        </div>
                        <div className="text-sm text-gray-700 mt-2">{activity.description || activity.activity_type}</div>
                        <div className="text-xs text-gray-400 mt-2">
                          {formatTimestamp(activity.timestamp)}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500 text-center py-4">No leadership activities recorded yet</p>
                )}
              </div>
            </div>
          </div>

          {/* Leadership Impact Summary */}
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg shadow p-6 border border-blue-100">
            <h3 className="text-xl font-bold text-gray-900 mb-4">How Leadership is Driving the Company Forward</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Strategic Vision</h4>
                <p className="text-sm text-gray-600">
                  Our leadership team is making {dashboardData?.leadership_insights?.metrics?.strategic_decisions_count || 0} strategic decisions 
                  that are shaping the company's direction and ensuring long-term success. 
                  {dashboardData?.leadership_insights?.metrics?.ceo_count > 0 && (
                    <> With {dashboardData.leadership_insights.metrics.ceo_count} CEO{dashboardData.leadership_insights.metrics.ceo_count > 1 ? 's' : ''} 
                    and {dashboardData.leadership_insights.metrics.manager_count} manager{dashboardData.leadership_insights.metrics.manager_count > 1 ? 's' : ''} 
                    at the helm, we have strong executive guidance.</>
                  )}
                </p>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Project Leadership</h4>
                <p className="text-sm text-gray-600">
                  Leadership is actively involved in {dashboardData?.leadership_insights?.metrics?.projects_led_by_leadership || 0} projects, 
                  ensuring strategic alignment and successful execution. This hands-on approach from executives 
                  demonstrates commitment to delivering results and maintaining high standards.
                </p>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Organizational Growth</h4>
                <p className="text-sm text-gray-600">
                  With a leadership team of {dashboardData?.leadership_insights?.metrics?.total_leadership_count || 0} members, 
                  we have the expertise and vision needed to scale operations, drive innovation, and maintain 
                  competitive advantage in the market.
                </p>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Continuous Improvement</h4>
                <p className="text-sm text-gray-600">
                  Leadership activities show ongoing engagement with {dashboardData?.leadership_insights?.recent_activities?.length || 0} recent actions, 
                  indicating active management and continuous improvement initiatives that keep the company 
                  moving forward.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Boardroom Tab Content */}
      {activeTab === 'boardroom' && (
        <BoardroomView 
          leadershipTeam={dashboardData?.leadership_insights?.leadership_team || []}
          chats={chats}
          onChatsUpdate={async () => {
            try {
              const response = await fetch('/api/chats?limit=500')
              if (response.ok) {
                const data = await response.json()
                setChats(data || [])
              }
            } catch (error) {
              console.error('Error fetching chats:', error)
            }
          }}
        />
      )}

      {/* Employee Suggestions Tab Content */}
      {activeTab === 'suggestions' && (
        <div className="space-y-6">
          {/* Header with Filter */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-2xl font-bold text-gray-900">Employee Suggestions</h3>
              <div className="flex items-center space-x-2">
                <label className="text-sm font-medium text-gray-700">Filter by status:</label>
                <select
                  value={suggestionFilter}
                  onChange={(e) => setSuggestionFilter(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="all">All</option>
                  <option value="pending">Pending</option>
                  <option value="reviewed">Reviewed</option>
                  <option value="implemented">Implemented</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>
            </div>
            <p className="text-sm text-gray-600">
              Track and review all suggestions submitted by employees. Suggestions are automatically generated as employees work.
            </p>
          </div>

          {/* Suggestions List */}
          {suggestionsLoading ? (
            <div className="bg-white rounded-lg shadow p-12 text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-500">Loading suggestions...</p>
            </div>
          ) : suggestions.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-12 text-center">
              <p className="text-gray-500 text-lg">No suggestions found</p>
              <p className="text-gray-400 text-sm mt-2">
                {suggestionFilter !== 'all' 
                  ? `No suggestions with status "${suggestionFilter}"`
                  : 'Suggestions will appear here as employees submit them'}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {suggestions.map((suggestion) => (
                <div key={suggestion.id} className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-2">
                        <h4 className="text-lg font-semibold text-gray-900">{suggestion.title}</h4>
                        <span className={`px-3 py-1 text-xs font-semibold rounded-full ${
                          suggestion.status === 'pending' ? 'bg-yellow-100 text-yellow-800 border border-yellow-300' :
                          suggestion.status === 'reviewed' ? 'bg-blue-100 text-blue-800 border border-blue-300' :
                          suggestion.status === 'implemented' ? 'bg-green-100 text-green-800 border border-green-300' :
                          suggestion.status === 'rejected' ? 'bg-red-100 text-red-800 border border-red-300' :
                          'bg-gray-100 text-gray-800 border border-gray-300'
                        }`}>
                          {suggestion.status === 'pending' && '⏳ '}
                          {suggestion.status === 'reviewed' && '👀 '}
                          {suggestion.status === 'implemented' && '✅ '}
                          {suggestion.status === 'rejected' && '❌ '}
                          {suggestion.status.charAt(0).toUpperCase() + suggestion.status.slice(1)}
                        </span>
                        <span className="px-2 py-1 text-xs font-medium rounded bg-purple-100 text-purple-800">
                          {suggestion.category.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-3">{suggestion.content}</p>
                    </div>
                    <div className="flex items-center space-x-2 ml-4">
                      <div className="flex items-center space-x-1 text-gray-600">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                        </svg>
                        <span className="text-sm font-medium">{suggestion.upvotes}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="border-t border-gray-200 pt-4 mt-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-gray-500">Submitted by: </span>
                        <span className="font-medium text-gray-900">{suggestion.employee_name}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Submitted on: </span>
                        <span className="font-medium text-gray-900">
                          {formatTimestamp(suggestion.created_at)}
                        </span>
                      </div>
                      {suggestion.reviewer_name && (
                        <div>
                          <span className="text-gray-500">Reviewed by: </span>
                          <span className="font-medium text-gray-900">{suggestion.reviewer_name}</span>
                        </div>
                      )}
                      {suggestion.reviewed_at && (
                        <div>
                          <span className="text-gray-500">Reviewed on: </span>
                          <span className="font-medium text-gray-900">
                            {formatTimestamp(suggestion.reviewed_at)}
                          </span>
                        </div>
                      )}
                    </div>
                    {suggestion.manager_comments && (
                      <div className="mt-4 pt-4 border-t border-gray-200">
                        <div className="flex items-center space-x-2 mb-2">
                          <span className="text-sm font-semibold text-gray-700">Manager Comment:</span>
                          {suggestion.reviewer_name && (
                            <span className="text-xs text-gray-500">by {suggestion.reviewer_name}</span>
                          )}
                        </div>
                        <p className="text-sm text-gray-700 bg-blue-50 p-3 rounded-md border-l-4 border-blue-400">
                          {suggestion.manager_comments}
                        </p>
                      </div>
                    )}
                    {suggestion.review_notes && (
                      <div className="mt-4 pt-4 border-t border-gray-200">
                        <span className="text-sm font-medium text-gray-700">Review Notes: </span>
                        <p className="text-sm text-gray-600 mt-1">{suggestion.review_notes}</p>
                      </div>
                    )}
                    {suggestion.votes && suggestion.votes.length > 0 && (
                      <div className="mt-4 pt-4 border-t border-gray-200">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-semibold text-gray-700">
                            Voted by {suggestion.votes.length} employee{suggestion.votes.length !== 1 ? 's' : ''}:
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-2 mt-2">
                          {suggestion.votes.map((vote) => (
                            <span
                              key={vote.id}
                              className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-green-100 text-green-800"
                              title={`Voted on ${vote.created_at ? formatTimestamp(vote.created_at) : 'N/A'}`}
                            >
                              {vote.employee_name}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default Dashboard

