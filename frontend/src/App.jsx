import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Employees from './pages/Employees'
import EmployeeDetail from './pages/EmployeeDetail'
import Projects from './pages/Projects'
import ProjectDetail from './pages/ProjectDetail'
import Products from './pages/Products'
import ProductDetail from './pages/ProductDetail'
import Tasks from './pages/Tasks'
import TaskDetail from './pages/TaskDetail'
import Financials from './pages/Financials'
import Communications from './pages/Communications'
import OfficeView from './pages/OfficeView'
import HomeView from './pages/HomeView'
import CustomerReviews from './pages/CustomerReviews'
import NotificationsHistory from './pages/NotificationsHistory'
import PetCareGame from './pages/PetCareGame'
import PetCareLog from './pages/PetCareLog'
import Changelog from './pages/Changelog'
import Notifications from './components/Notifications'

function NavLink({ to, children, icon }) {
  const location = useLocation()
  const isActive = location.pathname === to || (to !== '/' && location.pathname.startsWith(to))
  
  return (
    <Link
      to={to}
      className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors ${
        isActive
          ? 'bg-blue-50 text-blue-600 font-medium'
          : 'text-gray-700 hover:bg-gray-100'
      }`}
    >
      {icon && <span className="text-xl">{icon}</span>}
      <span>{children}</span>
    </Link>
  )
}

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50 flex">
        {/* Sidebar Navigation */}
        <aside className="w-64 bg-white shadow-sm border-r border-gray-200 flex flex-col">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900" id="business-name">TechFlow Solutions</h1>
                <p className="text-xs text-gray-500 mt-1">Business Simulation</p>
              </div>
              <Notifications />
            </div>
          </div>
          <nav className="flex-1 p-4 space-y-1">
            <NavLink to="/" icon="📊">Dashboard</NavLink>
            <NavLink to="/office-view" icon="🏢">Office View</NavLink>
            <NavLink to="/home-view" icon="🏠">Home View</NavLink>
            <NavLink to="/pet-care" icon="🐾">Pet Care Game</NavLink>
            <NavLink to="/pet-care-log" icon="📋">Pet Care Log</NavLink>
            <NavLink to="/employees" icon="👥">Employees</NavLink>
            <NavLink to="/products" icon="🛍️">Products</NavLink>
            <NavLink to="/projects" icon="📁">Projects</NavLink>
            <NavLink to="/tasks" icon="✅">Tasks</NavLink>
            <NavLink to="/communications" icon="💬">Communications</NavLink>
            <NavLink to="/financials" icon="💰">Financials</NavLink>
            <NavLink to="/customer-reviews" icon="⭐">Customer Reviews</NavLink>
            <NavLink to="/notifications" icon="🔔">Notifications</NavLink>
            <NavLink to="/changelog" icon="📝">Changelog</NavLink>
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/office-view" element={<OfficeView />} />
            <Route path="/home-view" element={<HomeView />} />
            <Route path="/pet-care" element={<PetCareGame />} />
            <Route path="/pet-care-log" element={<PetCareLog />} />
            <Route path="/employees" element={<Employees />} />
            <Route path="/employees/:id" element={<EmployeeDetail />} />
            <Route path="/products" element={<Products />} />
            <Route path="/products/:id" element={<ProductDetail />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/projects/:id" element={<ProjectDetail />} />
            <Route path="/tasks" element={<Tasks />} />
            <Route path="/tasks/:id" element={<TaskDetail />} />
            <Route path="/communications" element={<Communications />} />
            <Route path="/financials" element={<Financials />} />
            <Route path="/customer-reviews" element={<CustomerReviews />} />
            <Route path="/notifications" element={<NotificationsHistory />} />
            <Route path="/changelog" element={<Changelog />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App

