import { useState } from 'react'
import { Menu } from 'lucide-react'
import { Sidebar } from './Sidebar'

export interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen)
  }

  const closeSidebar = () => {
    setSidebarOpen(false)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar */}
      <Sidebar isOpen={sidebarOpen} onClose={closeSidebar} />

      {/* Main content area */}
      <div className="lg:pl-64 transition-all duration-300">
        {/* Mobile header with hamburger menu */}
        <header className="lg:hidden sticky top-0 z-30 bg-white border-b border-gray-200 shadow-sm px-4 py-3">
          <button
            onClick={toggleSidebar}
            className="p-2 rounded-lg hover:bg-gray-100 active:bg-gray-200 transition-colors focus-visible:ring-2 focus-visible:ring-primary-500"
            aria-label="Open sidebar"
            aria-expanded={sidebarOpen}
            aria-controls="sidebar"
            type="button"
          >
            <Menu className="w-6 h-6 text-gray-700" />
          </button>
        </header>

        {/* Page content */}
        <main className="p-4 sm:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  )
}
