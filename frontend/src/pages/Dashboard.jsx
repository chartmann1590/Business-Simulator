import { useState, useEffect, useCallback } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'

function Dashboard() {
  const [dashboardData, setDashboardData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')
  const activities = useWebSocket()

  // Helper function to safely format timestamps
  const formatTimestamp = (timestamp) => {
    // If no timestamp, use current time
    if (!timestamp) {
      return new Date().toLocaleString()
    }
    try {
      const date = new Date(timestamp)
      // If invalid date, use current time
      if (isNaN(date.getTime())) {
        return new Date().toLocaleString()
      }
      return date.toLocaleString()
    } catch {
      // If parsing fails, use current time
      return new Date().toLocaleString()
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
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
              <div className="text-sm font-medium text-gray-500">Projects Led</div>
              <div className="mt-2 text-3xl font-bold text-indigo-600">
                {dashboardData?.leadership_insights?.metrics?.projects_led_by_leadership || 0}
              </div>
              <div className="mt-2 text-sm text-gray-600">
                Leadership-driven projects
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
    </div>
  )
}

export default Dashboard

