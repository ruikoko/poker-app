import { useState, useEffect, useCallback } from 'react'
import { mtt } from '../api/client'
import HandRow from '../components/HandRow'

// ── Constantes ───────────────────────────────────────────────────────────────

const SUIT_COLORS  = { h: '#ef4444', d: '#f97316', c: '#22c55e', s: '#e2e8f0' }
const SUIT_BG      = { h: '#dc2626', d: '#2563eb', c: '#16a34a', s: '#1e293b' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }

const POS_COLORS = {
  BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa',
  SB: '#f59e0b', BB: '#ef4444',
  UTG: '#22c55e', UTG1: '#16a34a', UTG2: '#15803d',
  MP: '#06b6d4', MP1: '#0891b2',
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function PokerCard({ card, size = 'sm' }) {
  if (!card || card.length < 2) {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: 24, height: 34,
        background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 3, fontSize: 11, color: '#4b5563',
      }}>?</span>
    )
  }
  const rank = card.slice(0, -1).toUpperCase()
  const suit = card.slice(-1).toLowerCase()
  const bg = SUIT_BG[suit] || '#1e2130'
  const symbol = SUIT_SYMBOLS[suit] || suit
  return (
    <span style={{
      display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      width: 24, height: 34,
      background: bg, border: '1px solid rgba(255,255,255,0.2)',
      borderRadius: 3, fontFamily: "'Fira Code', monospace",
      fontSize: 11, fontWeight: 700, color: '#fff', lineHeight: 1, gap: 0,
      boxShadow: '0 1px 2px rgba(0,0,0,0.3)', userSelect: 'none',
    }}>
      <span>{rank}</span>
      <span style={{ fontSize: 9 }}>{symbol}</span>
    </span>
  )
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ display: 'inline-block', width: 48, textAlign: 'center', color: '#4b5563' }}>—</span>
  const c = POS_COLORS[pos] || '#64748b'
  const isBlind = pos === 'SB' || pos === 'BB'
  return (
    <span style={{
      display: 'inline-block', padding: '1px 0', borderRadius: 3, width: 48, textAlign: 'center',
      fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
      color: '#0a0c14', background: isBlind ? c : '#e2e8f0', border: `1px solid ${isBlind ? c : '#e2e8f0'}`,
    }}>{pos}</span>
  )
}

function ResultBadge({ result }) {
  if (result == null) return <span style={{ color: '#4b5563' }}>—</span>
  const val = Number(result)
  if (val > 0) return <span style={{ color: '#22c55e', fontWeight: 600, fontFamily: 'monospace', fontSize: 12 }}>+{val.toFixed(1)}</span>
  if (val < 0) return <span style={{ color: '#ef4444', fontWeight: 600, fontFamily: 'monospace', fontSize: 12 }}>{val.toFixed(1)}</span>
  return <span style={{ color: '#64748b', fontFamily: 'monospace', fontSize: 12 }}>0</span>
}

function formatDateLabel(iso) {
  if (!iso) return 'Sem data'
  const d = new Date(iso)
  const weekdays = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']
  return `${weekdays[d.getDay()]}, ${d.toLocaleDateString('pt-PT', { day: '2-digit', month: 'long', year: 'numeric' })}`
}

function formatDateKey(iso) {
  if (!iso) return 'unknown'
  return iso.slice(0, 10)
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
        borderRadius: 8, padding: '16px 24px', marginBottom: 16,
        background: dragOver ? 'rgba(99,102,241,0.05)' : 'rgba(255,255,255,0.02)',
        textAlign: 'center', transition: 'all 0.2s',
      }}
    >
      {importing ? (
        <div style={{ color: '#f59e0b' }}>A importar HH de MTT...</div>
      ) : (
        <>
          <div style={{ color: '#94a3b8', fontSize: 13 }}>
            Arrastar ficheiros HH (.txt / .zip) ou{' '}
            <label style={{ color: '#6366f1', cursor: 'pointer', textDecoration: 'underline' }}>
              clicar
              <input type="file" accept=".txt,.zip" multiple hidden
                onChange={(e) => handleFiles(e.target.files)} />
            </label>
          </div>
        </>
      )}
      {result && !result.error && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#94a3b8', display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
          <span style={{ color: '#22c55e' }}>{result.inserted} mãos</span>
          {result.skipped > 0 && <span style={{ color: '#f59e0b' }}>{result.skipped} dup</span>}
          <span style={{ color: '#6366f1' }}>{result.matched} com SS</span>
          <span style={{ color: '#8b5cf6' }}>{result.villains} villains</span>
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
    <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
      {[
        { label: 'Mãos', value: stats.total_hands, color: '#e2e8f0' },
        { label: 'Com SS', value: stats.hands_with_screenshot, color: '#22c55e' },
        { label: 'Torneios', value: stats.tournaments, color: '#6366f1' },
        { label: 'Villains', value: stats.unique_villains, color: '#f59e0b' },
      ].map(({ label, value, color }) => (
        <div key={label} style={{
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 6, padding: '6px 14px',
        }}>
          <span style={{ fontSize: 16, fontWeight: 700, color, fontFamily: 'monospace' }}>{value}</span>
          <span style={{ fontSize: 11, color: '#4b5563', marginLeft: 6 }}>{label}</span>
        </div>
      ))}
    </div>
  )
}

// ── Villain Row (inside hand detail) ─────────────────────────────────────────

function VillainRow({ v }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      background: 'rgba(255,255,255,0.02)', borderRadius: 4, padding: '4px 8px',
      border: '1px solid rgba(255,255,255,0.04)',
    }}>
      <PosBadge pos={v.position} />
      <span style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', minWidth: 100 }}>
        {v.player_name}
      </span>
      {v.stack && (
        <span style={{ fontSize: 11, color: '#64748b' }}>
          {Number(v.stack).toLocaleString()}
        </span>
      )}
      {v.bounty_pct && (
        <span style={{ fontSize: 11, color: '#f59e0b' }}>{v.bounty_pct}</span>
      )}
      {v.country && (
        <span style={{ fontSize: 11, color: '#64748b' }}>{v.country}</span>
      )}
      <span style={{
        fontSize: 11, fontWeight: 600, padding: '1px 5px', borderRadius: 3,
        color: v.vpip_action === 'call' ? '#22c55e' : v.vpip_action === 'raise' ? '#f97316' : '#ef4444',
        background: v.vpip_action === 'call' ? 'rgba(34,197,94,0.1)' : v.vpip_action === 'raise' ? 'rgba(249,115,22,0.1)' : 'rgba(239,68,68,0.1)',
      }}>{v.vpip_action}</span>
    </div>
  )
}

// ── Hand Row (inside tournament group) ───────────────────────────────────────

// Expansion abaixo da HandRow: villains (VPIP) + mesa (screenshot players) + acções.
function TournamentDetail({ hand, onDeleteHand, onDeleteScreenshot }) {
  const hasVillains = hand.villains && hand.villains.length > 0
  const hasSsPlayers = hand.screenshot_players && Object.keys(hand.screenshot_players).length > 0

  return (
    <div style={{ padding: '8px 12px 12px 52px', background: 'rgba(255,255,255,0.01)' }}>
      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
        {hand.raw && (
          <button onClick={() => navigator.clipboard.writeText(hand.raw)}
            style={{ padding: '4px 12px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: 'rgba(34,197,94,0.1)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.2)', cursor: 'pointer' }}
          >Copiar HH</button>
        )}
        <a href={`/replayer/${hand.id}`} target="_blank" rel="noopener noreferrer"
          style={{ padding: '4px 12px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: 'rgba(99,102,241,0.1)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.2)', textDecoration: 'none' }}
        >&#9654; Replayer</a>
        <a href={`/hand/${hand.id}`} target="_blank" rel="noopener noreferrer"
          style={{ padding: '4px 12px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: 'rgba(245,158,11,0.1)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.2)', textDecoration: 'none' }}
        >Detalhe</a>
      </div>

      {/* Villains */}
      {hasVillains && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4, fontWeight: 600 }}>
            Villains (VPIP)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {hand.villains.map((v, i) => <VillainRow key={i} v={v} />)}
          </div>
        </div>
      )}

      {/* Screenshot players */}
      {hasSsPlayers && (
        <div>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4, fontWeight: 600 }}>
            Mesa (Screenshot)
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {Object.entries(hand.screenshot_players).map(([pos, data]) => {
              const name = typeof data === 'string' ? data : data?.name || '?'
              const bounty = typeof data === 'object' ? (data?.bounty_pct || data?.bounty) : null
              const country = typeof data === 'object' ? (data?.country_flag || data?.country) : null
              return (
                <div key={pos} style={{
                  display: 'flex', alignItems: 'center', gap: 4,
                  background: 'rgba(255,255,255,0.02)', borderRadius: 3, padding: '2px 6px',
                  border: '1px solid rgba(255,255,255,0.04)', fontSize: 11,
                }}>
                  <PosBadge pos={pos} />
                  <span style={{ color: '#94a3b8' }}>{name}</span>
                  {bounty ? <span style={{ color: '#f59e0b', fontSize: 9 }}>{bounty}</span> : null}
                  {country ? <span style={{ fontSize: 9 }}>{country}</span> : null}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {!hasVillains && !hasSsPlayers && (
        <div style={{ fontSize: 11, color: '#4b5563', fontStyle: 'italic' }}>
          Sem dados adicionais
        </div>
      )}

      {/* Delete SS (apagar mão já está no HandRow) */}
      {hand.has_screenshot && hand.screenshot_entry_id && (
        <div style={{ display: 'flex', gap: 8, marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          <button
            onClick={() => onDeleteScreenshot(hand.screenshot_entry_id)}
            style={{
              padding: '3px 10px', borderRadius: 4, fontSize: 11, fontWeight: 600,
              background: 'rgba(239,68,68,0.08)', color: '#ef4444',
              border: '1px solid rgba(239,68,68,0.2)', cursor: 'pointer',
            }}
          >Apagar Screenshot</button>
        </div>
      )}
    </div>
  )
}

// ── Tournament Group ─────────────────────────────────────────────────────────

function TournamentGroup({ tmNumber, tournamentName, hands, expandedHands, toggleHand, onDeleteHand, onDeleteScreenshot }) {
  const [open, setOpen] = useState(false)
  const ssCount = hands.filter(h => h.has_screenshot).length
  const totalVillains = hands.reduce((a, h) => a + (h.villain_count || 0), 0)

  const buyIn = hands.find(h => h.buy_in != null)?.buy_in
  const fmtBuyIn = v => (v % 1 === 0 ? `$${v}` : `$${v.toFixed(2)}`)

  // hands vêm ordenadas DESC por played_at → [0]=mais recente, [last]=mais antiga
  const newest = hands[0]
  const oldest = hands[hands.length - 1]
  const blindsLabel = !oldest ? ''
    : (oldest.blinds === newest.blinds ? oldest.blinds : `${oldest.blinds} → ${newest.blinds}`)
  const timeRange = !oldest ? ''
    : (oldest.played_at === newest.played_at
        ? formatTime(oldest.played_at)
        : `${formatTime(oldest.played_at)} → ${formatTime(newest.played_at)}`)

  const sep = { fontSize: 11, color: '#4b5563' }

  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.05)',
      borderRadius: 6, marginBottom: 4, overflow: 'hidden',
    }}>
      {/* Tournament header */}
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
          cursor: 'pointer', background: 'rgba(255,255,255,0.02)',
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.04)'}
        onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
      >
        <span style={{ color: '#6366f1', fontSize: 12 }}>{open ? '▼' : '▶'}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0' }}>{tmNumber}</span>
        {tournamentName && (
          <>
            <span style={sep}>·</span>
            <span style={{ fontSize: 11, color: '#94a3b8', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {tournamentName}
            </span>
          </>
        )}
        {buyIn != null && (
          <>
            <span style={sep}>·</span>
            <span style={{ fontSize: 11, fontWeight: 600, color: '#f59e0b' }}>{fmtBuyIn(buyIn)}</span>
          </>
        )}
        {blindsLabel && (
          <>
            <span style={sep}>·</span>
            <span style={{ fontSize: 11, color: '#64748b' }}>{blindsLabel}</span>
          </>
        )}
        {timeRange && (
          <>
            <span style={sep}>·</span>
            <span style={{ fontSize: 11, color: '#64748b' }}>{timeRange}</span>
          </>
        )}
        <span style={{ marginLeft: 'auto', display: 'flex', gap: 12 }}>
          <span style={{ fontSize: 11, color: '#94a3b8' }}>{hands.length} mãos</span>
          <span style={{ fontSize: 11, color: '#22c55e' }}>{ssCount} SS</span>
          {totalVillains > 0 && (
            <span style={{ fontSize: 11, color: '#8b5cf6' }}>{totalVillains} V</span>
          )}
        </span>
      </div>

      {/* Hands list */}
      {open && (
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          {hands.map((h, idx) => (
            <div key={h.id}>
              <HandRow
                hand={h}
                idx={idx}
                onClick={() => toggleHand(h.id)}
                onDelete={onDeleteHand}
              />
              {expandedHands.has(h.id) && (
                <TournamentDetail
                  hand={h}
                  onDeleteHand={onDeleteHand}
                  onDeleteScreenshot={onDeleteScreenshot}
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Date Group ───────────────────────────────────────────────────────────────

function DateGroup({ dateKey, dateLabel, tournaments, expandedHands, toggleHand, onDeleteHand, onDeleteScreenshot }) {
  const [open, setOpen] = useState(false)
  const tmKeys = Object.keys(tournaments)
  const totalHands = tmKeys.reduce((a, k) => a + tournaments[k].hands.length, 0)
  const totalSS = tmKeys.reduce((a, k) => a + tournaments[k].hands.filter(h => h.has_screenshot).length, 0)

  return (
    <div style={{ marginBottom: 8 }}>
      {/* Date header */}
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px',
          cursor: 'pointer', background: 'rgba(255,255,255,0.03)',
          borderRadius: 6, border: '1px solid rgba(255,255,255,0.06)',
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
        onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
      >
        <span style={{ color: '#f59e0b', fontSize: 13 }}>{open ? '▼' : '▶'}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0' }}>{dateLabel}</span>
        <span style={{ fontSize: 11, color: '#6366f1' }}>
          {tmKeys.length} torneio{tmKeys.length !== 1 ? 's' : ''}
        </span>
        <span style={{ fontSize: 11, color: '#22c55e' }}>
          {totalSS} SS
        </span>
        <span style={{ fontSize: 11, color: '#94a3b8' }}>
          {totalHands} mãos
        </span>
      </div>

      {/* Tournaments */}
      {open && (
        <div style={{ paddingLeft: 16, paddingTop: 4 }}>
          {tmKeys.map(tm => (
            <TournamentGroup
              key={tm}
              tmNumber={tm}
              tournamentName={tournaments[tm].name}
              hands={tournaments[tm].hands}
              expandedHands={expandedHands}
              toggleHand={toggleHand}
              onDeleteHand={onDeleteHand}
              onDeleteScreenshot={onDeleteScreenshot}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function TournamentsPage() {
  const [tab, setTab] = useState('gg') // 'gg' or 'hm3'
  const [hands, setHands] = useState([])
  const [stats, setStats] = useState(null)
  const [notaStats, setNotaStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState({ ss_filter: 'with' })
  const [expandedHands, setExpandedHands] = useState(new Set())

  const loadHands = useCallback(async () => {
    setLoading(true)
    try {
      if (tab === 'gg') {
        const params = { page: 1, page_size: 200 }
        if (filter.ss_filter) params.ss_filter = filter.ss_filter
        if (filter.tm_search) params.tm_search = filter.tm_search
        const data = await mtt.hands(params)
        setHands(data.hands || [])
      } else {
        const { hm3 } = await import('../api/client')
        const data = await hm3.notaHands({ page: 1, page_size: 200 })
        setHands(data.hands || [])
      }
    } catch (e) {
      console.error('Erro a carregar mãos:', e)
    } finally {
      setLoading(false)
    }
  }, [filter, tab])

  const loadStats = useCallback(async () => {
    try {
      const data = await mtt.stats()
      setStats(data)
      const { hm3 } = await import('../api/client')
      const ns = await hm3.notaStats()
      setNotaStats(ns)
    } catch (e) {
      console.error('Erro a carregar stats:', e)
    }
  }, [])

  useEffect(() => { loadHands() }, [loadHands])
  useEffect(() => { loadStats() }, [loadStats])

  const toggleHand = useCallback((id) => {
    setExpandedHands(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const handleDeleteHand = async (handId) => {
    if (!confirm('Apagar esta mão e vilões associados?')) return
    try {
      await mtt.deleteHand(handId)
      loadHands()
      loadStats()
    } catch (e) {
      alert('Erro ao apagar: ' + e.message)
    }
  }

  const handleDeleteScreenshot = async (entryId) => {
    if (!confirm('Apagar screenshot e reverter match?')) return
    try {
      await mtt.deleteScreenshot(entryId)
      loadHands()
      loadStats()
    } catch (e) {
      alert('Erro ao apagar screenshot: ' + e.message)
    }
  }

  // Agrupar por data > torneio
  const grouped = {}
  for (const h of hands) {
    const dateKey = formatDateKey(h.played_at)
    if (!grouped[dateKey]) grouped[dateKey] = {}
    const tourneyKey = h.tournament_name || h.tm_number || h.stakes || 'unknown'
    if (!grouped[dateKey][tourneyKey]) {
      grouped[dateKey][tourneyKey] = { name: h.tournament_name || h.stakes, hands: [] }
    }
    grouped[dateKey][tourneyKey].hands.push(h)
  }
  const sortedDates = Object.keys(grouped).sort((a, b) => b.localeCompare(a))

  const tabStyle = (active) => ({
    padding: '8px 24px', borderRadius: '6px 6px 0 0', fontSize: 14, fontWeight: 700,
    cursor: 'pointer', border: 'none', transition: 'all 0.2s',
    background: active ? '#1e2130' : 'transparent',
    color: active ? '#e2e8f0' : '#64748b',
    borderBottom: active ? '2px solid #6366f1' : '2px solid transparent',
  })

  return (
    <div style={{ padding: '24px 32px' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0', marginBottom: 4 }}>MTT</h1>
      <p style={{ fontSize: 13, color: '#64748b', marginBottom: 16 }}>
        Mãos de torneios para estudo
      </p>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <button style={tabStyle(tab === 'gg')} onClick={() => { setTab('gg'); setFilter({ ss_filter: 'with' }) }}>
          GG
          {stats && <span style={{ fontSize: 11, color: '#22c55e', marginLeft: 8 }}>{stats.hands_with_screenshot || 0}</span>}
        </button>
        <button style={tabStyle(tab === 'hm3')} onClick={() => { setTab('hm3'); setFilter({}) }}>
          HM3 com Nota
          {notaStats && <span style={{ fontSize: 11, color: '#f59e0b', marginLeft: 8 }}>{notaStats.total_hands || 0}</span>}
        </button>
      </div>

      {/* Stats bar */}
      {tab === 'gg' && <StatsBar stats={stats} />}
      {tab === 'hm3' && notaStats && (
        <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
          {[
            { label: 'Mãos', value: notaStats.total_hands, color: '#e2e8f0' },
            { label: 'Com Showdown', value: notaStats.with_showdown, color: '#8b5cf6' },
            { label: 'Torneios', value: notaStats.tournaments, color: '#6366f1' },
            { label: 'Salas', value: notaStats.sites, color: '#f59e0b' },
          ].map(({ label, value, color }) => (
            <div key={label} style={{
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 6, padding: '6px 14px',
            }}>
              <span style={{ fontSize: 16, fontWeight: 700, color, fontFamily: 'monospace' }}>{value}</span>
              <span style={{ fontSize: 11, color: '#4b5563', marginLeft: 6 }}>{label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Sub-navegação GG: Com SS / Sem SS */}
      {tab === 'gg' && (
        <div style={{
          display: 'inline-flex', gap: 4, marginBottom: 12, padding: 3,
          background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 8,
        }}>
          {[
            { value: 'with',    label: 'Com SS', color: '#22c55e' },
            { value: 'without', label: 'Sem SS', color: '#94a3b8' },
          ].map(({ value, label, color }) => {
            const active = filter.ss_filter === value
            return (
              <button
                key={value}
                onClick={() => setFilter(f => ({ ...f, ss_filter: value }))}
                style={{
                  padding: '6px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                  border: 'none', cursor: 'pointer',
                  background: active ? color : 'transparent',
                  color: active ? '#0a0c14' : color,
                  transition: 'all 0.15s',
                }}
              >{label}</button>
            )
          })}
        </div>
      )}

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        {tab === 'gg' && (
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
        )}
      </div>

      {loading ? (
        <div style={{ color: '#f59e0b', padding: 20 }}>A carregar...</div>
      ) : sortedDates.length === 0 ? (
        <div style={{ color: '#4b5563', padding: 20, textAlign: 'center' }}>
          {tab === 'gg'
            ? (filter.ss_filter === 'without'
                ? 'Nenhuma mão GG sem SS encontrada.'
                : 'Nenhuma mão GG com SS encontrada.')
            : 'Nenhuma mão HM3 com tag nota encontrada.'}
        </div>
      ) : (
        <div>
          {sortedDates.map(dateKey => (
            <DateGroup
              key={dateKey}
              dateKey={dateKey}
              dateLabel={formatDateLabel(dateKey + 'T12:00:00')}
              tournaments={grouped[dateKey]}
              expandedHands={expandedHands}
              toggleHand={toggleHand}
              onDeleteHand={handleDeleteHand}
              onDeleteScreenshot={handleDeleteScreenshot}
            />
          ))}
        </div>
      )}
    </div>
  )
}
