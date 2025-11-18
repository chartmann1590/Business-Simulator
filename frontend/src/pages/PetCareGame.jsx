import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

function PetCareGame() {
  const [pets, setPets] = useState([])
  const [selectedPet, setSelectedPet] = useState(null)
  const [loading, setLoading] = useState(true)
  const [gameStats, setGameStats] = useState({
    totalCares: 0,
    totalFeeds: 0,
    totalPlays: 0,
    totalPets: 0
  })
  const [notifications, setNotifications] = useState([])
  const navigate = useNavigate()

  // Pet stats structure: { petId: { happiness: 50-100, hunger: 0-100, energy: 0-100, lastCare: null } }
  const [petStats, setPetStats] = useState({})

  useEffect(() => {
    fetchPets()
    // Load game stats from localStorage
    const savedStats = localStorage.getItem('petCareGameStats')
    if (savedStats) {
      setGameStats(JSON.parse(savedStats))
    }
    // Load pet stats from localStorage
    const savedPetStats = localStorage.getItem('petCareGamePetStats')
    if (savedPetStats) {
      setPetStats(JSON.parse(savedPetStats))
    }
  }, [])

  const fetchPets = async () => {
    try {
      const response = await fetch('/api/pets')
      if (response.ok) {
        const petsData = await response.json()
        setPets(petsData)
        
        // Initialize stats for new pets
        setPetStats(prev => {
          const updated = { ...prev }
          petsData.forEach(pet => {
            if (!updated[pet.id]) {
              updated[pet.id] = {
                happiness: 75 + Math.floor(Math.random() * 25), // 75-100
                hunger: 30 + Math.floor(Math.random() * 40), // 30-70
                energy: 60 + Math.floor(Math.random() * 40), // 60-100
                lastCare: null
              }
            }
          })
          return updated
        })
        setLoading(false)
      }
    } catch (error) {
      console.error('Error fetching pets:', error)
      setLoading(false)
    }
  }

  // Save stats to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem('petCareGameStats', JSON.stringify(gameStats))
  }, [gameStats])

  useEffect(() => {
    localStorage.setItem('petCareGamePetStats', JSON.stringify(petStats))
  }, [petStats])

  // Degrade pet stats over time
  useEffect(() => {
    const interval = setInterval(() => {
      setPetStats(prev => {
        const updated = { ...prev }
        Object.keys(updated).forEach(petId => {
          const stats = updated[petId]
          // Hunger increases (pets get hungrier)
          stats.hunger = Math.min(100, stats.hunger + Math.random() * 2)
          // Energy decreases (pets get tired)
          stats.energy = Math.max(0, stats.energy - Math.random() * 1.5)
          // Happiness decreases if hunger is high or energy is low
          if (stats.hunger > 70 || stats.energy < 30) {
            stats.happiness = Math.max(0, stats.happiness - Math.random() * 1)
          }
        })
        return updated
      })
    }, 5000) // Update every 5 seconds

    return () => clearInterval(interval)
  }, [])

  const addNotification = (message, type = 'info') => {
    const id = Date.now()
    setNotifications(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id))
    }, 3000)
  }

  const feedPet = (pet) => {
    if (!petStats[pet.id]) return
    
    const stats = petStats[pet.id]
    const hungerReduction = 30 + Math.floor(Math.random() * 20) // 30-50
    const happinessIncrease = 5 + Math.floor(Math.random() * 10) // 5-15
    
    setPetStats(prev => ({
      ...prev,
      [pet.id]: {
        ...prev[pet.id],
        hunger: Math.max(0, stats.hunger - hungerReduction),
        happiness: Math.min(100, stats.happiness + happinessIncrease),
        lastCare: new Date().toISOString()
      }
    }))

    setGameStats(prev => ({
      ...prev,
      totalFeeds: prev.totalFeeds + 1,
      totalCares: prev.totalCares + 1
    }))

    const messages = [
      `🍖 ${pet.name} loved the food!`,
      `🍖 ${pet.name} is happily eating!`,
      `🍖 ${pet.name} is munching away!`,
      `🍖 ${pet.name} looks satisfied!`
    ]
    addNotification(messages[Math.floor(Math.random() * messages.length)], 'success')
  }

  const playWithPet = (pet) => {
    if (!petStats[pet.id]) return
    
    const stats = petStats[pet.id]
    const energyReduction = 15 + Math.floor(Math.random() * 15) // 15-30
    const happinessIncrease = 10 + Math.floor(Math.random() * 15) // 10-25
    
    if (stats.energy < energyReduction) {
      addNotification(`😴 ${pet.name} is too tired to play right now!`, 'warning')
      return
    }

    setPetStats(prev => ({
      ...prev,
      [pet.id]: {
        ...prev[pet.id],
        energy: Math.max(0, stats.energy - energyReduction),
        happiness: Math.min(100, stats.happiness + happinessIncrease),
        lastCare: new Date().toISOString()
      }
    }))

    setGameStats(prev => ({
      ...prev,
      totalPlays: prev.totalPlays + 1,
      totalCares: prev.totalCares + 1
    }))

    const messages = [
      `🎾 ${pet.name} is having so much fun playing!`,
      `🎾 ${pet.name} is running around excitedly!`,
      `🎾 ${pet.name} is wagging their tail!`,
      `🎾 ${pet.name} is jumping with joy!`
    ]
    addNotification(messages[Math.floor(Math.random() * messages.length)], 'success')
  }

  const petPet = (pet) => {
    if (!petStats[pet.id]) return
    
    const stats = petStats[pet.id]
    const happinessIncrease = 5 + Math.floor(Math.random() * 10) // 5-15
    const energyIncrease = 2 + Math.floor(Math.random() * 5) // 2-7
    
    setPetStats(prev => ({
      ...prev,
      [pet.id]: {
        ...prev[pet.id],
        happiness: Math.min(100, stats.happiness + happinessIncrease),
        energy: Math.min(100, stats.energy + energyIncrease),
        lastCare: new Date().toISOString()
      }
    }))

    setGameStats(prev => ({
      ...prev,
      totalPets: prev.totalPets + 1,
      totalCares: prev.totalCares + 1
    }))

    const messages = [
      `❤️ ${pet.name} is purring/whining happily!`,
      `❤️ ${pet.name} loves the attention!`,
      `❤️ ${pet.name} is cuddling up!`,
      `❤️ ${pet.name} looks so content!`
    ]
    addNotification(messages[Math.floor(Math.random() * messages.length)], 'success')
  }

  const getStatColor = (value, reverse = false) => {
    if (reverse) {
      // For hunger (lower is better)
      if (value < 30) return 'text-green-600'
      if (value < 60) return 'text-yellow-600'
      return 'text-red-600'
    } else {
      // For happiness and energy (higher is better)
      if (value > 70) return 'text-green-600'
      if (value > 40) return 'text-yellow-600'
      return 'text-red-600'
    }
  }

  const getStatBarColor = (value, reverse = false) => {
    if (reverse) {
      if (value < 30) return 'bg-green-500'
      if (value < 60) return 'bg-yellow-500'
      return 'bg-red-500'
    } else {
      if (value > 70) return 'bg-green-500'
      if (value > 40) return 'bg-yellow-500'
      return 'bg-red-500'
    }
  }

  const getPetMood = (pet) => {
    if (!petStats[pet.id]) return '😊'
    const stats = petStats[pet.id]
    if (stats.happiness > 80 && stats.hunger < 40 && stats.energy > 50) return '😄'
    if (stats.happiness > 60 && stats.hunger < 60 && stats.energy > 30) return '😊'
    if (stats.happiness < 40 || stats.hunger > 70 || stats.energy < 20) return '😢'
    return '😐'
  }

  if (loading) {
    return (
      <div className="p-8">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          <p className="mt-4 text-gray-600">Loading office pets...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-8 bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 min-h-screen">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-4xl font-bold text-gray-900 mb-2">🐾 Pet Care Game</h1>
            <p className="text-gray-600">Take care of the office pets roaming around!</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => navigate('/pet-care-log')}
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors"
            >
              📋 View Care Log
            </button>
            <button
              onClick={() => navigate('/office-view')}
              className="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg transition-colors"
            >
              ← Back to Office
            </button>
          </div>
        </div>

        {/* Game Stats */}
        <div className="bg-white rounded-lg p-4 shadow-md mb-6">
          <h2 className="text-lg font-semibold mb-3">📊 Your Stats</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{gameStats.totalCares}</div>
              <div className="text-sm text-gray-600">Total Cares</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{gameStats.totalFeeds}</div>
              <div className="text-sm text-gray-600">Feeds</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">{gameStats.totalPlays}</div>
              <div className="text-sm text-gray-600">Play Sessions</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-pink-600">{gameStats.totalPets}</div>
              <div className="text-sm text-gray-600">Pets Given</div>
            </div>
          </div>
        </div>
      </div>

      {/* Notifications */}
      <div className="fixed top-4 right-4 z-50 space-y-2">
        {notifications.map(notif => (
          <div
            key={notif.id}
            className={`px-4 py-2 rounded-lg shadow-lg animate-slide-in ${
              notif.type === 'success' ? 'bg-green-500 text-white' :
              notif.type === 'warning' ? 'bg-yellow-500 text-white' :
              'bg-blue-500 text-white'
            }`}
          >
            {notif.message}
          </div>
        ))}
      </div>

      {/* Pets Grid */}
      {pets.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg shadow-md">
          <p className="text-xl text-gray-600">No pets in the office yet! 🐾</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {pets.map(pet => {
            const stats = petStats[pet.id] || {
              happiness: 75,
              hunger: 50,
              energy: 70,
              lastCare: null
            }
            const isSelected = selectedPet?.id === pet.id

            return (
              <div
                key={pet.id}
                className={`bg-white rounded-xl shadow-lg overflow-hidden transition-all transform hover:scale-105 ${
                  isSelected ? 'ring-4 ring-blue-400' : ''
                }`}
              >
                {/* Pet Header */}
                <div className="bg-gradient-to-r from-yellow-400 to-orange-400 p-4 text-center">
                  <div className="text-4xl mb-2">{getPetMood(pet)}</div>
                  <img
                    src={pet.avatar_path}
                    alt={pet.name}
                    className="w-24 h-24 mx-auto rounded-full border-4 border-white shadow-lg object-cover mb-2"
                    onError={(e) => {
                      e.target.style.display = 'none'
                    }}
                  />
                  <h3 className="text-xl font-bold text-white">{pet.name}</h3>
                  <p className="text-sm text-white/90 capitalize">{pet.pet_type}</p>
                  {pet.personality && (
                    <p className="text-xs text-white/80 mt-1 italic">{pet.personality}</p>
                  )}
                </div>

                {/* Pet Stats */}
                <div className="p-4 space-y-3">
                  {/* Happiness */}
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="font-medium">😊 Happiness</span>
                      <span className={getStatColor(stats.happiness)}>
                        {Math.round(stats.happiness)}%
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all ${getStatBarColor(stats.happiness)}`}
                        style={{ width: `${stats.happiness}%` }}
                      />
                    </div>
                  </div>

                  {/* Hunger */}
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="font-medium">🍖 Hunger</span>
                      <span className={getStatColor(stats.hunger, true)}>
                        {Math.round(stats.hunger)}%
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all ${getStatBarColor(stats.hunger, true)}`}
                        style={{ width: `${stats.hunger}%` }}
                      />
                    </div>
                  </div>

                  {/* Energy */}
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="font-medium">⚡ Energy</span>
                      <span className={getStatColor(stats.energy)}>
                        {Math.round(stats.energy)}%
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all ${getStatBarColor(stats.energy)}`}
                        style={{ width: `${stats.energy}%` }}
                      />
                    </div>
                  </div>

                  {/* Location */}
                  <div className="text-xs text-gray-500 pt-2 border-t">
                    📍 Floor {pet.floor} • {pet.current_room || 'Unknown'}
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="p-4 bg-gray-50 space-y-2">
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      onClick={() => feedPet(pet)}
                      className="px-3 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg transition-colors text-sm font-medium shadow-md hover:shadow-lg transform hover:scale-105"
                      title="Feed the pet"
                    >
                      🍖 Feed
                    </button>
                    <button
                      onClick={() => playWithPet(pet)}
                      className="px-3 py-2 bg-purple-500 hover:bg-purple-600 text-white rounded-lg transition-colors text-sm font-medium shadow-md hover:shadow-lg transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Play with the pet"
                      disabled={stats.energy < 15}
                    >
                      🎾 Play
                    </button>
                    <button
                      onClick={() => petPet(pet)}
                      className="px-3 py-2 bg-pink-500 hover:bg-pink-600 text-white rounded-lg transition-colors text-sm font-medium shadow-md hover:shadow-lg transform hover:scale-105"
                      title="Pet and comfort the pet"
                    >
                      ❤️ Pet
                    </button>
                  </div>
                  <button
                    onClick={() => navigate(`/office-view?pet=${pet.id}&floor=${pet.floor}`)}
                    className="w-full px-3 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors text-sm font-medium shadow-md hover:shadow-lg transform hover:scale-105"
                    title="View this pet in the office"
                  >
                    🏢 View in Office
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Instructions */}
      <div className="mt-8 bg-white rounded-lg p-6 shadow-md">
        <h2 className="text-xl font-semibold mb-3">📖 How to Play</h2>
        <ul className="space-y-2 text-gray-700">
          <li>🍖 <strong>Feed:</strong> Reduces hunger and increases happiness</li>
          <li>🎾 <strong>Play:</strong> Increases happiness but uses energy (pets need energy to play!)</li>
          <li>❤️ <strong>Pet:</strong> Increases happiness and gives a small energy boost</li>
          <li>📊 Pet stats change over time - keep an eye on them!</li>
          <li>🎯 Keep all pets happy, well-fed, and energized!</li>
        </ul>
      </div>

      <style>{`
        @keyframes slide-in {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
        .animate-slide-in {
          animation: slide-in 0.3s ease-out;
        }
      `}</style>
    </div>
  )
}

export default PetCareGame

