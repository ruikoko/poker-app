import { useState, useEffect, useCallback } from 'react'
import { mtt } from '../api/client'

// ── Constantes ───────────────────────────────────────────────────────────────

const SUIT_COLORS  = { h: '#ef4444', d: '#f97316', c: '#22c55e', s: '#e2e8f0' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }

const POS_COLORS = {
  BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa',
  SB: '#f59e0b', BB: '#ef4444',
  UTG: '#22c55e', UTG1: '#16a34a', UTG2: '#15803d',
  MP: '#06b6d4', MP1: '#0891b2',
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function PokerCard({ card, size = 'md' }) {
  if (!card || card.length < 2) {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: size === 'sm' ? 26 : 34, height: size === 'sm' ? 36 : 46,
        background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 4, fontSize: size === 'sm' ? 10 : 12, color: '#4b5563',
      }}>?</span>
    )
  }
  const rank = card.slice(0, -1).toUpperCase()
  const suit = card.slice(-1).toLowerCase()
  const color = SUIT_COLORS[suit] || '#e2e8f0'
  const symbol = SUIT_SYMBOLS[suit] || suit
  return (
    <span style={{
      display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      width: size === 'sm' ? 26 : 34, height: size === 'sm' ? 36 : 46,
      background: '#1e2130', border: '1px solid rgba(255,255,255,0.12)',
      borderRadius: 4, fontFamily: "'Fira Code', monospace",
      fontSize: size === 'sm' ? 10 : 12, fontWeight: 700, color, lineHeight: 1, gap: 1,
      boxShadow: '0 1px 3px rgba(0,0,0,0.4)', userSelect: 'none',
    }}>
      <span>{rank}</span>
      <span style={{ fontSize: size === 'sm' ? 9 : 11 }}>{symbol}</span>
    </span>
  )
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ color: '#4b5563' }}>—</span>
  const c = POS_COLORS[pos] || '#64748b'
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 4,
      fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
      color: c, background: `${c}20`, border: `1px solid ${c}40`,
    }}>{pos}</span>
  )
}

function ResultBadge({ result }) {
  if (result == null) return <span style={{ color: '#4b5563' }}>—</span>
  const val = Number(result)
  if (val > 0) return <span style={{ color: '#22c55e', fontWeight: 600, fontFamily: 'monospace' }}>+{val.toFixed(1)} BB</span>
  if (val < 0) return <span style={{ color: '#ef4444', fontWeight: 600, fontFamily: 'monospace' }}>{val.toFixed(1)} BB</span>
  return <span style={{ color: '#64748b', fontFamily: 'monospace' }}>0 BB</span>
}

function VpipBadge({ action }) {
  const colors = {
    call: { color: '#22c55e', bg: 'rgba(34,197,94,0.10)' },
    raise: { color: '#f97316', bg: 'rgba(249,115,22,0.10)' },
    bet: { color: '#f59e0b', bg: 'rgba(245,158,11,0.10)' },
    'all-in': { color: '#ef4444', bg: 'rgba(239,68,68,0.12)' },
  }
  const s = colors[action] || { color: '#94a3b8', bg: 'rgba(148,163,184,0.08)' }
  return (
    <span style={{
      display: 'inline-block', padding: '1px 6px', borderRadius: 3,
      fontSize: 10, fontWeight: 600, color: s.color, background: s.bg,
    }}>{action}</span>
  )
}

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('pt-PT', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit' })
}

// ── Import Panel ─────────────────────────────────────────────────────────────

function ImportPanel({ onImported }) {
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  const handleFiles = async (files) => {
    if (!files || files.length === 0) return
    setImporting(true)
    setResult(null)
    try {
      const results = []
      for (const file of files) {
        const r = await mtt.import(file)
        results.push(r)
      }
      const total = results.reduce((a, r) => ({
        inserted: a.inserted + (r.inserted || 0),
        skipped: a.skipped + (r.skipped || 0),
        matched: a.matched + (r.matched_with_screenshots || 0),
        villains: a.villains + (r.villains_created || 0),
        errors: a.errors + (r.errors || 0),
      }), { inserted: 0, skipped: 0, matched: 0, villains: 0, errors: 0 })
      setResult(total)
      if (total.inserted > 0) onImported?.()
    } catch (e) {
      setResult({ error: e.message })
    } finally {
      setImporting(false)
    }
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}
      style={{
        border: `2px dashed ${dragOver ? '#6366f1' : 'rgba(255,255,255,0.1)'}`,
        borderRadius: 8, padding: '20px 24px', marginBottom: 16,
        background: dragOver ? 'rgba(99,102,241,0.05)' : 'rgba(255,255,255,0.02)',
        textAlign: 'center', transition: 'all 0.2s',
      }}
    >
      {importing ? (
        <div style={{ color: '#f59e0b' }}>A importar HH de MTT...</div>
      ) : (
        <>
          <div style={{ color: '#94a3b8', marginBottom: 4 }}>
            Arrastar ficheiros HH (.txt / .zip) ou{' '}
            <label style={{ color: '#6366f1', cursor: 'pointer', textDecoration: 'underline' }}>
              clicar para seleccionar
              <input type="file" accept=".txt,.zip" multiple hidden
                onChange={(e) => handleFiles(e.target.files)} />
            </label>
          </div>
          <div style={{ fontSize: 11, color: '#4b5563' }}>
            Hand Histories de MTT completos
          </div>
        </>
      )}
      {result && !result.error && (
        <div style={{ marginTop: 12, fontSize: 12, color: '#94a3b8', display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
          <span style={{ color: '#22c55e' }}>{result.inserted} inseridas</span>
          {result.skipped > 0 && <span style={{ color: '#f59e0b' }}>{result.skipped} duplicadas</span>}
          <span style={{ color: '#6366f1' }}>{result.matched} com screenshot</span>
          <span style={{ color: '#8b5cf6' }}>{result.villains} villains</span>
          {result.errors > 0 && <span style={{ color: '#ef4444' }}>{result.errors} erros</span>}
        </div>
      )}
      {result?.error && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#ef4444' }}>{result.error}</div>
      )}
    </div>
  )
}

// ── Stats Bar ────────────────────────────────────────────────────────────────

function StatsBar({ stats }) {
  if (!stats) return null
  return (
    <div style={{ display: 'flex', gap: 24, marginBottom: 16, flexWrap: 'wrap' }}>
      {[
        { label: 'Mãos MTT', value: stats.total_hands, color: '#e2e8f0' },
        { label: 'Com screenshot', value: stats.hands_with_screenshot, color: '#22c55e' },
        { label: 'Torneios', value: stats.tournaments, color: '#6366f1' },
        { label: 'Villains', value: stats.unique_villains, color: '#f59e0b' },
      ].map(({ label, value, color }) => (
        <div key={label} style={{
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 6, padding: '8px 16px', minWidth: 100,
        }}>
          <div style={{ fontSize: 20, fontWeight: 700, color, fontFamily: 'monospace' }}>{value}</div>
          <div style={{ fontSize: 11, color: '#64748b' }}>{label}</div>
        </div>
      ))}
    </div>
  )
}

// ── Hand Row ─────────────────────────────────────────────────────────────────

function HandRow({ hand, onClick }) {
  return (
    <tr
      onClick={() => onClick(hand)}
      style={{ cursor: 'pointer', borderBottom: '1px solid rgba(255,255,255,0.04)' }}
      onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
      onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
    >
      <td style={{ padding: '8px 12px', fontSize: 12, color: '#94a3b8', whiteSpace: 'nowrap' }}>
        {formatDate(hand.played_at)}<br />
        <span style={{ fontSize: 11, color: '#4b5563' }}>{formatTime(hand.played_at)}</span>
      </td>
      <td style={{ padding: '8px 12px', fontSize: 11, color: '#64748b', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {hand.tournament_name || '—'}
      </td>
      <td style={{ padding: '8px 12px' }}>
        <PosBadge pos={hand.hero_position} />
      </td>
      <td style={{ padding: '8px 12px' }}>
        <div style={{ display: 'flex', gap: 2 }}>
          {(hand.hero_cards || []).map((c, i) => <PokerCard key={i} card={c} size="sm" />)}
        </div>
      </td>
      <td style={{ padding: '8px 12px' }}>
        <div style={{ display: 'flex', gap: 2 }}>
          {(hand.board || []).map((c, i) => <PokerCard key={i} card={c} size="sm" />)}
        </div>
      </td>
      <td style={{ padding: '8px 12px', fontSize: 11, color: '#64748b' }}>
        {hand.blinds}
      </td>
      <td style={{ padding: '8px 12px' }}>
        <ResultBadge result={hand.hero_result} />
      </td>
      <td style={{ padding: '8px 12px' }}>
        {hand.has_screenshot ? (
          <span style={{ color: '#22c55e', fontSize: 11 }}>SS</span>
        ) : (
          <span style={{ color: '#4b5563', fontSize: 11 }}>—</span>
        )}
      </td>
      <td style={{ padding: '8px 12px', fontSize: 11, color: '#8b5cf6' }}>
        {hand.villain_count > 0 ? `${hand.villain_count} V` : '—'}
      </td>
    </tr>
  )
}

// ── Hand Detail Modal ────────────────────────────────────────────────────────

function HandDetailModal({ hand, onClose }) {
  if (!hand) return null

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div style={{
        background: '#1a1d2e', border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 12, padding: 24, maxWidth: 700, width: '95%', maxHeight: '90vh',
        overflow: 'auto', boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
      }} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#e2e8f0' }}>
              {hand.tm_number}
            </div>
            <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
              {hand.tournament_name} — {formatDate(hand.played_at)} {formatTime(hand.played_at)}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: '#64748b', fontSize: 18, cursor: 'pointer',
          }}>x</button>
        </div>

        {/* Hero info */}
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
          <PosBadge pos={hand.hero_position} />
          <div style={{ display: 'flex', gap: 3 }}>
            {(hand.hero_cards || []).map((c, i) => <PokerCard key={i} card={c} />)}
          </div>
          <ResultBadge result={hand.hero_result} />
          <span style={{ fontSize: 12, color: '#64748b' }}>Blinds: {hand.blinds}</span>
          <span style={{ fontSize: 12, color: '#64748b' }}>{hand.num_players} jogadores</span>
        </div>

        {/* Board */}
        {hand.board && hand.board.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Board</div>
            <div style={{ display: 'flex', gap: 4 }}>
              {hand.board.map((c, i) => <PokerCard key={i} card={c} />)}
            </div>
          </div>
        )}

        {/* Villains */}
        {hand.villains && hand.villains.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8 }}>
              Villains (VPIP)
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {hand.villains.map((v, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  background: 'rgba(255,255,255,0.03)', borderRadius: 6, padding: '8px 12px',
                  border: '1px solid rgba(255,255,255,0.05)',
                }}>
                  <PosBadge pos={v.position} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', minWidth: 120 }}>
                    {v.player_name}
                  </span>
                  {v.stack && (
                    <span style={{ fontSize: 11, color: '#64748b' }}>
                      {Number(v.stack).toLocaleString()} chips
                    </span>
                  )}
                  {v.bounty_pct && (
                    <span style={{ fontSize: 11, color: '#f59e0b' }}>
                      {v.bounty_pct}
                    </span>
                  )}
                  {v.country && (
                    <span style={{ fontSize: 11, color: '#64748b' }}>
                      {v.country}
                    </span>
                  )}
                  <VpipBadge action={v.vpip_action} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Screenshot players (from Vision) */}
        {hand.screenshot_players && Object.keys(hand.screenshot_players).length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8 }}>
              Mesa (Screenshot)
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 6 }}>
              {Object.entries(hand.screenshot_players).map(([pos, data]) => {
                const name = typeof data === 'string' ? data : data?.name || '?'
                const stack = typeof data === 'object' ? (data?.stack || data?.stack_chips) : null
                const bounty = typeof data === 'object' ? (data?.bounty_pct || data?.bounty) : null
                const country = typeof data === 'object' ? (data?.country_flag || data?.country) : null
                return (
                  <div key={pos} style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    background: 'rgba(255,255,255,0.02)', borderRadius: 4, padding: '4px 8px',
                    border: '1px solid rgba(255,255,255,0.04)',
                  }}>
                    <PosBadge pos={pos} />
                    <span style={{ fontSize: 12, color: '#94a3b8' }}>{name}</span>
                    {stack && <span style={{ fontSize: 10, color: '#4b5563' }}>{Number(stack).toLocaleString()}</span>}
                    {bounty && <span style={{ fontSize: 10, color: '#f59e0b' }}>{bounty}</span>}
                    {country && <span style={{ fontSize: 10 }}>{country}</span>}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Filter Bar ───────────────────────────────────────────────────────────────

function FilterBar({ filter, setFilter }) {
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
      <select
        value={filter.has_screenshot ?? ''}
        onChange={(e) => setFilter(f => ({ ...f, has_screenshot: e.target.value || null }))}
        style={{
          background: '#1e2130', color: '#94a3b8', border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 4, padding: '4px 8px', fontSize: 12,
        }}
      >
        <option value="">Todas as mãos</option>
        <option value="true">Com screenshot</option>
        <option value="false">Sem screenshot</option>
      </select>
      <input
        type="text"
        placeholder="Pesquisar TM..."
        value={filter.tm_search || ''}
        onChange={(e) => setFilter(f => ({ ...f, tm_search: e.target.value }))}
        style={{
          background: '#1e2130', color: '#e2e8f0', border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 4, padding: '4px 8px', fontSize: 12, width: 160,
        }}
      />
    </div>
  )
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function TournamentsPage() {
  const [hands, setHands] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState({ has_screenshot: 'true', tm_search: '' })
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [selectedHand, setSelectedHand] = useState(null)
  const [detailHand, setDetailHand] = useState(null)
  const pageSize = 50

  const loadHands = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: pageSize }
      if (filter.has_screenshot) params.has_screenshot = filter.has_screenshot
      if (filter.tm_search) params.tm_search = filter.tm_search
      const data = await mtt.hands(params)
      setHands(data.hands || [])
      setTotal(data.total || 0)
    } catch (e) {
      console.error('Erro a carregar mãos MTT:', e)
    } finally {
      setLoading(false)
    }
  }, [page, filter])

  const loadStats = useCallback(async () => {
    try {
      const data = await mtt.stats()
      setStats(data)
    } catch (e) {
      console.error('Erro a carregar stats MTT:', e)
    }
  }, [])

  useEffect(() => { loadHands() }, [loadHands])
  useEffect(() => { loadStats() }, [loadStats])

  const handleHandClick = async (hand) => {
    try {
      const detail = await mtt.hand(hand.id)
      setDetailHand(detail)
    } catch (e) {
      console.error('Erro a carregar detalhe:', e)
    }
  }

  const handleImported = () => {
    loadHands()
    loadStats()
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div style={{ padding: '24px 32px' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0', marginBottom: 4 }}>MTT</h1>
      <p style={{ fontSize: 13, color: '#64748b', marginBottom: 20 }}>
        Mãos de torneios MTT com screenshots e villains
      </p>

      <ImportPanel onImported={handleImported} />
      <StatsBar stats={stats} />
      <FilterBar filter={filter} setFilter={(fn) => { setFilter(fn); setPage(1) }} />

      {loading ? (
        <div style={{ color: '#f59e0b', padding: 20 }}>A carregar...</div>
      ) : hands.length === 0 ? (
        <div style={{ color: '#4b5563', padding: 20, textAlign: 'center' }}>
          Nenhuma mão encontrada. Importa ficheiros HH de MTT acima.
        </div>
      ) : (
        <>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                  {['Data', 'Torneio', 'Pos', 'Cartas', 'Board', 'Blinds', 'Resultado', 'SS', 'Villains'].map(h => (
                    <th key={h} style={{
                      padding: '8px 12px', fontSize: 10, fontWeight: 600,
                      color: '#4b5563', textTransform: 'uppercase', letterSpacing: 0.5,
                      textAlign: 'left',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {hands.map(h => (
                  <HandRow key={h.id} hand={h} onClick={handleHandClick} />
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
              <button
                disabled={page <= 1}
                onClick={() => setPage(p => p - 1)}
                style={{
                  background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 4, padding: '4px 12px', color: '#94a3b8', fontSize: 12,
                  cursor: page <= 1 ? 'default' : 'pointer', opacity: page <= 1 ? 0.4 : 1,
                }}
              >Anterior</button>
              <span style={{ fontSize: 12, color: '#64748b', padding: '4px 8px' }}>
                {page} / {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage(p => p + 1)}
                style={{
                  background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 4, padding: '4px 12px', color: '#94a3b8', fontSize: 12,
                  cursor: page >= totalPages ? 'default' : 'pointer', opacity: page >= totalPages ? 0.4 : 1,
                }}
              >Seguinte</button>
            </div>
          )}
        </>
      )}

      {/* Detail Modal */}
      <HandDetailModal hand={detailHand} onClose={() => setDetailHand(null)} />
    </div>
  )
}
