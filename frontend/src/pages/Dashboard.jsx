import { useEffect, useState } from 'react'
import { tournaments } from '../api/client'

function fmt(n, currency) {
  const abs = Math.abs(n).toLocaleString('pt-PT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return (n >= 0 ? '+' : '-') + (currency || '') + abs
}

export default function DashboardPage() {
  const [summary, setSummary] = useState([])
  const [error, setError]     = useState('')

  useEffect(() => {
    tournaments.summary()
      .then(setSummary)
      .catch(e => setError(e.message))
  }, [])

  const total_profit = summary.reduce((s, r) => s + Number(r.profit), 0)
  const total_tours  = summary.reduce((s, r) => s + Number(r.total), 0)

  return (
    <>
      <div className="page-header">
        <div className="page-title">Dashboard</div>
        <div className="page-subtitle">Resumo por sala</div>
      </div>

      {error && <div className="error-msg" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="stat-grid" style={{ marginBottom: 32 }}>
        <div className="stat-card">
          <div className="stat-label">Profit total</div>
          <div className={`stat-value ${total_profit >= 0 ? 'green' : 'red'}`}>
            {fmt(total_profit)}
          </div>
          <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>mix EUR/USD</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Torneios</div>
          <div className="stat-value">{total_tours.toLocaleString()}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Salas</div>
          <div className="stat-value">{summary.length}</div>
        </div>
      </div>

      {summary.length > 0 && (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Sala</th>
                  <th>Torneios</th>
                  <th>Buy-in total</th>
                  <th>Cashout total</th>
                  <th>Profit</th>
                  <th>ITM%</th>
                  <th>ROI%</th>
                </tr>
              </thead>
              <tbody>
                {summary.map(r => (
                  <tr key={r.site + r.currency}>
                    <td>{r.site}</td>
                    <td>{r.total}</td>
                    <td className="muted">{r.currency}{Number(r.total_buyin).toLocaleString('pt-PT', { minimumFractionDigits: 2 })}</td>
                    <td className="muted">{r.currency}{Number(r.total_cashout).toLocaleString('pt-PT', { minimumFractionDigits: 2 })}</td>
                    <td className={Number(r.profit) >= 0 ? 'green' : 'red'}>
                      {fmt(Number(r.profit), r.currency)}
                    </td>
                    <td>{r.itm_pct}%</td>
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

      {summary.length === 0 && !error && (
        <div className="empty-state">
          Sem dados ainda. Importa ficheiros em P&L → Import.
        </div>
      )}
    </>
  )
}
