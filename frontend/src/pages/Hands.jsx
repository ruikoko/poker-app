import { useEffect, useState, useCallback } from 'react'
import { hands } from '../api/client'

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
  const color = SUIT_COLORS[suit] || '#e2e8f0'
  const symbol = SUIT_SYMBOLS[suit] || suit

  return (
    <span style={{
      display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      width: size === 'sm' ? 26 : size === 'lg' ? 38 : 34,
      height: size === 'sm' ? 36 : size === 'lg' ? 50 : 46,
      background: '#1e2130', border: '1px solid rgba(255,255,255,0.12)',
      borderRadius: 4, fontFamily: "'Fira Code', monospace",
      fontSize: size === 'sm' ? 10 : size === 'lg' ? 14 : 12,
      fontWeight: 700, color, lineHeight: 1, gap: 1, userSelect: 'none',
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
    <div style={{ display: 'flex', gap: 3, alignItems: 'center', flexWrap: 'wrap' }}>
      {board.slice(0, 5).map((c, i) => (
        <span key={i}>
          {(i === 3 || i === 4) && <span style={{ display: 'inline-block', width: 4 }} />}
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
      fontSize: 10, fontWeight: 600, letterSpacing: 0.3,
      color: meta.color, background: meta.bg,
    }}>{meta.label}</span>
  )
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ color: '#4b5563' }}>&mdash;</span>
  const colors = {
    BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa',
    SB: '#f59e0b', BB: '#ef4444',
    UTG: '#22c55e', UTG1: '#16a34a', UTG2: '#15803d',
    MP: '#06b6d4', MP1: '#0891b2',
  }
  const c = colors[pos] || '#64748b'
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 4,
      fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
      color: c, background: `${c}20`, border: `1px solid ${c}40`,
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
        fontSize: 10, fontWeight: 600, marginRight: 3, marginBottom: 2,
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
      fontSize: 10, fontWeight: 600, fontFamily: 'monospace',
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
                fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
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
                      {player.isHero && <span style={{ fontSize: 9, color: '#6366f1', marginLeft: 4 }}>(HERO)</span>}
                    </span>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {acts.map((a, j) => <ActionBadge key={j} text={a} />)}
                    </div>
                    {player.stackBB != null && (
                      <span style={{ fontSize: 9, color: '#4b5563', marginLeft: 'auto', fontFamily: 'monospace' }}>
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
              <span style={{ color: '#64748b', fontSize: 10, fontWeight: 600 }}>{street}: </span>
              <span style={{ color: '#e2e8f0', fontFamily: 'monospace' }}>{action}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Componente: Modal de Detalhe ─────────────────────────────────────────────

function HandDetailModal({ hand, onClose, onUpdate }) {
  const [notes, setNotes] = useState(hand.notes || '')
  const [tags, setTags]   = useState((hand.tags || []).join(', '))
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

  const isGG = (hand.raw || '').includes('gg.gl')

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
            {hand.stakes && <div style={{ fontSize: 12, color: '#64748b' }}>{hand.stakes}</div>}
          </div>
          <button
            style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 18, padding: 4 }}
            onClick={onClose}
          >&#10005;</button>
        </div>

        {/* Cartas + Board */}
        <div style={{
          background: '#0f1117', borderRadius: 10, padding: '16px 20px',
          marginBottom: 20, display: 'flex', gap: 32, alignItems: 'center', flexWrap: 'wrap',
        }}>
          <div>
            <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>
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
              <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Board</div>
              <div style={{ display: 'flex', gap: 5 }}>
                {hand.board.slice(0, 5).map((c, i) => <PokerCard key={i} card={c} size="lg" />)}
              </div>
            </div>
          )}
        </div>

        {/* Info grid */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px 20px',
          marginBottom: 20, fontSize: 13,
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
              <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, letterSpacing: 0.4, marginBottom: 3, textTransform: 'uppercase' }}>{l}</div>
              <div>{v || <span style={{ color: '#4b5563' }}>&mdash;</span>}</div>
            </div>
          ))}
        </div>

        {/* Acções de todos os jogadores (se disponível) ou fallback hero */}
        {hand.all_players_actions
          ? <AllPlayersActions actions={hand.all_players_actions} />
          : <HeroActionsFromNotes notes={hand.notes} />
        }

        {/* Screenshot inline */}
        {hand.screenshot_url && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Screenshot</div>
            <img
              src={hand.screenshot_url}
              alt="Screenshot da mão"
              style={{ maxWidth: '100%', borderRadius: 8, border: '1px solid #2a2d3a', cursor: 'pointer' }}
              onClick={() => window.open(hand.screenshot_url, '_blank')}
            />
          </div>
        )}

        {/* Replayer link */}
        {isGG && (
          <div style={{ marginBottom: 16 }}>
            <a href={hand.raw} target="_blank" rel="noopener noreferrer" style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 500,
              background: 'rgba(99,102,241,0.12)', color: '#818cf8',
              border: '1px solid rgba(99,102,241,0.25)', textDecoration: 'none',
            }}>
              &#9654; Abrir Replayer GG
            </a>
          </div>
        )}

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

function HandRow({ hand, onClick, onDelete }) {
  const isWin = hand.result != null && Number(hand.result) > 0
  const isLose = hand.result != null && Number(hand.result) < 0

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '10px 16px',
        background: '#1a1d27',
        borderBottom: '1px solid #1e2130',
        cursor: 'pointer',
        transition: 'background 0.1s',
      }}
      onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.04)'}
      onMouseLeave={e => e.currentTarget.style.background = '#1a1d27'}
    >
      {/* Estado */}
      <div style={{ minWidth: 60 }}>
        <StateBadge state={hand.study_state} />
      </div>

      {/* Posição */}
      <div style={{ minWidth: 50 }}>
        <PosBadge pos={hand.position} />
      </div>

      {/* Cartas do hero */}
      <div style={{ display: 'flex', gap: 3, minWidth: 60 }}>
        {hand.hero_cards?.length > 0
          ? hand.hero_cards.map((c, i) => <PokerCard key={i} card={c} size="sm" />)
          : <span style={{ color: '#374151', fontSize: 11 }}>&mdash;</span>
        }
      </div>

      {/* Board */}
      <div style={{ minWidth: 140, flex: 0 }}>
        <BoardCards board={hand.board} size="sm" />
      </div>

      {/* Resultado */}
      <div style={{ minWidth: 80 }}>
        <ResultBadge result={hand.result} />
      </div>

      {/* Torneio */}
      <div style={{
        flex: 1, fontSize: 11, color: '#64748b',
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      }}>
        {hand.stakes || ''}
      </div>

      {/* Data */}
      <div style={{ fontSize: 11, color: '#4b5563', minWidth: 70 }}>
        {hand.played_at ? hand.played_at.slice(0, 10) : ''}
      </div>

      {/* Delete */}
      <button
        style={{ background: 'transparent', border: 'none', color: '#374151', cursor: 'pointer', fontSize: 12, padding: '0 4px' }}
        onClick={e => { e.stopPropagation(); onDelete() }}
        onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
        onMouseLeave={e => e.currentTarget.style.color = '#374151'}
      >&#10005;</button>
    </div>
  )
}

// ── Componente: Tag Group (colapsável) ──────────────────────────────────────

// TagGroup recebe metadados do endpoint tag-groups e faz lazy-load das mãos ao expandir
function TagGroup({ tagKey, tags, count, wins, losses, totalBB, filters, onOpenDetail, onDeleteHand }) {
  const [open, setOpen] = useState(false)
  const [tagHands, setTagHands] = useState([])
  const [loadingHands, setLoadingHands] = useState(false)

  async function expand() {
    if (!open && tagHands.length === 0) {
      setLoadingHands(true)
      try {
        // Fetch mãos deste grupo específico
        const params = { ...filters, page_size: 500, page: 1 }
        if (!params.date_from) delete params.date_from
        if (tags.length === 0) {
          // sem-tag: buscar mãos sem tags
          params.tag = '__none__'
        } else {
          // Para grupos com tags, filtrar pela tag principal (combinação)
          // Usamos a primeira tag como filtro e depois filtramos no frontend
          params.tag = tags[0]
        }
        const result = await hands.list(params)
        let fetched = result.data || []
        // Se o grupo tem múltiplas tags, filtrar para só mostrar mãos com exactamente essas tags
        if (tags.length > 1) {
          const keySet = tags.sort().join('+')
          fetched = fetched.filter(h => h.tags && h.tags.sort().join('+') === keySet)
        } else if (tags.length === 0) {
          fetched = fetched.filter(h => !h.tags || h.tags.length === 0)
        }
        setTagHands(fetched)
      } catch (e) {
        console.error('Erro ao carregar mãos do grupo:', e)
      } finally {
        setLoadingHands(false)
      }
    }
    setOpen(o => !o)
  }

  // Cor baseada na primeira tag
  const tag = tags.length > 0 ? tags[0] : 'sem-tag'
  const colors = {
    icm: '#6366f1', pko: '#f59e0b', ko: '#f59e0b', pos: '#22c55e',
    bvb: '#8b5cf6', ss: '#ef4444', ft: '#06b6d4', nota: '#64748b',
    cbet: '#a78bfa', ip: '#34d399', mw: '#fb923c',
    speed: '#ec4899', racer: '#ec4899',
  }
  const tagColor = colors[tag] || '#64748b'

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
            display: 'inline-block', fontSize: 10, color: tagColor,
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

        {/* Stats rápidas */}
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
          ) : (
            tagHands.map(h => (
              <HandRow
                key={h.id}
                hand={h}
                onClick={() => onOpenDetail(h.id)}
                onDelete={() => onDeleteHand(h.id)}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

// ── Página Principal ─────────────────────────────────────────────────────────

export default function HandsPage() {
  const [data, setData]           = useState({ data: [], total: 0, pages: 1 })
  const [tagGroupsData, setTagGroupsData] = useState({ groups: [], total: 0 })
  const [page, setPage]           = useState(1)
  const [filters, setFilters]     = useState({ study_state: '', site: '', position: '', search: '', date_from: '' })
  const [error, setError]         = useState('')
  const [loading, setLoading]     = useState(false)
  const [selected, setSelected]   = useState(null)
  const [viewMode, setViewMode]   = useState('tags') // 'tags' | 'grid' | 'table'

  // Para a vista por tags: usa o endpoint tag-groups (sem paginação, só metadados)
  const loadTagGroups = useCallback(() => {
    if (viewMode !== 'tags') return
    setLoading(true)
    setError('')
    const params = { ...filters }
    if (!params.date_from) delete params.date_from
    hands.tagGroups(params)
      .then(setTagGroupsData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [filters, viewMode])

  // Para as vistas grid/tabela: usa o endpoint paginado normal
  const loadList = useCallback(() => {
    if (viewMode === 'tags') return
    setLoading(true)
    setError('')
    const params = { ...filters, page, page_size: 200 }
    if (!params.date_from) delete params.date_from
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
            {totalHands} mãos registadas
          </div>
        </div>
        {/* Toggle views */}
        <div style={{ display: 'flex', gap: 4, background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 8, padding: 3 }}>
          {[
            { mode: 'tags', icon: '\u25A4', label: 'Por Tags' },
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

      {/* Filtros temporais rápidos */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
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
            color: '#e2e8f0', padding: '6px 12px', fontSize: 12, minWidth: 200, flex: 1,
          }}
        />

        {(filters.study_state || filters.site || filters.position || filters.search || filters.date_from) && (
          <button
            onClick={() => { setFilters({ study_state: '', site: '', position: '', search: '', date_from: '' }); setPage(1) }}
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
          <div style={{ fontSize: 13 }}>Importa ficheiros HH na página P&amp;L ou sincroniza o Discord.</div>
        </div>
      )}

      {/* Tags View (default) — grupos com contagens reais, lazy-load ao expandir */}
      {!loading && viewMode === 'tags' && tagGroupsData.groups.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          {tagGroupsData.groups.map((group, i) => {
            const tagKey = group.tags.length === 0 ? '__no_tag__' : group.tags.sort().join('+')
            return (
              <TagGroup
                key={tagKey + i}
                tagKey={tagKey}
                tags={group.tags}
                count={group.count}
                wins={group.wins}
                losses={group.losses}
                totalBB={group.total_bb}
                filters={filters}
                onOpenDetail={openDetail}
                onDeleteHand={deleteHand}
              />
            )
          })}
        </div>
      )}

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
                  {['Estado', 'Data', 'Torneio', 'Pos', 'Cartas', 'Board', 'Resultado', 'Tags', ''].map(h => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#64748b', fontWeight: 600, fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.5, whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map(h => (
                  <tr key={h.id}
                    style={{ borderBottom: '1px solid #1e2130', cursor: 'pointer', transition: 'background 0.1s' }}
                    onClick={() => openDetail(h.id)}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.04)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <td style={{ padding: '10px 14px' }}><StateBadge state={h.study_state} /></td>
                    <td style={{ padding: '10px 14px', color: '#64748b', whiteSpace: 'nowrap' }}>{h.played_at ? h.played_at.slice(0, 10) : '&mdash;'}</td>
                    <td style={{ padding: '10px 14px', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#94a3b8', fontSize: 11 }}>{h.stakes || '&mdash;'}</td>
                    <td style={{ padding: '10px 14px' }}><PosBadge pos={h.position} /></td>
                    <td style={{ padding: '10px 14px' }}>
                      <div style={{ display: 'flex', gap: 3 }}>
                        {h.hero_cards?.length > 0 ? h.hero_cards.map((c, i) => <PokerCard key={i} card={c} size="sm" />) : <span style={{ color: '#374151' }}>&mdash;</span>}
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
                      <button style={{ background: 'transparent', border: 'none', color: '#374151', cursor: 'pointer', fontSize: 12 }}
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
          onUpdate={() => { setSelected(null); load() }}
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
          <button style={{ background: 'transparent', border: 'none', color: '#374151', cursor: 'pointer', fontSize: 13, padding: '0 2px', lineHeight: 1 }}
            onClick={e => { e.stopPropagation(); onDelete() }}
            onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
            onMouseLeave={e => e.currentTarget.style.color = '#374151'}
          >&#10005;</button>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
        {hand.hero_cards?.length > 0
          ? hand.hero_cards.map((c, i) => <PokerCard key={i} card={c} size="md" />)
          : <span style={{ color: '#374151', fontSize: 12, fontStyle: 'italic' }}>cartas não visíveis</span>
        }
      </div>
      {hand.board?.length > 0 && <div style={{ marginBottom: 10 }}><BoardCards board={hand.board} size="sm" /></div>}
      {hand.stakes && <div style={{ fontSize: 10, color: '#64748b', marginBottom: 8, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{hand.stakes}</div>}
      {hand.tags?.length > 0 && <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>{hand.tags.map(t => <Tag key={t} t={t} />)}</div>}
    </div>
  )
}
