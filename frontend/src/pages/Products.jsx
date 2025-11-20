import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiGet } from '../utils/api'

function Products() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchProducts()
    const interval = setInterval(fetchProducts, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchProducts = async () => {
    setLoading(true)
    try {
      const result = await apiGet('/api/products')
      setProducts(Array.isArray(result.data) ? result.data : [])
    } catch (error) {
      console.error('Error fetching products:', error)
      setProducts([])
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="text-center py-12">Loading products...</div>
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
          <span key={i} className="text-yellow-400">★</span>
        ))}
        {hasHalfStar && <span className="text-yellow-400">☆</span>}
        {[...Array(emptyStars)].map((_, i) => (
          <span key={i} className="text-gray-300">★</span>
        ))}
        <span className="ml-2 text-sm text-gray-600">{rating.toFixed(1)}</span>
      </div>
    )
  }

  return (
    <div className="px-4 py-6">
      <h2 className="text-3xl font-bold text-gray-900 mb-6">Products</h2>
      
      {products.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <p className="text-gray-500 text-lg mb-2">No products found</p>
          <p className="text-gray-400 text-sm">
            Products will appear here once they are created
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {products.map((product) => (
            <Link
              key={product.id}
              to={`/products/${product.id}`}
              className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow p-6 cursor-pointer"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <h3 className="text-xl font-semibold text-gray-900">{product.name}</h3>
                  {product.category && (
                    <p className="text-sm text-gray-500 mt-1">{product.category}</p>
                  )}
                </div>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(product.status)}`}>
                  {product.status}
                </span>
              </div>
              
              {product.description && (
                <p className="text-sm text-gray-600 mb-4 line-clamp-2">{product.description}</p>
              )}
              
              <div className="space-y-3 mb-4">
                {product.average_rating > 0 && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Rating</span>
                    {renderStars(product.average_rating)}
                  </div>
                )}
                
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Reviews</span>
                  <span className="font-medium text-gray-900">{product.review_count || 0}</span>
                </div>
                
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Team Members</span>
                  <span className="font-medium text-gray-900">{product.team_count || 0}</span>
                </div>
                
                {product.total_sales > 0 && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Total Sales</span>
                    <span className="font-medium text-green-600">${product.total_sales.toLocaleString()}</span>
                  </div>
                )}
                
                {product.price > 0 && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Price</span>
                    <span className="font-medium text-gray-900">${product.price.toLocaleString()}</span>
                  </div>
                )}
              </div>
              
              {product.launch_date && (
                <div className="mt-2 text-xs text-gray-500">
                  Launched: {new Date(product.launch_date).toLocaleDateString()}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

export default Products




