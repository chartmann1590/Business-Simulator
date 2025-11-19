import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

function PetCareLog() {
  const [careLogs, setCareLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all') // 'all', 'feed', 'play', 'pet'
  const [selectedEmployee, setSelectedEmployee] = useState(null)
  const [selectedPet, setSelectedPet] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    fetchCareLogs()
    // Refresh every 10 seconds to see new care activities
    const interval = setInterval(fetchCareLogs, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchCareLogs = async () => {
    try {
      const response = await fetch('/api/pets/care-log?limit=100')
      if (response.ok) {
        const data = await response.json()
        setCareLogs(data || [])
        setLoading(false)
      } else {
        console.error('Failed to fetch care logs:', response.status, response.statusText)
        setLoading(false)
      }
    } catch (error) {
      console.error('Error fetching care logs:', error)
      setLoading(false)
    }
  }


  const getActionIcon = (action) => {
    switch (action) {
      case 'feed': return '🍖'
      case 'play': return '🎾'
      case 'pet': return '❤️'
      default: return '🐾'
    }
  }

  const getActionColor = (action) => {
    switch (action) {
      case 'feed': return 'bg-green-100 text-green-800 border-green-300'
      case 'play': return 'bg-purple-100 text-purple-800 border-purple-300'
      case 'pet': return 'bg-pink-100 text-pink-800 border-pink-300'
      default: return 'bg-gray-100 text-gray-800 border-gray-300'
    }
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown'
    const date = new Date(dateString)
    return date.toLocaleString()
  }

  const filteredLogs = careLogs.filter(log => {
    if (filter !== 'all' && log.care_action !== filter) return false
    if (selectedEmployee && log.employee_id !== selectedEmployee) return false
    if (selectedPet && log.pet_id !== selectedPet) return false
    return true
  })

  // Get unique employees and pets for filters
  const uniqueEmployees = [...new Set(careLogs.map(log => ({
    id: log.employee_id,
    name: log.employee_name,
    title: log.employee_title
  })))].filter((emp, index, self) => 
    index === self.findIndex(e => e.id === emp.id)
  )

  const uniquePets = [...new Set(careLogs.map(log => ({
    id: log.pet_id,
    name: log.pet_name,
    type: log.pet_type
  })))].filter((pet, index, self) => 
    index === self.findIndex(p => p.id === pet.id)
  )

  // Calculate statistics
  const stats = {
    totalCares: careLogs.length,
    feeds: careLogs.filter(l => l.care_action === 'feed').length,
    plays: careLogs.filter(l => l.care_action === 'play').length,
    pets: careLogs.filter(l => l.care_action === 'pet').length,
    uniqueEmployees: uniqueEmployees.length,
    uniquePets: uniquePets.length
  }

  // Top caregivers
  const employeeCareCounts = {}
  careLogs.forEach(log => {
    const key = `${log.employee_id}-${log.employee_name}`
    if (!employeeCareCounts[key]) {
      employeeCareCounts[key] = {
        employee_id: log.employee_id,
        employee_name: log.employee_name,
        employee_title: log.employee_title,
        count: 0,
        feeds: 0,
        plays: 0,
        pets: 0
      }
    }
    employeeCareCounts[key].count++
    employeeCareCounts[key][`${log.care_action}s`]++
  })
  const topCaregivers = Object.values(employeeCareCounts)
    .sort((a, b) => b.count - a.count)
    .slice(0, 10)

  if (loading) {
    return (
      <div className="p-8">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          <p className="mt-4 text-gray-600">Loading pet care log...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-4xl font-bold text-gray-900 mb-2">🐾 Pet Care Log</h1>
            <p className="text-gray-600">Track which employees are caring for office pets</p>
          </div>
          <button
            onClick={() => navigate('/pet-care')}
            className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors"
          >
            🎮 Play Pet Care Game
          </button>
        </div>

        {/* Statistics */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 mb-6">
          <div className="bg-white rounded-lg p-4 shadow-md text-center">
            <div className="text-2xl font-bold text-blue-600">{stats.totalCares}</div>
            <div className="text-sm text-gray-600">Total Cares</div>
          </div>
          <div className="bg-white rounded-lg p-4 shadow-md text-center">
            <div className="text-2xl font-bold text-green-600">{stats.feeds}</div>
            <div className="text-sm text-gray-600">🍖 Feeds</div>
          </div>
          <div className="bg-white rounded-lg p-4 shadow-md text-center">
            <div className="text-2xl font-bold text-purple-600">{stats.plays}</div>
            <div className="text-sm text-gray-600">🎾 Plays</div>
          </div>
          <div className="bg-white rounded-lg p-4 shadow-md text-center">
            <div className="text-2xl font-bold text-pink-600">{stats.pets}</div>
            <div className="text-sm text-gray-600">❤️ Pets</div>
          </div>
          <div className="bg-white rounded-lg p-4 shadow-md text-center">
            <div className="text-2xl font-bold text-orange-600">{stats.uniqueEmployees}</div>
            <div className="text-sm text-gray-600">Employees</div>
          </div>
          <div className="bg-white rounded-lg p-4 shadow-md text-center">
            <div className="text-2xl font-bold text-yellow-600">{stats.uniquePets}</div>
            <div className="text-sm text-gray-600">Pets</div>
          </div>
          <div className="bg-white rounded-lg p-4 shadow-md text-center">
            <div className="text-2xl font-bold text-indigo-600">{topCaregivers[0]?.count || 0}</div>
            <div className="text-sm text-gray-600">Top Caregiver</div>
          </div>
        </div>

        {/* Top Caregivers */}
        {topCaregivers.length > 0 && (
          <div className="bg-white rounded-lg p-4 shadow-md mb-6">
            <h2 className="text-lg font-semibold mb-3">🏆 Top Caregivers</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {topCaregivers.map((caregiver, index) => (
                <div
                  key={caregiver.employee_id}
                  className="border rounded-lg p-3 hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => {
                    setSelectedEmployee(selectedEmployee === caregiver.employee_id ? null : caregiver.employee_id)
                    setSelectedPet(null)
                  }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-gray-700">
                      #{index + 1} {caregiver.employee_name.split(' ')[0]}
                    </span>
                    <span className="text-xs text-gray-500">{caregiver.count}</span>
                  </div>
                  <div className="text-xs text-gray-600">{caregiver.employee_title}</div>
                  <div className="flex gap-1 mt-2 text-xs">
                    <span className="text-green-600">🍖 {caregiver.feeds}</span>
                    <span className="text-purple-600">🎾 {caregiver.plays}</span>
                    <span className="text-pink-600">❤️ {caregiver.pets}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="bg-white rounded-lg p-4 shadow-md mb-6">
          <div className="flex flex-wrap gap-4 items-center">
            <div>
              <label className="text-sm font-medium text-gray-700 mr-2">Action:</label>
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="px-3 py-1 border border-gray-300 rounded-lg"
              >
                <option value="all">All Actions</option>
                <option value="feed">🍖 Feed</option>
                <option value="play">🎾 Play</option>
                <option value="pet">❤️ Pet</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 mr-2">Employee:</label>
              <select
                value={selectedEmployee || ''}
                onChange={(e) => setSelectedEmployee(e.target.value ? parseInt(e.target.value) : null)}
                className="px-3 py-1 border border-gray-300 rounded-lg"
              >
                <option value="">All Employees</option>
                {uniqueEmployees.map(emp => (
                  <option key={emp.id} value={emp.id}>
                    {emp.name} - {emp.title}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 mr-2">Pet:</label>
              <select
                value={selectedPet || ''}
                onChange={(e) => setSelectedPet(e.target.value ? parseInt(e.target.value) : null)}
                className="px-3 py-1 border border-gray-300 rounded-lg"
              >
                <option value="">All Pets</option>
                {uniquePets.map(pet => (
                  <option key={pet.id} value={pet.id}>
                    {pet.name} ({pet.type})
                  </option>
                ))}
              </select>
            </div>
            {(selectedEmployee || selectedPet || filter !== 'all') && (
              <button
                onClick={() => {
                  setFilter('all')
                  setSelectedEmployee(null)
                  setSelectedPet(null)
                }}
                className="px-3 py-1 bg-gray-200 hover:bg-gray-300 rounded-lg text-sm"
              >
                Clear Filters
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Care Log List */}
      {filteredLogs.length === 0 ? (
        <div className="bg-white rounded-lg p-8 shadow-md text-center">
          <p className="text-gray-600">No pet care activities found.</p>
          {careLogs.length === 0 && (
            <p className="text-sm text-gray-500 mt-2">
              Employees will automatically care for pets when they need attention. Check back soon!
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {filteredLogs.map(log => (
            <div
              key={log.id}
              className="bg-white rounded-lg p-6 shadow-md hover:shadow-lg transition-shadow"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-4">
                  <div className={`text-3xl ${getActionColor(log.care_action)} px-4 py-2 rounded-lg border-2`}>
                    {getActionIcon(log.care_action)}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-lg font-semibold text-gray-900">
                        {log.employee_name}
                      </h3>
                      <span className="text-sm text-gray-500">{log.employee_title}</span>
                    </div>
                    <div className="text-sm text-gray-600 mt-1">
                      {log.care_action === 'feed' && 'fed'}
                      {log.care_action === 'play' && 'played with'}
                      {log.care_action === 'pet' && 'petted'}
                      {' '}
                      <span className="font-medium">{log.pet_name}</span>
                      {' '}
                      <span className="text-gray-500">({log.pet_type})</span>
                    </div>
                  </div>
                </div>
                <div className="text-sm text-gray-500">
                  {formatDate(log.created_at)}
                </div>
              </div>

              {/* Stats Changes */}
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="bg-blue-50 rounded-lg p-3">
                  <div className="text-xs text-gray-600 mb-1">😊 Happiness</div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{log.pet_happiness_before?.toFixed(1) || 'N/A'}</span>
                    <span className="text-gray-400">→</span>
                    <span className="text-sm font-bold text-blue-600">{log.pet_happiness_after?.toFixed(1) || 'N/A'}</span>
                    {log.pet_happiness_after > log.pet_happiness_before && (
                      <span className="text-xs text-green-600">↑</span>
                    )}
                  </div>
                </div>
                <div className="bg-orange-50 rounded-lg p-3">
                  <div className="text-xs text-gray-600 mb-1">🍖 Hunger</div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{log.pet_hunger_before?.toFixed(1) || 'N/A'}</span>
                    <span className="text-gray-400">→</span>
                    <span className="text-sm font-bold text-orange-600">{log.pet_hunger_after?.toFixed(1) || 'N/A'}</span>
                    {log.pet_hunger_after < log.pet_hunger_before && (
                      <span className="text-xs text-green-600">↓</span>
                    )}
                  </div>
                </div>
                <div className="bg-yellow-50 rounded-lg p-3">
                  <div className="text-xs text-gray-600 mb-1">⚡ Energy</div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{log.pet_energy_before?.toFixed(1) || 'N/A'}</span>
                    <span className="text-gray-400">→</span>
                    <span className="text-sm font-bold text-yellow-600">{log.pet_energy_after?.toFixed(1) || 'N/A'}</span>
                    {log.pet_energy_after > log.pet_energy_before && (
                      <span className="text-xs text-green-600">↑</span>
                    )}
                  </div>
                </div>
              </div>

              {/* AI Reasoning */}
              {log.ai_reasoning && (
                <div className="bg-gray-50 rounded-lg p-3 border-l-4 border-blue-500">
                  <div className="text-xs font-medium text-gray-700 mb-1">🤖 AI Reasoning:</div>
                  <div className="text-sm text-gray-600 italic">{log.ai_reasoning}</div>
                </div>
              )}

              {/* Quick Actions */}
              <div className="mt-4 flex gap-2">
                <button
                  onClick={() => navigate(`/employees/${log.employee_id}`)}
                  className="text-xs px-3 py-1 bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-lg transition-colors"
                >
                  View Employee
                </button>
                <button
                  onClick={() => navigate(`/office-view?pet=${log.pet_id}&floor=1`)}
                  className="text-xs px-3 py-1 bg-green-100 hover:bg-green-200 text-green-700 rounded-lg transition-colors"
                >
                  View Pet in Office
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default PetCareLog


