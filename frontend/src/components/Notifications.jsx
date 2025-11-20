import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { apiGet, apiPost } from '../utils/api'

function Notifications() {
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const buttonRef = useRef(null)
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, right: 0 })

  useEffect(() => {
    fetchNotifications()
    fetchUnreadCount()
    
    // Poll for new notifications every 5 seconds
    const interval = setInterval(() => {
      fetchNotifications()
      fetchUnreadCount()
    }, 5000)
    
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (isOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect()
      setDropdownPosition({
        top: rect.bottom + 8, // 8px gap (mt-2 equivalent)
        right: 16 // 16px from the right edge of the viewport
      })
    }
  }, [isOpen])

  const fetchNotifications = async () => {
    try {
      const result = await apiGet('/api/notifications?limit=20&unread_only=true')
      const data = result.data || {}
      // Handle both old format (array) and new format (object with notifications array)
      const notificationsData = Array.isArray(data) ? data : (data.notifications || [])
      // Filter out read notifications to only show unread ones
      setNotifications(notificationsData.filter(n => !n.read))
    } catch (error) {
      console.error('Error fetching notifications:', error)
      setNotifications([])
    }
  }

  const fetchUnreadCount = async () => {
    try {
      const result = await apiGet('/api/notifications/unread-count')
      setUnreadCount(result.data?.count || 0)
    } catch (error) {
      console.error('Error fetching unread count:', error)
      setUnreadCount(0)
    }
  }

  const markAsRead = async (notificationId) => {
    try {
      await apiPost(`/api/notifications/${notificationId}/read`, {})
      // Remove the notification from the list immediately
      setNotifications(prev => prev.filter(n => n.id !== notificationId))
      fetchUnreadCount()
    } catch (error) {
      console.error('Error marking notification as read:', error)
    }
  }

  const markAllAsRead = async () => {
    try {
      await apiPost('/api/notifications/read-all', {})
      // Remove all notifications from the list immediately
      setNotifications([])
      fetchUnreadCount()
    } catch (error) {
      console.error('Error marking all as read:', error)
    }
  }

  const getNotificationIcon = (type) => {
    switch (type) {
      case 'review_completed':
        return '📋'
      case 'raise_recommendation':
        return '💰'
      case 'employee_fired':
        return '⚠️'
      case 'employee_hired':
        return '👤'
      case 'project_completed':
        return '✅'
      default:
        return '🔔'
    }
  }

  const getNotificationColor = (type) => {
    switch (type) {
      case 'review_completed':
        return 'bg-blue-50 border-blue-200'
      case 'raise_recommendation':
        return 'bg-green-50 border-green-200'
      case 'employee_fired':
        return 'bg-red-50 border-red-200'
      case 'employee_hired':
        return 'bg-purple-50 border-purple-200'
      case 'project_completed':
        return 'bg-emerald-50 border-emerald-200'
      default:
        return 'bg-gray-50 border-gray-200'
    }
  }

  // Only show unread notifications
  const unreadNotifications = notifications.filter(n => !n.read)

  return (
    <div className="relative">
      {/* Bell Icon Button */}
      <button
        ref={buttonRef}
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-full transition-colors"
        title="Notifications"
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute top-0 right-0 block h-5 w-5 rounded-full bg-red-500 text-white text-xs flex items-center justify-center font-bold">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          
          {/* Dropdown Panel */}
          <div 
            className="fixed w-96 bg-white rounded-lg shadow-xl border border-gray-200 z-20 max-h-[600px] flex flex-col"
            style={{ 
              top: `${dropdownPosition.top}px`,
              right: `${dropdownPosition.right}px`
            }}
          >
            {/* Header */}
            <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Notifications</h3>
              <div className="flex items-center gap-3">
                <Link
                  to="/notifications"
                  onClick={() => setIsOpen(false)}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                >
                  View All
                </Link>
                {unreadNotifications.length > 0 && (
                  <button
                    onClick={markAllAsRead}
                    className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                  >
                    Mark all as read
                  </button>
                )}
              </div>
            </div>

            {/* Notifications List */}
            <div className="flex-1 overflow-y-auto">
              {unreadNotifications.length === 0 ? (
                <div className="px-4 py-8 text-center text-gray-500">
                  <svg className="mx-auto h-12 w-12 text-gray-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                  <p>No notifications</p>
                </div>
              ) : (
                <div className="divide-y divide-gray-100">
                  {unreadNotifications.map((notification) => (
                    <div
                      key={notification.id}
                      className={`px-4 py-3 hover:bg-gray-50 transition-colors cursor-pointer border-l-4 border-blue-500 bg-blue-50 ${getNotificationColor(notification.notification_type)}`}
                      onClick={() => {
                        markAsRead(notification.id)
                        if (notification.employee_id) {
                          setIsOpen(false)
                        }
                      }}
                    >
                      <div className="flex items-start space-x-3">
                        <span className="text-2xl flex-shrink-0">
                          {getNotificationIcon(notification.notification_type)}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <p className="text-sm font-medium text-gray-900">
                                {notification.title}
                              </p>
                              <p className="text-sm text-gray-600 mt-1">
                                {notification.message}
                              </p>
                              {notification.employee_name && (
                                <Link
                                  to={`/employees/${notification.employee_id}`}
                                  onClick={(e) => e.stopPropagation()}
                                  className="text-xs text-blue-600 hover:text-blue-800 mt-1 inline-block"
                                >
                                  View {notification.employee_name} →
                                </Link>
                              )}
                              {notification.notification_type === 'project_completed' && (
                                <Link
                                  to="/projects"
                                  onClick={(e) => e.stopPropagation()}
                                  className="text-xs text-blue-600 hover:text-blue-800 mt-1 inline-block"
                                >
                                  View Projects →
                                </Link>
                              )}
                            </div>
                            <span className="ml-2 flex-shrink-0 h-2 w-2 bg-blue-500 rounded-full"></span>
                          </div>
                          <p className="text-xs text-gray-400 mt-2">
                            {notification.created_at && new Date(notification.created_at).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default Notifications

