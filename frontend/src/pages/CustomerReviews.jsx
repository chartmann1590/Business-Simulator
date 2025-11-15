import { useState, useEffect } from 'react'
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts'

const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6']

function CustomerReviews() {
  const [reviews, setReviews] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filterRating, setFilterRating] = useState('all')
  const [filterProject, setFilterProject] = useState('all')
  const [projects, setProjects] = useState([])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [])

  const fetchData = async () => {
    try {
      const [reviewsRes, statsRes, projectsRes] = await Promise.all([
        fetch('/api/customer-reviews?limit=200'),
        fetch('/api/customer-reviews/stats'),
        fetch('/api/projects')
      ])
      
      const reviewsData = reviewsRes.ok ? await reviewsRes.json() : []
      const statsData = statsRes.ok ? await statsRes.json() : null
      const projectsData = projectsRes.ok ? await projectsRes.json() : []
      
      setReviews(reviewsData || [])
      setStats(statsData)
      setProjects(projectsData || [])
      setLoading(false)
    } catch (error) {
      console.error('Error fetching customer reviews:', error)
      setReviews([])
      setStats(null)
      setLoading(false)
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
        <span className="ml-2 text-sm text-gray-600">{rating.toFixed(1)}</span>
      </div>
    )
  }

  const getRatingColor = (rating) => {
    if (rating >= 4.5) return 'text-green-600'
    if (rating >= 4.0) return 'text-blue-600'
    if (rating >= 3.0) return 'text-yellow-600'
    if (rating >= 2.0) return 'text-orange-600'
    return 'text-red-600'
  }

  // Get unique project names for filter
  const uniqueProjects = [...new Set(reviews.map(r => r.project_name))].sort()

  // Filter reviews
  const filteredReviews = reviews.filter(review => {
    if (filterRating !== 'all') {
      const ratingFilter = parseFloat(filterRating)
      if (Math.floor(review.rating) !== ratingFilter) return false
    }
    if (filterProject !== 'all' && review.project_name !== filterProject) {
      return false
    }
    return true
  })

  if (loading) {
    return <div className="text-center py-12">Loading customer reviews...</div>
  }

  // Prepare chart data
  const ratingDistributionData = stats?.rating_distribution ? 
    Object.entries(stats.rating_distribution).map(([name, value]) => ({
      name,
      value
    })) : []

  const reviewsByProjectData = stats?.reviews_by_project ?
    Object.entries(stats.reviews_by_project).map(([name, data]) => ({
      name: name.length > 20 ? name.substring(0, 20) + '...' : name,
      fullName: name,
      count: data.count,
      averageRating: data.average_rating
    })).sort((a, b) => b.count - a.count).slice(0, 10) : []

  return (
    <div className="px-4 py-6 space-y-6">
      <div className="mb-6">
        <h2 className="text-3xl font-bold text-gray-900">Customer Reviews</h2>
        <p className="text-sm text-gray-500 mt-1">Reviews from customers using our products and services</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Total Reviews</div>
          <div className="mt-2 text-3xl font-bold text-gray-900">
            {stats?.total_reviews || 0}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Average Rating</div>
          <div className={`mt-2 text-3xl font-bold ${getRatingColor(stats?.average_rating || 0)}`}>
            {stats?.average_rating ? stats.average_rating.toFixed(1) : '0.0'}
          </div>
          {stats?.average_rating && (
            <div className="mt-2">
              {renderStars(stats.average_rating)}
            </div>
          )}
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Products Reviewed</div>
          <div className="mt-2 text-3xl font-bold text-blue-600">
            {stats?.reviews_by_project ? Object.keys(stats.reviews_by_project).length : 0}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Verified Purchases</div>
          <div className="mt-2 text-3xl font-bold text-green-600">
            {reviews.filter(r => r.verified_purchase).length}
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Rating Distribution Pie Chart */}
        {ratingDistributionData.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Rating Distribution</h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={ratingDistributionData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {ratingDistributionData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Reviews by Project Bar Chart */}
        {reviewsByProjectData.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Reviews by Product</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={reviewsByProjectData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="name" 
                  tick={{ fontSize: 12 }}
                  angle={-45}
                  textAnchor="end"
                  height={80}
                />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip 
                  formatter={(value, name) => {
                    if (name === 'count') return [value, 'Reviews']
                    if (name === 'averageRating') return [value.toFixed(1), 'Avg Rating']
                    return [value, name]
                  }}
                  labelFormatter={(label, payload) => {
                    if (payload && payload[0] && payload[0].payload) {
                      return payload[0].payload.fullName
                    }
                    return label
                  }}
                />
                <Legend />
                <Bar dataKey="count" fill="#3b82f6" name="Review Count" />
                <Bar dataKey="averageRating" fill="#10b981" name="Avg Rating" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex flex-wrap gap-4 items-center">
          <label className="text-sm font-medium text-gray-700">Filter by Rating:</label>
          <select
            value={filterRating}
            onChange={(e) => setFilterRating(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Ratings</option>
            <option value="5">5 Stars</option>
            <option value="4">4 Stars</option>
            <option value="3">3 Stars</option>
            <option value="2">2 Stars</option>
            <option value="1">1 Star</option>
          </select>

          <label className="text-sm font-medium text-gray-700 ml-4">Filter by Product:</label>
          <select
            value={filterProject}
            onChange={(e) => setFilterProject(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Products</option>
            {uniqueProjects.map(project => (
              <option key={project} value={project}>{project}</option>
            ))}
          </select>

          <div className="ml-auto text-sm text-gray-600">
            Showing {filteredReviews.length} of {reviews.length} reviews
          </div>
        </div>
      </div>

      {/* Reviews List */}
      <div className="space-y-4">
        {filteredReviews.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <p className="text-gray-500 text-lg mb-2">No customer reviews found</p>
            <p className="text-gray-400 text-sm">
              {reviews.length === 0 
                ? 'Reviews will appear here once projects are completed and reviews are generated'
                : 'Try adjusting your filters'}
            </p>
          </div>
        ) : (
          filteredReviews.map((review) => (
            <div key={review.id} className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow">
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-2">
                    <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white font-bold text-lg">
                      {review.customer_name.charAt(0)}
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900">{review.customer_name}</div>
                      <div className="text-sm text-gray-600">
                        {review.customer_title}
                        {review.company_name && ` at ${review.company_name}`}
                      </div>
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  {renderStars(review.rating)}
                  {review.verified_purchase && (
                    <div className="mt-1 text-xs text-green-600 font-medium">
                      ✓ Verified Purchase
                    </div>
                  )}
                </div>
              </div>

              <div className="mb-4">
                <h4 className="font-medium text-gray-900 mb-1">{review.project_name}</h4>
                <p className="text-gray-700 leading-relaxed">{review.review_text}</p>
              </div>

              <div className="flex items-center justify-between text-sm text-gray-500">
                <div>
                  {review.created_at && (
                    <span>{new Date(review.created_at).toLocaleDateString('en-US', { 
                      year: 'numeric', 
                      month: 'long', 
                      day: 'numeric' 
                    })}</span>
                  )}
                </div>
                {review.helpful_count > 0 && (
                  <div className="text-gray-600">
                    {review.helpful_count} {review.helpful_count === 1 ? 'person' : 'people'} found this helpful
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default CustomerReviews

