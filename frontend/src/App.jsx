import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import Shell from './components/Shell'
import LoginPage from './pages/Login'
import DashboardPage from './pages/Dashboard'
import PnlPage from './pages/Pnl'
import HandsPage from './pages/Hands'
import VillainsPage from './pages/Villains'
import DiscordPage from './pages/Discord'
import TournamentsPage from './pages/Tournaments'
import HM3Page from './pages/HM3'
import StatsPage from './pages/Stats'
import ReplayerPage from './pages/ReplayerPage'
import HandDetailPage from './pages/HandDetailPage'
import GTOBrainPage from './pages/GTOBrain'
import HRCQueuePage from './pages/HRCQueue'
import HRCResultsPage from './pages/HRCResults'
import HRCSessionsPage from './pages/HRCSessions'
import HRCSessionDetailPage from './pages/HRCSessionDetail'
import TableSSPage from './pages/TableSS'
import LobbysPage from './pages/Lobbys'
import ImportHealthPage from './pages/ImportHealth'
import CaptureTriagePage from './pages/CaptureTriage'
import SuspiciousHandsPage from './pages/SuspiciousHands'
import GGHealthPage from './pages/GGHealth'
import { StudyTimerProvider } from './contexts/StudyTimerContext'

function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div style={{ padding: 32, color: 'var(--muted)' }}>A carregar…</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  const { user } = useAuth()

  return (
    <StudyTimerProvider>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
        <Route path="/replayer/:id" element={
          <RequireAuth>
            <ReplayerPage />
          </RequireAuth>
        } />
        <Route path="/hand/:id" element={
          <RequireAuth>
            <Shell />
          </RequireAuth>
        }>
          <Route index element={<HandDetailPage />} />
        </Route>
        <Route path="/" element={
          <RequireAuth>
            <Shell />
          </RequireAuth>
        }>
          <Route index element={<DashboardPage />} />
          <Route path="hands" element={<HandsPage />} />
          <Route path="hm3" element={<HM3Page />} />
          <Route path="table-ss" element={<TableSSPage />} />
          <Route path="marcadas-por-captura" element={<CaptureTriagePage />} />
          <Route path="suspeitas" element={<SuspiciousHandsPage />} />
          <Route path="gg-health" element={<GGHealthPage />} />
          <Route path="lobbys" element={<LobbysPage />} />
          <Route path="import-health" element={<ImportHealthPage />} />
          <Route path="stats" element={<StatsPage />} />
          <Route path="villains" element={<VillainsPage />} />
          <Route path="pnl" element={<PnlPage />} />
          <Route path="discord" element={<DiscordPage />} />
          <Route path="tournaments" element={<TournamentsPage />} />
          <Route path="gto" element={<GTOBrainPage />} />
          <Route path="hrc" element={<HRCQueuePage />} />
          <Route path="hrc-results" element={<HRCResultsPage />} />
          <Route path="hrc-sessions" element={<HRCSessionsPage />} />
          <Route path="hrc-sessions/:id" element={<HRCSessionDetailPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </StudyTimerProvider>
  )
}
