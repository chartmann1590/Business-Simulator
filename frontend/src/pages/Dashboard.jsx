import { useState, useEffect, useCallback } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'

function Dashboard() {
  const [dashboardData, setDashboardData] = useState(null)
  const [loading, setLoading] = useState(true)
  const activities = useWebSocket()

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
          goal_progress: {}
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
        goal_progress: {}
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

  return (
    <div className="px-4 py-6">
      <h2 className="text-3xl font-bold text-gray-900 mb-6">Dashboard</h2>

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
                        {new Date(activity.timestamp).toLocaleString()}
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
    </div>
  )
}

export default Dashboard

