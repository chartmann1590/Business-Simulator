import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Employees from './pages/Employees'
import EmployeeDetail from './pages/EmployeeDetail'
import Projects from './pages/Projects'
import ProjectDetail from './pages/ProjectDetail'
import Financials from './pages/Financials'
import Communications from './pages/Communications'
import OfficeView from './pages/OfficeView'

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
            <h1 className="text-2xl font-bold text-gray-900" id="business-name">TechFlow Solutions</h1>
            <p className="text-xs text-gray-500 mt-1">Business Simulation</p>
          </div>
          <nav className="flex-1 p-4 space-y-1">
            <NavLink to="/" icon="📊">Dashboard</NavLink>
            <NavLink to="/office-view" icon="🏢">Office View</NavLink>
            <NavLink to="/employees" icon="👥">Employees</NavLink>
            <NavLink to="/projects" icon="📁">Projects</NavLink>
            <NavLink to="/communications" icon="💬">Communications</NavLink>
            <NavLink to="/financials" icon="💰">Financials</NavLink>
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/office-view" element={<OfficeView />} />
            <Route path="/employees" element={<Employees />} />
            <Route path="/employees/:id" element={<EmployeeDetail />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/projects/:id" element={<ProjectDetail />} />
            <Route path="/communications" element={<Communications />} />
            <Route path="/financials" element={<Financials />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App

