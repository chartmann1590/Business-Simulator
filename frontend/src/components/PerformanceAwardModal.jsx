import { useState, useEffect } from 'react'
import { getAvatarPath } from '../utils/avatarMapper'

function PerformanceAwardModal({ employeeId, employee, isOpen, onClose }) {
  const [awardData, setAwardData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (isOpen && employeeId && employee?.has_performance_award) {
      fetchAwardMessage()
    }
  }, [isOpen, employeeId])

  useEffect(() => {
    // Close modal on escape key
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  const fetchAwardMessage = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/employees/${employeeId}/award-message`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data = await response.json()
      setAwardData(data)
    } catch (err) {
      console.error('Error fetching award message:', err)
      setError('Failed to load award message. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div 
        className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="bg-gradient-to-r from-yellow-400 via-amber-400 to-yellow-500 p-6 rounded-t-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="text-6xl">🏆</div>
              <div>
                <h2 className="text-3xl font-bold text-white">Performance Award</h2>
                <p className="text-yellow-100 text-lg mt-1">Outstanding Achievement</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-white hover:text-yellow-100 transition-colors p-2"
              aria-label="Close"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-yellow-500 mb-4"></div>
              <p className="text-gray-600">Generating congratulatory message...</p>
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <p className="text-red-600 mb-4">{error}</p>
              <button
                onClick={fetchAwardMessage}
                className="px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 transition-colors"
              >
                Retry
              </button>
            </div>
          ) : awardData ? (
            <>
              {/* Employee Info */}
              <div className="flex items-center gap-4 mb-6 pb-6 border-b border-gray-200">
                {employee && (
                  <>
                    <img
                      src={getAvatarPath(employee)}
                      alt={employee.name}
                      className="w-20 h-20 rounded-full object-cover border-4 border-yellow-400"
                      onError={(e) => {
                        e.target.src = '/avatars/office_char_01_manager.png'
                      }}
                    />
                    <div>
                      <h3 className="text-2xl font-bold text-gray-900">{awardData.employee_name}</h3>
                      <p className="text-gray-600">{employee.title}</p>
                      <p className="text-sm text-gray-500 mt-1">
                        {awardData.award_wins === 1 
                          ? "First time award winner!" 
                          : `${awardData.award_wins} time${awardData.award_wins > 1 ? 's' : ''} winning this award!`}
                      </p>
                    </div>
                  </>
                )}
              </div>

              {/* Rating Badge */}
              <div className="flex items-center justify-center mb-6">
                <div className="bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-300 rounded-lg px-6 py-3">
                  <div className="flex items-center gap-3">
                    <span className="text-3xl">⭐</span>
                    <div>
                      <p className="text-sm text-gray-600">Performance Rating</p>
                      <p className="text-3xl font-bold text-green-700">{awardData.rating.toFixed(1)}/5.0</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Manager Message */}
              <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border-l-4 border-blue-500 rounded-lg p-6 mb-6">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0">
                    <div className="w-12 h-12 bg-blue-500 rounded-full flex items-center justify-center text-white font-bold text-lg">
                      {awardData.manager_name.split(' ').map(n => n[0]).join('').toUpperCase()}
                    </div>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <p className="font-semibold text-gray-900">{awardData.manager_name}</p>
                      <span className="text-sm text-gray-500">•</span>
                      <p className="text-sm text-gray-600">{awardData.manager_title}</p>
                    </div>
                    <p className="text-gray-700 leading-relaxed italic text-lg">
                      "{awardData.message}"
                    </p>
                  </div>
                </div>
              </div>

              {/* Achievement Stats */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 rounded-lg p-4 text-center">
                  <p className="text-sm text-gray-600 mb-1">Award Wins</p>
                  <p className="text-2xl font-bold text-yellow-600">{awardData.award_wins}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-4 text-center">
                  <p className="text-sm text-gray-600 mb-1">Current Rating</p>
                  <p className="text-2xl font-bold text-green-600">{awardData.rating.toFixed(1)}</p>
                </div>
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-6 py-4 rounded-b-lg border-t border-gray-200">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 transition-colors font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

export default PerformanceAwardModal

