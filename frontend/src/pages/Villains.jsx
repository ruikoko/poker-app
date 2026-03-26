import { useEffect, useState } from 'react'
import { villains } from '../api/client'

// ── Mini helpers ─────────────────────────────────────────────────────────────

const SUIT_COLORS  = { h: '#ef4444', d: '#f97316', c: '#22c55e', s: '#e2e8f0' }
const SUIT_SYMBOLS = { h: '♥', d: '♦', c: '♣', s: '♠' }

function MiniCard({ card }) {
  if (!card || card.length < 2) return <span style={{ color: '#4b5563' }}>?</span>
  const rank = card.slice(0, -1).toUpperCase()
  const suit = card.slice(-1).toLowerCase()
  const color = SUIT_COLORS[suit] || '#e2e8f0'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 22, height: 30, background: '#1e2130', border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 3, fontFamily: "'Fira Code', monospace", fontSize: 9,
      fontWeight: 700, color, lineHeight: 1, flexDirection: 'column', gap: 0,
    }}>
      <span>{rank}</span>
      <span style={{ fontSize: 7 }}>{SUIT_SYMBOLS[suit]}</span>
    </span>
  )
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ color: '#4b5563' }}>—</span>
  const colors = {
    BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa',
    SB: '#f59e0b', BB: '#ef4444',
    UTG: '#22c55e', UTG1: '#16a34a', UTG2: '#15803d',
    MP: '#06b6d4', MP1: '#0891b2',
  }
  const c = colors[pos] || '#64748b'
  return (
    <span style={{
      display: 'inline-block', padding: '1px 6px', borderRadius: 3,
      fontSize: 10, fontWeight: 700, letterSpacing: 0.4,
      color: c, background: `${c}18`, border: `1px solid ${c}30`,
    }}>{pos}</span>
  )
}

function ResultBadge({ result }) {
  if (result == null) return <span style={{ color: '#4b5563' }}>—</span>
  const val = Number(result)
  if (val > 0) return <span style={{ color: '#22c55e', fontWeight: 600, fontFamily: 'monospace', fontSize: 11 }}>+{val.toFixed(1)}</span>
  if (val < 0) return <span style={{ color: '#ef4444', fontWeight: 600, fontFamily: 'monospace', fontSize: 11 }}>{val.toFixed(1)}</span>
  return <span style={{ color: '#64748b', fontFamily: 'monospace', fontSize: 11 }}>0</span>
}

// ── Villain Profile Panel ────────────────────────────────────────────────────

function VillainProfile({ villain, onClose, onSave }) {
  const [note, setNote]   = useState(villain.note || '')
  const [tags, setTags]   = useState((villain.tags || []).join(', '))
  const [saving, setSaving] = useState(false)

  const [hands, setHands]     = useState([])
  const [handsTotal, setHandsTotal] = useState(0)
  const [handsLoading, setHandsLoading] = useState(false)
  const [handsPage, setHandsPage] = useState(1)

  useEffect(() => {
    loadHands(1)
  }, [villain.nick])

  function loadHands(p) {
    setHandsLoading(true)
    setHandsPage(p)
    villains.searchHands(villain.nick, { page: p, page_size: 10 })
      .then(res => {
        setHands(res.data || [])
        setHandsTotal(res.total || 0)
      })
      .catch(() => {})
      .finally(() => setHandsLoading(false))
  }

  async function save() {
    setSaving(true)
    try {
      await villains.update(villain.id, {
        note,
        tags: tags ? tags.split(',').map(t => t.trim()).filter(Boolean) : [],
      })
      onSave()
    } catch (e) {
      alert(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handsPages = Math.ceil(handsTotal / 10)

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
      backdropFilter: 'blur(4px)',
    }} onClick={onClose}>
      <div
        style={{
          width: '95%', maxWidth: 860, maxHeight: '92vh', overflow: 'auto',
          background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12,
          padding: 28,
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>{villain.nick}</div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              {villain.site && (
                <span style={{ fontSize: 12, color: '#64748b', background: '#0f1117', padding: '2px 8px', borderRadius: 4, border: '1px solid #2a2d3a' }}>
                  {villain.site}
                </span>
              )}
              {(villain.tags || []).map(t => (
                <span key={t} style={{ fontSize: 11, color: '#818cf8', background: 'rgba(99,102,241,0.12)', padding: '2px 8px', borderRadius: 999, border: '1px solid rgba(99,102,241,0.25)' }}>
                  #{t}
                </span>
              ))}
              <span style={{ fontSize: 12, color: '#4b5563' }}>{handsTotal} mãos em comum</span>
            </div>
          </div>
          <button
            style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 18, padding: 4 }}
            onClick={onClose}
          >✕</button>
        </div>

        {/* 2-column layout: notes + hands */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr', gap: 20 }}>

          {/* Left: Notas e Tags */}
          <div>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>
              Notas
            </div>
            <textarea
              rows={6}
              style={{
                width: '100%', fontSize: 13, background: '#0f1117',
                border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0',
                padding: '8px 12px', fontFamily: 'inherit', resize: 'vertical',
                marginBottom: 10,
              }}
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="Tendências, reads, exploits..."
            />

            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 6, textTransform: 'uppercase' }}>
              Tags
            </div>
            <input
              type="text"
              style={{
                width: '100%', fontSize: 13, background: '#0f1117',
                border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0',
                padding: '8px 12px', marginBottom: 14,
              }}
              value={tags}
              onChange={e => setTags(e.target.value)}
              placeholder="fish, aggro, nitty, reg..."
            />

            <button
              style={{
                padding: '8px 20px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                background: '#6366f1', color: '#fff', border: 'none', cursor: 'pointer',
                opacity: saving ? 0.6 : 1,
              }}
              disabled={saving}
              onClick={save}
            >{saving ? 'A guardar...' : 'Guardar'}</button>
          </div>

          {/* Right: Histórico de mãos */}
          <div>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>
              Mãos em Comum ({handsTotal})
            </div>

            {handsLoading && (
              <div style={{ textAlign: 'center', padding: '24px 0', color: '#4b5563', fontSize: 13 }}>A carregar...</div>
            )}

            {!handsLoading && hands.length === 0 && (
              <div style={{
                textAlign: 'center', padding: '32px 16px', color: '#4b5563', fontSize: 13,
                background: '#0f1117', borderRadius: 8, border: '1px solid #1e2130',
              }}>
                Sem mãos em comum na BD.<br />
                <span style={{ fontSize: 11, color: '#374151' }}>Importa HH ou faz match de screenshots.</span>
              </div>
            )}

            {!handsLoading && hands.length > 0 && (
              <div style={{ background: '#0f1117', borderRadius: 8, border: '1px solid #1e2130', overflow: 'hidden' }}>
                {hands.map((h, i) => {
                  const villainActions = h.all_players_actions?.[villain.nick]
                  const villainPos = villainActions?.position || '?'
                  return (
                    <div key={h.id} style={{
                      padding: '10px 14px',
                      borderBottom: i < hands.length - 1 ? '1px solid #1a1d27' : 'none',
                      display: 'flex', alignItems: 'center', gap: 10,
                    }}>
                      {/* Data */}
                      <span style={{ fontSize: 10, color: '#4b5563', minWidth: 48 }}>
                        {h.played_at ? h.played_at.slice(5, 10) : '—'}
                      </span>

                      {/* Hero pos + cards */}
                      <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
                        <PosBadge pos={h.position} />
                        {h.hero_cards?.map((c, j) => <MiniCard key={j} card={c} />)}
                      </div>

                      {/* Villain pos */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <span style={{ fontSize: 10, color: '#4b5563' }}>vs</span>
                        <PosBadge pos={villainPos} />
                      </div>

                      {/* Board */}
                      <div style={{ display: 'flex', gap: 2, flex: 1 }}>
                        {h.board?.slice(0, 5).map((c, j) => <MiniCard key={j} card={c} />)}
                      </div>

                      {/* Resultado */}
                      <ResultBadge result={h.result} />
                    </div>
                  )
                })}
              </div>
            )}

            {/* Paginação */}
            {handsPages > 1 && (
              <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 10 }}>
                <button
                  disabled={handsPage <= 1}
                  onClick={() => loadHands(handsPage - 1)}
                  style={{
                    padding: '4px 12px', borderRadius: 6, fontSize: 11,
                    background: 'transparent', color: handsPage <= 1 ? '#374151' : '#94a3b8',
                    border: '1px solid #2a2d3a', cursor: handsPage <= 1 ? 'not-allowed' : 'pointer',
                  }}
                >←</button>
                <span style={{ color: '#4b5563', fontSize: 11, alignSelf: 'center' }}>
                  {handsPage} / {handsPages}
                </span>
                <button
                  disabled={handsPage >= handsPages}
                  onClick={() => loadHands(handsPage + 1)}
                  style={{
                    padding: '4px 12px', borderRadius: 6, fontSize: 11,
                    background: 'transparent', color: handsPage >= handsPages ? '#374151' : '#94a3b8',
                    border: '1px solid #2a2d3a', cursor: handsPage >= handsPages ? 'not-allowed' : 'pointer',
                  }}
                >→</button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Página Principal ─────────────────────────────────────────────────────────

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

  // Profile panel
  const [selected, setSelected] = useState(null)

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
              <input value={form.site} onChange={e => setForm(f => ({ ...f, site: e.target.value }))} placeholder="GGPoker, Winamax…" />
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
              {!loading && rows.map(v => (
                <tr
                  key={v.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setSelected(v)}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.04)'}
                  onMouseLeave={e => e.currentTarget.style.background = ''}
                >
                  <td>
                    <strong style={{ color: '#e2e8f0' }}>{v.nick}</strong>
                  </td>
                  <td className="muted">{v.site || '—'}</td>
                  <td style={{ minWidth: 200, maxWidth: 300 }}>
                    <span className="muted" style={{ fontSize: 12, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {v.note || <em style={{ color: '#374151' }}>Sem nota</em>}
                    </span>
                  </td>
                  <td>
                    {(v.tags || []).map(t => (
                      <span key={t} className="badge badge-normal" style={{ marginRight: 3 }}>{t}</span>
                    ))}
                  </td>
                  <td className="muted">{v.hands_seen ?? 0}</td>
                  <td onClick={e => e.stopPropagation()}>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => deleteVillain(v.id)}
                    >✕</button>
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

      {/* Profile panel */}
      {selected && (
        <VillainProfile
          villain={selected}
          onClose={() => setSelected(null)}
          onSave={() => { load(); setSelected(null) }}
        />
      )}
    </>
  )
}
