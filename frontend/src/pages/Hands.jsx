import { useEffect, useState, useCallback } from 'react'
import { hands, equity, screenshots } from '../api/client'
import Replayer from '../components/Replayer'
import { isHero } from '../heroNames'
import TagEditor from '../components/TagEditor'
import HandRow from '../components/HandRow'
import HandHistoryViewer from '../components/HandHistoryViewer'

// A aba Mãos é para estudo — exclui mãos que só têm a tag #mtt (bulk HH sem marcação)

// ── Constantes ──────────────────────────────────────────────────────────────

const STATES = [
  { v: '',          l: 'Todos os estados' },
  { v: 'new',       l: 'Novas' },
  { v: 'review',    l: 'Em Revisão' },
  { v: 'studying',  l: 'A Estudar' },
  { v: 'resolved',  l: 'Resolvidas' },
]

const POSITIONS = ['', 'UTG', 'UTG1', 'UTG2', 'MP', 'MP1', 'HJ', 'CO', 'BTN', 'SB', 'BB']

const STATE_META = {
  new:      { label: 'Nova',      color: '#3b82f6', bg: 'rgba(59,130,246,0.15)' },
  review:   { label: 'Revisão',   color: '#f59e0b', bg: 'rgba(245,158,11,0.15)' },
  studying: { label: 'A Estudar', color: '#8b5cf6', bg: 'rgba(139,92,246,0.15)' },
  resolved: { label: 'Resolvida', color: '#22c55e', bg: 'rgba(34,197,94,0.15)'  },
}

const SUIT_COLORS = {
  h: '#ef4444', d: '#f97316', c: '#22c55e', s: '#e2e8f0',
}
const SUIT_BG = {
  h: '#dc2626', d: '#2563eb', c: '#16a34a', s: '#1e293b',
}
const SUIT_SYMBOLS = {
  h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660',
}

const STREET_LABELS = {
  preflop: 'Pre-Flop',
  flop: 'Flop',
  turn: 'Turn',
  river: 'River',
}

const STREET_COLORS = {
  preflop: '#6366f1',
  flop: '#22c55e',
  turn: '#f59e0b',
  river: '#ef4444',
}

// ── Componente: Carta de Poker ───────────────────────────────────────────────

function PokerCard({ card, size = 'md' }) {
  if (!card || card.length < 2) {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: size === 'sm' ? 26 : size === 'lg' ? 38 : 34,
        height: size === 'sm' ? 36 : size === 'lg' ? 50 : 46,
        background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 4, fontSize: size === 'sm' ? 10 : 12, color: '#4b5563',
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
      width: size === 'sm' ? 26 : size === 'lg' ? 38 : 34,
      height: size === 'sm' ? 36 : size === 'lg' ? 50 : 46,
      background: bg, border: '1px solid rgba(255,255,255,0.2)',
      borderRadius: 4, fontFamily: "'Fira Code', monospace",
      fontSize: size === 'sm' ? 10 : size === 'lg' ? 14 : 12,
      fontWeight: 700, color: '#fff', lineHeight: 1, gap: 1, userSelect: 'none',
      boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
    }}>
      <span>{rank}</span>
      <span style={{ fontSize: size === 'sm' ? 9 : size === 'lg' ? 13 : 11 }}>{symbol}</span>
    </span>
  )
}

function BoardCards({ board, size = 'sm' }) {
  if (!board || board.length === 0) return <span style={{ color: '#4b5563', fontSize: 12 }}>&mdash;</span>
  return (
    <div style={{ display: 'flex', gap: 2, alignItems: 'center' }}>
      {board.slice(0, 5).map((c, i) => (
        <span key={i} style={{ display: 'inline-flex', marginLeft: (i === 3 || i === 4) ? 8 : 0 }}>
          <PokerCard card={c} size={size} />
        </span>
      ))}
    </div>
  )
}

// ── Badges ───────────────────────────────────────────────────────────────────

function StateBadge({ state }) {
  const meta = STATE_META[state] || { label: state, color: '#666', bg: 'rgba(100,100,100,0.15)' }
  return (
    <span style={{
      display: 'inline-block', padding: '2px 9px', borderRadius: 999,
      fontSize: 11, fontWeight: 600, letterSpacing: 0.3,
      color: meta.color, background: meta.bg,
    }}>{meta.label}</span>
  )
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ display: 'inline-block', width: 48, textAlign: 'center', color: '#4b5563' }}>&mdash;</span>
  const colors = {
    BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa',
    SB: '#f59e0b', BB: '#ef4444',
    UTG: '#22c55e', UTG1: '#16a34a', UTG2: '#15803d',
    MP: '#06b6d4', MP1: '#0891b2',
  }
  const c = colors[pos] || '#64748b'
  const isBlind = pos === 'SB' || pos === 'BB'
  return (
    <span style={{
      display: 'inline-block', padding: '2px 0', borderRadius: 4, width: 48, textAlign: 'center',
      fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
      color: '#0a0c14', background: isBlind ? c : '#e2e8f0', border: `1px solid ${isBlind ? c : '#e2e8f0'}`,
    }}>{pos}</span>
  )
}

function ResultBadge({ result }) {
  if (result == null) return <span style={{ color: '#4b5563' }}>&mdash;</span>
  const val = Number(result)
  if (val > 0) return <span style={{ color: '#22c55e', fontWeight: 600, fontFamily: 'monospace' }}>+{val.toFixed(1)} BB</span>
  if (val < 0) return <span style={{ color: '#ef4444', fontWeight: 600, fontFamily: 'monospace' }}>{val.toFixed(1)} BB</span>
  return <span style={{ color: '#64748b', fontFamily: 'monospace' }}>0 BB</span>
}

function Tag({ t, onClick, active }) {
  const colors = {
    icm: '#6366f1', pko: '#f59e0b', ko: '#f59e0b', pos: '#22c55e',
    bvb: '#8b5cf6', ss: '#ef4444', ft: '#06b6d4', nota: '#64748b',
    cbet: '#a78bfa', ip: '#34d399', mw: '#fb923c',
    'speed': '#ec4899', 'racer': '#ec4899',
  }
  const c = colors[t] || '#64748b'
  return (
    <span
      onClick={onClick}
      style={{
        display: 'inline-block', padding: '1px 7px', borderRadius: 999,
        fontSize: 11, fontWeight: 600, marginRight: 3, marginBottom: 2,
        color: c, background: active ? `${c}30` : `${c}18`,
        border: `1px solid ${active ? c : `${c}30`}`,
        cursor: onClick ? 'pointer' : 'default',
      }}
    >#{t}</span>
  )
}

// ── Componente: Acções de Todos os Jogadores ────────────────────────────────

// Normalise all_players_actions coming from the DB.
// Two formats exist:
//   A) { players: [...], hero_name } — old vision pipeline
//   B) { "PlayerName": { seat, position, actions: { preflop: [...], ... }, is_hero, cards, stack_bb } } — HH import
function normaliseActions(raw) {
  if (!raw) return null
  // Format A — already normalised
  if (Array.isArray(raw.players)) {
    return raw.players.map(p => ({
      name: p.name || 'Player',
      position: p.position,
      isHero: p.name === raw.hero_name,
      cards: p.cards || null,
      stackBB: p.stack_bb ?? null,
      actions: Object.fromEntries(
        Object.entries(p.actions || {}).map(([street, val]) => [
          street,
          Array.isArray(val) ? val : (val && val !== '-' && val !== 'None') ? [val] : [],
        ])
      ),
    }))
  }
  // Format B — dict keyed by player name
  const SEAT_ORDER = ['SB', 'BB', 'UTG', 'UTG1', 'UTG2', 'MP', 'MP1', 'HJ', 'CO', 'BTN']
  return Object.entries(raw)
    .map(([name, info]) => ({
      name,
      position: info.position || '',
      isHero: !!info.is_hero,
      cards: info.cards || null,
      stackBB: info.stack_bb ?? null,
      actions: Object.fromEntries(
        Object.entries(info.actions || {}).map(([street, val]) => [
          street,
          Array.isArray(val) ? val : (val && val !== '-' && val !== 'None') ? [val] : [],
        ])
      ),
    }))
    .sort((a, b) => {
      const ia = SEAT_ORDER.indexOf(a.position)
      const ib = SEAT_ORDER.indexOf(b.position)
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
    })
}

const ACTION_COLORS = {
  fold: { color: '#64748b', bg: 'rgba(100,116,139,0.10)' },
  check: { color: '#94a3b8', bg: 'rgba(148,163,184,0.10)' },
  call: { color: '#22c55e', bg: 'rgba(34,197,94,0.10)' },
  bet: { color: '#f59e0b', bg: 'rgba(245,158,11,0.10)' },
  raise: { color: '#f97316', bg: 'rgba(249,115,22,0.10)' },
  allin: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)' },
}

function actionStyle(text) {
  const t = (text || '').toLowerCase()
  if (t.includes('all-in') || t.includes('allin') || t.includes('all in')) return ACTION_COLORS.allin
  if (t.startsWith('raise') || t.startsWith('re-raise')) return ACTION_COLORS.raise
  if (t.startsWith('bet')) return ACTION_COLORS.bet
  if (t.startsWith('call')) return ACTION_COLORS.call
  if (t.startsWith('check')) return ACTION_COLORS.check
  if (t.startsWith('fold')) return ACTION_COLORS.fold
  return { color: '#94a3b8', bg: 'rgba(148,163,184,0.08)' }
}

function ActionBadge({ text }) {
  const s = actionStyle(text)
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 4,
      fontSize: 11, fontWeight: 600, fontFamily: 'monospace',
      color: s.color, background: s.bg, border: `1px solid ${s.color}25`,
      whiteSpace: 'nowrap',
    }}>{text}</span>
  )
}

function AllPlayersActions({ actions }) {
  const players = normaliseActions(actions)
  if (!players || players.length === 0) return null

  const streets = ['preflop', 'flop', 'turn', 'river']

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5,
        marginBottom: 10, textTransform: 'uppercase',
      }}>
        Acções de Todos os Jogadores
      </div>

      {streets.map(street => {
        const hasActions = players.some(p => p.actions?.[street]?.length > 0)
        if (!hasActions) return null

        return (
          <div key={street} style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{
                fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
                color: STREET_COLORS[street], textTransform: 'uppercase',
                padding: '2px 8px', borderRadius: 4,
                background: `${STREET_COLORS[street]}15`,
                border: `1px solid ${STREET_COLORS[street]}30`,
              }}>{STREET_LABELS[street]}</span>
            </div>
            <div style={{
              display: 'flex', flexDirection: 'column', gap: 0,
              background: '#0f1117', borderRadius: 8, padding: '6px 12px',
              border: '1px solid #1e2130',
            }}>
              {players.map((player, i) => {
                const acts = player.actions?.[street] || []
                if (acts.length === 0) return null
                return (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '5px 0',
                    borderBottom: '1px solid #1a1d27',
                  }}>
                    <PosBadge pos={player.position} />
                    <span style={{
                      fontSize: 11,
                      color: player.isHero ? '#818cf8' : '#94a3b8',
                      fontWeight: player.isHero ? 600 : 400,
                      minWidth: 80,
                    }}>
                      {player.name}
                      {player.isHero && <span style={{ fontSize: 11, color: '#6366f1', marginLeft: 4 }}>(HERO)</span>}
                    </span>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {acts.map((a, j) => <ActionBadge key={j} text={a} />)}
                    </div>
                    {player.stackBB != null && (
                      <span style={{ fontSize: 11, color: '#4b5563', marginLeft: 'auto', fontFamily: 'monospace' }}>
                        {player.stackBB.toFixed(1)} BB
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}


// ── Componente: Acções do Hero (fallback das notas) ─────────────────────────

function HeroActionsFromNotes({ notes }) {
  const visionLine = (notes || '').split('\n').find(l => l.includes('[Vision]')) || ''
  if (!visionLine) return null

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>
        Acções do Hero
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {[
          { street: 'Pre-Flop', key: 'PF' },
          { street: 'Flop', key: 'F' },
          { street: 'Turn', key: 'T' },
          { street: 'River', key: 'R' },
        ].map(({ street, key }) => {
          const m = visionLine.match(new RegExp(`${key}=([^|\\s][^|]*?)(?=\\s+[A-Z]=|\\s*\\|)`, 'i'))
          const action = m ? m[1].trim() : null
          if (!action || action === 'None' || action === 'null') return null
          return (
            <div key={key} style={{
              background: '#0f1117', borderRadius: 6, padding: '6px 12px',
              fontSize: 12, border: '1px solid #2a2d3a',
            }}>
              <span style={{ color: '#64748b', fontSize: 11, fontWeight: 600 }}>{street}: </span>
              <span style={{ color: '#e2e8f0', fontFamily: 'monospace' }}>{action}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Componente: Modal de Detalhe ─────────────────────────────────────────────

// ── Hand Analysis Panel (Pot Odds, MDF, MBF) ────────────────────────────────

function HandAnalysisPanel({ handId }) {
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)

  async function load() {
    if (analysis) { setOpen(!open); return }
    setLoading(true)
    try {
      const data = await equity.handAnalysis(handId)
      setAnalysis(data)
      setOpen(true)
    } catch (e) {
      console.error('Analysis error:', e)
    } finally {
      setLoading(false)
    }
  }

  const SC = { preflop: '#6366f1', flop: '#22c55e', turn: '#f59e0b', river: '#ef4444' }
  const SL = { preflop: 'Pre-Flop', flop: 'Flop', turn: 'Turn', river: 'River' }

  return (
    <div style={{ marginBottom: 16 }}>
      <button onClick={load} style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px',
        borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer',
        background: open ? 'rgba(99,102,241,0.12)' : '#1a1d27',
        color: open ? '#818cf8' : '#64748b',
        border: `1px solid ${open ? 'rgba(99,102,241,0.3)' : '#2a2d3a'}`,
        width: '100%', justifyContent: 'center',
      }}>
        {loading ? 'A calcular...' : open ? '▼ Análise de Decisões' : '▶ Análise (Pot Odds · MDF · MBF)'}
      </button>
      {open && analysis && analysis.analysis?.length > 0 && (
        <div style={{ marginTop: 8, background: '#0f1117', borderRadius: 8, border: '1px solid #1e2130', overflow: 'hidden' }}>
          {analysis.analysis.map((a, i) => {
            const color = SC[a.street] || '#94a3b8'
            const isBet = a.action?.includes('bet') || a.action?.includes('raise')
            return (
              <div key={i} style={{ padding: '10px 14px', borderBottom: i < analysis.analysis.length - 1 ? '1px solid #1a1d27' : 'none' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color, textTransform: 'uppercase', padding: '1px 6px', borderRadius: 3, background: `${color}15`, border: `1px solid ${color}30` }}>{SL[a.street]}</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: a.action?.includes('fold') ? '#ef4444' : a.action?.includes('call') ? '#22c55e' : '#f59e0b' }}>Hero {a.action}</span>
                </div>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  {a.pot_before != null && <div style={{ background: '#1a1d27', borderRadius: 6, padding: '4px 10px' }}><div style={{ fontSize: 9, color: '#64748b', fontWeight: 600 }}>POT</div><div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', fontFamily: 'monospace' }}>{a.pot_before.toLocaleString()}{a.pot_bb ? <span style={{ fontSize: 11, color: '#4b5563' }}> {a.pot_bb}bb</span> : ''}</div></div>}
                  {a.facing_bet != null && <div style={{ background: '#1a1d27', borderRadius: 6, padding: '4px 10px' }}><div style={{ fontSize: 9, color: '#64748b', fontWeight: 600 }}>BET</div><div style={{ fontSize: 13, fontWeight: 700, color: '#f59e0b', fontFamily: 'monospace' }}>{a.facing_bet.toLocaleString()}{a.bet_bb ? <span style={{ fontSize: 11, color: '#4b5563' }}> {a.bet_bb}bb</span> : ''}</div></div>}
                  {a.bet_size != null && <div style={{ background: '#1a1d27', borderRadius: 6, padding: '4px 10px' }}><div style={{ fontSize: 9, color: '#64748b', fontWeight: 600 }}>BET</div><div style={{ fontSize: 13, fontWeight: 700, color: '#f59e0b', fontFamily: 'monospace' }}>{a.bet_size.toLocaleString()}{a.bet_bb ? <span style={{ fontSize: 11, color: '#4b5563' }}> {a.bet_bb}bb</span> : ''}</div></div>}
                  {a.pot_odds != null && <div style={{ background: '#1a1d27', borderRadius: 6, padding: '4px 10px' }}><div style={{ fontSize: 9, color: '#64748b', fontWeight: 600 }}>POT ODDS</div><div style={{ fontSize: 13, fontWeight: 700, color: '#3b82f6', fontFamily: 'monospace' }}>{a.pot_odds}%</div></div>}
                  {a.mdf != null && <div style={{ background: '#1a1d27', borderRadius: 6, padding: '4px 10px' }}><div style={{ fontSize: 9, color: '#64748b', fontWeight: 600 }}>MDF</div><div style={{ fontSize: 13, fontWeight: 700, color: '#8b5cf6', fontFamily: 'monospace' }}>{a.mdf}%</div></div>}
                  {a.mbf != null && <div style={{ background: '#1a1d27', borderRadius: 6, padding: '4px 10px' }}><div style={{ fontSize: 9, color: '#64748b', fontWeight: 600 }}>MBF</div><div style={{ fontSize: 13, fontWeight: 700, color: '#ec4899', fontFamily: 'monospace' }}>{a.mbf}%</div></div>}
                  {a.bet_to_pot != null && <div style={{ background: '#1a1d27', borderRadius: 6, padding: '4px 10px' }}><div style={{ fontSize: 9, color: '#64748b', fontWeight: 600 }}>BET/POT</div><div style={{ fontSize: 13, fontWeight: 700, color: '#22c55e', fontFamily: 'monospace' }}>{a.bet_to_pot}%</div></div>}
                </div>
              </div>
            )
          })}
        </div>
      )}
      {open && analysis && (!analysis.analysis || analysis.analysis.length === 0) && (
        <div style={{ marginTop: 8, padding: 16, textAlign: 'center', color: '#4b5563', fontSize: 12, background: '#0f1117', borderRadius: 8, border: '1px solid #1e2130' }}>Sem decisões do Hero para analisar</div>
      )}
    </div>
  )
}

function HandDetailModal({ hand, onClose, onUpdate }) {
  const [notes, setNotes] = useState(hand.notes || '')
  const [tags, setTags]   = useState((hand.tags || []).join(', '))
  const [saving, setSaving] = useState(false)
  const [screenshotUrl, setScreenshotUrl] = useState(hand.screenshot_url || null)
  const [ssLoading, setSsLoading] = useState(false)
  const [ssFullscreen, setSsFullscreen] = useState(false)
  const [copied, setCopied] = useState(false)

  // Carregar screenshot se a mão tem entry_id (screenshot associado)
  useEffect(() => {
    if (screenshotUrl) return
    const entryId = hand.entry_id || hand.player_names?.screenshot_entry_id
    if (!entryId) return
    setSsLoading(true)
    hands.screenshot(hand.id)
      .then(data => {
        if (data?.data_url) setScreenshotUrl(data.data_url)
      })
      .catch(() => {})
      .finally(() => setSsLoading(false))
  }, [hand.id])

  // Extrair TM number para link GG
  const tmNumber = hand.hand_id ? hand.hand_id.replace('GG-', '') : null

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
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
      backdropFilter: 'blur(4px)',
    }} onClick={onClose}>
      <div
        style={{
          width: '92%', maxWidth: 800, maxHeight: '90vh', overflow: 'auto',
          background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12,
          padding: 28,
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <span style={{ fontWeight: 700, fontSize: 17 }}>Mão #{hand.id}</span>
              <StateBadge state={hand.study_state} />
              {hand.result != null && <ResultBadge result={hand.result} />}
            </div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              {hand.stakes && <span style={{ fontSize: 12, color: '#64748b' }}>{hand.stakes}</span>}
              {(() => {
                const m = hand.all_players_actions?._meta
                const lvl = extractLevel(hand.raw)
                if (m || lvl) {
                  return <span style={{ fontSize: 11, color: '#4b5563', fontFamily: 'monospace', fontWeight: 600 }}>
                    {lvl || ''}{m ? ` · ${Math.round(m.sb)}/${Math.round(m.bb)}${m.ante ? `(${Math.round(m.ante)})` : ''}` : ''}
                  </span>
                }
                return null
              })()}
              <span style={{ fontSize: 11, color: '#4b5563' }}>{hand.site} &middot; {hand.played_at ? hand.played_at.slice(0, 10) : ''}</span>
            </div>
          </div>
          <button
            style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 18, padding: 4 }}
            onClick={onClose}
          >&#10005;</button>
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          {hand.raw && (
            <button
              onClick={() => { navigator.clipboard.writeText(hand.raw); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
              style={{ padding: '5px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600, background: copied ? 'rgba(34,197,94,0.15)' : 'rgba(34,197,94,0.1)', color: '#22c55e', border: `1px solid ${copied ? 'rgba(34,197,94,0.3)' : 'rgba(34,197,94,0.2)'}`, cursor: 'pointer' }}
            >{copied ? '✓ Copiado' : 'Copiar HH'}</button>
          )}
          {hand.raw && hand.all_players_actions && (
            <a href={`/replayer/${hand.id}`} target="_blank" rel="noopener noreferrer"
              style={{ padding: '5px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600, background: 'rgba(99,102,241,0.1)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.2)', cursor: 'pointer', textDecoration: 'none' }}
            >&#9654; Replayer</a>
          )}
          <a href={`/hand/${hand.id}`} target="_blank" rel="noopener noreferrer"
            style={{ padding: '5px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600, background: 'rgba(245,158,11,0.1)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.2)', cursor: 'pointer', textDecoration: 'none' }}
          >Detalhe</a>
        </div>

        {/* Info grid — FIRST */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px 20px',
          marginBottom: 16, fontSize: 13,
        }}>
          {[
            { l: 'Sala', v: hand.site },
            { l: 'Data', v: hand.played_at ? hand.played_at.slice(0, 10) : null },
            { l: 'Resultado', v: <ResultBadge result={hand.result} /> },
            { l: 'Posição', v: <PosBadge pos={hand.position} /> },
            { l: 'Torneio', v: hand.stakes },
            { l: 'Hand ID', v: hand.hand_id ? <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{hand.hand_id.slice(-12)}</span> : null },
          ].map(({ l, v }) => (
            <div key={l} style={{ background: '#0f1117', borderRadius: 6, padding: '8px 12px' }}>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.4, marginBottom: 3, textTransform: 'uppercase' }}>{l}</div>
              <div>{v || <span style={{ color: '#4b5563' }}>&mdash;</span>}</div>
            </div>
          ))}
        </div>

        {/* Cartas + Board */}
        <div style={{
          background: '#0f1117', borderRadius: 10, padding: '16px 20px',
          marginBottom: 20, display: 'flex', gap: 32, alignItems: 'center', flexWrap: 'wrap',
        }}>
          <div>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>
              Hero &middot; <PosBadge pos={hand.position} />
            </div>
            <div style={{ display: 'flex', gap: 5 }}>
              {hand.hero_cards?.length > 0
                ? hand.hero_cards.map((c, i) => <PokerCard key={i} card={c} size="lg" />)
                : <span style={{ color: '#4b5563', fontSize: 13 }}>Cartas não visíveis</span>
              }
            </div>
          </div>
          {hand.board?.length > 0 && (
            <div>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Board</div>
              <div style={{ display: 'flex', gap: 5 }}>
                {hand.board.slice(0, 5).map((c, i) => <PokerCard key={i} card={c} size="lg" />)}
              </div>
            </div>
          )}
        </div>

        {/* Players table — stacks & positions */}
        {hand.all_players_actions && (() => {
          const SEAT_ORDER = ['BTN', 'SB', 'BB', 'UTG', 'UTG1', 'UTG2', 'MP', 'MP1', 'HJ', 'CO']
          const players = Object.entries(hand.all_players_actions)
            .filter(([k]) => k !== '_meta')
            .map(([name, info]) => ({ name, ...info }))
            .sort((a, b) => {
              const ia = SEAT_ORDER.indexOf(a.position)
              const ib = SEAT_ORDER.indexOf(b.position)
              return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
            })
          if (players.length === 0) return null
          return (
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>
                Mesa ({players.length} jogadores)
              </div>
              <div style={{ background: '#0f1117', borderRadius: 8, border: '1px solid #1e2130', overflow: 'hidden' }}>
                {players.map((p, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center',
                    padding: '6px 12px',
                    background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)',
                    borderBottom: i < players.length - 1 ? '1px solid #1a1d27' : 'none',
                  }}>
                    <div style={{ width: 54, flexShrink: 0 }}><PosBadge pos={p.position} /></div>
                    <div style={{ width: 150, flexShrink: 0 }}>
                      <span style={{ fontSize: 12, fontWeight: p.is_hero ? 700 : 600, color: '#0a0c14', background: p.is_hero ? '#a5b4fc' : '#fbbf24', padding: '2px 8px', borderRadius: 4, display: 'inline-block' }}>
                        {p.name}{p.is_hero && <span style={{ fontSize: 9, fontWeight: 700, color: '#4338ca', marginLeft: 4 }}>HERO</span>}
                      </span>
                    </div>
                    <div style={{ width: 75, flexShrink: 0, textAlign: 'right', fontSize: 12, color: '#f97316', fontFamily: 'monospace', fontWeight: 700 }}>
                      {p.stack ? Number(p.stack).toLocaleString() : '—'}
                    </div>
                    <div style={{ width: 70, flexShrink: 0, textAlign: 'right' }}>
                      <span style={{ fontSize: 11, color: '#fff', fontFamily: 'monospace', fontWeight: 700, background: '#f97316', padding: '2px 6px', borderRadius: 3 }}>
                        {p.stack_bb ? `${p.stack_bb} BB` : '—'}
                      </span>
                    </div>
                    <div style={{ width: 70, flexShrink: 0, textAlign: 'right', paddingLeft: 12 }}>
                      {p.bounty != null && (
                        <span style={{ fontSize: 11, color: '#f1f5f9', fontWeight: 700, padding: '2px 6px', borderRadius: 3, background: 'rgba(30,58,95,0.4)', border: '1px solid rgba(30,58,95,0.5)' }}>
                          {p.bounty}€
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })()}

        {/* Acções — prioridade: HH parseada (raw) > all_players_actions > fallback notas */}
        {/* Tech Debt #8: HandHistoryViewer canónico (substitui ParsedHandHistory + parseRawHH local). */}
        {hand.raw
          ? <HandHistoryViewer hand={hand} />
          : hand.all_players_actions
            ? <AllPlayersActions actions={hand.all_players_actions} />
            : <HeroActionsFromNotes notes={hand.notes} />
        }

        {/* Screenshot inline */}
        {ssLoading && (
          <div style={{ marginBottom: 20, color: '#f59e0b', fontSize: 12 }}>A carregar screenshot...</div>
        )}
        {screenshotUrl && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Screenshot</div>
            <img
              src={screenshotUrl}
              alt="Screenshot da mão"
              style={{ maxWidth: '100%', borderRadius: 8, border: '1px solid #2a2d3a', cursor: 'pointer' }}
              onClick={() => setSsFullscreen(true)}
            />
          </div>
        )}

        {/* Screenshot fullscreen modal */}
        {ssFullscreen && screenshotUrl && (
          <div
            style={{
              position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.92)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000,
              cursor: 'pointer',
            }}
            onClick={() => setSsFullscreen(false)}
          >
            <img src={screenshotUrl} alt="Screenshot" style={{ maxWidth: '95vw', maxHeight: '95vh', borderRadius: 8 }} onClick={e => e.stopPropagation()} />
            <button onClick={() => setSsFullscreen(false)} style={{ position: 'absolute', top: 20, right: 20, background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff', fontSize: 24, cursor: 'pointer', borderRadius: 8, padding: '4px 12px' }}>✕</button>
          </div>
        )}

        {/* Replayer */}
        {hand.raw && hand.all_players_actions && (
          <>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 6 }}>
              <a href={`/replayer/${hand.id}`} target="_blank" rel="noopener noreferrer" style={{
                fontSize: 11, fontWeight: 600, color: '#818cf8', textDecoration: 'none',
                padding: '4px 12px', borderRadius: 5, background: 'rgba(99,102,241,0.1)',
                border: '1px solid rgba(99,102,241,0.25)', display: 'inline-flex', alignItems: 'center', gap: 4,
              }}>&#9654; Fullscreen</a>
            </div>
            <Replayer hand={hand} />
          </>
        )}

        {/* Source info */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
          {tmNumber && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 6, fontSize: 11, background: 'rgba(99,102,241,0.08)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.2)', fontFamily: 'monospace' }}>TM{tmNumber}</span>
          )}
          {hand.site === 'GGPoker' && tmNumber && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 10px', borderRadius: 6, fontSize: 11, background: 'rgba(34,197,94,0.08)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.2)' }}>&#9654; GG Replayer</span>
          )}
        </div>

        {/* Notes */}
        <div style={{ marginBottom: 14 }}>
          <label style={{ fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 6, color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Notas de Estudo
          </label>
          <textarea
            rows={3}
            style={{
              width: '100%', fontSize: 13, background: '#0f1117',
              border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0',
              padding: '8px 12px', fontFamily: 'inherit', resize: 'vertical',
            }}
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder="Adicionar notas de estudo..."
          />
        </div>

        {/* Tags */}
        <div style={{ marginBottom: 20 }}>
          <label style={{ fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 6, color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Tags (separadas por vírgula)
          </label>
          <input
            type="text"
            style={{
              width: '100%', fontSize: 13, background: '#0f1117',
              border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0',
              padding: '8px 12px',
            }}
            value={tags}
            onChange={e => setTags(e.target.value)}
            placeholder="icm, bvb, sqz-pko..."
          />
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', borderTop: '1px solid #2a2d3a', paddingTop: 16 }}>
          <button
            style={{
              padding: '7px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600,
              background: '#6366f1', color: '#fff', border: 'none', cursor: 'pointer',
              opacity: saving ? 0.6 : 1,
            }}
            disabled={saving} onClick={save}
          >{saving ? 'A guardar...' : 'Guardar'}</button>
          {hand.study_state !== 'review' && (
            <button style={{ padding: '7px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: 'rgba(245,158,11,0.12)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)', cursor: 'pointer' }}
              onClick={() => changeState('review')}>Marcar Revisão</button>
          )}
          {hand.study_state !== 'studying' && (
            <button style={{ padding: '7px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: 'rgba(139,92,246,0.12)', color: '#8b5cf6', border: '1px solid rgba(139,92,246,0.3)', cursor: 'pointer' }}
              onClick={() => changeState('studying')}>A Estudar</button>
          )}
          {hand.study_state !== 'resolved' && (
            <button style={{ padding: '7px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: 'rgba(34,197,94,0.12)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.3)', cursor: 'pointer' }}
              onClick={() => changeState('resolved')}>Resolvida &#10003;</button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Componente: Hand Row (compacto dentro de tag group) ─────────────────────

function extractLevel(raw) {
  if (!raw) return null
  // Winamax: "level: 6"
  const wn = raw.match(/level:\s*(\d+)/i)
  if (wn) return `Lv ${wn[1]}`
  // PokerStars: "Level V" or "Level XV" (roman) or "Level 5"
  const ps = raw.match(/Level\s+([IVXLCDM]+|\d+)/i)
  if (ps) {
    const v = ps[1]
    // Convert roman to number
    const roman = { I:1, V:5, X:10, L:50, C:100, D:500, M:1000 }
    if (/^[IVXLCDM]+$/i.test(v)) {
      let num = 0
      for (let i = 0; i < v.length; i++) {
        const cur = roman[v[i].toUpperCase()] || 0
        const next = roman[v[i+1]?.toUpperCase()] || 0
        num += cur < next ? -cur : cur
      }
      return `Lv ${num}`
    }
    return `Lv ${v}`
  }
  return null
}

// ── Componente: Tag Group (colapsável) ──────────────────────────────────────

// TagGroup recebe metadados do endpoint tag-groups e faz lazy-load das mãos ao expandir
// ── Tags que justificam atalho HRC Ninja (decisões ICM/bubble/SS) ─────────
const ICM_TAGS = new Set([
  'ICM', 'ICM PKO', 'PKO SS', 'SQZ', 'SQZ PKO',
  'cc/3b IP PKO +', 'cc/3b IP PKO-',
  'IP vs 3bet PKO', 'OP vs 3bet PKO',
  'bvB PKO PRE', 'Bvb PKO pre',
  'SB vs Steal PKO', 'SB vs Steal', 'SB vs Steal LS',
])

function TournamentGroup({ name, hands, wins, losses, totalBB, onOpenDetail, onDeleteHand, showHrcButton = false }) {
  const [open, setOpen] = useState(false)
  const bbColor = totalBB > 0 ? '#22c55e' : totalBB < 0 ? '#ef4444' : '#64748b'
  return (
    <div style={{ marginBottom: 8, border: `1px solid ${open ? 'rgba(99,102,241,0.3)' : '#2a2d3a'}`, borderRadius: 10, overflow: 'hidden' }}>
      <div onClick={() => setOpen(o => !o)} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', background: open ? 'rgba(99,102,241,0.06)' : '#1a1d27', cursor: 'pointer', userSelect: 'none' }}
        onMouseEnter={e => { if (!open) e.currentTarget.style.background = '#1e2130' }}
        onMouseLeave={e => { if (!open) e.currentTarget.style.background = open ? 'rgba(99,102,241,0.06)' : '#1a1d27' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ display: 'inline-block', fontSize: 11, color: '#818cf8', transform: open ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>&#9654;</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9' }}>{name}</span>
          <span style={{ fontSize: 11, color: '#64748b' }}>{hands.length} mãos</span>
          {showHrcButton && (
            <a
              href="https://hrc.ninja/create-structure/"
              target="_blank"
              rel="noopener noreferrer"
              onClick={e => e.stopPropagation()}
              title="Abrir HRC Ninja (criar estrutura ICM)"
              style={{
                fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                color: '#f87171', textDecoration: 'none', letterSpacing: 0.3,
              }}
            >HRC</a>
          )}
        </div>
        <div style={{ display: 'flex', gap: 12, fontSize: 11, fontFamily: 'monospace' }}>
          <span style={{ color: '#22c55e' }}>{wins}W</span>
          <span style={{ color: '#ef4444' }}>{losses}L</span>
          <span style={{ color: bbColor, fontWeight: 700 }}>{totalBB > 0 ? '+' : ''}{totalBB.toFixed(1)} BB</span>
        </div>
      </div>
      {open && hands.map((h, idx) => <HandRow key={h.id} hand={h} onClick={() => onOpenDetail(h.id)} onDelete={() => onDeleteHand(h.id)} idx={idx} />)}
    </div>
  )
}

// ── Tier headers/collapsibles para a página Estudo ──────────────────────────

function TierHeader({ label, subtitle, count }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'baseline', gap: 10,
      padding: '14px 4px 8px',
      borderBottom: '1px solid rgba(255,255,255,0.06)',
      marginBottom: 6,
    }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: '#e5e7eb', letterSpacing: 0.4, textTransform: 'uppercase' }}>{label}</span>
      <span style={{ fontSize: 10, color: 'var(--muted)' }}>{subtitle}</span>
      <span style={{ fontSize: 10, color: '#4b5563', marginLeft: 'auto' }}>{count} grupos</span>
    </div>
  )
}

function TierCollapsible({ label, subtitle, count, defaultOpen = false, children, colorOverride }) {
  const [open, setOpen] = useState(defaultOpen)
  const labelColor = colorOverride || '#cbd5e1'
  const borderColor = colorOverride ? `${colorOverride}33` : 'rgba(255,255,255,0.06)'
  return (
    <div style={{ marginTop: 12 }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%', display: 'flex', alignItems: 'baseline', gap: 10,
          padding: '10px 4px 8px',
          background: 'transparent', border: 'none',
          borderBottom: `1px solid ${borderColor}`,
          cursor: 'pointer', textAlign: 'left',
          marginBottom: open ? 6 : 0,
        }}
      >
        <span style={{ fontSize: 10, color: colorOverride || 'var(--muted)', width: 10 }}>{open ? '▼' : '▶'}</span>
        <span style={{ fontSize: 11, fontWeight: 700, color: labelColor, letterSpacing: 0.4, textTransform: 'uppercase' }}>{label}</span>
        <span style={{ fontSize: 10, color: 'var(--muted)' }}>{subtitle}</span>
        <span style={{ fontSize: 10, color: '#4b5563', marginLeft: 'auto' }}>{count} grupos</span>
      </button>
      {open && <div>{children}</div>}
    </div>
  )
}


function TagGroup({ tagKey, tags, source, count, wins, losses, totalBB, filters, useHm3Tags, studyView, isPlaceholder, onOpenDetail, onDeleteHand }) {
  const [open, setOpen] = useState(false)
  const [tagHands, setTagHands] = useState([])
  const [loadingHands, setLoadingHands] = useState(false)

  async function expand() {
    if (!open && tagHands.length === 0) {
      setLoadingHands(true)
      try {
        const params = { ...filters, page_size: 500, page: 1 }
        if (!params.date_from) delete params.date_from
        if (studyView) params.study_view = true
        // Sub-fase 4b: para a secção "Discord — Só SS (sem HH)", o backend só
        // devolve placeholders se este flag for passado também na expansão.
        if (isPlaceholder) params.include_discord_placeholders = true
        if (tags.length === 0) {
          // Grupo "(sem tag)" em modo auto (source='none'): nem hm3 nem discord.
          // Legado use_hm3_tags: só hm3 ausente. Default: coluna tags auto.
          if (source === 'none') {
            params.hm3_tag = '__none__'
            params.discord_tag = '__none__'
          } else if (useHm3Tags) {
            params.hm3_tag = '__none__'
          } else {
            params.tag = '__none__'
          }
        } else if (source === 'discord') {
          params.discord_tag = tags[0]
        } else {
          // Filtrar pela tag HM3 principal do grupo (tema).
          params.hm3_tag = tags[0]
        }
        const result = await hands.list(params)
        const fetched = result.data || []
        setTagHands(fetched)
      } catch (e) {
        console.error('Erro ao carregar mãos do grupo:', e)
      } finally {
        setLoadingHands(false)
      }
    }
    setOpen(o => !o)
  }

  // Cor: Discord matched #5865F2; placeholder Discord #38bdf8 (azul claro).
  // HM3 mantém mapa por tema. "(sem tag)" cinzento.
  const tag = tags.length > 0 ? tags[0] : 'sem-tag'
  const HM3_COLORS = {
    icm: '#6366f1', pko: '#f59e0b', ko: '#f59e0b', pos: '#22c55e',
    bvb: '#8b5cf6', ss: '#ef4444', ft: '#06b6d4', nota: '#64748b',
    cbet: '#a78bfa', ip: '#34d399', mw: '#fb923c',
    speed: '#ec4899', racer: '#ec4899',
  }
  const tagColor = isPlaceholder ? '#38bdf8'
    : (source === 'discord' ? '#5865F2' : (HM3_COLORS[tag] || '#64748b'))

  return (
    <div style={{
      marginBottom: 8,
      border: `1px solid ${open ? `${tagColor}40` : '#2a2d3a'}`,
      borderRadius: 10,
      overflow: 'hidden',
      transition: 'border-color 0.2s',
    }}>
      {/* Header colapsável */}
      <div
        onClick={expand}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 16px',
          background: open ? `${tagColor}08` : '#1a1d27',
          cursor: 'pointer',
          transition: 'background 0.15s',
          userSelect: 'none',
        }}
        onMouseEnter={e => { if (!open) e.currentTarget.style.background = '#1e2130' }}
        onMouseLeave={e => { if (!open) e.currentTarget.style.background = '#1a1d27' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Seta */}
          <span style={{
            display: 'inline-block', fontSize: 11, color: tagColor,
            transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s',
          }}>&#9654;</span>

          {/* Tag badges */}
          <div style={{ display: 'flex', gap: 4 }}>
            {tags.length === 0 ? (
              <span style={{
                display: 'inline-block', padding: '3px 12px', borderRadius: 999,
                fontSize: 12, fontWeight: 700, letterSpacing: 0.3,
                color: '#64748b', background: 'rgba(100,116,139,0.15)',
                border: '1px solid rgba(100,116,139,0.3)',
              }}>#sem-tag</span>
            ) : tags.map(t => (
              <span key={t} style={{
                display: 'inline-block', padding: '3px 10px', borderRadius: 999,
                fontSize: 12, fontWeight: 700, letterSpacing: 0.3,
                color: tagColor, background: `${tagColor}20`,
                border: `1px solid ${tagColor}40`,
              }}>#{t}</span>
            ))}
          </div>

          {/* Contagem */}
          <span style={{ fontSize: 12, color: '#64748b' }}>
            {count} {count === 1 ? 'mão' : 'mãos'}
          </span>
        </div>

        {/* Stats rápidas — escondidas para placeholders (sem HH = sem resultado) */}
        {!isPlaceholder && (
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', fontSize: 11 }}>
            <span style={{ color: '#22c55e' }}>{wins}W</span>
            <span style={{ color: '#ef4444' }}>{losses}L</span>
            <span style={{
              color: totalBB >= 0 ? '#22c55e' : '#ef4444',
              fontWeight: 600, fontFamily: 'monospace',
            }}>
              {totalBB >= 0 ? '+' : ''}{totalBB.toFixed(1)} BB
            </span>
          </div>
        )}
        {isPlaceholder && (
          <span style={{ fontSize: 10, color: '#64748b', fontStyle: 'italic' }}>
            sem HH ainda
          </span>
        )}
      </div>

      {/* Conteúdo expandido */}
      {open && (
        <div>
          {loadingHands ? (
            <div style={{ padding: '16px', textAlign: 'center', color: '#64748b', fontSize: 12 }}>
              A carregar mãos...
            </div>
          ) : tagHands.length === 0 ? (
            <div style={{ padding: '16px', textAlign: 'center', color: '#4b5563', fontSize: 12 }}>
              Sem mãos neste grupo
            </div>
          ) : isPlaceholder ? (
            // Placeholders Discord (sem HH): mostra SS inline + nicks Vision +
            // hora + botão Apagar. Não há cartas/board/resultado/posição.
            tagHands.map(h => (
              <PlaceholderHandRow
                key={h.id}
                hand={h}
                onDelete={() => onDeleteHand(h.id)}
              />
            ))
          ) : (() => {
            // Agrupar mãos por torneio (stakes)
            const byTournament = {}
            for (const h of tagHands) {
              const tName = h.stakes || 'Sem torneio'
              // Data do torneio (YYYY-MM-DD), extraída de played_at
              const dayIso = h.played_at
                ? new Date(h.played_at).toISOString().slice(0, 10)
                : 'sem-data'
              const key = `${dayIso}__${tName}`
              if (!byTournament[key]) {
                byTournament[key] = {
                  name: tName,
                  day: dayIso,
                  hands: [],
                  maxTime: 0,
                }
              }
              byTournament[key].hands.push(h)
              const t = h.played_at ? new Date(h.played_at).getTime() : 0
              if (t > byTournament[key].maxTime) byTournament[key].maxTime = t
            }
            // Ordem: data descendente (mais recente primeiro)
            const entries = Object.values(byTournament).sort((a, b) => b.maxTime - a.maxTime)

            if (entries.length === 1) {
              // Só um torneio/dia — mostrar mãos directamente sem sub-grupo
              return tagHands.map((h, idx) => (
                <HandRow key={h.id} hand={h} idx={idx} onClick={() => onOpenDetail(h.id)} onDelete={() => onDeleteHand(h.id)} />
              ))
            }

            // Formatar label: "GRAVITY · 17/04" (PT-PT)
            const fmtDay = (iso) => {
              if (!iso || iso === 'sem-data') return ''
              const [y, m, d] = iso.split('-')
              return `${d}/${m}`
            }

            return entries.map(ent => {
              const tHands = ent.hands
              const wins   = tHands.filter(h => Number(h.result) > 0).length
              const losses = tHands.filter(h => Number(h.result) < 0).length
              const tBB    = tHands.reduce((s, h) => s + Number(h.result || 0), 0)
              const dayLabel = fmtDay(ent.day)
              const label = dayLabel ? `${ent.name} · ${dayLabel}` : ent.name
              // Tema do grupo = tags[0]. Mostrar botão HRC se estiver na lista ICM.
              const groupTheme = tags[0]
              const showHrc = groupTheme && ICM_TAGS.has(groupTheme)
              return (
                <TournamentGroup
                  key={`${ent.day}__${ent.name}`}
                  name={label}
                  hands={tHands}
                  wins={wins}
                  losses={losses}
                  totalBB={tBB}
                  onOpenDetail={onOpenDetail}
                  onDeleteHand={onDeleteHand}
                  showHrcButton={showHrc}
                />
              )
            })
          })()}
        </div>
      )}
    </div>
  )
}

// ── Linha de mão placeholder Discord (sub-fase 4b) ──────────────────────────
// Mãos sem HH não têm cartas/board/resultado. Mostramos o que existe:
// imagem do SS inline (Discord CDN ou imageUrl(entry_id)), nicks Vision
// extraídos pelo Vision (players_list), stack do hero, hora.
// Botão único Apagar — Rematch e Ignorar não aplicam (HH só chega via HM3/import).
function PlaceholderHandRow({ hand, onDelete }) {
  const pn = hand.player_names || {}
  const playersList = pn.players_list || []
  const heroName = pn.hero || null
  const channels = hand.discord_tags || []
  const playedAt = hand.played_at
    ? new Date(hand.played_at).toLocaleString('pt-PT', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
    : '—'
  // Hero stack: tenta encontrar player com nome do hero em players_list e usar stack
  const heroPlayer = heroName
    ? playersList.find(p => (p.name || '').toLowerCase() === heroName.toLowerCase())
    : null
  const heroStack = heroPlayer?.stack ?? null
  // SS source: prioriza screenshot_url (CDN GG), fallback para imageUrl(entry_id)
  const imgSrc = hand.screenshot_url
    || (hand.entry_id ? screenshots.imageUrl(hand.entry_id) : null)
  // Bucket 1 Tech Debt #1: anexos imagem inline. Até 3 thumbs + "+N" overflow.
  const attachments = hand.attachments || []
  const attachmentCount = hand.attachment_count || 0
  const attSrc = (att) =>
    att.img_b64 ? `data:${att.mime_type || 'image/png'};base64,${att.img_b64}` : att.image_url

  return (
    <div style={{
      display: 'flex', gap: 14, padding: '12px 16px',
      borderTop: '1px solid rgba(255,255,255,0.04)',
      alignItems: 'flex-start',
    }}>
      {/* SS inline */}
      <div style={{ flexShrink: 0, width: 200 }}>
        {imgSrc ? (
          <a href={imgSrc} target="_blank" rel="noopener noreferrer" style={{ lineHeight: 0 }}>
            <img
              src={imgSrc}
              alt="screenshot"
              title="Abrir SS em nova aba"
              style={{
                width: 200, height: 'auto', borderRadius: 4,
                border: '1px solid rgba(255,255,255,0.08)',
                display: 'block',
                cursor: 'zoom-in',
              }}
            />
          </a>
        ) : (
          <div style={{
            width: 200, height: 120, borderRadius: 4,
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.06)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 11, color: '#4b5563',
          }}>Sem imagem</div>
        )}
      </div>

      {/* Anexos imagem (Bucket 1 Tech Debt #1) */}
      {attachmentCount > 0 && (
        <div style={{ flexShrink: 0, width: 120, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: 11, color: '#94a3b8', fontFamily: 'monospace' }}>
            📎 {attachmentCount}
          </div>
          {(() => {
            const overflow = attachments.length > 3 ? attachments.length - 2 : 0
            const visible = overflow > 0 ? attachments.slice(0, 2) : attachments.slice(0, 3)
            return (
              <>
                {visible.map((att) => (
                  <a key={att.id} href={att.image_url} target="_blank" rel="noopener noreferrer" style={{ lineHeight: 0 }}>
                    <img
                      src={attSrc(att)}
                      alt="anexo"
                      title="Abrir em nova aba"
                      style={{
                        width: 120, height: 'auto', borderRadius: 4,
                        border: '1px solid rgba(0,0,0,0.1)',
                        display: 'block',
                        cursor: 'zoom-in',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.9' }}
                      onMouseLeave={(e) => { e.currentTarget.style.opacity = '1' }}
                    />
                  </a>
                ))}
                {overflow > 0 && (
                  <div style={{
                    width: 120, height: 90, borderRadius: 4,
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 14, color: '#cbd5e1', fontWeight: 600,
                  }}>+{overflow}</div>
                )}
              </>
            )
          })()}
        </div>
      )}

      {/* Metadata + nicks */}
      <div style={{ flex: 1, fontSize: 12, color: '#cbd5e1', minWidth: 0 }}>
        {/* Header: hora + canais + hand_id curto */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
          <span style={{ fontFamily: 'monospace', color: '#94a3b8', fontSize: 11 }}>{playedAt}</span>
          {channels.length > 0 && (
            <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
              {channels.map(ch => (
                <span key={ch} style={{
                  padding: '1px 7px', borderRadius: 3,
                  fontSize: 10, fontWeight: 600, letterSpacing: 0.3,
                  color: '#38bdf8', background: 'rgba(56,189,248,0.14)',
                  border: '1px solid rgba(56,189,248,0.3)',
                }}>#{ch}</span>
              ))}
            </span>
          )}
          {hand.hand_id && (
            <span style={{ fontFamily: 'monospace', color: '#4b5563', fontSize: 10 }}>{hand.hand_id}</span>
          )}
        </div>

        {/* Hero + stack */}
        {heroName && (
          <div style={{ marginBottom: 6, fontSize: 12 }}>
            <span style={{ color: '#64748b', fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.5, marginRight: 6 }}>Hero</span>
            <span style={{ color: '#818cf8', fontWeight: 600 }}>{heroName}</span>
            {heroStack != null && (
              <span style={{ color: '#94a3b8', marginLeft: 8, fontFamily: 'monospace', fontSize: 11 }}>
                {Number(heroStack).toLocaleString('pt-PT')}
              </span>
            )}
          </div>
        )}

        {/* Lista de nicks Vision */}
        {playersList.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, fontSize: 11 }}>
            <span style={{ color: '#64748b', fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.5, marginRight: 4, alignSelf: 'center' }}>
              Mesa
            </span>
            {playersList.map((p, i) => {
              const isPlayerHero = heroName && (p.name || '').toLowerCase() === heroName.toLowerCase()
              return (
                <span key={i} style={{
                  padding: '2px 8px', borderRadius: 3,
                  background: isPlayerHero ? 'rgba(129,140,248,0.15)' : 'rgba(255,255,255,0.03)',
                  color: isPlayerHero ? '#818cf8' : '#cbd5e1',
                  fontWeight: isPlayerHero ? 600 : 400,
                  fontSize: 11,
                }}>
                  {p.name}
                  {p.stack != null && (
                    <span style={{ color: '#64748b', marginLeft: 4, fontFamily: 'monospace', fontSize: 10 }}>
                      {Number(p.stack).toLocaleString('pt-PT')}
                    </span>
                  )}
                </span>
              )
            })}
          </div>
        )}
      </div>

      {/* Botão Apagar */}
      <div style={{ flexShrink: 0 }}>
        <button
          onClick={onDelete}
          title="Apagar permanentemente"
          style={{
            fontSize: 10, padding: '4px 10px', borderRadius: 4,
            background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)',
            color: '#f87171', cursor: 'pointer', fontWeight: 600,
          }}
        >Apagar</button>
      </div>
    </div>
  )
}


// ── Página Principal ─────────────────────────────────────────────────────────

function applyFilterTransform(params) {
  if (!params.date_from) delete params.date_from
  const { sd_yes, sd_no } = params
  delete params.sd_yes
  delete params.sd_no
  if (sd_yes && !sd_no) params.has_showdown = true
  else if (!sd_yes && sd_no) params.has_showdown = false
  return params
}

export default function HandsPage() {
  const [data, setData]           = useState({ data: [], total: 0, pages: 1 })
  const [tagGroupsData, setTagGroupsData] = useState({ groups: [], total: 0 })
  // Sub-fase 4b: groups que aparecem só quando include_discord_placeholders=true.
  // Calculado por subtracção (count em response2 menos count em response1, por
  // chave source+tags). Os matched continuam em tagGroupsData; os placeholders
  // separados aqui para serem renderizados em secção própria com cor distinta.
  const [placeholderGroups, setPlaceholderGroups] = useState([])
  const [page, setPage]           = useState(1)
  const [filters, setFilters]     = useState({ study_state: '', site: '', position: '', search: '', date_from: '', villain: '', sd_yes: false, sd_no: false })
  const [error, setError]         = useState('')
  const [loading, setLoading]     = useState(false)
  const [selected, setSelected]   = useState(null)
  const [viewMode, setViewMode]   = useState('tags') // 'tags' | 'tournament' | 'grid' | 'table'

  // Para a vista por tags: usa o endpoint tag-groups (sem paginação, só metadados).
  // Faz 2 chamadas em paralelo:
  //   - response1: matched apenas (study_view=true)
  //   - response2: matched + placeholders Discord não-nota-only
  // Subtrai count(response2) - count(response1) por chave source+tags para
  // isolar os placeholders. Hoje matched=0 → placeholders == response2.
  const loadTagGroups = useCallback(() => {
    if (viewMode !== 'tags') return
    setLoading(true)
    setError('')
    // Excluir mãos que só têm #mtt (bulk HH sem marcação de estudo).
    // tag_source='auto' agrupa por hm3_tags > discord_tags > '(sem tag)'.
    const baseParams = applyFilterTransform({ ...filters, exclude_mtt_only: true, tag_source: 'auto', study_view: true })
    const matchedReq = hands.tagGroups(baseParams)
    const allReq = hands.tagGroups({ ...baseParams, include_discord_placeholders: true })
    Promise.all([matchedReq, allReq])
      .then(([matched, all]) => {
        setTagGroupsData(matched)
        // Diff por chave source+sorted(tags). Subtracção por count: para cada
        // group em `all`, count_placeholder = all.count - matched.count (se key
        // existir em matched). W/L/BB zerados — placeholders não têm resultado.
        const keyOf = (g) => `${g.source || 'none'}:${(g.tags || []).slice().sort().join('+')}`
        const matchedByKey = new Map()
        for (const g of (matched.groups || [])) matchedByKey.set(keyOf(g), g)
        const placeholders = []
        for (const g of (all.groups || [])) {
          // Só interessa source='discord' aqui — o filtro do backend não muda
          // counts de hm3/none, mas defensivo por ruído de re-agregação.
          if (g.source !== 'discord') continue
          const matchedCount = matchedByKey.get(keyOf(g))?.count || 0
          const placeholderCount = (g.count || 0) - matchedCount
          if (placeholderCount > 0) {
            placeholders.push({
              ...g,
              count: placeholderCount,
              wins: 0, losses: 0, total_bb: 0,
            })
          }
        }
        setPlaceholderGroups(placeholders)
      })
      .catch(e => {
        setError(e.message)
        setPlaceholderGroups([])
      })
      .finally(() => setLoading(false))
  }, [filters, viewMode])

  // Para as vistas grid/tabela: usa o endpoint paginado normal
  const loadList = useCallback(() => {
    if (viewMode === 'tags') return
    setLoading(true)
    setError('')
    const ps = viewMode === 'tournament' ? 1000 : 200
    const params = applyFilterTransform({ ...filters, page, page_size: ps, exclude_mtt_only: true, study_view: true })
    hands.list(params)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [page, filters, viewMode])

  useEffect(() => { loadTagGroups() }, [loadTagGroups])
  useEffect(() => { loadList() }, [loadList])

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
      loadTagGroups()
      loadList()
    } catch (e) {
      setError(e.message)
    }
  }

  const rows = data.data || []
  const totalHands = viewMode === 'tags' ? tagGroupsData.total : data.total

  return (
    <>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: -0.5 }}>Mãos</div>
          <div style={{ color: '#64748b', fontSize: 13, marginTop: 3 }}>
            {totalHands} mãos de estudo &middot; <span style={{ fontSize: 11, color: '#4b5563' }}>mãos de torneio (bulk) em MTT</span>
          </div>
        </div>
        {/* Toggle views */}
        <div style={{ display: 'flex', gap: 4, background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 8, padding: 3 }}>
          {[
            { mode: 'tags', icon: '\u25A4', label: 'Por Tags' },
            { mode: 'tournament', icon: '\uD83C\uDFC6', label: 'Por Torneio' },
            { mode: 'grid', icon: '\u229E', label: 'Cards' },
            { mode: 'table', icon: '\u2261', label: 'Tabela' },
          ].map(({ mode, icon, label }) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              title={label}
              style={{
                padding: '5px 12px', borderRadius: 6, fontSize: 12, fontWeight: 500,
                border: 'none', cursor: 'pointer',
                background: viewMode === mode ? '#6366f1' : 'transparent',
                color: viewMode === mode ? '#fff' : '#64748b',
                transition: 'all 0.15s',
              }}
            >{icon} {label}</button>
          ))}
        </div>
      </div>

      {error && (
        <div style={{ color: '#ef4444', fontSize: 13, marginBottom: 12, padding: '8px 12px', background: 'rgba(239,68,68,0.08)', borderRadius: 6, border: '1px solid rgba(239,68,68,0.2)' }}>
          {error}
        </div>
      )}

      {/* Filtros temporais + showdown toggles (grupos separados) */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        {/* Datas — pills indigo */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {[
            { label: 'Todas', value: '' },
            { label: 'Hoje', value: (() => { const d = new Date(); d.setHours(0,0,0,0); return d.toISOString().slice(0,10) })() },
            { label: '3 dias', value: (() => { const d = new Date(); d.setDate(d.getDate()-3); return d.toISOString().slice(0,10) })() },
            { label: 'Semana', value: (() => { const d = new Date(); d.setDate(d.getDate()-7); return d.toISOString().slice(0,10) })() },
            { label: 'Mês', value: (() => { const d = new Date(); d.setDate(d.getDate()-30); return d.toISOString().slice(0,10) })() },
          ].map(({ label, value }) => (
            <button
              key={label}
              onClick={() => set('date_from', value)}
              style={{
                padding: '5px 14px', borderRadius: 20, fontSize: 12, fontWeight: 500,
                border: '1px solid',
                borderColor: filters.date_from === value ? '#6366f1' : '#2a2d3a',
                background: filters.date_from === value ? 'rgba(99,102,241,0.15)' : 'transparent',
                color: filters.date_from === value ? '#818cf8' : '#64748b',
                cursor: 'pointer', transition: 'all 0.15s',
              }}
            >{label}</button>
          ))}
        </div>

        {/* Showdown toggles — shape mais quadrada + cor emerald */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {[
            { key: 'sd_yes', label: 'Com showdown' },
            { key: 'sd_no',  label: 'Sem showdown' },
          ].map(({ key, label }) => {
            const active = !!filters[key]
            return (
              <button
                key={key}
                onClick={() => { setFilters(f => ({ ...f, [key]: !f[key] })); setPage(1) }}
                style={{
                  padding: '5px 12px', borderRadius: 6, fontSize: 12, fontWeight: 500,
                  border: '1px solid',
                  borderColor: active ? '#10b981' : '#2a2d3a',
                  background: active ? 'rgba(16,185,129,0.15)' : 'transparent',
                  color: active ? '#34d399' : '#64748b',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
              >{label}</button>
            )
          })}
        </div>
      </div>

      {/* Filtros */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20,
        background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 10, padding: '12px 16px',
      }}>
        <select value={filters.study_state} onChange={e => set('study_state', e.target.value)}
          style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 10px', fontSize: 12, minWidth: 130 }}>
          {STATES.map(s => <option key={s.v} value={s.v}>{s.l}</option>)}
        </select>

        <select value={filters.site} onChange={e => set('site', e.target.value)}
          style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 10px', fontSize: 12, minWidth: 120 }}>
          <option value="">Todas as salas</option>
          <option value="GGPoker">GGPoker</option>
          <option value="Winamax">Winamax</option>
          <option value="PokerStars">PokerStars</option>
          <option value="WPN">WPN</option>
        </select>

        <select value={filters.position} onChange={e => set('position', e.target.value)}
          style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 10px', fontSize: 12, minWidth: 100 }}>
          <option value="">Posição</option>
          {POSITIONS.filter(p => p).map(p => <option key={p} value={p}>{p}</option>)}
        </select>

        <input type="text" placeholder="Pesquisar torneio, tag..."
          value={filters.search} onChange={e => set('search', e.target.value)}
          style={{
            background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6,
            color: '#e2e8f0', padding: '6px 12px', fontSize: 12, minWidth: 160, flex: 1,
          }}
        />

        <input type="text" placeholder="Vilão (nick)"
          value={filters.villain || ''} onChange={e => set('villain', e.target.value)}
          style={{
            background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6,
            color: '#f59e0b', padding: '6px 12px', fontSize: 12, minWidth: 120,
          }}
        />

        {(filters.study_state || filters.site || filters.position || filters.search || filters.date_from || filters.villain || filters.sd_yes || filters.sd_no) && (
          <button
            onClick={() => { setFilters({ study_state: '', site: '', position: '', search: '', date_from: '', villain: '', sd_yes: false, sd_no: false }); setPage(1) }}
            style={{
              padding: '6px 12px', borderRadius: 6, fontSize: 12, fontWeight: 500,
              background: 'transparent', color: '#64748b', border: '1px solid #2a2d3a', cursor: 'pointer',
            }}
          >&#10005; Limpar</button>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '48px 0', color: '#64748b' }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>&#10227;</div>
          A carregar...
        </div>
      )}

      {/* Empty */}
      {!loading && rows.length === 0 && viewMode !== 'tags' && (
        <div style={{ textAlign: 'center', padding: '64px 0', color: '#64748b' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>&#127183;</div>
          <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 6 }}>Sem mãos</div>
          <div style={{ fontSize: 13 }}>Marca mãos com tags (#icm, #pko, #nota...) para aparecerem aqui. Mãos de torneio (bulk) estão na página Torneios.</div>
        </div>
      )}

      {/* Tags View (default) — grupos com contagens reais, lazy-load ao expandir.
          Re-agrega por TEMA (primeira tag que não seja 'nota*'); se só houver notas, usa a tag de nota.
          Depois parte em tiers: A (>100), B (10-100), C (<10).
          Gate inclui placeholderGroups: vista renderiza se houver matched OU placeholders. */}
      {!loading && viewMode === 'tags' && (tagGroupsData.groups.length > 0 || placeholderGroups.length > 0) && (() => {
        // Regra: se uma mão tem tags [X, Y, nota++], o tema é a primeira (alfabética) que não seja "nota*".
        // Fallback: se só tem tags de nota, usa a nota mesma.
        const pickTheme = (tags) => {
          if (!tags || tags.length === 0) return null
          const sorted = tags.slice().sort((a, b) => a.localeCompare(b))
          const themes = sorted.filter(t => !/nota/i.test(t))
          return themes.length > 0 ? themes[0] : sorted[0]
        }

        // Re-agregar: chave inclui source para hm3 e discord não se fundirem
        // (improvável no dataset porque são disjuntos, mas defensivo).
        const themeAgg = {}
        for (const g of tagGroupsData.groups) {
          const theme = pickTheme(g.tags)
          const src = g.source || 'none'
          const key = theme ? `${src}:${theme}` : '__no_tag__'
          if (!themeAgg[key]) {
            themeAgg[key] = { tags: theme ? [theme] : [], source: src, count: 0, wins: 0, losses: 0, total_bb: 0 }
          }
          const t = themeAgg[key]
          t.count    += g.count
          t.wins     += g.wins
          t.losses   += g.losses
          t.total_bb += g.total_bb
        }
        const merged = Object.values(themeAgg).sort((a, b) => b.count - a.count)

        // Secções: HM3 em tiers A/B/C, Discord em secção própria, (sem tag) no fim.
        const hm3Groups     = merged.filter(g => g.source === 'hm3')
        const discordGroups = merged.filter(g => g.source === 'discord')
        const noTagGroup    = merged.find(g => g.source === 'none' && g.tags.length === 0)

        const tierA = hm3Groups.filter(g => g.count > 100)
        const tierB = hm3Groups.filter(g => g.count > 10 && g.count <= 100)
        const tierC = hm3Groups.filter(g => g.count <= 10)

        const renderGroup = (group, i) => {
          const tagKey = group.tags.length === 0 ? '__no_tag__' : group.tags.slice().sort().join('+')
          return (
            <TagGroup
              key={(group.source || 'none') + ':' + tagKey + i}
              tagKey={tagKey}
              tags={group.tags}
              source={group.source}
              count={group.count}
              wins={group.wins}
              losses={group.losses}
              totalBB={group.total_bb}
              filters={filters}
              useHm3Tags={true}
              studyView={true}
              onOpenDetail={openDetail}
              onDeleteHand={deleteHand}
            />
          )
        }

        return (
          <div style={{ marginBottom: 24 }}>
            {tierA.length > 0 && (
              <>
                <TierHeader label="Principais" subtitle=">100 mãos" count={tierA.length} />
                {tierA.map(renderGroup)}
              </>
            )}
            {tierB.length > 0 && (
              <TierCollapsible label="Secundárias" subtitle="10–100 mãos" count={tierB.length} defaultOpen={tierA.length === 0}>
                {tierB.map(renderGroup)}
              </TierCollapsible>
            )}
            {tierC.length > 0 && (
              <TierCollapsible label="Spots específicos" subtitle="<10 mãos" count={tierC.length} defaultOpen={false}>
                {tierC.map(renderGroup)}
              </TierCollapsible>
            )}
            {discordGroups.length > 0 && (
              <TierCollapsible
                label="Canais Discord"
                subtitle={`${discordGroups.length} canal${discordGroups.length === 1 ? '' : 'is'}`}
                count={discordGroups.length}
                defaultOpen={tierA.length === 0 && tierB.length === 0}
              >
                {discordGroups.map(renderGroup)}
              </TierCollapsible>
            )}
            {/* Sub-fase 4b: placeholders Discord (sem HH ainda).
                Re-agrega por pickTheme (igual aos matched), depois renderiza
                cada canal como TagGroup com isPlaceholder=true (cor azul claro,
                sem stats W/L/BB, expand pede include_discord_placeholders=true). */}
            {placeholderGroups.length > 0 && (() => {
              const phAgg = {}
              for (const g of placeholderGroups) {
                const theme = pickTheme(g.tags)
                const key = `discord:${theme || ''}`
                if (!phAgg[key]) {
                  phAgg[key] = { tags: theme ? [theme] : [], source: 'discord', count: 0, wins: 0, losses: 0, total_bb: 0 }
                }
                phAgg[key].count += g.count
              }
              const phMerged = Object.values(phAgg).sort((a, b) => b.count - a.count)
              const totalPh = phMerged.reduce((s, g) => s + g.count, 0)
              return (
                <TierCollapsible
                  label="Discord — Só SS (sem HH)"
                  subtitle={`${totalPh} mã${totalPh === 1 ? 'o' : 'os'} · ${phMerged.length} canal${phMerged.length === 1 ? '' : 'is'}`}
                  count={phMerged.length}
                  defaultOpen={tierA.length === 0 && tierB.length === 0 && discordGroups.length === 0}
                  colorOverride="#38bdf8"
                >
                  {phMerged.map((group, i) => {
                    const tagKey = group.tags.length === 0 ? '__no_tag__' : group.tags.slice().sort().join('+')
                    return (
                      <TagGroup
                        key={'ph:' + tagKey + i}
                        tagKey={tagKey}
                        tags={group.tags}
                        source={group.source}
                        count={group.count}
                        wins={group.wins}
                        losses={group.losses}
                        totalBB={group.total_bb}
                        filters={filters}
                        useHm3Tags={true}
                        studyView={true}
                        isPlaceholder={true}
                        onOpenDetail={openDetail}
                        onDeleteHand={deleteHand}
                      />
                    )
                  })}
                </TierCollapsible>
              )
            })()}
            {noTagGroup && noTagGroup.count > 0 && (
              <TierCollapsible
                label="(Sem tag)"
                subtitle={`${noTagGroup.count} mã${noTagGroup.count === 1 ? 'o' : 'os'}`}
                count={1}
                defaultOpen={false}
              >
                {renderGroup(noTagGroup, 0)}
              </TierCollapsible>
            )}
          </div>
        )
      })()}

      {/* Tournament View — group hands by tournament name */}
      {!loading && viewMode === 'tournament' && rows.length > 0 && (() => {
        const tournGroups = {}
        for (const h of rows) {
          const tName = h.stakes || 'Sem torneio'
          if (!tournGroups[tName]) tournGroups[tName] = []
          tournGroups[tName].push(h)
        }
        const sorted = Object.entries(tournGroups).sort((a, b) => {
          const aTime = Math.max(...a[1].map(h => h.played_at ? new Date(h.played_at).getTime() : 0))
          const bTime = Math.max(...b[1].map(h => h.played_at ? new Date(h.played_at).getTime() : 0))
          return bTime - aTime
        })
        return (
          <div style={{ marginBottom: 24 }}>
            {sorted.map(([tName, tHands]) => {
              const wins = tHands.filter(h => h.result != null && Number(h.result) > 0).length
              const losses = tHands.filter(h => h.result != null && Number(h.result) < 0).length
              const totalBB = tHands.reduce((a, h) => a + (Number(h.result) || 0), 0)
              return <TournamentGroup key={tName} name={tName} hands={tHands} wins={wins} losses={losses} totalBB={totalBB} onOpenDetail={openDetail} onDeleteHand={deleteHand} />
            })}
          </div>
        )
      })()}

      {/* Grid View */}
      {!loading && rows.length > 0 && viewMode === 'grid' && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 12, marginBottom: 24,
        }}>
          {rows.map(h => (
            <HandCard
              key={h.id}
              hand={h}
              onClick={() => openDetail(h.id)}
              onDelete={() => deleteHand(h.id)}
            />
          ))}
        </div>
      )}

      {/* Table View */}
      {!loading && rows.length > 0 && viewMode === 'table' && (
        <div style={{ background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 10, overflow: 'hidden', marginBottom: 24 }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #2a2d3a' }}>
                  {['Estado', 'Sala', 'Data', 'Torneio', 'Pos', 'Cartas', 'Board', 'Resultado', 'Tags', ''].map(h => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#64748b', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5, whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((h, idx) => (
                  <tr key={h.id}
                    style={{ borderBottom: '1px solid #1e2130', cursor: 'pointer', transition: 'background 0.1s', background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}
                    onClick={() => openDetail(h.id)}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.04)'}
                    onMouseLeave={e => e.currentTarget.style.background = idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)'}
                  >
                    <td style={{ padding: '10px 14px' }}><StateBadge state={h.study_state} /></td>
                    <td style={{ padding: '10px 14px' }}>
                      {(() => {
                        const ss = h.site === 'Winamax' ? 'WN' : h.site === 'PokerStars' ? 'PS' : h.site === 'WPN' ? 'WPN' : h.site === 'GGPoker' ? 'GG' : '?'
                        const sc = h.site === 'Winamax' ? '#f59e0b' : h.site === 'PokerStars' ? '#ef4444' : h.site === 'WPN' ? '#22c55e' : '#6366f1'
                        return <span style={{ fontSize: 10, fontWeight: 700, color: sc }}>{ss}</span>
                      })()}
                    </td>
                    <td style={{ padding: '10px 14px', color: '#64748b', whiteSpace: 'nowrap' }}>{h.played_at ? h.played_at.slice(0, 10) : '&mdash;'}</td>
                    <td style={{ padding: '10px 14px', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#94a3b8', fontSize: 11 }}>{h.stakes || '&mdash;'}</td>
                    <td style={{ padding: '10px 14px' }}><PosBadge pos={h.position} /></td>
                    <td style={{ padding: '10px 14px' }}>
                      <div style={{ display: 'flex', gap: 3 }}>
                        {h.hero_cards?.length > 0 ? h.hero_cards.map((c, i) => <PokerCard key={i} card={c} size="sm" />) : <span style={{ color: '#4b5563' }}>&mdash;</span>}
                      </div>
                    </td>
                    <td style={{ padding: '10px 14px' }}><BoardCards board={h.board} size="sm" /></td>
                    <td style={{ padding: '10px 14px' }}><ResultBadge result={h.result} /></td>
                    <td style={{ padding: '10px 14px' }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
                        {h.tags?.map(t => <Tag key={t} t={t} />)}
                      </div>
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <button style={{ background: 'transparent', border: 'none', color: '#4b5563', cursor: 'pointer', fontSize: 12 }}
                        onClick={e => { e.stopPropagation(); deleteHand(h.id) }}
                        onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
                        onMouseLeave={e => e.currentTarget.style.color = '#374151'}
                      >&#10005;</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Paginação */}
      {data.pages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center', marginBottom: 24 }}>
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
            style={{
              padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 500,
              background: page <= 1 ? 'transparent' : '#1a1d27',
              color: page <= 1 ? '#374151' : '#e2e8f0',
              border: '1px solid #2a2d3a', cursor: page <= 1 ? 'not-allowed' : 'pointer',
            }}>&#8592; Anterior</button>
          <span style={{ color: '#64748b', fontSize: 12 }}>
            Pág. {page} / {data.pages} &middot; {data.total} mãos
          </span>
          <button disabled={page >= data.pages} onClick={() => setPage(p => p + 1)}
            style={{
              padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 500,
              background: page >= data.pages ? 'transparent' : '#1a1d27',
              color: page >= data.pages ? '#374151' : '#e2e8f0',
              border: '1px solid #2a2d3a', cursor: page >= data.pages ? 'not-allowed' : 'pointer',
            }}>Próxima &#8594;</button>
        </div>
      )}

      {/* Modal */}
      {selected && (
        <HandDetailModal
          hand={selected}
          onClose={() => setSelected(null)}
          onUpdate={() => { setSelected(null); loadTagGroups(); loadList() }}
        />
      )}
    </>
  )
}

// ── Componente: Hand Card (grid view) — mantido para compatibilidade ────────

function HandCard({ hand, onClick, onDelete }) {
  const meta = STATE_META[hand.study_state] || STATE_META.new
  const isWin = hand.result != null && Number(hand.result) > 0
  const isLose = hand.result != null && Number(hand.result) < 0

  return (
    <div onClick={onClick} style={{
      background: '#1a1d27',
      border: `1px solid ${isWin ? 'rgba(34,197,94,0.2)' : isLose ? 'rgba(239,68,68,0.15)' : '#2a2d3a'}`,
      borderRadius: 10, padding: '14px 16px', cursor: 'pointer',
      transition: 'border-color 0.15s, transform 0.1s, box-shadow 0.15s',
      position: 'relative', overflow: 'hidden',
    }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = '#6366f1'; e.currentTarget.style.boxShadow = '0 4px 20px rgba(99,102,241,0.15)'; e.currentTarget.style.transform = 'translateY(-1px)' }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = isWin ? 'rgba(34,197,94,0.2)' : isLose ? 'rgba(239,68,68,0.15)' : '#2a2d3a'; e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.transform = 'none' }}
    >
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: meta.color, opacity: 0.7 }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          <StateBadge state={hand.study_state} />
          <PosBadge pos={hand.position} />
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <ResultBadge result={hand.result} />
          <button style={{ background: 'transparent', border: 'none', color: '#4b5563', cursor: 'pointer', fontSize: 13, padding: '0 2px', lineHeight: 1 }}
            onClick={e => { e.stopPropagation(); onDelete() }}
            onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
            onMouseLeave={e => e.currentTarget.style.color = '#374151'}
          >&#10005;</button>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
        {hand.hero_cards?.length > 0
          ? hand.hero_cards.map((c, i) => <PokerCard key={i} card={c} size="md" />)
          : <span style={{ color: '#4b5563', fontSize: 12, fontStyle: 'italic' }}>cartas não visíveis</span>
        }
      </div>
      {hand.board?.length > 0 && <div style={{ marginBottom: 10 }}><BoardCards board={hand.board} size="sm" /></div>}
      {hand.stakes && <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{hand.stakes}</div>}
      {hand.tags?.length > 0 && <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>{hand.tags.map(t => <Tag key={t} t={t} />)}</div>}
    </div>
  )
}
