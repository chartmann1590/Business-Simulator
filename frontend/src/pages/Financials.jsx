import { useState, useEffect } from 'react'

function Financials() {
  const [financials, setFinancials] = useState([])
  const [metrics, setMetrics] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchData = async () => {
    try {
      const [financialsRes, metricsRes] = await Promise.all([
        fetch('/api/financials?days=90'),
        fetch('/api/metrics')
      ])
      const financialsData = financialsRes.ok ? await financialsRes.json() : []
      const metricsData = metricsRes.ok ? await metricsRes.json() : {}
      setFinancials(financialsData || [])
      setMetrics(metricsData || {})
      setLoading(false)
    } catch (error) {
      console.error('Error fetching financial data:', error)
      setFinancials([])
      setMetrics({})
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="text-center py-12">Loading financial data...</div>
  }

  const totalIncome = financials
    .filter(f => f.type === 'income')
    .reduce((sum, f) => sum + f.amount, 0)
  
  const totalExpenses = financials
    .filter(f => f.type === 'expense')
    .reduce((sum, f) => sum + f.amount, 0)

  return (
    <div className="px-4 py-6">
      <h2 className="text-3xl font-bold text-gray-900 mb-6">Financials</h2>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Total Income</div>
          <div className="mt-2 text-3xl font-bold text-green-600">
            ${totalIncome.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Total Expenses</div>
          <div className="mt-2 text-3xl font-bold text-red-600">
            ${totalExpenses.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Net Profit</div>
          <div className={`mt-2 text-3xl font-bold ${(totalIncome - totalExpenses) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            ${(totalIncome - totalExpenses).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
      </div>

      {/* Financial Transactions */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Recent Transactions (Last 90 Days)</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {financials.length === 0 ? (
                <tr>
                  <td colSpan="4" className="px-6 py-4 text-center text-gray-500">No transactions found</td>
                </tr>
              ) : (
                financials.map((financial) => (
                  <tr key={financial.id}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(financial.timestamp).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
                        financial.type === 'income' 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {financial.type}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">{financial.description || 'N/A'}</td>
                    <td className={`px-6 py-4 whitespace-nowrap text-sm text-right font-medium ${
                      financial.type === 'income' ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {financial.type === 'income' ? '+' : '-'}${financial.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default Financials

