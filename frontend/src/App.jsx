import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import Shell from './components/Shell'
import LoginPage from './pages/Login'
import DashboardPage from './pages/Dashboard'
import InboxPage from './pages/Inbox'
import PnlPage from './pages/Pnl'
import HandsPage from './pages/Hands'
import VillainsPage from './pages/Villains'
import DiscordPage from './pages/Discord'
import TournamentsPage from './pages/Tournaments'

function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div style={{ padding: 32, color: 'var(--muted)' }}>A carregar…</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  const { user } = useAuth()

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route path="/" element={
        <RequireAuth>
          <Shell />
        </RequireAuth>
      }>
        <Route index element={<DashboardPage />} />
        <Route path="inbox" element={<InboxPage />} />
        <Route path="hands" element={<HandsPage />} />
        <Route path="villains" element={<VillainsPage />} />
        <Route path="pnl" element={<PnlPage />} />
        <Route path="discord" element={<DiscordPage />} />
        <Route path="tournaments" element={<TournamentsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
