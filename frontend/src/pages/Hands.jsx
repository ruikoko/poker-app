import { useEffect, useState, useCallback } from 'react'
import { hands } from '../api/client'

const STATES = [
  { v: '',          l: 'Todos os estados' },
  { v: 'new',       l: 'Novas (Inbox)' },
  { v: 'review',    l: 'Em Revisão' },
  { v: 'studying',  l: 'A Estudar' },
  { v: 'resolved',  l: 'Resolvidas' },
]

const STATE_COLORS = {
  new:       '#3b82f6',
  review:    '#f59e0b',
  studying:  '#8b5cf6',
  resolved:  '#22c55e',
}

const STATE_LABELS = {
  new:       'Nova',
  review:    'Revisão',
  studying:  'A Estudar',
  resolved:  'Resolvida',
}

function StateBadge({ state }) {
  return (
    <span
      className="badge"
      style={{
        background: STATE_COLORS[state] || '#666',
        color: '#fff',
        fontSize: 10,
        padding: '2px 8px',
        borderRadius: 4,
      }}
    >
      {STATE_LABELS[state] || state}
    </span>
  )
}

function HandDetailModal({ hand, onClose, onUpdate }) {
  const [notes, setNotes] = useState(hand.notes || '')
  const [tags, setTags] = useState((hand.tags || []).join(', '))
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      const tagList = tags.split(',').map(t => t.trim()).filter(Boolean)
      await hands.update(hand.id, { notes, tags: tagList })
      onUpdate()
    } catch (e) {
      alert(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function changeState(newState) {
    try {
      await hands.update(hand.id, { study_state: newState })
      onUpdate()
    } catch (e) {
      alert(e.message)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }} onClick={onClose}>
      <div
        className="card"
        style={{ width: '90%', maxWidth: 700, maxHeight: '85vh', overflow: 'auto', padding: 24 }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontWeight: 700, fontSize: 16 }}>Mão #{hand.id}</span>
            <StateBadge state={hand.study_state} />
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>

        {/* Info grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 24px', marginBottom: 16, fontSize: 13 }}>
          <div><span className="muted">Sala:</span> {hand.site || '—'}</div>
          <div><span className="muted">Data:</span> {hand.played_at ? hand.played_at.slice(0, 16).replace('T', ' ') : '—'}</div>
          <div><span className="muted">Stakes:</span> <span className="mono">{hand.stakes || '—'}</span></div>
          <div><span className="muted">Posição:</span> {hand.position || '—'}</div>
          <div><span className="muted">Cartas:</span> <span className="mono">{hand.hero_cards?.join(' ') || '—'}</span></div>
          <div><span className="muted">Board:</span> <span className="mono">{hand.board?.join(' ') || '—'}</span></div>
          <div><span className="muted">Resultado:</span> <span className={Number(hand.result) >= 0 ? 'green' : 'red'}>{hand.result != null ? Number(hand.result).toFixed(2) : '—'}</span></div>
          <div><span className="muted">Hand ID:</span> <span className="mono" style={{ fontSize: 11 }}>{hand.hand_id || '—'}</span></div>
        </div>

        {/* Raw HH */}
        {hand.raw && (
          <details style={{ marginBottom: 16 }}>
            <summary style={{ cursor: 'pointer', fontSize: 12, color: 'var(--muted)' }}>Ver Hand History completa</summary>
            <pre style={{
              background: 'var(--bg)', padding: 12, borderRadius: 6,
              fontSize: 11, maxHeight: 200, overflow: 'auto', marginTop: 8,
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              {hand.raw}
            </pre>
          </details>
        )}

        {/* Notes */}
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 4 }}>Notas</label>
          <textarea
            rows={3}
            style={{ width: '100%', fontSize: 13 }}
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder="Adicionar notas de estudo…"
          />
        </div>

        {/* Tags */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 4 }}>Tags (separadas por vírgula)</label>
          <input
            type="text"
            style={{ width: '100%', fontSize: 13 }}
            value={tags}
            onChange={e => setTags(e.target.value)}
            placeholder="icm, bvb, sqz-pko…"
          />
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="btn btn-primary btn-sm" disabled={saving} onClick={save}>
            {saving ? 'A guardar…' : 'Guardar'}
          </button>
          {hand.study_state !== 'review' && (
            <button className="btn btn-ghost btn-sm" style={{ borderColor: '#f59e0b', color: '#f59e0b' }} onClick={() => changeState('review')}>
              Marcar para Revisão
            </button>
          )}
          {hand.study_state !== 'studying' && (
            <button className="btn btn-ghost btn-sm" style={{ borderColor: '#8b5cf6', color: '#8b5cf6' }} onClick={() => changeState('studying')}>
              A Estudar
            </button>
          )}
          {hand.study_state !== 'resolved' && (
            <button className="btn btn-ghost btn-sm" style={{ borderColor: '#22c55e', color: '#22c55e' }} onClick={() => changeState('resolved')}>
              Resolvida
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function HandsPage() {
  const [data, setData]       = useState({ data: [], total: 0, pages: 1 })
  const [page, setPage]       = useState(1)
  const [filters, setFilters] = useState({ study_state: '', site: '', position: '', search: '' })
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    const params = { ...filters, page, page_size: 50 }
    hands.list(params)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [page, filters])

  useEffect(() => { load() }, [load])

  function set(key, val) {
    setFilters(f => ({ ...f, [key]: val }))
    setPage(1)
  }

  async function openDetail(id) {
    try {
      const h = await hands.get(id)
      setSelected(h)
    } catch (e) {
      setError(e.message)
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

      {/* Filtros */}
      <div className="filters" style={{ marginBottom: 16 }}>
        <select value={filters.study_state} onChange={e => set('study_state', e.target.value)}>
          {STATES.map(s => <option key={s.v} value={s.v}>{s.l}</option>)}
        </select>
        <select value={filters.site} onChange={e => set('site', e.target.value)}>
          <option value="">Todas as salas</option>
          <option value="GGPoker">GGPoker</option>
          <option value="Winamax">Winamax</option>
        </select>
        <input
          type="text"
          placeholder="Pesquisar…"
          value={filters.search}
          onChange={e => set('search', e.target.value)}
          style={{ maxWidth: 200 }}
        />
        <button className="btn btn-ghost btn-sm" onClick={() => { setFilters({ study_state: '', site: '', position: '', search: '' }); setPage(1) }}>
          Limpar
        </button>
      </div>

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Estado</th>
                <th>Data</th>
                <th>Sala</th>
                <th>Stakes</th>
                <th>Posição</th>
                <th>Cartas</th>
                <th>Board</th>
                <th>Tags</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={9} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>A carregar…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={9}><div className="empty-state">Sem mãos.<br/>Importa ficheiros HH na página P&L.</div></td></tr>
              )}
              {!loading && rows.map(h => (
                <tr key={h.id} style={{ cursor: 'pointer' }} onClick={() => openDetail(h.id)}>
                  <td><StateBadge state={h.study_state} /></td>
                  <td className="muted">{h.played_at ? h.played_at.slice(0, 10) : '—'}</td>
                  <td>{h.site || '—'}</td>
                  <td className="mono">{h.stakes || '—'}</td>
                  <td>{h.position || '—'}</td>
                  <td className="mono">{h.hero_cards?.join(' ') || '—'}</td>
                  <td className="mono">{h.board?.join(' ') || '—'}</td>
                  <td>{h.tags?.map(t => <span key={t} className="badge badge-normal" style={{ marginRight: 3 }}>{t}</span>)}</td>
                  <td>
                    <button className="btn btn-ghost btn-sm" onClick={e => { e.stopPropagation(); deleteHand(h.id) }}>✕</button>
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

      {/* Modal de detalhe */}
      {selected && (
        <HandDetailModal
          hand={selected}
          onClose={() => setSelected(null)}
          onUpdate={() => { setSelected(null); load() }}
        />
      )}
    </>
  )
}
