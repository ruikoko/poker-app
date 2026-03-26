import { Outlet, NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const NAV = [
  { to: '/',            label: 'Dashboard' },
  { to: '/inbox',       label: 'Inbox' },
  { to: '/hands',       label: 'Mãos' },
  { to: '/tournaments', label: 'Torneios' },
  { to: '/villains',    label: 'Vilões' },
  { to: '/pnl',         label: 'P&L' },
  { to: '/discord',     label: 'Discord' },
]

export default function Shell() {
  const { user, logout } = useAuth()

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-logo">poker<span>app</span></div>

        <nav>
          {NAV.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div style={{ marginTop: 'auto', padding: '0 20px' }}>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8 }}>
            {user?.email}
          </div>
          <button className="btn btn-ghost btn-sm" onClick={logout} style={{ width: '100%' }}>
            Sair
          </button>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
