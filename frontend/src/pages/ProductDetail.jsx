import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'

function ProductDetail() {
  const { id } = useParams()
  const [product, setProduct] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchProduct()
    const interval = setInterval(fetchProduct, 10000)
    return () => clearInterval(interval)
  }, [id])

  const fetchProduct = async () => {
    try {
      const response = await fetch(`/api/products/${id}`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data = await response.json()
      setProduct(data)
      setLoading(false)
    } catch (error) {
      console.error('Error fetching product:', error)
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="text-center py-12">Loading product details...</div>
  }

  if (!product) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 text-lg mb-4">Product not found</p>
        <Link to="/products" className="text-blue-600 hover:text-blue-800">
          ← Back to Products
        </Link>
      </div>
    )
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800'
      case 'development': return 'bg-blue-100 text-blue-800'
      case 'discontinued': return 'bg-red-100 text-red-800'
      case 'planned': return 'bg-yellow-100 text-yellow-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const renderStars = (rating) => {
    const fullStars = Math.floor(rating)
    const hasHalfStar = rating % 1 >= 0.5
    const emptyStars = 5 - fullStars - (hasHalfStar ? 1 : 0)
    
    return (
      <div className="flex items-center">
        {[...Array(fullStars)].map((_, i) => (
          <span key={i} className="text-yellow-400 text-lg">★</span>
        ))}
        {hasHalfStar && <span className="text-yellow-400 text-lg">☆</span>}
        {[...Array(emptyStars)].map((_, i) => (
          <span key={i} className="text-gray-300 text-lg">★</span>
        ))}
        <span className="ml-2 text-gray-900 font-medium">{rating.toFixed(1)}</span>
      </div>
    )
  }

  return (
    <div className="px-4 py-6">
      <Link to="/products" className="text-blue-600 hover:text-blue-800 mb-4 inline-block">
        ← Back to Products
      </Link>
      
      {/* Product Header */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-start justify-between mb-6">
          <div className="flex-1">
            <h2 className="text-3xl font-bold text-gray-900">{product.name}</h2>
            {product.category && (
              <p className="text-gray-500 mt-1">{product.category}</p>
            )}
            {product.description && (
              <p className="text-gray-600 mt-3">{product.description}</p>
            )}
          </div>
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(product.status)}`}>
            {product.status}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {product.price > 0 && (
            <div>
              <span className="text-sm text-gray-500">Price</span>
              <p className="text-lg font-medium text-gray-900">${product.price.toLocaleString()}</p>
            </div>
          )}
          {product.sales && (
            <div>
              <span className="text-sm text-gray-500">Total Revenue</span>
              <p className="text-lg font-medium text-green-600">${product.sales.total_revenue.toLocaleString()}</p>
            </div>
          )}
          {product.average_rating > 0 && (
            <div>
              <span className="text-sm text-gray-500">Average Rating</span>
              <div className="mt-1">{renderStars(product.average_rating)}</div>
            </div>
          )}
          <div>
            <span className="text-sm text-gray-500">Reviews</span>
            <p className="text-lg font-medium text-gray-900">{product.review_count || 0}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-4 text-sm text-gray-600">
          {product.launch_date && (
            <div>
              <span className="font-medium">Launch Date: </span>
              {new Date(product.launch_date).toLocaleDateString()}
            </div>
          )}
          {product.created_at && (
            <div>
              <span className="font-medium">Created: </span>
              {new Date(product.created_at).toLocaleDateString()}
            </div>
          )}
        </div>
      </div>

      {/* Team Members */}
      {product.team_members && product.team_members.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="text-xl font-semibold text-gray-900 mb-4">Team Members</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {product.team_members.map((member) => (
              <div key={member.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                <div className="flex items-center space-x-3 mb-2">
                  {member.avatar_path && (
                    <img
                      src={member.avatar_path}
                      alt={member.employee_name}
                      className="w-12 h-12 rounded-full object-cover"
                      onError={(e) => {
                        e.target.style.display = 'none'
                      }}
                    />
                  )}
                  <div className="flex-1">
                    <Link
                      to={`/employees/${member.employee_id}`}
                      className="font-semibold text-gray-900 hover:text-blue-600"
                    >
                      {member.employee_name}
                    </Link>
                    <p className="text-sm text-gray-600">{member.employee_title}</p>
                    {member.employee_department && (
                      <p className="text-xs text-gray-500">{member.employee_department}</p>
                    )}
                  </div>
                </div>
                {member.role && (
                  <p className="text-sm font-medium text-blue-600 mb-1">{member.role}</p>
                )}
                {member.responsibility && (
                  <p className="text-sm text-gray-600">{member.responsibility}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sales Information */}
      {product.sales && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="text-xl font-semibold text-gray-900 mb-4">Sales Information</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-green-50 rounded-lg p-4">
              <span className="text-sm text-gray-600">Total Revenue</span>
              <p className="text-2xl font-bold text-green-600">
                ${product.sales.total_revenue.toLocaleString()}
              </p>
            </div>
            <div className="bg-blue-50 rounded-lg p-4">
              <span className="text-sm text-gray-600">Total Budget</span>
              <p className="text-2xl font-bold text-blue-600">
                ${product.sales.total_budget.toLocaleString()}
              </p>
            </div>
            <div className="bg-purple-50 rounded-lg p-4">
              <span className="text-sm text-gray-600">Related Projects</span>
              <p className="text-2xl font-bold text-purple-600">
                {product.sales.project_count}
              </p>
            </div>
          </div>

          {product.sales.projects && product.sales.projects.length > 0 && (
            <div>
              <h4 className="text-lg font-semibold text-gray-900 mb-3">Related Projects</h4>
              <div className="space-y-2">
                {product.sales.projects.map((project) => (
                  <Link
                    key={project.id}
                    to={`/projects/${project.id}`}
                    className="flex items-center justify-between p-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    <div>
                      <p className="font-medium text-gray-900">{project.name}</p>
                      <p className="text-sm text-gray-500">
                        Status: <span className="capitalize">{project.status}</span>
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-medium text-green-600">
                        ${project.revenue.toLocaleString()}
                      </p>
                      <p className="text-xs text-gray-500">
                        Budget: ${project.budget.toLocaleString()}
                      </p>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {product.recent_transactions && product.recent_transactions.length > 0 && (
            <div className="mt-6">
              <h4 className="text-lg font-semibold text-gray-900 mb-3">Recent Transactions</h4>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Amount</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {product.recent_transactions.slice(0, 10).map((transaction) => (
                      <tr key={transaction.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            transaction.type === 'income' 
                              ? 'bg-green-100 text-green-800' 
                              : 'bg-red-100 text-red-800'
                          }`}>
                            {transaction.type}
                          </span>
                        </td>
                        <td className={`px-4 py-3 whitespace-nowrap font-medium ${
                          transaction.type === 'income' ? 'text-green-600' : 'text-red-600'
                        }`}>
                          ${transaction.amount.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">
                          {transaction.description || 'N/A'}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                          {transaction.timestamp 
                            ? new Date(transaction.timestamp).toLocaleDateString()
                            : 'N/A'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Customer Reviews */}
      {product.customer_reviews && product.customer_reviews.length > 0 ? (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-xl font-semibold text-gray-900 mb-4">
            Customer Reviews ({product.customer_reviews.length})
          </h3>
          <div className="space-y-4">
            {product.customer_reviews.map((review) => (
              <div key={review.id} className="border-l-4 border-blue-500 pl-4 py-3">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-1">
                      <p className="font-semibold text-gray-900">{review.customer_name}</p>
                      {review.customer_title && (
                        <span className="text-sm text-gray-500">• {review.customer_title}</span>
                      )}
                      {review.verified_purchase && (
                        <span className="px-2 py-0.5 bg-green-100 text-green-800 text-xs rounded">
                          ✓ Verified Purchase
                        </span>
                      )}
                    </div>
                    {review.company_name && (
                      <p className="text-sm text-gray-500">{review.company_name}</p>
                    )}
                  </div>
                  <div className="flex items-center space-x-2">
                    {renderStars(review.rating)}
                  </div>
                </div>
                <p className="text-gray-700 mb-2">{review.review_text}</p>
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>{new Date(review.created_at).toLocaleDateString()}</span>
                  {review.helpful_count > 0 && (
                    <span>{review.helpful_count} helpful</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-xl font-semibold text-gray-900 mb-4">Customer Reviews</h3>
          <p className="text-gray-500 text-center py-4">No customer reviews yet</p>
        </div>
      )}
    </div>
  )
}

export default ProductDetail





