import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

function NotificationsHistory() {
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all') // all, unread, read
  const [typeFilter, setTypeFilter] = useState('all') // all, or specific type
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const limit = 50
  const maxPages = 5 // 250 notifications max (5 pages of 50)

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1)
  }, [filter, typeFilter])

  useEffect(() => {
    fetchNotifications()
    // Refresh every 10 seconds
    const interval = setInterval(fetchNotifications, 10000)
    return () => clearInterval(interval)
  }, [page, filter, typeFilter])

  const fetchNotifications = async () => {
    try {
      setLoading(true)
      const offset = (page - 1) * limit
      const unreadOnly = filter === 'unread' ? '&unread_only=true' : ''
      const response = await fetch(`/api/notifications?limit=${limit}&offset=${offset}${unreadOnly}`)
      const data = await response.json()
      
      // Handle both old format (array) and new format (object with notifications array)
      let notificationsData = []
      let total = 0
      let hasMoreData = false
      
      if (Array.isArray(data)) {
        // Old format - backward compatibility
        notificationsData = data
        total = data.length
        hasMoreData = data.length >= limit
      } else {
        // New format with pagination info
        notificationsData = data.notifications || []
        total = data.total || 0
        hasMoreData = data.has_more || false
      }
      
      // Apply type filter on client side
      let filteredData = notificationsData
      if (typeFilter !== 'all') {
        filteredData = notificationsData.filter(n => n.notification_type === typeFilter)
      }
      
      // Apply read/unread filter on client side if needed
      if (filter === 'read') {
        filteredData = filteredData.filter(n => n.read)
      } else if (filter === 'unread') {
        filteredData = filteredData.filter(n => !n.read)
      }
      
      setNotifications(filteredData)
      setTotalCount(total)
      setHasMore(hasMoreData && page < maxPages)
      setLoading(false)
    } catch (error) {
      console.error('Error fetching notifications:', error)
      setLoading(false)
    }
  }

  const markAsRead = async (notificationId) => {
    try {
      await fetch(`/api/notifications/${notificationId}/read`, {
        method: 'POST'
      })
      // Update the notification in the list
      setNotifications(prev => 
        prev.map(n => n.id === notificationId ? { ...n, read: true } : n)
      )
    } catch (error) {
      console.error('Error marking notification as read:', error)
    }
  }

  const markAllAsRead = async () => {
    try {
      await fetch('/api/notifications/read-all', {
        method: 'POST'
      })
      // Update all notifications to read
      setNotifications(prev => prev.map(n => ({ ...n, read: true })))
    } catch (error) {
      console.error('Error marking all as read:', error)
    }
  }

  const getNotificationIcon = (type) => {
    switch (type) {
      case 'review_completed':
        return '📋'
      case 'review_conducted':
        return '📝'
      case 'raise_recommendation':
        return '💰'
      case 'employee_fired':
        return '⚠️'
      case 'employee_hired':
        return '👤'
      case 'project_completed':
        return '✅'
      case 'birthday_party':
        return '🎉'
      case 'newsletter':
        return '📰'
      case 'random_event':
        return '🎲'
      case 'suggestion':
        return '💡'
      case 'performance_award':
        return '🏆'
      case 'award_announcement':
        return '🎖️'
      case 'award_transferred':
        return '🔄'
      default:
        return '🔔'
    }
  }

  const getNotificationColor = (type, read) => {
    const baseColors = {
      'review_completed': 'bg-blue-50 border-blue-200',
      'review_conducted': 'bg-indigo-50 border-indigo-200',
      'raise_recommendation': 'bg-green-50 border-green-200',
      'employee_fired': 'bg-red-50 border-red-200',
      'employee_hired': 'bg-purple-50 border-purple-200',
      'project_completed': 'bg-emerald-50 border-emerald-200',
      'birthday_party': 'bg-pink-50 border-pink-200',
      'newsletter': 'bg-cyan-50 border-cyan-200',
      'random_event': 'bg-yellow-50 border-yellow-200',
      'suggestion': 'bg-orange-50 border-orange-200',
      'performance_award': 'bg-amber-50 border-amber-200',
      'award_announcement': 'bg-amber-50 border-amber-200',
      'award_transferred': 'bg-amber-50 border-amber-200',
    }
    
    const color = baseColors[type] || 'bg-gray-50 border-gray-200'
    return read ? `${color} opacity-75` : color
  }

  const getNotificationTypes = () => {
    const types = new Set(notifications.map(n => n.notification_type))
    return Array.from(types).sort()
  }

  const unreadCount = notifications.filter(n => !n.read).length
  const totalPages = Math.min(maxPages, Math.ceil(Math.min(totalCount, 250) / limit))
  
  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setPage(newPage)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  return (
    <div className="px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-3xl font-bold text-gray-900">Notifications History</h2>
        {unreadCount > 0 && (
          <button
            onClick={markAllAsRead}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            Mark All as Read
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex flex-wrap gap-4 items-center">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All</option>
              <option value="unread">Unread</option>
              <option value="read">Read</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Types</option>
              {getNotificationTypes().map(type => (
                <option key={type} value={type}>
                  {type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </option>
              ))}
            </select>
          </div>
          <div className="ml-auto flex items-end gap-4">
            <div className="text-sm text-gray-600">
              Showing <span className="font-semibold">{(page - 1) * limit + 1}</span>-<span className="font-semibold">{Math.min(page * limit, Math.min(totalCount, 250))}</span> of <span className="font-semibold">{Math.min(totalCount, 250)}</span>
              {unreadCount > 0 && (
                <span className="ml-2">
                  (<span className="font-semibold text-blue-600">{unreadCount}</span> unread on this page)
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Notifications List */}
      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-500">Loading notifications...</p>
        </div>
      ) : notifications.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <svg className="mx-auto h-16 w-16 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          <p className="text-gray-500 text-lg">No notifications found</p>
          <p className="text-gray-400 text-sm mt-2">Try adjusting your filters</p>
        </div>
      ) : (
        <div className="space-y-3">
          {notifications.map((notification) => (
            <div
              key={notification.id}
              className={`bg-white rounded-lg shadow border-l-4 p-4 hover:shadow-md transition-all ${
                notification.read 
                  ? getNotificationColor(notification.notification_type, true)
                  : `${getNotificationColor(notification.notification_type, false)} border-blue-500`
              }`}
            >
              <div className="flex items-start space-x-4">
                <span className="text-3xl flex-shrink-0">
                  {getNotificationIcon(notification.notification_type)}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="text-base font-semibold text-gray-900">
                          {notification.title}
                        </p>
                        {!notification.read && (
                          <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                            New
                          </span>
                        )}
                        <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-700 rounded-full">
                          {notification.notification_type.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <p className="text-sm text-gray-700 mt-1">
                        {notification.message}
                      </p>
                      <div className="flex items-center gap-4 mt-2">
                        {notification.employee_name && (
                          <Link
                            to={`/employees/${notification.employee_id}`}
                            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                          >
                            View {notification.employee_name} →
                          </Link>
                        )}
                        {notification.notification_type === 'project_completed' && (
                          <Link
                            to="/projects"
                            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                          >
                            View Projects →
                          </Link>
                        )}
                        {!notification.read && (
                          <button
                            onClick={() => markAsRead(notification.id)}
                            className="text-sm text-gray-600 hover:text-gray-800 font-medium"
                          >
                            Mark as read
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                  <p className="text-xs text-gray-400 mt-3">
                    {notification.created_at && new Date(notification.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      {!loading && notifications.length > 0 && totalPages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-2">
          <button
            onClick={() => handlePageChange(page - 1)}
            disabled={page === 1}
            className={`px-4 py-2 rounded-md border ${
              page === 1
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed border-gray-200'
                : 'bg-white text-gray-700 hover:bg-gray-50 border-gray-300'
            }`}
          >
            Previous
          </button>
          
          <div className="flex items-center gap-1">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((pageNum) => {
              // Show first page, last page, current page, and pages around current
              if (
                pageNum === 1 ||
                pageNum === totalPages ||
                (pageNum >= page - 1 && pageNum <= page + 1)
              ) {
                return (
                  <button
                    key={pageNum}
                    onClick={() => handlePageChange(pageNum)}
                    className={`px-3 py-2 rounded-md border ${
                      pageNum === page
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-gray-700 hover:bg-gray-50 border-gray-300'
                    }`}
                  >
                    {pageNum}
                  </button>
                )
              } else if (
                pageNum === page - 2 ||
                pageNum === page + 2
              ) {
                return (
                  <span key={pageNum} className="px-2 text-gray-400">
                    ...
                  </span>
                )
              }
              return null
            })}
          </div>
          
          <button
            onClick={() => handlePageChange(page + 1)}
            disabled={page === totalPages || !hasMore}
            className={`px-4 py-2 rounded-md border ${
              page === totalPages || !hasMore
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed border-gray-200'
                : 'bg-white text-gray-700 hover:bg-gray-50 border-gray-300'
            }`}
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}

export default NotificationsHistory

