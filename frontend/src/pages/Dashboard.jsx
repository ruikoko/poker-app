import { useEffect, useState } from 'react'
import { hands, tournaments } from '../api/client'

function fmt(n, currency) {
  const abs = Math.abs(n).toLocaleString('pt-PT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return (n >= 0 ? '+' : '-') + (currency || '') + abs
}

export default function DashboardPage() {
  const [handStats, setHandStats] = useState(null)
  const [pnlSummary, setPnlSummary] = useState([])
  const [recentHands, setRecentHands] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    hands.stats().then(setHandStats).catch(e => setError(e.message))
    hands.list({ page_size: 5, study_state: 'new' }).then(d => setRecentHands(d.data || [])).catch(() => {})
    tournaments.summary().then(setPnlSummary).catch(() => {})
  }, [])

  const total_profit = pnlSummary.reduce((s, r) => s + Number(r.profit), 0)

  return (
    <>
      <div className="page-header">
        <div className="page-title">Dashboard</div>
        <div className="page-subtitle">Visão geral do estudo e resultados</div>
      </div>

      {error && <div className="error-msg" style={{ marginBottom: 16 }}>{error}</div>}

      {/* ── Estatísticas de Mãos ── */}
      <div className="stat-grid" style={{ marginBottom: 24 }}>
        <div className="stat-card">
          <div className="stat-label">Total de Mãos</div>
          <div className="stat-value">{handStats?.total ?? '—'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Novas (Inbox)</div>
          <div className="stat-value" style={{ color: 'var(--accent)' }}>{handStats?.new ?? '—'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Em Revisão</div>
          <div className="stat-value" style={{ color: '#f59e0b' }}>{handStats?.review ?? '—'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Resolvidas</div>
          <div className="stat-value green">{handStats?.resolved ?? '—'}</div>
        </div>
      </div>

      {/* ── Mãos recentes na inbox ── */}
      {recentHands.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 13 }}>
            Últimas mãos na Inbox
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Sala</th>
                  <th>Cartas</th>
                  <th>Posição</th>
                  <th>Board</th>
                </tr>
              </thead>
              <tbody>
                {recentHands.map(h => (
                  <tr key={h.id}>
                    <td className="muted">{h.played_at ? h.played_at.slice(0, 10) : '—'}</td>
                    <td>{h.site || '—'}</td>
                    <td className="mono">{h.hero_cards?.join(' ') || '—'}</td>
                    <td>{h.position || '—'}</td>
                    <td className="mono">{h.board?.join(' ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Resumo P&L (read-only) ── */}
      {pnlSummary.length > 0 && (
        <div className="card">
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 600, fontSize: 13 }}>P&L por Sala</span>
            <span className={`mono ${total_profit >= 0 ? 'green' : 'red'}`} style={{ fontSize: 13 }}>
              Total: {fmt(total_profit)}
            </span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Sala</th>
                  <th>Torneios</th>
                  <th>Buy-in</th>
                  <th>Cashout</th>
                  <th>Profit</th>
                  <th>ROI%</th>
                </tr>
              </thead>
              <tbody>
                {pnlSummary.map(r => (
                  <tr key={r.site + r.currency}>
                    <td>{r.site}</td>
                    <td>{r.total}</td>
                    <td className="muted">{r.currency}{Number(r.total_buyin).toLocaleString('pt-PT', { minimumFractionDigits: 2 })}</td>
                    <td className="muted">{r.currency}{Number(r.total_cashout).toLocaleString('pt-PT', { minimumFractionDigits: 2 })}</td>
                    <td className={Number(r.profit) >= 0 ? 'green' : 'red'}>
                      {fmt(Number(r.profit), r.currency)}
                    </td>
                    <td className={Number(r.roi_pct) >= 0 ? 'green' : 'red'}>
                      {r.roi_pct}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!handStats && !error && (
        <div className="empty-state">
          A carregar dados…
        </div>
      )}
    </>
  )
}
