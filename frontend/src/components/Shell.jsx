import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import ImportModal from './ImportModal'

const NAV = [
  { to: '/',            label: 'Dashboard' },
  { to: '/hands',       label: 'Estudo' },
  { to: '/tournaments', label: 'Torneios' },
  { to: '/villains',    label: 'Vilões' },
  { to: '/gto',         label: 'GTO' },
]

export default function Shell() {
  const { user, logout } = useAuth()
  const [importOpen, setImportOpen] = useState(false)

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

        <div style={{ padding: '16px 16px 0' }}>
          <button
            onClick={() => setImportOpen(true)}
            style={{
              width: '100%', padding: '8px 0', fontSize: 12, fontWeight: 600,
              background: 'var(--accent)', color: '#fff', border: 'none',
              borderRadius: 'var(--radius)', cursor: 'pointer',
              letterSpacing: 0.3,
            }}
          >+ Importar</button>
        </div>

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

      <ImportModal open={importOpen} onClose={() => setImportOpen(false)} />
    </div>
  )
}
