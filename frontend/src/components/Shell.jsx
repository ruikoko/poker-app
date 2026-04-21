import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import ImportModal from './ImportModal'
import { useStudyTimer } from '../contexts/StudyTimerContext'

const NAV = [
  { to: '/',            label: 'Dashboard' },
  { to: '/hands',       label: 'Estudo' },
  { to: '/discord',     label: 'Discord' },
  { to: '/tournaments', label: 'Torneios' },
  { to: '/hm3',         label: 'HM3' },
  { to: '/villains',    label: 'Vilões' },
  { to: '/gto',         label: 'GTO' },
]

function fmt(s) {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const pad = (n) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`
}

function StudyTimerControl() {
  const { active, paused, elapsed, start, pause, resume, stop } = useStudyTimer()

  const idle = !active

  // Cores por estado
  const dotColor = idle ? '#4b5563' : paused ? '#f59e0b' : '#22c55e'
  const timeColor = idle ? '#4b5563' : paused ? '#9ca3af' : '#e5e7eb'

  return (
    <div style={{ padding: '12px 16px' }}>
      <div style={{
        fontSize: 9, color: 'var(--muted)',
        textTransform: 'uppercase', letterSpacing: 0.5,
        marginBottom: 6,
      }}>
        Tempo de estudo
      </div>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '6px 8px',
        background: 'rgba(255,255,255,0.02)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 5,
      }}>
        <span style={{
          width: 7, height: 7, borderRadius: '50%',
          background: dotColor,
          boxShadow: idle ? 'none' : `0 0 6px ${dotColor}`,
          animation: (!idle && !paused) ? 'pulse 1.6s ease-in-out infinite' : 'none',
          flexShrink: 0,
        }} />
        <span style={{
          fontFamily: "'Fira Code', monospace",
          fontSize: 12, fontWeight: 600,
          color: timeColor,
          flex: 1,
          letterSpacing: 0.3,
        }}>
          {fmt(elapsed)}
        </span>
        {idle && (
          <button
            onClick={start}
            title="Iniciar sessão"
            style={iconBtnStyle('#86efac', 'rgba(34,197,94,0.12)', 'rgba(34,197,94,0.3)')}
          >
            <svg width="9" height="9" viewBox="0 0 10 10" fill="currentColor"><path d="M2 1 L9 5 L2 9 Z"/></svg>
          </button>
        )}
        {!idle && !paused && (
          <button
            onClick={pause}
            title="Pausar"
            style={iconBtnStyle('#fcd34d', 'rgba(245,158,11,0.12)', 'rgba(245,158,11,0.3)')}
          >
            <svg width="9" height="9" viewBox="0 0 10 10" fill="currentColor">
              <rect x="2" y="1" width="2.5" height="8"/><rect x="5.5" y="1" width="2.5" height="8"/>
            </svg>
          </button>
        )}
        {paused && (
          <button
            onClick={resume}
            title="Retomar"
            style={iconBtnStyle('#86efac', 'rgba(34,197,94,0.12)', 'rgba(34,197,94,0.3)')}
          >
            <svg width="9" height="9" viewBox="0 0 10 10" fill="currentColor"><path d="M2 1 L9 5 L2 9 Z"/></svg>
          </button>
        )}
        {!idle && (
          <button
            onClick={stop}
            title="Terminar sessão"
            style={iconBtnStyle('#f87171', 'rgba(239,68,68,0.12)', 'rgba(239,68,68,0.3)')}
          >
            <svg width="9" height="9" viewBox="0 0 10 10" fill="currentColor"><rect x="1.5" y="1.5" width="7" height="7"/></svg>
          </button>
        )}
      </div>
      <style>{`@keyframes pulse { 0%,100% { opacity:1; transform:scale(1);} 50% {opacity:.5; transform:scale(.85);} }`}</style>
    </div>
  )
}

const iconBtnStyle = (color, bg, border) => ({
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  width: 22, height: 22, padding: 0,
  background: bg, color, border: `1px solid ${border}`,
  borderRadius: 4, cursor: 'pointer', flexShrink: 0,
})

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

        {/* ── Timer de estudo (controlo manual) ── */}
        <StudyTimerControl />

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
