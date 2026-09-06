import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, CreditCard, LogOut, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/transactions', icon: CreditCard, label: 'Transactions' },
]

export default function Layout() {
  const navigate = useNavigate()

  const logout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  return (
    <div className="min-h-screen flex flex-col md:flex-row overflow-x-hidden bg-paper text-ink">
      <aside className="w-full md:w-64 shrink-0 border-b md:border-b-0 md:border-r border-paper-line bg-paper flex flex-col">
        <div className="p-4 md:p-6 border-b border-paper-line">
          <div className="flex items-center gap-2">
            <div className="border border-ink p-1">
              <Zap className="w-5 h-5 text-ink" />
            </div>
            <span className="font-bold text-lg">RecoverAI</span>
          </div>
        </div>

        <nav className="flex flex-row md:flex-col flex-1 p-3 md:p-4 gap-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex-1 md:flex-none flex items-center justify-center md:justify-start gap-2 md:gap-3 px-3 py-2.5 border-b text-sm font-medium transition-colors',
                  isActive
                    ? 'border-brand-500 text-brand-600'
                    : 'border-transparent text-slate-500 hover:text-ink hover:border-paper-line'
                )
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 md:p-4 border-t border-paper-line">
          <button
            onClick={logout}
            className="flex items-center gap-3 px-3 py-2.5 text-sm text-slate-500 hover:text-flatline w-full transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  )
}
