import { useState, useEffect } from 'react'

function BirthdayDetail({ birthday, meeting, onClose, employees = [] }) {
  const [meetingData, setMeetingData] = useState(meeting)
  const [loading, setLoading] = useState(false)
  const [allEmployees, setAllEmployees] = useState(employees)

  useEffect(() => {
    if (meeting?.id) {
      fetchMeetingDetails()
      const interval = setInterval(fetchMeetingDetails, 5000) // Refresh every 5 seconds
      return () => clearInterval(interval)
    }
  }, [meeting?.id])
  
  // Fetch all employees if we don't have them all
  useEffect(() => {
    if (meetingData && meetingData.attendee_ids && allEmployees.length < meetingData.attendee_ids.length) {
      fetch('/api/employees')
        .then(res => res.json())
        .then(data => {
          if (data && Array.isArray(data)) {
            setAllEmployees(data)
          }
        })
        .catch(err => console.error('Error fetching employees:', err))
    }
  }, [meetingData, allEmployees.length])

  const fetchMeetingDetails = async () => {
    if (!meeting?.id) return
    try {
      setLoading(true)
      const response = await fetch(`/api/meetings/${meeting.id}`)
      if (response.ok) {
        const data = await response.json()
        setMeetingData(data)
      }
    } catch (error) {
      console.error('Error fetching meeting details:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatTime = (timeString) => {
    if (!timeString) return ''
    const date = new Date(timeString)
    return date.toLocaleString('en-US', { 
      weekday: 'short',
      month: 'short', 
      day: 'numeric',
      hour: '2-digit', 
      minute: '2-digit' 
    })
  }

  // Get meeting metadata for birthday party details
  const metadata = meetingData?.meeting_metadata || {}
  const isBirthdayParty = metadata.is_birthday_party || false
  const partyRoom = metadata.room_name || metadata.party_room || 'Breakroom'
  const partyFloor = metadata.party_floor || 1
  const age = metadata.age
  const specialNotes = metadata.special_notes || []

  // Get all attendees (15 total: 14 + birthday person)
  // Use attendees from API if available, otherwise build from attendee_ids
  let attendees = []
  if (meetingData?.attendees && meetingData.attendees.length > 0) {
    // Use attendees from API (most reliable)
    attendees = meetingData.attendees
  } else if (meetingData?.attendee_ids && meetingData.attendee_ids.length > 0) {
    // Build from attendee_ids using allEmployees (which should have all employees)
    attendees = meetingData.attendee_ids.map(id => {
      const emp = allEmployees.find(e => e.id === id)
      return emp ? {
        id: emp.id,
        name: emp.name,
        title: emp.title,
        avatar_path: emp.avatar_path
      } : null
    }).filter(Boolean)
  }
  
  // If we still don't have all attendees, the API should provide them
  // The meeting detail API endpoint returns all attendees

  // Find birthday person (organizer)
  const birthdayPerson = meetingData ? 
    (attendees.find(a => a.id === meetingData.organizer_id) || 
     allEmployees.find(e => e.id === meetingData.organizer_id)) :
    (birthday ? allEmployees.find(e => e.id === birthday.employee_id) : null)

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="border-b border-gray-200 p-6 bg-gradient-to-r from-pink-50 to-purple-50 sticky top-0 z-10 shadow-sm">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h2 className="text-2xl font-bold text-gray-900">
                🎂 {birthdayPerson?.name || birthday?.employee_name || 'Birthday'} Party
              </h2>
              <span className="px-3 py-1 rounded-full text-sm font-medium bg-pink-100 text-pink-800 border border-pink-200">
                Birthday Party
              </span>
            </div>
            {age && (
              <p className="text-lg text-gray-700 mb-3">
                Turning {age} years old! 🎉
              </p>
            )}
            {meetingData && (
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <span className="flex items-center gap-1">
                  <span>🕐</span>
                  {formatTime(meetingData.start_time)} - {formatTime(meetingData.end_time)}
                </span>
                <span className="flex items-center gap-1">
                  <span>📍</span>
                  {partyRoom} on Floor {partyFloor}
                </span>
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors font-medium flex items-center gap-2"
            title="Close birthday details"
          >
            <span>✕</span>
            <span>Close</span>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Party Information */}
          {meetingData && (
            <div className="bg-pink-50 border-2 border-pink-200 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <span>🎉</span>
                Party Details
              </h3>
              <div className="space-y-3 text-sm">
                <div className="flex items-start gap-3">
                  <span className="font-medium text-gray-700 min-w-[100px]">Time:</span>
                  <span className="text-gray-900">
                    {formatTime(meetingData.start_time)} - {formatTime(meetingData.end_time)}
                  </span>
                </div>
                <div className="flex items-start gap-3">
                  <span className="font-medium text-gray-700 min-w-[100px]">Location:</span>
                  <span className="text-gray-900">
                    {partyRoom} on Floor {partyFloor}
                  </span>
                </div>
                <div className="flex items-start gap-3">
                  <span className="font-medium text-gray-700 min-w-[100px]">Attendees:</span>
                  <span className="text-gray-900">
                    {attendees.length} people total ({meetingData?.attendee_ids?.length || attendees.length} expected)
                    {attendees.length === 15 ? ' ✅' : attendees.length < 15 ? ' ⚠️' : ''}
                    {attendees.length > 0 && ` - including ${birthdayPerson?.name || 'birthday person'}`}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Special Notes */}
          {specialNotes.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">✨ Special Notes</h3>
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <ul className="space-y-2">
                  {specialNotes.map((note, index) => (
                    <li key={index} className="text-sm text-gray-700">
                      {note}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Attendees */}
          {meetingData && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                👥 Party Attendees ({attendees.length} of {meetingData?.attendee_ids?.length || 15} people)
                {attendees.length === 15 && <span className="ml-2 text-green-600">✅ All 15 attendees</span>}
                {attendees.length < 15 && <span className="ml-2 text-orange-600">⚠️ Missing {15 - attendees.length} attendee(s)</span>}
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {attendees.map(attendee => {
                  const isBirthdayPerson = attendee.id === meetingData.organizer_id
                  return (
                    <div
                      key={attendee.id}
                      className={`flex items-center gap-3 px-4 py-3 rounded-lg ${
                        isBirthdayPerson 
                          ? 'bg-pink-100 border-2 border-pink-300' 
                          : 'bg-gray-50 border border-gray-200'
                      }`}
                    >
                      {attendee.avatar_path ? (
                        <img
                          src={`/avatars/${attendee.avatar_path}`}
                          alt={attendee.name}
                          className="w-10 h-10 rounded-full"
                          onError={(e) => {
                            e.target.style.display = 'none'
                            e.target.nextSibling.style.display = 'flex'
                          }}
                        />
                      ) : null}
                      <span
                        className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium ${
                          isBirthdayPerson 
                            ? 'bg-pink-500 text-white' 
                            : 'bg-blue-500 text-white'
                        }`}
                        style={{ display: attendee.avatar_path ? 'none' : 'flex' }}
                      >
                        {attendee.name.charAt(0)}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-medium truncate ${
                          isBirthdayPerson ? 'text-pink-900' : 'text-gray-900'
                        }`}>
                          {attendee.name}
                          {isBirthdayPerson && <span className="ml-1">🎂</span>}
                        </p>
                        <p className="text-xs text-gray-500 truncate">{attendee.title}</p>
                      </div>
                    </div>
                  )
                })}
              </div>
              {attendees.length === 15 ? (
                <div className="bg-green-50 border border-green-200 rounded-lg p-3 mt-2">
                  <p className="text-sm text-green-800 font-medium">
                    ✅ All 15 attendees confirmed! (14 colleagues + {birthdayPerson?.name || 'birthday person'})
                  </p>
                </div>
              ) : meetingData?.attendee_ids?.length === 15 && attendees.length < 15 ? (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mt-2">
                  <p className="text-sm text-yellow-800">
                    ⚠️ Expected 15 attendees but only showing {attendees.length}. Loading employee data...
                  </p>
                </div>
              ) : null}
            </div>
          )}
          
          {!meetingData && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <p className="text-sm text-gray-700">
                Birthday party meeting details will be available once the party is scheduled.
              </p>
            </div>
          )}

          {/* Agenda/Outline */}
          {meetingData?.outline && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">🎊 Party Schedule</h3>
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <div className="text-sm text-gray-700 space-y-1">
                  {meetingData.outline.split('\n').map((line, index) => {
                    if (!line.trim()) return <div key={index} className="h-2" />
                    return (
                      <div key={index} className="pl-4">
                        {line.trim()}
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Description */}
          {meetingData?.description && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">📝 Party Information</h3>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="text-sm text-gray-700 whitespace-pre-wrap">
                  {meetingData.description}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default BirthdayDetail

