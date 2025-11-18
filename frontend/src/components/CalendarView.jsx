import { useState, useEffect } from 'react'
import MeetingDetail from './MeetingDetail'
import LiveMeetingView from './LiveMeetingView'
import BirthdayDetail from './BirthdayDetail'

function CalendarView({ employees = [] }) {
  const [meetings, setMeetings] = useState([])
  const [birthdays, setBirthdays] = useState([])
  const [selectedMeeting, setSelectedMeeting] = useState(null)
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState('day') // 'day', 'week', 'month'
  const [currentDate, setCurrentDate] = useState(new Date())

  useEffect(() => {
    fetchMeetings()
    fetchBirthdays()
    const interval = setInterval(() => {
      fetchMeetings()
      fetchBirthdays()
    }, 5000) // Refresh every 5 seconds
    return () => clearInterval(interval)
  }, [])

  const fetchMeetings = async () => {
    try {
      const response = await fetch('/api/meetings')
      if (response.ok) {
        const data = await response.json()
        setMeetings(data || [])
      }
    } catch (error) {
      console.error('Error fetching meetings:', error)
      setMeetings([])
    } finally {
      setLoading(false)
    }
  }

  const fetchBirthdays = async () => {
    try {
      // Fetch birthdays for the next 365 days to cover a full year
      const response = await fetch('/api/birthdays/upcoming?days=365')
      if (response.ok) {
        const data = await response.json()
        setBirthdays(data || [])
      }
    } catch (error) {
      console.error('Error fetching birthdays:', error)
      setBirthdays([])
    }
  }


  const formatTime = (timeString) => {
    if (!timeString) return ''
    const date = new Date(timeString)
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  }

  const formatDate = (date) => {
    if (!date) return ''
    if (typeof date === 'string') {
      date = new Date(date)
    }
    return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
  }

  const formatDateLong = (date) => {
    if (!date) return ''
    if (typeof date === 'string') {
      date = new Date(date)
    }
    return date.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
  }

  const getDateRange = () => {
    const start = new Date(currentDate)
    start.setHours(0, 0, 0, 0)
    
    if (viewMode === 'day') {
      const end = new Date(start)
      end.setDate(end.getDate() + 1)
      return { start, end }
    } else if (viewMode === 'week') {
      // Start of week (Sunday)
      const dayOfWeek = start.getDay()
      start.setDate(start.getDate() - dayOfWeek)
      const end = new Date(start)
      end.setDate(end.getDate() + 7)
      return { start, end }
    } else { // month
      start.setDate(1) // First day of month
      const end = new Date(start)
      end.setMonth(end.getMonth() + 1) // First day of next month
      return { start, end }
    }
  }

  // Convert birthdays to calendar events
  const getBirthdayEvents = () => {
    return birthdays.map(birthday => {
      // Parse the birthday date and extract just the date part (ignore time)
      const birthdayDate = new Date(birthday.date)
      // Create a new date with just the date part (year, month, day) at 9 AM local time
      const eventDate = new Date(birthdayDate.getFullYear(), birthdayDate.getMonth(), birthdayDate.getDate(), 9, 0, 0, 0)
      const endDate = new Date(eventDate)
      endDate.setHours(10, 0, 0, 0)
      
      return {
        id: `birthday-${birthday.employee_id}`,
        title: `🎂 ${birthday.employee_name}'s Birthday`,
        description: `Birthday celebration for ${birthday.employee_name}`,
        start_time: eventDate.toISOString(),
        end_time: endDate.toISOString(),
        is_birthday: true,
        employee_name: birthday.employee_name,
        employee_id: birthday.employee_id,
        days_until: birthday.days_until,
        status: 'scheduled'
      }
    })
  }

  // Get all events (meetings + birthdays)
  // Filter out birthday party meetings to avoid duplicates - we'll use birthday events instead
  const getAllEvents = () => {
    const birthdayEvents = getBirthdayEvents()
    // Filter out meetings that are birthday parties (we show them as birthday events instead)
    const regularMeetings = meetings.filter(m => {
      const metadata = m.meeting_metadata || {}
      return !metadata.is_birthday_party
    })
    return [...regularMeetings, ...birthdayEvents]
  }

  const getMeetingsForRange = () => {
    const { start, end } = getDateRange()
    const allEvents = getAllEvents()
    
    return allEvents.filter(event => {
      if (!event.start_time) return false
      const eventDate = new Date(event.start_time)
      return eventDate >= start && eventDate < end
    }).sort((a, b) => {
      const timeA = new Date(a.start_time).getTime()
      const timeB = new Date(b.start_time).getTime()
      return timeA - timeB
    })
  }

  const getMeetingsForDay = (date) => {
    const dayStart = new Date(date)
    dayStart.setHours(0, 0, 0, 0)
    const dayEnd = new Date(dayStart)
    dayEnd.setDate(dayEnd.getDate() + 1)

    const allEvents = getAllEvents()
    return allEvents.filter(event => {
      if (!event.start_time) return false
      const eventDate = new Date(event.start_time)
      return eventDate >= dayStart && eventDate < dayEnd
    }).sort((a, b) => {
      // Prioritize birthdays first
      if (a.is_birthday && !b.is_birthday) return -1
      if (!a.is_birthday && b.is_birthday) return 1
      // Then sort by time
      const timeA = new Date(a.start_time).getTime()
      const timeB = new Date(b.start_time).getTime()
      return timeA - timeB
    })
  }

  const navigateDate = (direction) => {
    const newDate = new Date(currentDate)
    if (viewMode === 'day') {
      newDate.setDate(newDate.getDate() + direction)
    } else if (viewMode === 'week') {
      newDate.setDate(newDate.getDate() + (direction * 7))
    } else { // month
      newDate.setMonth(newDate.getMonth() + direction)
    }
    setCurrentDate(newDate)
  }

  const goToToday = () => {
    setCurrentDate(new Date())
  }

  const isMeetingInProgress = (meeting) => {
    if (!meeting.start_time || !meeting.end_time) return false
    const now = new Date()
    const startTime = new Date(meeting.start_time)
    const endTime = new Date(meeting.end_time)
    // Meeting is in progress if current time is between start and end time
    // OR if status is explicitly 'in_progress'
    return (now >= startTime && now <= endTime) || meeting.status === 'in_progress'
  }

  const getStatusColor = (status, meeting) => {
    // Special styling for birthdays
    if (meeting && meeting.is_birthday) {
      const isToday = meeting.days_until === 0
      return isToday 
        ? 'bg-pink-200 text-pink-900 border-pink-300' 
        : 'bg-pink-100 text-pink-800 border-pink-200'
    }
    
    // If meeting is currently happening based on time, show as in_progress
    if (meeting && isMeetingInProgress(meeting)) {
      return 'bg-green-100 text-green-800 border-green-200'
    }
    
    switch (status) {
      case 'scheduled':
        return 'bg-blue-100 text-blue-800 border-blue-200'
      case 'in_progress':
        return 'bg-green-100 text-green-800 border-green-200'
      case 'completed':
        return 'bg-gray-100 text-gray-800 border-gray-200'
      case 'cancelled':
        return 'bg-red-100 text-red-800 border-red-200'
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  const handleMeetingClick = (meeting) => {
    // If it's a birthday event, find the corresponding birthday party meeting
    if (meeting.is_birthday) {
      const birthdayDate = new Date(meeting.start_time)
      const birthdayEmployeeId = meeting.employee_id
      
      // Find the birthday party meeting for this date and employee
      const birthdayMeeting = meetings.find(m => {
        // Check if it's a birthday party meeting
        const metadata = m.meeting_metadata || {}
        if (!metadata.is_birthday_party) return false
        
        // Check if it matches the birthday employee
        if (birthdayEmployeeId && metadata.birthday_employee_id === birthdayEmployeeId) {
          return true
        }
        
        // Also check by date and title
        const meetingDate = new Date(m.start_time)
        const sameDate = meetingDate.getFullYear() === birthdayDate.getFullYear() &&
                         meetingDate.getMonth() === birthdayDate.getMonth() &&
                         meetingDate.getDate() === birthdayDate.getDate()
        
        if (sameDate && m.title && m.title.includes('Birthday Party')) {
          // Check if the title contains the employee name from the birthday event
          const employeeName = meeting.employee_name || ''
          if (employeeName && m.title.includes(employeeName)) {
            return true
          }
        }
        
        return false
      })
      
      if (birthdayMeeting) {
        setSelectedMeeting({ ...birthdayMeeting, is_birthday: true, birthday_data: meeting })
      } else {
        // If no meeting found, still show birthday info
        setSelectedMeeting({ ...meeting, is_birthday: true })
      }
      return
    }
    
    // Ensure meeting status is set to 'in_progress' if it's currently happening
    const meetingToView = { ...meeting }
    if (isMeetingInProgress(meeting) && meeting.status !== 'in_progress') {
      meetingToView.status = 'in_progress'
    }
    setSelectedMeeting(meetingToView)
  }

  const handleCloseDetail = () => {
    setSelectedMeeting(null)
  }

  const handleJoinLiveMeeting = (meeting) => {
    // Ensure meeting status is set to 'in_progress' if it's currently happening
    const meetingToJoin = { ...meeting }
    if (isMeetingInProgress(meeting) && meeting.status !== 'in_progress') {
      meetingToJoin.status = 'in_progress'
    }
    setSelectedMeeting(meetingToJoin)
  }

  const handleDayClick = (day) => {
    setCurrentDate(day)
    setViewMode('day')
  }

  const renderDayView = () => {
    const dayMeetings = getMeetingsForDay(currentDate)
    const { start } = getDateRange()
    
    return (
      <div className="space-y-3">
        <div className="text-sm text-gray-600 mb-4">
          {formatDateLong(start)}
        </div>
        {dayMeetings.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <p className="text-lg mb-2">No meetings scheduled for this day</p>
          </div>
        ) : (
          dayMeetings.map(meeting => (
            <div
              key={meeting.id}
              onClick={() => handleMeetingClick(meeting)}
              className={`bg-white border-2 rounded-lg p-4 transition-shadow ${
                meeting.is_birthday ? 'cursor-pointer hover:shadow-md' : 'cursor-pointer hover:shadow-md'
              }`}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                  <h4 className="font-semibold text-gray-900 mb-1">{meeting.title}</h4>
                  <p className="text-sm text-gray-600 mb-2">{meeting.description}</p>
                  {meeting.is_birthday ? (
                    <div className="flex items-center gap-4 text-sm text-gray-500">
                      <span className="flex items-center gap-1">
                        <span>🎂</span>
                        {meeting.days_until === 0 ? 'Today!' : `${meeting.days_until} day${meeting.days_until !== 1 ? 's' : ''} away`}
                      </span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-4 text-sm text-gray-500">
                      <span className="flex items-center gap-1">
                        <span>🕐</span>
                        {formatTime(meeting.start_time)} - {formatTime(meeting.end_time)}
                      </span>
                      <span className="flex items-center gap-1">
                        <span>👤</span>
                        {meeting.organizer_name}
                      </span>
                      <span className="flex items-center gap-1">
                        <span>👥</span>
                        {meeting.attendee_names?.length || 0} attendees
                      </span>
                    </div>
                  )}
                </div>
                <div className="ml-4">
                  <span className={`px-2 py-1 rounded text-xs font-medium border ${getStatusColor(meeting.status, meeting)}`}>
                    {meeting.is_birthday 
                      ? (meeting.days_until === 0 ? '🎉 Today!' : 'Birthday')
                      : (isMeetingInProgress(meeting) ? '🔴 Live' : meeting.status)
                    }
                  </span>
                </div>
              </div>
              {isMeetingInProgress(meeting) && !meeting.is_birthday && (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleJoinLiveMeeting(meeting)
                  }}
                  className="mt-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium"
                >
                  Join Live Meeting →
                </button>
              )}
            </div>
          ))
        )}
      </div>
    )
  }

  const renderWeekView = () => {
    const { start } = getDateRange()
    const days = []
    for (let i = 0; i < 7; i++) {
      const day = new Date(start)
      day.setDate(day.getDate() + i)
      days.push(day)
    }

    return (
      <div className="grid grid-cols-7 gap-4">
        {days.map((day, index) => {
          const dayMeetings = getMeetingsForDay(day)
          const isToday = day.toDateString() === new Date().toDateString()
          
          return (
            <div 
              key={index} 
              onClick={() => handleDayClick(day)}
              className={`border rounded-lg p-3 cursor-pointer hover:bg-blue-50 hover:border-blue-300 transition-colors ${isToday ? 'bg-blue-50 border-blue-300' : 'bg-white border-gray-200'}`}
              title={`Click to view ${day.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}`}
            >
              <div className={`text-sm font-semibold mb-2 ${isToday ? 'text-blue-700' : 'text-gray-700'}`}>
                {day.toLocaleDateString('en-US', { weekday: 'short' })}
              </div>
              <div className={`text-xs mb-3 ${isToday ? 'text-blue-600' : 'text-gray-500'}`}>
                {day.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </div>
              <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
                {dayMeetings.slice(0, 3).map(meeting => (
                  <div
                    key={meeting.id}
                    onClick={() => handleMeetingClick(meeting)}
                    className={`text-xs p-2 rounded transition-shadow ${getStatusColor(meeting.status, meeting)} ${
                      meeting.is_birthday ? 'cursor-default' : 'cursor-pointer hover:shadow-sm'
                    }`}
                  >
                    <div className="font-medium truncate">{meeting.title}</div>
                    {!meeting.is_birthday && (
                      <div className="text-xs opacity-75">{formatTime(meeting.start_time)}</div>
                    )}
                  </div>
                ))}
                {dayMeetings.length > 3 && (
                  <div className="text-xs text-gray-500 text-center pt-1">
                    +{dayMeetings.length - 3} more
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  const renderMonthView = () => {
    const { start } = getDateRange()
    const firstDay = new Date(start)
    const lastDay = new Date(start)
    lastDay.setMonth(lastDay.getMonth() + 1)
    lastDay.setDate(0) // Last day of current month
    
    // Get first day of calendar grid (might be from previous month)
    const calendarStart = new Date(firstDay)
    calendarStart.setDate(1)
    const dayOfWeek = calendarStart.getDay()
    calendarStart.setDate(calendarStart.getDate() - dayOfWeek)
    
    const weeks = []
    let currentDay = new Date(calendarStart)
    
    while (currentDay < lastDay || weeks.length < 6) {
      const week = []
      for (let i = 0; i < 7; i++) {
        week.push(new Date(currentDay))
        currentDay.setDate(currentDay.getDate() + 1)
      }
      weeks.push(week)
      if (weeks.length >= 6 && currentDay > lastDay) break
    }

    return (
      <div className="space-y-2">
        {/* Day headers */}
        <div className="grid grid-cols-7 gap-2 mb-2">
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
            <div key={day} className="text-center text-xs font-semibold text-gray-600 py-2">
              {day}
            </div>
          ))}
        </div>
        
        {/* Calendar grid */}
        {weeks.map((week, weekIndex) => (
          <div key={weekIndex} className="grid grid-cols-7 gap-2">
            {week.map((day, dayIndex) => {
              const dayMeetings = getMeetingsForDay(day)
              const isToday = day.toDateString() === new Date().toDateString()
              const isCurrentMonth = day.getMonth() === start.getMonth()
              
              return (
                <div
                  key={dayIndex}
                  onClick={() => handleDayClick(day)}
                  className={`min-h-24 border rounded p-2 cursor-pointer hover:bg-blue-50 hover:border-blue-300 transition-colors ${
                    isToday 
                      ? 'bg-blue-50 border-blue-300' 
                      : isCurrentMonth 
                        ? 'bg-white border-gray-200' 
                        : 'bg-gray-50 border-gray-100'
                  }`}
                  title={`Click to view ${day.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}`}
                >
                  <div className={`text-xs font-medium mb-1 ${isCurrentMonth ? 'text-gray-900' : 'text-gray-400'}`}>
                    {day.getDate()}
                  </div>
                  <div className="space-y-1" onClick={(e) => e.stopPropagation()}>
                    {dayMeetings.slice(0, 2).map(meeting => (
                      <div
                        key={meeting.id}
                        onClick={() => handleMeetingClick(meeting)}
                        className={`text-xs p-1 rounded transition-shadow truncate ${getStatusColor(meeting.status, meeting)} ${
                          meeting.is_birthday ? 'cursor-default' : 'cursor-pointer hover:shadow-sm'
                        }`}
                        title={meeting.title}
                      >
                        <div className="truncate">
                          {meeting.is_birthday ? '🎂' : formatTime(meeting.start_time)}
                        </div>
                      </div>
                    ))}
                    {dayMeetings.length > 2 && (
                      <div className="text-xs text-gray-500 text-center">
                        +{dayMeetings.length - 2}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        ))}
      </div>
    )
  }

  if (loading) {
    return <div className="text-center py-12">Loading calendar...</div>
  }

  const rangeMeetings = getMeetingsForRange()

  return (
    <div className="h-full flex flex-col">
      {selectedMeeting?.is_birthday ? (
        <BirthdayDetail 
          birthday={selectedMeeting.birthday_data || selectedMeeting}
          meeting={selectedMeeting.birthday_data ? selectedMeeting : null}
          onClose={handleCloseDetail}
          employees={employees}
        />
      ) : selectedMeeting && isMeetingInProgress(selectedMeeting) ? (
        <LiveMeetingView 
          meeting={selectedMeeting} 
          onClose={handleCloseDetail}
          employees={employees}
        />
      ) : selectedMeeting ? (
        <MeetingDetail 
          meeting={selectedMeeting} 
          onClose={handleCloseDetail}
          employees={employees}
        />
      ) : (
        <>
          {/* Header Controls */}
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex gap-2">
                <button
                  onClick={() => setViewMode('day')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    viewMode === 'day'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  Day
                </button>
                <button
                  onClick={() => setViewMode('week')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    viewMode === 'week'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  Week
                </button>
                <button
                  onClick={() => setViewMode('month')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    viewMode === 'month'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  Month
                </button>
              </div>
              
              <div className="flex items-center gap-2">
                <button
                  onClick={() => navigateDate(-1)}
                  className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                >
                  ←
                </button>
                <button
                  onClick={goToToday}
                  className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors text-sm font-medium"
                >
                  Today
                </button>
                <button
                  onClick={() => navigateDate(1)}
                  className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                >
                  →
                </button>
              </div>
            </div>
            
            <div className="text-sm text-gray-600">
              {viewMode === 'day' && formatDateLong(currentDate)}
              {viewMode === 'week' && (() => {
                const { start } = getDateRange()
                const end = new Date(start)
                end.setDate(end.getDate() + 6)
                return `${formatDate(start)} - ${formatDate(end)}`
              })()}
              {viewMode === 'month' && currentDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto">
            {viewMode === 'day' && renderDayView()}
            {viewMode === 'week' && renderWeekView()}
            {viewMode === 'month' && renderMonthView()}
          </div>
        </>
      )}
    </div>
  )
}

export default CalendarView
