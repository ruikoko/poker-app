import { useEffect, useState } from 'react'
import { hands } from '../api/client'

export default function HandsPage() {
  const [data, setData]       = useState({ data: [], total: 0, pages: 1 })
  const [page, setPage]       = useState(1)
  const [search, setSearch]   = useState('')
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)

  // Inline note editing
  const [editing, setEditing]   = useState(null)  // { id, notes }
  const [saving, setSaving]     = useState(false)

  function load(p = page) {
    setLoading(true)
    hands.list({ page: p, page_size: 50 })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [page])

  async function saveNote(id, notes) {
    setSaving(true)
    try {
      await hands.update(id, { notes })
      setEditing(null)
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function deleteHand(id) {
    if (!confirm('Apagar esta mão?')) return
    try {
      await hands.delete(id)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  const rows = data.data || []

  return (
    <>
      <div className="page-header">
        <div className="page-title">Mãos</div>
        <div className="page-subtitle">{data.total} mãos registadas</div>
      </div>

      {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Data</th>
                <th>Sala</th>
                <th>Stakes</th>
                <th>Cartas</th>
                <th>Resultado</th>
                <th>Notas</th>
                <th>Tags</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>A carregar…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={8}><div className="empty-state">Sem mãos ainda.<br/>As mãos são importadas via ficheiro HH.</div></td></tr>
              )}
              {!loading && rows.map(h => {
                const isEditing = editing?.id === h.id
                return (
                  <tr key={h.id}>
                    <td className="muted">{h.played_at ? h.played_at.slice(0, 10) : '—'}</td>
                    <td>{h.site || '—'}</td>
                    <td className="mono">{h.stakes || '—'}</td>
                    <td className="mono">{h.hero_cards?.join(' ') || '—'}</td>
                    <td className={Number(h.result) >= 0 ? 'green' : 'red'}>
                      {h.result != null ? (Number(h.result) >= 0 ? '+' : '') + Number(h.result).toFixed(2) : '—'}
                    </td>
                    <td style={{ minWidth: 200 }}>
                      {isEditing
                        ? <div style={{ display: 'flex', gap: 6 }}>
                            <textarea
                              rows={2}
                              style={{ flex: 1, fontSize: 12 }}
                              value={editing.notes}
                              onChange={e => setEditing(ed => ({ ...ed, notes: e.target.value }))}
                            />
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                              <button className="btn btn-primary btn-sm" disabled={saving} onClick={() => saveNote(h.id, editing.notes)}>✓</button>
                              <button className="btn btn-ghost btn-sm" onClick={() => setEditing(null)}>✕</button>
                            </div>
                          </div>
                        : <span
                            className="muted"
                            style={{ cursor: 'pointer', fontSize: 12 }}
                            onClick={() => setEditing({ id: h.id, notes: h.notes || '' })}
                          >
                            {h.notes || <em>Adicionar nota…</em>}
                          </span>
                      }
                    </td>
                    <td>{h.tags?.map(t => <span key={t} className="badge badge-normal" style={{ marginRight: 3 }}>{t}</span>)}</td>
                    <td>
                      <button className="btn btn-ghost btn-sm" onClick={() => deleteHand(h.id)}>✕</button>
                    </td>
                  </tr>
                )
              })}
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
