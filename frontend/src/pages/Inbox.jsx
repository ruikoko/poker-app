import { useEffect, useState, useCallback } from 'react'
import { hands, imports } from '../api/client'

const STATE_COLORS = {
  new:       '#3b82f6',
  review:    '#f59e0b',
  studying:  '#8b5cf6',
  resolved:  '#22c55e',
}

export default function InboxPage() {
  const [data, setData]       = useState({ data: [], total: 0, pages: 1 })
  const [page, setPage]       = useState(1)
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)

  // Import
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    hands.list({ study_state: 'new', page, page_size: 50 })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [page])

  useEffect(() => { load() }, [load])

  async function handleImport(e) {
    const file = e.target.files[0]
    if (!file) return
    setImporting(true)
    setImportResult(null)
    try {
      const res = await imports.upload(file)
      setImportResult(res)
      // Reload if hands were inserted
      if (res.hands_inserted > 0 || res.inserted > 0) load()
    } catch (err) {
      setImportResult({ error: err.message })
    } finally {
      setImporting(false)
      e.target.value = ''
    }
  }

  async function quickAction(id, newState) {
    try {
      await hands.update(id, { study_state: newState })
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  const rows = data.data || []

  return (
    <>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <div>
            <div className="page-title">Inbox</div>
            <div className="page-subtitle">{data.total} mãos novas por processar</div>
          </div>
          <label className="btn btn-primary btn-sm" style={{ cursor: 'pointer' }}>
            {importing ? 'A importar…' : '↑ Importar HH'}
            <input type="file" accept=".txt,.zip" onChange={handleImport} style={{ display: 'none' }} />
          </label>
        </div>
      </div>

      {/* Import result */}
      {importResult && (
        <div className="card" style={{ marginBottom: 16, fontSize: 13, padding: '12px 16px' }}>
          {importResult.error
            ? <span className="red">{importResult.error}</span>
            : importResult.import_type === 'hands'
              ? <>
                  <strong>{importResult.site || 'HH'}</strong> — {importResult.filename}
                  {' · '}mãos encontradas: <strong>{importResult.hands_found}</strong>
                  {' · '}inseridas: <strong className="green">{importResult.hands_inserted}</strong>
                  {' · '}duplicadas: <strong className="muted">{importResult.hands_skipped}</strong>
                  {importResult.errors > 0 && <> · erros: <strong className="red">{importResult.errors}</strong></>}
                </>
              : <>
                  <strong>{importResult.site}</strong> — {importResult.filename}
                  {' · '}registos: <strong>{importResult.records_found}</strong>
                  {' · '}inseridos: <strong className="green">{importResult.inserted}</strong>
                  {importResult.import_type === 'tournaments' && <span className="muted"> (torneios → P&L)</span>}
                </>
          }
        </div>
      )}

      {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Data</th>
                <th>Sala</th>
                <th>Stakes</th>
                <th>Posição</th>
                <th>Cartas</th>
                <th>Board</th>
                <th>Acções</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>A carregar…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={7}>
                  <div className="empty-state">
                    Inbox vazia — todas as mãos foram processadas.<br/>
                    Importa novos ficheiros HH com o botão acima.
                  </div>
                </td></tr>
              )}
              {!loading && rows.map(h => (
                <tr key={h.id}>
                  <td className="muted">{h.played_at ? h.played_at.slice(0, 10) : '—'}</td>
                  <td>{h.site || '—'}</td>
                  <td className="mono">{h.stakes || '—'}</td>
                  <td>{h.position || '—'}</td>
                  <td className="mono">{h.hero_cards?.join(' ') || '—'}</td>
                  <td className="mono">{h.board?.join(' ') || '—'}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ borderColor: '#f59e0b', color: '#f59e0b', fontSize: 11 }}
                        onClick={() => quickAction(h.id, 'review')}
                        title="Marcar para revisão"
                      >
                        Revisão
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ borderColor: '#8b5cf6', color: '#8b5cf6', fontSize: 11 }}
                        onClick={() => quickAction(h.id, 'studying')}
                        title="Marcar como a estudar"
                      >
                        Estudar
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ borderColor: '#22c55e', color: '#22c55e', fontSize: 11 }}
                        onClick={() => quickAction(h.id, 'resolved')}
                        title="Marcar como resolvida"
                      >
                        ✓
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {data.pages > 1 && (
          <div className="pagination">
            <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Anterior</button>
            <span className="muted">Pág. {page} / {data.pages}</span>
            <button className="btn btn-ghost btn-sm" disabled={page >= data.pages} onClick={() => setPage(p => p + 1)}>Próxima →</button>
          </div>
        )}
      </div>
    </>
  )
}
