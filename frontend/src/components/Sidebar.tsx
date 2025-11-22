import { Link, useLocation } from 'react-router-dom'
import { LayoutDashboard, FileText, X } from 'lucide-react'

export interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const location = useLocation()

  const navItems = [
    {
      name: 'Dashboard',
      path: '/',
      icon: LayoutDashboard,
    },
    {
      name: 'Generations',
      path: '/generations',
      icon: FileText,
    },
  ]

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/'
    }
    return location.pathname.startsWith(path)
  }

  return (
    <>
      {/* Mobile overlay backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden transition-opacity duration-300"
          onClick={onClose}
          aria-hidden="true"
          role="presentation"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 h-full bg-white border-r border-gray-200 shadow-lg z-50
          transition-transform duration-300 ease-in-out
          w-64
          ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
        aria-label="Sidebar navigation"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 bg-gradient-to-r from-primary-50 to-secondary-50">
          <h1 className="text-xl font-bold text-gray-900 truncate">
            Question Generator
          </h1>
          
          {/* Close button - mobile only */}
          <button
            onClick={onClose}
            className="lg:hidden p-2 rounded-lg hover:bg-gray-100 active:bg-gray-200 transition-colors focus-visible:ring-2 focus-visible:ring-primary-500"
            aria-label="Close sidebar"
            type="button"
          >
            <X className="w-5 h-5 text-gray-600" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-2" aria-label="Main navigation">
          {navItems.map((item) => {
            const Icon = item.icon
            const active = isActive(item.path)

            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={onClose}
                className={`
                  flex items-center gap-3 px-4 py-3 rounded-lg
                  transition-all duration-200
                  focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2
                  ${
                    active
                      ? 'bg-primary-50 text-primary-700 font-medium shadow-sm border border-primary-100'
                      : 'text-gray-700 hover:bg-gray-100 active:bg-gray-200'
                  }
                `}
                aria-current={active ? 'page' : undefined}
              >
                <Icon
                  className={`w-5 h-5 flex-shrink-0 ${
                    active ? 'text-primary-600' : 'text-gray-500'
                  }`}
                  aria-hidden="true"
                />
                <span className="truncate">{item.name}</span>
              </Link>
            )
          })}
        </nav>
      </aside>
    </>
  )
}
