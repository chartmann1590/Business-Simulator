import { useState, useEffect } from 'react'
import EmployeeScreenView from './EmployeeScreenView'

function EmployeeScreenModal({ employeeId, isOpen, onClose }) {
  const [employeeInfo, setEmployeeInfo] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (isOpen && employeeId) {
      fetchEmployeeInfo()
    }
  }, [isOpen, employeeId])

  const fetchEmployeeInfo = async () => {
    try {
      const response = await fetch(`/api/employees/${employeeId}`)
      if (response.ok) {
        const data = await response.json()
        setEmployeeInfo(data)
      }
    } catch (error) {
      console.error('Error fetching employee info:', error)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-75" onClick={onClose}>
      <div
        className="bg-gray-900 rounded-lg shadow-2xl w-[95vw] h-[90vh] max-h-[90vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="bg-gray-800 px-6 py-4 flex items-center justify-between border-b border-gray-700">
          <div className="flex items-center gap-4">
            {employeeInfo && (
              <>
                <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white font-semibold">
                  {employeeInfo.name?.charAt(0) || 'E'}
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-white">{employeeInfo.name || 'Employee'}</h2>
                  <p className="text-sm text-gray-400">{employeeInfo.title || ''}</p>
                </div>
                <div className="ml-4 px-3 py-1 bg-green-600 text-white text-xs rounded-full">
                  View Only
                </div>
              </>
            )}
            {loading && (
              <div className="flex items-center gap-2">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white"></div>
                <span className="text-white">Loading...</span>
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-2 hover:bg-gray-700 rounded"
            title="Close"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Screen View Content */}
        <div className="flex-1 overflow-hidden relative bg-gradient-to-br from-blue-900 via-blue-800 to-indigo-900">
          <EmployeeScreenView employeeId={employeeId} />
        </div>
      </div>
    </div>
  )
}

export default EmployeeScreenModal

