import { useState, useEffect } from 'react'
import { apiGet } from '../utils/api'

function TrainingDetailModal({ employeeId, employeeName, isOpen, onClose, selectedSession = null }) {
  const [trainingData, setTrainingData] = useState(null)
  const [trainingMaterial, setTrainingMaterial] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (isOpen && employeeId) {
      fetchTrainingData()
    }
  }, [isOpen, employeeId])

  const fetchTrainingData = async () => {
    setLoading(true)
    try {
      // Get employee training summary
      const trainingResult = await apiGet(`/api/employees/${employeeId}/training`)
      const training = trainingResult.data || {}
      setTrainingData(training)

      // Get training material - prioritize selected session, then current session, then recent sessions
      let materialId = null
      if (selectedSession && selectedSession.training_material_id) {
        // Use the selected session's material
        materialId = selectedSession.training_material_id
      } else if (training.current_session && training.current_session.training_material_id) {
        materialId = training.current_session.training_material_id
      } else if (training.recent_sessions && training.recent_sessions.length > 0) {
        // Get material for most recent session
        const recentSession = training.recent_sessions[0]
        if (recentSession.training_material_id) {
          materialId = recentSession.training_material_id
        }
      }
      
      if (materialId) {
        try {
          const materialResult = await apiGet(`/api/training/materials/${materialId}`)
          setTrainingMaterial(materialResult.data || null)
        } catch (error) {
          console.error('Error fetching training material:', error)
        }
      }
    } catch (error) {
      console.error('Error fetching training data:', error)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) {
    return null
  }

  // Use selected session if provided, otherwise use current session or most recent
  const displaySession = selectedSession || trainingData?.current_session || (trainingData?.recent_sessions && trainingData.recent_sessions[0])
  const isCurrentSession = !selectedSession && trainingData?.current_session && displaySession?.id === trainingData.current_session.id

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-75" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-2xl w-[90vw] max-w-4xl h-[85vh] max-h-[85vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-6 py-4 flex items-center justify-between border-b border-blue-800">
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center text-blue-600 font-bold text-xl">
              📚
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white">{employeeName}'s Training</h2>
              <p className="text-sm text-blue-100">
                {isCurrentSession ? 'Currently in Training' : selectedSession ? 'Training Session Details' : 'Training History'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-white hover:text-gray-200 transition-colors p-2 hover:bg-blue-800 rounded"
            title="Close"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Current/Recent Session Info */}
              {displaySession && (
                <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-6 border border-blue-200">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <span className="text-sm font-medium text-blue-800 bg-blue-100 px-3 py-1 rounded-full">
                          {isCurrentSession ? 'Active Training' : selectedSession ? 'Completed Training' : 'Recent Training'}
                        </span>
                        {isCurrentSession && (
                          <span className="flex items-center text-sm text-blue-700">
                            <div className="animate-pulse w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
                            In Progress
                          </span>
                        )}
                      </div>
                      <h3 className="text-2xl font-bold text-gray-900 mb-2">
                        {displaySession.topic}
                      </h3>
                      <div className="grid grid-cols-2 gap-4 mt-4 text-sm">
                        <div>
                          <span className="text-gray-600">Room:</span>
                          <span className="ml-2 font-medium text-gray-900">{displaySession.room}</span>
                        </div>
                        {displaySession.start_time && (
                          <div>
                            <span className="text-gray-600">Started:</span>
                            <span className="ml-2 font-medium text-gray-900">
                              {new Date(displaySession.start_time).toLocaleString()}
                            </span>
                          </div>
                        )}
                        {displaySession.duration_minutes && (
                          <div>
                            <span className="text-gray-600">Duration:</span>
                            <span className="ml-2 font-medium text-gray-900">
                              {displaySession.duration_minutes} minutes
                            </span>
                          </div>
                        )}
                        {displaySession.end_time && (
                          <div>
                            <span className="text-gray-600">Completed:</span>
                            <span className="ml-2 font-medium text-gray-900">
                              {new Date(displaySession.end_time).toLocaleString()}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Training Material Content */}
              {trainingMaterial ? (
                <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
                  <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
                    <div className="flex items-center justify-between">
                      <h4 className="text-lg font-semibold text-gray-900">Training Material</h4>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-medium px-2 py-1 rounded bg-purple-100 text-purple-800">
                          {trainingMaterial.difficulty_level || 'intermediate'}
                        </span>
                        {trainingMaterial.estimated_duration_minutes && (
                          <span className="text-xs text-gray-600">
                            ~{trainingMaterial.estimated_duration_minutes} min
                          </span>
                        )}
                      </div>
                    </div>
                    {trainingMaterial.description && (
                      <p className="text-sm text-gray-600 mt-2">{trainingMaterial.description}</p>
                    )}
                  </div>
                  <div className="px-6 py-4">
                    <div className="prose max-w-none">
                      <div className="whitespace-pre-wrap text-gray-700 leading-relaxed">
                        {trainingMaterial.content}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
                  <div className="flex items-center space-x-3">
                    <svg className="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <div>
                      <p className="text-sm font-medium text-yellow-800">Training Material Not Available</p>
                      <p className="text-xs text-yellow-700 mt-1">
                        The AI-generated training material for this session is not available.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Training Summary */}
              {trainingData && (
                <div className="bg-gray-50 rounded-lg p-6 border border-gray-200">
                  <h4 className="text-lg font-semibold text-gray-900 mb-4">Training Summary</h4>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <div className="text-sm text-gray-600">Total Sessions</div>
                      <div className="text-2xl font-bold text-blue-600">
                        {trainingData.total_sessions || 0}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-600">Total Time</div>
                      <div className="text-2xl font-bold text-green-600">
                        {trainingData.total_hours || 0} hrs
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-600">Topics Covered</div>
                      <div className="text-2xl font-bold text-purple-600">
                        {trainingData.unique_topics || 0}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default TrainingDetailModal

