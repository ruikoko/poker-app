import { useEffect, useState } from 'react'
import { villains, hands as handsApi, mtt, hm3 } from '../api/client'

// ── Mini helpers ─────────────────────────────────────────────────────────────

const SUIT_COLORS  = { h: '#ef4444', d: '#f97316', c: '#22c55e', s: '#e2e8f0' }
const SUIT_BG      = { h: '#dc2626', d: '#2563eb', c: '#16a34a', s: '#1e293b' }
const SUIT_SYMBOLS = { h: '♥', d: '♦', c: '♣', s: '♠' }

function MiniCard({ card }) {
  if (!card || card.length < 2) return <span style={{ color: '#4b5563' }}>?</span>
  const rank = card.slice(0, -1).toUpperCase()
  const suit = card.slice(-1).toLowerCase()
  const bg = SUIT_BG[suit] || '#1e2130'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 22, height: 30, background: bg, border: '1px solid rgba(255,255,255,0.2)',
      borderRadius: 3, fontFamily: "'Fira Code', monospace", fontSize: 11,
      fontWeight: 700, color: '#fff', lineHeight: 1, flexDirection: 'column', gap: 0,
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
      fontSize: 11, fontWeight: 700, letterSpacing: 0.4,
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
  const [expandedHand, setExpandedHand] = useState(null)
  const [ssCache, setSsCache] = useState({}) // hand_id -> data_url
  const [ssFullscreen, setSsFullscreen] = useState(null) // data_url for fullscreen

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
                <span style={{ fontSize: 11, color: '#4b5563' }}>Importa HH ou faz match de screenshots.</span>
              </div>
            )}

            {!handsLoading && hands.length > 0 && (
              <div style={{ background: '#0f1117', borderRadius: 8, border: '1px solid #1e2130', overflow: 'hidden' }}>
                {hands.map((h, i) => {
                  const villainActions = h.all_players_actions?.[villain.nick]
                  const villainPos = villainActions?.position || '?'
                  const isExpanded = expandedHand === h.id

                  function toggleExpand() {
                    if (isExpanded) {
                      setExpandedHand(null)
                    } else {
                      setExpandedHand(h.id)
                      // Load screenshot if not cached
                      if (!ssCache[h.id] && (h.entry_id || h.player_names?.screenshot_entry_id)) {
                        handsApi.screenshot(h.id)
                          .then(data => {
                            if (data?.data_url) setSsCache(prev => ({...prev, [h.id]: data.data_url}))
                          })
                          .catch(() => {})
                      }
                    }
                  }

                  // Parse all_players_actions for display
                  const allPlayers = h.all_players_actions || {}
                  const SEAT_ORDER = ['SB', 'BB', 'UTG', 'UTG1', 'UTG2', 'MP', 'MP1', 'HJ', 'CO', 'BTN']
                  const sortedPlayers = Object.entries(allPlayers)
                    .filter(([k]) => k !== '_meta')
                    .map(([name, info]) => ({ name, ...info }))
                    .sort((a, b) => {
                      const ia = SEAT_ORDER.indexOf(a.position)
                      const ib = SEAT_ORDER.indexOf(b.position)
                      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
                    })

                  return (
                    <div key={h.id} style={{ borderBottom: i < hands.length - 1 ? '1px solid #1a1d27' : 'none' }}>
                      {/* Summary row */}
                      <div
                        onClick={toggleExpand}
                        style={{
                          padding: '10px 14px',
                          display: 'flex', alignItems: 'center', gap: 10,
                          cursor: 'pointer',
                        }}
                        onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.04)'}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                      >
                        <span style={{ color: '#4b5563', fontSize: 10 }}>{isExpanded ? '▼' : '▶'}</span>
                        <span style={{ fontSize: 11, color: '#4b5563', minWidth: 48 }}>
                          {h.played_at ? h.played_at.slice(5, 10) : '—'}
                        </span>
                        {/* Villain position + cards first */}
                        <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
                          <PosBadge pos={villainPos} />
                          <span style={{ fontSize: 11, color: '#f59e0b', fontWeight: 600 }}>{villain.nick}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span style={{ fontSize: 11, color: '#4b5563' }}>vs</span>
                          <PosBadge pos={h.position} />
                          {h.hero_cards?.map((c, j) => <MiniCard key={j} card={c} />)}
                        </div>
                        <div style={{ display: 'flex', gap: 2, flex: 1 }}>
                          {h.board?.slice(0, 5).map((c, j) => <MiniCard key={j} card={c} />)}
                        </div>
                        <ResultBadge result={h.result} />
                        {h.stakes && (
                          <span style={{ fontSize: 11, color: '#4b5563', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {h.stakes}
                          </span>
                        )}
                      </div>

                      {/* Expanded detail */}
                      {isExpanded && (
                        <div style={{ padding: '8px 14px 16px 30px', background: 'rgba(255,255,255,0.01)' }}>
                          {/* Tournament info */}
                          {h.stakes && (
                            <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 8 }}>
                              {h.stakes} • {h.played_at ? new Date(h.played_at).toLocaleString('pt-PT') : ''}
                            </div>
                          )}

                          {/* All players table */}
                          {sortedPlayers.length > 0 && (
                            <div style={{ marginBottom: 12 }}>
                              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase' }}>
                                Mesa ({sortedPlayers.length} jogadores)
                              </div>
                              <div style={{ background: '#0f1117', borderRadius: 6, padding: '4px 8px', border: '1px solid #1e2130' }}>
                                {sortedPlayers.map((p, pi) => (
                                  <div key={pi} style={{
                                    display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0',
                                    borderBottom: pi < sortedPlayers.length - 1 ? '1px solid #1a1d27' : 'none',
                                  }}>
                                    <PosBadge pos={p.position} />
                                    <span style={{
                                      fontSize: 11, minWidth: 100,
                                      color: p.is_hero ? '#818cf8' : p.name === villain.nick ? '#f59e0b' : '#94a3b8',
                                      fontWeight: p.is_hero || p.name === villain.nick ? 600 : 400,
                                    }}>
                                      {p.real_name || p.name}
                                      {p.is_hero && <span style={{ fontSize: 8, color: '#6366f1', marginLeft: 3 }}>HERO</span>}
                                      {p.name === villain.nick && <span style={{ fontSize: 8, color: '#f59e0b', marginLeft: 3 }}>★</span>}
                                    </span>
                                    {p.stack_bb != null && (
                                      <span style={{ fontSize: 11, color: '#4b5563', fontFamily: 'monospace' }}>
                                        {p.stack_bb.toFixed(1)} BB
                                      </span>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Screenshot */}
                          {ssCache[h.id] && (
                            <div style={{ marginBottom: 12 }}>
                              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase' }}>Screenshot</div>
                              <img
                                src={ssCache[h.id]}
                                alt="Screenshot"
                                style={{ maxWidth: '100%', maxHeight: 400, borderRadius: 6, border: '1px solid #2a2d3a', cursor: 'pointer' }}
                                onClick={() => setSsFullscreen(ssCache[h.id])}
                              />
                            </div>
                          )}
                          {!ssCache[h.id] && (h.entry_id || h.player_names?.screenshot_entry_id) && (
                            <div style={{ fontSize: 11, color: '#f59e0b', marginBottom: 8 }}>A carregar screenshot...</div>
                          )}

                          {/* 3 acessos à mão */}
                          <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                            {h.raw && h.all_players_actions && (
                              <a href={`/replayer/${h.id}`} target="_blank" rel="noopener noreferrer" style={{
                                fontSize: 11, color: '#818cf8', textDecoration: 'none', padding: '4px 10px',
                                borderRadius: 4, background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)',
                                fontWeight: 600,
                              }}>&#9654; Replayer</a>
                            )}
                            <a href={`/hand/${h.id}`} style={{
                              fontSize: 11, color: '#22c55e', textDecoration: 'none', padding: '4px 10px',
                              borderRadius: 4, background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.2)',
                              fontWeight: 600,
                            }}>HH Formatada</a>
                            {h.raw && (
                              <button onClick={() => { navigator.clipboard.writeText(h.raw); alert('HH copiada!') }} style={{
                                fontSize: 11, color: '#f59e0b', padding: '4px 10px',
                                borderRadius: 4, background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)',
                                fontWeight: 600, cursor: 'pointer',
                              }}>Copiar HH</button>
                            )}
                            {h.player_names?.gg_link && (
                              <a href={h.player_names.gg_link} target="_blank" rel="noopener noreferrer" style={{
                                fontSize: 11, color: '#fbbf24', textDecoration: 'none', padding: '4px 10px',
                                borderRadius: 4, background: 'rgba(251,191,36,0.1)', border: '1px solid rgba(251,191,36,0.2)',
                                fontWeight: 600,
                              }}>GG Replayer</a>
                            )}
                          </div>
                        </div>
                      )}
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

        {/* Screenshot fullscreen modal */}
        {ssFullscreen && (
          <div
            style={{
              position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.92)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000,
              cursor: 'pointer',
            }}
            onClick={() => setSsFullscreen(null)}
          >
            <img src={ssFullscreen} alt="Screenshot" style={{ maxWidth: '95vw', maxHeight: '95vh', borderRadius: 8 }} onClick={e => e.stopPropagation()} />
            <button onClick={() => setSsFullscreen(null)} style={{ position: 'absolute', top: 20, right: 20, background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff', fontSize: 24, cursor: 'pointer', borderRadius: 8, padding: '4px 12px' }}>✕</button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Página Principal ─────────────────────────────────────────────────────────

export default function VillainsPage() {
  const [data, setData]       = useState({ data: [], total: 0, pages: 1 })
  const [page, setPage]       = useState(1)
  const [search, setSearch]   = useState('')
  const [siteFilter, setSiteFilter] = useState('')
  const [sortBy, setSortBy]   = useState('hands_desc')
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
    villains.list({ page: p, page_size: 50, search: s || undefined, site: siteFilter || undefined, sort: sortBy || undefined })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [page, siteFilter, sortBy])

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
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <button
              onClick={async () => {
                if (!confirm('Recalcular hands_seen de todos os vilões (só VPIP)?')) return
                try {
                  const res = await villains.recalculate()
                  alert(`Recalculado: ${res.updated || 0} vilões actualizados`)
                  load()
                } catch (err) { alert('Erro: ' + err.message) }
              }}
              style={{ padding: '4px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: 'rgba(99,102,241,0.12)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.25)', cursor: 'pointer' }}
            >&#x1F504; Recalcular</button>
            <button
              onClick={async () => {
                if (!confirm('Re-enrich: re-processar todos os screenshots e criar villains VPIP?')) return
                try {
                  const res = await mtt.reEnrich()
                  alert(`Re-enrich: ${res.processed || 0} mãos, ${res.villains_created || 0} villains`)
                  load()
                } catch (err) { alert('Erro: ' + err.message) }
              }}
              style={{ padding: '4px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: 'rgba(245,158,11,0.12)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.25)', cursor: 'pointer' }}
            >&#x1F9E0; Re-enrich</button>
            <button
              onClick={async () => {
                if (!confirm('Re-parse: extrair acções de todas as mãos na BD? Pode demorar.')) return
                try {
                  const res = await hm3.reParse()
                  alert(`Re-parse concluído!\n\n${res.processed || 0} mãos processadas\n${res.updated || 0} actualizadas\n${res.errors || 0} erros`)
                  load()
                } catch (err) { alert('Erro: ' + err.message) }
              }}
              style={{ padding: '4px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: 'rgba(34,197,94,0.12)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.25)', cursor: 'pointer' }}
            >&#x1F4BE; Re-parse DB</button>
            <button
              onClick={async () => {
                if (!confirm('Migrar mtt_hands → hands? Copia mãos que faltam para a tabela principal.')) return
                try {
                  const res = await mtt.migrate()
                  alert(`Migração concluída!\n\n${res.migrated || 0} mãos migradas\n${res.skipped || 0} já existiam\n${res.errors || 0} erros`)
                  load()
                } catch (err) { alert('Erro: ' + err.message) }
              }}
              style={{ padding: '4px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: 'rgba(139,92,246,0.12)', color: '#8b5cf6', border: '1px solid rgba(139,92,246,0.25)', cursor: 'pointer' }}
            >&#x1F4E6; Migrar BD</button>
            <button className="btn btn-primary btn-sm" onClick={() => setShowCreate(s => !s)}>
              {showCreate ? 'Cancelar' : '+ Novo'}
            </button>
          </div>
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
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Buscar por nick…"
            style={{ width: 220 }}
          />
          <button type="submit" className="btn btn-ghost btn-sm">Buscar</button>
          {search && <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setSearch(''); load(1, '') }}>✕</button>}
          <select value={siteFilter} onChange={e => { setSiteFilter(e.target.value); setPage(1) }} style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 11px', fontSize: 12 }}>
            <option value="">Todas as salas</option>
            <option value="GGPoker">GGPoker</option>
            <option value="Winamax">Winamax</option>
            <option value="PokerStars">PokerStars</option>
            <option value="WPN">WPN</option>
          </select>
          <select value={sortBy} onChange={e => { setSortBy(e.target.value); setPage(1) }} style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 11px', fontSize: 12 }}>
            <option value="hands_desc">Mais mãos</option>
            <option value="hands_asc">Menos mãos</option>
            <option value="updated_desc">Actualizado recente</option>
            <option value="updated_asc">Actualizado antigo</option>
            <option value="nick_asc">Nick A-Z</option>
          </select>
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
                      {v.note || <em style={{ color: '#4b5563' }}>Sem nota</em>}
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
