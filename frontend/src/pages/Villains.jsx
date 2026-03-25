import { useEffect, useState } from 'react'
import { villains } from '../api/client'

export default function VillainsPage() {
  const [data, setData]       = useState({ data: [], total: 0, pages: 1 })
  const [page, setPage]       = useState(1)
  const [search, setSearch]   = useState('')
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)

  // Create form
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ site: '', nick: '', note: '', tags: '' })
  const [creating, setCreating]     = useState(false)

  // Inline edit
  const [editing, setEditing] = useState(null)
  const [saving, setSaving]   = useState(false)

  function load(p = page, s = search) {
    setLoading(true)
    villains.list({ page: p, page_size: 50, search: s || undefined })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [page])

  function handleSearch(e) {
    e.preventDefault()
    setPage(1)
    load(1, search)
  }

  async function handleCreate(e) {
    e.preventDefault()
    setCreating(true)
    try {
      await villains.create({
        ...form,
        tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : []
      })
      setForm({ site: '', nick: '', note: '', tags: '' })
      setShowCreate(false)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setCreating(false)
    }
  }

  async function saveEdit(id) {
    setSaving(true)
    try {
      await villains.update(id, {
        note: editing.note,
        tags: editing.tags ? editing.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
      })
      setEditing(null)
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function deleteVillain(id) {
    if (!confirm('Apagar este vilão?')) return
    try {
      await villains.delete(id)
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
            <div className="page-title">Vilões</div>
            <div className="page-subtitle">{data.total} notas</div>
          </div>
          <button className="btn btn-primary btn-sm" onClick={() => setShowCreate(s => !s)}>
            {showCreate ? 'Cancelar' : '+ Novo'}
          </button>
        </div>
      </div>

      {showCreate && (
        <div className="card" style={{ marginBottom: 16 }}>
          <form onSubmit={handleCreate} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="form-group">
              <label>Nick *</label>
              <input required value={form.nick} onChange={e => setForm(f => ({ ...f, nick: e.target.value }))} />
            </div>
            <div className="form-group">
              <label>Sala</label>
              <input value={form.site} onChange={e => setForm(f => ({ ...f, site: e.target.value }))} placeholder="Winamax, GGPoker…" />
            </div>
            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
              <label>Nota</label>
              <textarea rows={3} value={form.note} onChange={e => setForm(f => ({ ...f, note: e.target.value }))} />
            </div>
            <div className="form-group">
              <label>Tags (separadas por vírgula)</label>
              <input value={form.tags} onChange={e => setForm(f => ({ ...f, tags: e.target.value }))} placeholder="fish, aggro, nitty" />
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button className="btn btn-primary" type="submit" disabled={creating}>
                {creating ? 'A guardar…' : 'Guardar'}
              </button>
            </div>
          </form>
        </div>
      )}

      {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}

      <div style={{ marginBottom: 12 }}>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8 }}>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Buscar por nick…"
            style={{ width: 220 }}
          />
          <button type="submit" className="btn btn-ghost btn-sm">Buscar</button>
          {search && <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setSearch(''); load(1, '') }}>✕</button>}
        </form>
      </div>

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Nick</th>
                <th>Sala</th>
                <th>Nota</th>
                <th>Tags</th>
                <th>Mãos</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={6} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>A carregar…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={6}><div className="empty-state">Sem vilões. Cria o primeiro acima.</div></td></tr>
              )}
              {!loading && rows.map(v => {
                const isEditing = editing?.id === v.id
                return (
                  <tr key={v.id}>
                    <td><strong>{v.nick}</strong></td>
                    <td className="muted">{v.site || '—'}</td>
                    <td style={{ minWidth: 240 }}>
                      {isEditing
                        ? <textarea
                            rows={2}
                            style={{ width: '100%', fontSize: 12 }}
                            value={editing.note}
                            onChange={e => setEditing(ed => ({ ...ed, note: e.target.value }))}
                          />
                        : <span
                            className="muted"
                            style={{ cursor: 'pointer', fontSize: 12 }}
                            onClick={() => setEditing({ id: v.id, note: v.note || '', tags: v.tags?.join(', ') || '' })}
                          >
                            {v.note || <em>Clica para editar…</em>}
                          </span>
                      }
                    </td>
                    <td>
                      {isEditing
                        ? <input
                            value={editing.tags}
                            onChange={e => setEditing(ed => ({ ...ed, tags: e.target.value }))}
                            style={{ fontSize: 12, width: 140 }}
                            placeholder="tag1, tag2"
                          />
                        : v.tags?.map(t => <span key={t} className="badge badge-normal" style={{ marginRight: 3 }}>{t}</span>)
                      }
                    </td>
                    <td className="muted">{v.hands_seen ?? 0}</td>
                    <td>
                      {isEditing
                        ? <div style={{ display: 'flex', gap: 4 }}>
                            <button className="btn btn-primary btn-sm" disabled={saving} onClick={() => saveEdit(v.id)}>✓</button>
                            <button className="btn btn-ghost btn-sm" onClick={() => setEditing(null)}>✕</button>
                          </div>
                        : <button className="btn btn-ghost btn-sm" onClick={() => deleteVillain(v.id)}>✕</button>
                      }
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
