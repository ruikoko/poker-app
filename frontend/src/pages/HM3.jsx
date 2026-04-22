import { useEffect, useState, useCallback } from 'react'
import { hands, hm3 } from '../api/client'
import Replayer from '../components/Replayer'
import HandRow from '../components/HandRow'

// ── Constants ────────────────────────────────────────────────────────────────

const SUIT_BG = { h: '#dc2626', d: '#2563eb', c: '#16a34a', s: '#1e293b' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }

const STATES = [
  { v: '',          l: 'Todos os estados' },
  { v: 'new',       l: 'Novas' },
  { v: 'review',    l: 'Em Revisão' },
  { v: 'studying',  l: 'A Estudar' },
  { v: 'resolved',  l: 'Resolvidas' },
]

const STATE_META = {
  new:      { label: 'Nova',      color: '#3b82f6', bg: 'rgba(59,130,246,0.15)' },
  review:   { label: 'Revisão',   color: '#f59e0b', bg: 'rgba(245,158,11,0.15)' },
  studying: { label: 'A Estudar', color: '#8b5cf6', bg: 'rgba(139,92,246,0.15)' },
  resolved: { label: 'Resolvida', color: '#22c55e', bg: 'rgba(34,197,94,0.15)' },
}

const STREET_LABELS = { preflop: 'Pre-Flop', flop: 'Flop', turn: 'Turn', river: 'River', showdown: 'Showdown' }
const STREET_COLORS = { preflop: '#6366f1', flop: '#22c55e', turn: '#f59e0b', river: '#ef4444', showdown: '#8b5cf6' }

const ACTION_COLORS = {
  fold: { color: '#64748b', bg: 'rgba(100,116,139,0.10)' },
  check: { color: '#94a3b8', bg: 'rgba(148,163,184,0.10)' },
  call: { color: '#22c55e', bg: 'rgba(34,197,94,0.10)' },
  bet: { color: '#f59e0b', bg: 'rgba(245,158,11,0.10)' },
  raise: { color: '#f97316', bg: 'rgba(249,115,22,0.10)' },
  allin: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)' },
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function PokerCard({ card, size = 'sm' }) {
  if (!card || card.length < 2) return <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 24, height: 34, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 3, fontSize: 11, color: '#4b5563' }}>?</span>
  const rank = card.slice(0, -1).toUpperCase()
  const suit = card.slice(-1).toLowerCase()
  const bg = SUIT_BG[suit] || '#1e2130'
  const w = size === 'lg' ? 38 : size === 'md' ? 34 : 24
  const h = size === 'lg' ? 50 : size === 'md' ? 46 : 34
  const fs = size === 'lg' ? 14 : size === 'md' ? 12 : 10
  return (
    <span style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', width: w, height: h, background: bg, border: '1px solid rgba(255,255,255,0.2)', borderRadius: 3, fontFamily: "'Fira Code', monospace", fontSize: fs, fontWeight: 700, color: '#fff', lineHeight: 1, gap: 0, boxShadow: '0 1px 2px rgba(0,0,0,0.3)', userSelect: 'none' }}>
      <span>{rank}</span>
      <span style={{ fontSize: fs - 1 }}>{SUIT_SYMBOLS[suit] || suit}</span>
    </span>
  )
}

function StateBadge({ state }) {
  const meta = STATE_META[state] || { label: state, color: '#666', bg: 'rgba(100,100,100,0.15)' }
  return <span style={{ display: 'inline-block', padding: '2px 9px', borderRadius: 999, fontSize: 11, fontWeight: 600, letterSpacing: 0.3, color: meta.color, background: meta.bg }}>{meta.label}</span>
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ display: 'inline-block', width: 48, textAlign: 'center', color: '#4b5563' }}>&mdash;</span>
  const colors = { BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa', SB: '#f59e0b', BB: '#ef4444', UTG: '#22c55e', UTG1: '#16a34a', UTG2: '#15803d', MP: '#06b6d4', MP1: '#0891b2' }
  const c = colors[pos] || '#64748b'
  const isBlind = pos === 'SB' || pos === 'BB'
  return <span style={{ display: 'inline-block', padding: '2px 0', borderRadius: 4, width: 48, textAlign: 'center', fontSize: 11, fontWeight: 700, letterSpacing: 0.5, color: '#0a0c14', background: isBlind ? c : '#e2e8f0', border: `1px solid ${isBlind ? c : '#e2e8f0'}` }}>{pos}</span>
}

function ResultBadge({ result }) {
  if (result == null) return <span style={{ color: '#4b5563' }}>&mdash;</span>
  const val = Number(result)
  if (val > 0) return <span style={{ color: '#22c55e', fontWeight: 600, fontFamily: 'monospace' }}>+{val.toFixed(1)} BB</span>
  if (val < 0) return <span style={{ color: '#ef4444', fontWeight: 600, fontFamily: 'monospace' }}>{val.toFixed(1)} BB</span>
  return <span style={{ color: '#64748b', fontFamily: 'monospace' }}>0 BB</span>
}

function Tag({ t }) {
  const colors = { icm: '#6366f1', pko: '#f59e0b', ko: '#f59e0b', pos: '#22c55e', bvb: '#8b5cf6', ss: '#ef4444', ft: '#06b6d4', nota: '#64748b', 'nota++': '#818cf8', 'ICM PKO': '#f59e0b', 'PKO pos': '#22c55e', 'For Review': '#3b82f6', GTw: '#06b6d4', 'MW PKO': '#fb923c' }
  const c = colors[t] || '#64748b'
  return <span style={{ display: 'inline-block', padding: '1px 7px', borderRadius: 999, fontSize: 11, fontWeight: 600, marginRight: 3, color: c, background: `${c}18`, border: `1px solid ${c}30` }}>#{t}</span>
}

function extractLevel(raw) {
  if (!raw) return null
  const wn = raw.match(/level:\s*(\d+)/i)
  if (wn) return `Lv ${wn[1]}`
  const ps = raw.match(/Level\s+([IVXLCDM]+|\d+)/i)
  if (ps) {
    const v = ps[1]
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
  return <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600, fontFamily: 'monospace', color: s.color, background: s.bg, border: `1px solid ${s.color}25`, whiteSpace: 'nowrap' }}>{text}</span>
}

// ── HH Parser ────────────────────────────────────────────────────────────────

function parseRawHH(raw) {
  if (!raw) return null
  let heroName = null
  const dealtM = raw.match(/Dealt to (\S+)/)
  if (dealtM) heroName = dealtM[1]

  const streets = []
  const markers = [
    { key: 'preflop', start: /\*\*\* (?:HOLE CARDS|PRE-FLOP) \*\*\*/, end: [/\*\*\* FLOP \*\*\*/, /\*\*\* SUMMARY \*\*\*/, /\*\*\* SHOW DOWN \*\*\*/] },
    { key: 'flop', start: /\*\*\* FLOP \*\*\*/, end: [/\*\*\* TURN \*\*\*/, /\*\*\* SUMMARY \*\*\*/, /\*\*\* SHOW DOWN \*\*\*/] },
    { key: 'turn', start: /\*\*\* TURN \*\*\*/, end: [/\*\*\* RIVER \*\*\*/, /\*\*\* SUMMARY \*\*\*/, /\*\*\* SHOW DOWN \*\*\*/] },
    { key: 'river', start: /\*\*\* RIVER \*\*\*/, end: [/\*\*\* SUMMARY \*\*\*/, /\*\*\* SHOW DOWN \*\*\*/] },
  ]

  for (const { key, start, end } of markers) {
    const startM = raw.match(start)
    if (!startM) continue
    const startIdx = startM.index + startM[0].length
    let endIdx = raw.length
    for (const e of end) {
      const em = raw.slice(startIdx).match(e)
      if (em && startIdx + em.index < endIdx) endIdx = startIdx + em.index
    }
    const section = raw.slice(startIdx, endIdx)
    const actions = []
    for (const line of section.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith('***') || trimmed.startsWith('Dealt') || trimmed.startsWith('Main pot') || trimmed.startsWith('Side pot')) continue
      const m = trimmed.match(/^(.+?)(?::)?\s+(folds|checks|calls|bets|raises|posts|collected|wins|shows|mucks|is sitting|has timed|has returned)(.*)$/i)
      if (m) {
        const name = m[1].trim()
        const action = m[2] + (m[3] || '')
        const isHero = heroName && name === heroName
        if (!action.toLowerCase().startsWith('posts') && !action.toLowerCase().startsWith('is sitting') && !action.toLowerCase().startsWith('has timed') && !action.toLowerCase().startsWith('has returned'))
          actions.push({ name, action: action.trim(), isHero })
      }
    }
    if (actions.length > 0) streets.push({ key, actions })
  }

  // Showdown
  const sdStart = raw.indexOf('*** SHOW DOWN ***')
  const sdEnd = raw.indexOf('*** SUMMARY ***')
  if (sdStart !== -1) {
    const sdSection = raw.slice(sdStart, sdEnd !== -1 ? sdEnd : undefined)
    const actions = []
    for (const line of sdSection.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith('***')) continue
      const showM = trimmed.match(/^(.+?)(?::)?\s+shows\s+\[(.+?)\](.*)/)
      const collectM = trimmed.match(/^(.+?)\s+collected\s+([\d,]+)/)
      if (showM) {
        const cards = showM[2].trim().split(/\s+/)
        actions.push({ name: showM[1].trim(), action: `shows [${showM[2]}]${showM[3] ? ' ' + showM[3].trim() : ''}`, cards, isHero: heroName && showM[1].trim() === heroName })
      }
      else if (collectM) actions.push({ name: collectM[1].trim(), action: `collected ${collectM[2]}`, isHero: heroName && collectM[1].trim() === heroName })
    }
    if (actions.length > 0) streets.push({ key: 'showdown', actions })
  }

  return streets.length > 0 ? streets : null
}

// ── Detail Modal ─────────────────────────────────────────────────────────────

function HandDetailModal({ hand, onClose, onUpdate }) {
  const [notes, setNotes] = useState(hand.notes || '')
  const [tags, setTags] = useState((hand.tags || []).join(', '))
  const [saving, setSaving] = useState(false)
  const [copied, setCopied] = useState(false)

  const streets = parseRawHH(hand.raw)
  const level = extractLevel(hand.raw)

  async function save() {
    setSaving(true)
    try {
      const tagList = tags.split(',').map(t => t.trim()).filter(Boolean)
      await hands.update(hand.id, { notes, tags: tagList })
      onUpdate()
    } catch (e) { alert(e.message) }
    finally { setSaving(false) }
  }

  async function changeState(newState) {
    try { await hands.update(hand.id, { study_state: newState }); onUpdate() }
    catch (e) { alert(e.message) }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, backdropFilter: 'blur(4px)' }} onClick={onClose}>
      <div style={{ width: '92%', maxWidth: 800, maxHeight: '90vh', overflow: 'auto', background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12, padding: 28 }} onClick={e => e.stopPropagation()}>

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
                if (m || level) {
                  return <span style={{ fontSize: 11, color: '#4b5563', fontFamily: 'monospace', fontWeight: 600 }}>
                    {level || ''}{m ? ` · ${Math.round(m.sb)}/${Math.round(m.bb)}${m.ante ? `(${Math.round(m.ante)})` : ''}` : ''}
                  </span>
                }
                return null
              })()}
              <span style={{ fontSize: 11, color: '#4b5563' }}>{hand.site} &middot; {hand.played_at ? hand.played_at.slice(0, 10) : ''}</span>
            </div>
          </div>
          <button style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 18, padding: 4 }} onClick={onClose}>&#10005;</button>
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          {hand.raw && (
            <button onClick={() => { navigator.clipboard.writeText(hand.raw); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
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

        {/* Info Grid */}
        {(() => {
          const m = hand.all_players_actions?._meta || {}
          const blindsLabel = m.sb && m.bb ? `${Math.round(m.sb)}/${Math.round(m.bb)}${m.ante ? `(${Math.round(m.ante)})` : ''}` : ''
          const resultColor = hand.result > 0 ? '#22c55e' : hand.result < 0 ? '#ef4444' : '#64748b'
          return (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginBottom: 14 }}>
              {[
                { l: 'SALA', v: hand.site },
                { l: 'DATA', v: hand.played_at ? hand.played_at.slice(0, 10) : '—' },
                { l: 'RESULTADO', v: hand.result != null ? `${hand.result > 0 ? '+' : ''}${Number(hand.result).toFixed(1)} BB` : '—', c: resultColor },
                { l: 'POSIÇÃO', v: null, badge: hand.position },
                { l: 'TORNEIO', v: hand.stakes || '—' },
                { l: 'HAND ID', v: hand.hand_id || '—' },
                { l: 'BLINDS', v: blindsLabel || '—' },
                { l: 'LEVEL', v: level || (m.level != null ? `Lv ${m.level}` : '—') },
                { l: 'JOGADORES', v: Object.keys(hand.all_players_actions || {}).filter(k => k !== '_meta').length || '—' },
              ].map(({ l, v, c, badge }) => (
                <div key={l} style={{ background: '#0f1117', borderRadius: 6, padding: '8px 12px' }}>
                  <div style={{ fontSize: 10, color: '#64748b', fontWeight: 700, letterSpacing: 0.5, marginBottom: 3 }}>{l}</div>
                  {badge ? <PosBadge pos={badge} /> : <div style={{ fontSize: 13, color: c || '#f1f5f9', fontWeight: 700, wordBreak: 'break-all' }}>{v}</div>}
                </div>
              ))}
            </div>
          )
        })()}
        <div style={{ background: '#0f1117', borderRadius: 10, padding: '16px 20px', marginBottom: 20, display: 'flex', gap: 32, alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Hero &middot; <PosBadge pos={hand.position} /></div>
            <div style={{ display: 'flex', gap: 5 }}>
              {hand.hero_cards?.length > 0 ? hand.hero_cards.map((c, i) => <PokerCard key={i} card={c} size="lg" />) : <span style={{ color: '#4b5563', fontSize: 13 }}>Cartas não visíveis</span>}
            </div>
          </div>
          {hand.board?.length > 0 && (
            <div>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Board</div>
              <div style={{ display: 'flex', gap: 5 }}>{hand.board.slice(0, 5).map((c, i) => <PokerCard key={i} card={c} size="lg" />)}</div>
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
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>
                Mesa ({players.length} jogadores)
              </div>
              <div style={{ background: '#0f1117', borderRadius: 8, border: '1px solid #1e2130', overflow: 'hidden' }}>
                {players.map((p, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', padding: '6px 12px',
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

        {/* Tags */}
        {hand.tags?.length > 0 && (
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 16 }}>
            {hand.tags.map(t => <Tag key={t} t={t} />)}
          </div>
        )}

        {/* Parsed HH Actions */}
        {streets && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: '#94a3b8', fontWeight: 700, letterSpacing: 0.5, marginBottom: 10, textTransform: 'uppercase' }}>
              <span>Hand History</span>
              {(() => {
                const m = hand.all_players_actions?._meta
                return m ? <span style={{ fontFamily: 'monospace', color: '#94a3b8', fontWeight: 600, fontSize: 14 }}>
                  {m.sb && m.bb ? `${Math.round(m.sb)}/${Math.round(m.bb)}${m.ante ? `(${Math.round(m.ante)})` : ''}` : ''}
                  {m.level != null ? ` LV ${m.level}` : ''}
                </span> : null
              })()}
            </div>
            {(() => {
              const raw = hand.raw
              const meta = hand.all_players_actions?._meta
              const bb = meta?.bb || 1

              // Build stack tracker
              const stacks = {}
              if (hand.all_players_actions) {
                for (const [name, info] of Object.entries(hand.all_players_actions)) {
                  if (name === '_meta') continue
                  stacks[name] = { stack: info.stack || 0, invested: 0 }
                }
              }

              // Deduct antes/blinds
              if (raw) {
                const sbM = raw.match(/(.+?)(?::)?\s+posts\s+(?:the\s+)?small blind\s+([\d,]+)/i)
                if (sbM) { const n = sbM[1].trim(); for (const k of Object.keys(stacks)) { if (k === n || k.includes(n) || n.includes(k)) { stacks[k].stack -= parseFloat(sbM[2].replace(/,/g, '')); stacks[k].invested = parseFloat(sbM[2].replace(/,/g, '')); break } } }
                const bbM = raw.match(/(.+?)(?::)?\s+posts\s+(?:the\s+)?big blind\s+([\d,]+)/i)
                if (bbM) { const n = bbM[1].trim(); for (const k of Object.keys(stacks)) { if (k === n || k.includes(n) || n.includes(k)) { stacks[k].stack -= parseFloat(bbM[2].replace(/,/g, '')); stacks[k].invested = parseFloat(bbM[2].replace(/,/g, '')); break } } }
              }

              // Initial pot
              let initPot = 0
              if (raw) {
                const anteMs = raw.match(/posts\s+(?:the\s+)?ante\s+([\d,]+)/gi) || []
                for (const am of anteMs) { const n = am.match(/([\d,]+)/); if (n) initPot += parseFloat(n[0].replace(/,/g, '')) }
                const sbM = raw.match(/posts\s+(?:the\s+)?small blind\s+([\d,]+)/i)
                if (sbM) initPot += parseFloat(sbM[1].replace(/,/g, ''))
                const bbM = raw.match(/posts\s+(?:the\s+)?big blind\s+([\d,]+)/i)
                if (bbM) initPot += parseFloat(bbM[1].replace(/,/g, ''))
              }

              // Pot BEFORE each street
              let runPot = initPot
              const streetPots = {}
              for (const { key, actions } of streets) {
                streetPots[key] = runPot
                for (const a of actions) {
                  const callM = a.action.match(/calls ([\d,]+)/); const betM = a.action.match(/bets ([\d,]+)/)
                  const raiseToM = a.action.match(/raises [\d,]+ to ([\d,]+)/)
                  if (callM) runPot += parseFloat(callM[1].replace(/,/g, ''))
                  else if (raiseToM) runPot += parseFloat(raiseToM[1].replace(/,/g, ''))
                  else if (betM) runPot += parseFloat(betM[1].replace(/,/g, ''))
                }
              }

              return streets.map(({ key, actions }, si) => {
                const color = STREET_COLORS[key] || '#94a3b8'
                const isShowdown = key === 'showdown'
                const potBefore = streetPots[key] || 0
                const potBB = bb > 0 ? (potBefore / bb).toFixed(1) : '?'

                if (si > 0 && !isShowdown) {
                  for (const k of Object.keys(stacks)) stacks[k].invested = 0
                }

                return (
                  <div key={key} style={{ marginBottom: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 0.5, color, textTransform: 'uppercase', padding: '3px 10px', borderRadius: 4, background: `${color}15`, border: `1px solid ${color}30` }}>{STREET_LABELS[key]}</span>
                      {!isShowdown && potBefore > 0 && (
                        <span style={{ fontSize: 14, color: '#94a3b8', fontFamily: 'monospace', fontWeight: 700, marginLeft: 'auto', background: 'rgba(255,255,255,0.03)', padding: '3px 12px', borderRadius: 4 }}>
                          Pot: {Math.round(potBefore).toLocaleString()} ({potBB}bb)
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', background: isShowdown ? '#0d1020' : '#0f1117', borderRadius: 8, padding: isShowdown ? '8px 12px' : '4px 12px', border: `1px solid ${isShowdown ? '#2a2050' : '#1e2130'}` }}>
                      {actions.map((a, i) => {
                        const showCards = a.cards || []
                        const isShow = showCards.length > 0
                        const playerInfo = hand.all_players_actions?.[a.name]
                        const pos = playerInfo?.position
                        const bounty = playerInfo?.bounty || playerInfo?.bounty_pct
                        const showBounty = (key === 'preflop' || key === 'flop') && bounty != null

                        // Track stacks
                        const s = stacks[a.name]
                        let actionBBLabel = ''
                        if (s && !isShowdown) {
                          const callM2 = a.action.match(/calls ([\d,]+)/)
                          const betM2 = a.action.match(/bets ([\d,]+)/)
                          const raiseToM2 = a.action.match(/raises [\d,]+ to ([\d,]+)/)
                          const wonM = a.action.match(/collected ([\d,]+)/)
                          if (callM2) { const amt = parseFloat(callM2[1].replace(/,/g, '')); s.stack -= amt; s.invested += amt; actionBBLabel = ` (${(amt/bb).toFixed(1)}bb)` }
                          else if (raiseToM2) { const to = parseFloat(raiseToM2[1].replace(/,/g, '')); const add = to - s.invested; if (add > 0) s.stack -= add; s.invested = to; actionBBLabel = ` (${(to/bb).toFixed(1)}bb)` }
                          else if (betM2) { const amt = parseFloat(betM2[1].replace(/,/g, '')); s.stack -= amt; s.invested += amt; actionBBLabel = ` (${(amt/bb).toFixed(1)}bb)` }
                          else if (wonM) { actionBBLabel = ` (${(parseFloat(wonM[1].replace(/,/g,''))/bb).toFixed(1)}bb)` }
                        }
                        const currentBB = s ? (s.stack / bb).toFixed(1) : ''

                        // Action colors
                        let col = '#94a3b8', bg = 'rgba(148,163,184,0.06)'
                        if (/fold/i.test(a.action)) { col = '#e2e8f0'; bg = 'rgba(226,232,240,0.06)' }
                        else if (/check/i.test(a.action)) { col = '#64748b'; bg = 'rgba(100,116,139,0.06)' }
                        else if (/call/i.test(a.action)) { col = '#22c55e'; bg = 'rgba(34,197,94,0.08)' }
                        else if (/raise|bet/i.test(a.action)) { col = '#ef4444'; bg = 'rgba(239,68,68,0.08)' }
                        else if (/collect|win|won/i.test(a.action)) { col = '#22c55e'; bg = 'rgba(34,197,94,0.1)' }
                        if (/all-in/i.test(a.action)) { col = '#ef4444'; bg = 'rgba(239,68,68,0.12)' }

                        return (
                          <div key={i} style={{ display: 'flex', alignItems: 'center', padding: isShowdown ? '6px 0' : '5px 0', borderBottom: i < actions.length - 1 ? `1px solid ${isShowdown ? '#1e1840' : '#1a1d27'}` : 'none' }}>
                            <div style={{ width: 54, flexShrink: 0 }}>{pos && <PosBadge pos={pos} />}</div>
                            <div style={{ width: 140, flexShrink: 0 }}>
                              <span style={{ fontSize: 12, fontWeight: a.isHero ? 700 : 600, color: '#0a0c14', background: a.isHero ? '#a5b4fc' : '#fbbf24', padding: '2px 8px', borderRadius: 4, display: 'inline-block' }}>
                                {a.name}{a.isHero && <span style={{ fontSize: 9, fontWeight: 700, color: '#4338ca', marginLeft: 4 }}>HERO</span>}
                              </span>
                            </div>
                            {!isShowdown && (
                              <div style={{ width: 50, flexShrink: 0, textAlign: 'right', fontSize: 12, color: '#f1f5f9', fontFamily: 'monospace', fontWeight: 600 }}>{currentBB ? `${currentBB}bb` : ''}</div>
                            )}
                            {showBounty ? (
                              <div style={{ width: 50, flexShrink: 0, textAlign: 'right', fontSize: 11, paddingLeft: 4 }}>
                                <span style={{ color: '#f1f5f9', fontWeight: 700, padding: '1px 5px', borderRadius: 3, background: 'rgba(30,58,95,0.4)' }}>{typeof bounty === 'number' && bounty < 10 ? `${bounty}%` : `${bounty}€`}</span>
                              </div>
                            ) : <div style={{ width: 50, flexShrink: 0 }} />}
                            <div style={{ flex: 1, paddingLeft: 10, display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
                              {isShow ? (
                                <>
                                  <span style={{ fontSize: 11, color: '#8b5cf6', fontWeight: 600 }}>shows</span>
                                  <div style={{ display: 'flex', gap: 3 }}>{showCards.map((c, ci) => <PokerCard key={ci} card={c} size="md" />)}</div>
                                  {a.action.includes('(') && <span style={{ fontSize: 11, color: '#4b5563', fontStyle: 'italic' }}>{a.action.match(/\((.+)\)/)?.[1] || ''}</span>}
                                </>
                              ) : (
                                <span style={{ fontSize: 13, fontWeight: 700, color: col, padding: '3px 12px', borderRadius: 5, background: bg, border: `1px solid ${col}25` }}>{a.action}{actionBBLabel}</span>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )
              })
            })()}
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

        {/* Notes */}
        <div style={{ marginBottom: 14 }}>
          <label style={{ fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 6, color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.5 }}>Notas de Estudo</label>
          <textarea rows={3} style={{ width: '100%', fontSize: 13, background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '8px 12px', fontFamily: 'inherit', resize: 'vertical' }} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Adicionar notas..." />
        </div>

        {/* Tags edit */}
        <div style={{ marginBottom: 20 }}>
          <label style={{ fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 6, color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.5 }}>Tags (separadas por vírgula)</label>
          <input type="text" style={{ width: '100%', fontSize: 13, background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '8px 12px' }} value={tags} onChange={e => setTags(e.target.value)} placeholder="ICM PKO, nota++..." />
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', borderTop: '1px solid #2a2d3a', paddingTop: 16 }}>
          <button style={{ padding: '7px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: '#6366f1', color: '#fff', border: 'none', cursor: 'pointer', opacity: saving ? 0.6 : 1 }} disabled={saving} onClick={save}>{saving ? 'A guardar...' : 'Guardar'}</button>
          {hand.study_state !== 'review' && <button style={{ padding: '7px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: 'rgba(245,158,11,0.12)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)', cursor: 'pointer' }} onClick={() => changeState('review')}>Revisão</button>}
          {hand.study_state !== 'studying' && <button style={{ padding: '7px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: 'rgba(139,92,246,0.12)', color: '#8b5cf6', border: '1px solid rgba(139,92,246,0.3)', cursor: 'pointer' }} onClick={() => changeState('studying')}>A Estudar</button>}
          {hand.study_state !== 'resolved' && <button style={{ padding: '7px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: 'rgba(34,197,94,0.12)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.3)', cursor: 'pointer' }} onClick={() => changeState('resolved')}>Resolvida &#10003;</button>}
        </div>
      </div>
    </div>
  )
}

// ── Day Group (collapsible) ───────────────────────────────────────────────────

function TournamentSubGroup({ name, hands, onOpenDetail, onDeleteHand }) {
  const [open, setOpen] = useState(false)
  const wins = hands.filter(h => h.result != null && Number(h.result) > 0).length
  const losses = hands.filter(h => h.result != null && Number(h.result) < 0).length
  const totalBB = hands.reduce((a, h) => a + (Number(h.result) || 0), 0)

  return (
    <div style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
      <div onClick={() => setOpen(!open)} style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '7px 16px 7px 32px', cursor: 'pointer', userSelect: 'none',
      }}
        onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 10, color: '#6366f1', transform: open ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}>&#9654;</span>
          <span style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', maxWidth: 350, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
          <span style={{ fontSize: 11, color: '#4b5563' }}>{hands.length} {hands.length === 1 ? 'mão' : 'mãos'}</span>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', fontSize: 11 }}>
          <span style={{ color: '#22c55e' }}>{wins}W</span>
          <span style={{ color: '#ef4444' }}>{losses}L</span>
          <span style={{ color: totalBB >= 0 ? '#22c55e' : '#ef4444', fontWeight: 600, fontFamily: 'monospace' }}>
            {totalBB >= 0 ? '+' : ''}{totalBB.toFixed(1)} BB
          </span>
        </div>
      </div>
      {open && hands.map((h, idx) => (
        <HandRow
          key={h.id}
          hand={h}
          idx={idx}
          onClick={() => onOpenDetail(h.id)}
          onDelete={onDeleteHand}
        />
      ))}
    </div>
  )
}

function DayGroup({ dateKey, dateLabel, hands, wins, losses, totalBB, onOpenDetail, onDeleteHand }) {
  const [open, setOpen] = useState(false)

  // Sub-group by tournament (stakes field)
  const byTourney = {}
  for (const h of hands) {
    const key = h.stakes || 'Sem torneio'
    if (!byTourney[key]) byTourney[key] = []
    byTourney[key].push(h)
  }
  const tourneyKeys = Object.keys(byTourney).sort()

  return (
    <div style={{ marginBottom: 6, border: `1px solid ${open ? 'rgba(139,92,246,0.3)' : '#2a2d3a'}`, borderRadius: 10, overflow: 'hidden', transition: 'border-color 0.2s' }}>
      <div onClick={() => setOpen(!open)} style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 16px', background: open ? 'rgba(139,92,246,0.06)' : '#1a1d27',
        cursor: 'pointer', userSelect: 'none',
      }}
        onMouseEnter={e => { if (!open) e.currentTarget.style.background = '#1e2130' }}
        onMouseLeave={e => { if (!open) e.currentTarget.style.background = '#1a1d27' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ display: 'inline-block', fontSize: 11, color: '#8b5cf6', transform: open ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>&#9654;</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0' }}>{dateLabel}</span>
          <span style={{ fontSize: 12, color: '#6366f1' }}>{tourneyKeys.length} torneio{tourneyKeys.length !== 1 ? 's' : ''}</span>
          <span style={{ fontSize: 12, color: '#64748b' }}>{hands.length} {hands.length === 1 ? 'mão' : 'mãos'}</span>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', fontSize: 11 }}>
          <span style={{ color: '#22c55e' }}>{wins}W</span>
          <span style={{ color: '#ef4444' }}>{losses}L</span>
          <span style={{ color: totalBB >= 0 ? '#22c55e' : '#ef4444', fontWeight: 600, fontFamily: 'monospace' }}>
            {totalBB >= 0 ? '+' : ''}{totalBB.toFixed(1)} BB
          </span>
        </div>
      </div>
      {open && (
        <div>
          {tourneyKeys.map(tk => (
            <TournamentSubGroup
              key={tk}
              name={tk}
              hands={byTourney[tk]}
              onOpenDetail={onOpenDetail}
              onDeleteHand={onDeleteHand}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main Page ────────────────────────────────────────────────────────────────

// ── Import Panel with date/nota filter ───────────────────────────────────────

function HM3ImportPanel({ onImported }) {
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState(null)
  const [daysBack, setDaysBack] = useState('7')
  const [notaOnly, setNotaOnly] = useState(true)
  const [reparsing, setReparsing] = useState(false)
  const [reparseResult, setReparseResult] = useState(null)

  const handleImport = async (files) => {
    if (!files || files.length === 0) return
    setImporting(true)
    setImportResult(null)
    try {
      const results = []
      for (const file of files) {
        const r = await hm3.import(file, { daysBack: daysBack || null, notaOnly })
        results.push(r)
      }
      const total = results.reduce((a, r) => ({
        inserted: a.inserted + (r.inserted || 0),
        skipped: a.skipped + (r.skipped_duplicates || 0),
        skippedDate: a.skippedDate + (r.skipped_date_filter || 0),
        skippedNota: a.skippedNota + (r.skipped_nota_filter || 0),
        villains: a.villains + (r.villains_created || 0),
      }), { inserted: 0, skipped: 0, skippedDate: 0, skippedNota: 0, villains: 0 })
      setImportResult(total)
      if (total.inserted > 0) onImported?.()
    } catch (e) {
      setImportResult({ error: e.message })
    } finally {
      setImporting(false)
    }
  }

  return (
    <div style={{
      background: 'rgba(139,92,246,0.04)', border: '1px solid rgba(139,92,246,0.15)',
      borderRadius: 8, padding: '14px 20px', marginBottom: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: '#a78bfa' }}>Importar CSV</span>
        <select value={daysBack} onChange={e => setDaysBack(e.target.value)} style={{
          background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6,
          color: '#e2e8f0', padding: '5px 10px', fontSize: 12,
        }}>
          <option value="">Todas as datas</option>
          <option value="3">Últimos 3 dias</option>
          <option value="7">Últimos 7 dias</option>
          <option value="14">Últimos 14 dias</option>
          <option value="30">Últimos 30 dias</option>
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#94a3b8', cursor: 'pointer' }}>
          <input type="checkbox" checked={notaOnly} onChange={e => setNotaOnly(e.target.checked)}
            style={{ accentColor: '#8b5cf6' }} />
          Só com tag nota
        </label>
        <label style={{
          padding: '6px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600,
          background: importing ? 'rgba(139,92,246,0.1)' : 'rgba(139,92,246,0.15)',
          color: '#a78bfa', border: '1px solid rgba(139,92,246,0.3)', cursor: 'pointer',
        }}>
          {importing ? 'A importar...' : '📂 Escolher CSV'}
          <input type="file" accept=".csv" hidden onChange={e => handleImport(e.target.files)} />
        </label>
        <button onClick={async () => {
          setReparsing(true); setReparseResult(null)
          try { const r = await hm3.reParse(); setReparseResult(r); onImported?.() }
          catch (e) { setReparseResult({ error: e.message }) }
          finally { setReparsing(false) }
        }} style={{ padding: '6px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: 'rgba(245,158,11,0.1)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.25)', cursor: 'pointer' }}>
          {reparsing ? 'A re-parsear...' : '🔄 Re-parse'}
        </button>
      </div>
      {importResult && !importResult.error && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#94a3b8', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ color: '#22c55e' }}>{importResult.inserted} importadas</span>
          {importResult.skipped > 0 && <span style={{ color: '#f59e0b' }}>{importResult.skipped} duplicadas</span>}
          {importResult.skippedDate > 0 && <span style={{ color: '#64748b' }}>{importResult.skippedDate} fora do prazo</span>}
          {importResult.skippedNota > 0 && <span style={{ color: '#64748b' }}>{importResult.skippedNota} sem nota</span>}
          {importResult.villains > 0 && <span style={{ color: '#8b5cf6' }}>{importResult.villains} vilões</span>}
        </div>
      )}
      {importResult?.error && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#ef4444' }}>{importResult.error}</div>
      )}
      {reparseResult && !reparseResult.error && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#f59e0b' }}>Re-parse: {reparseResult.updated || 0} actualizadas de {reparseResult.processed || 0}</div>
      )}
      {reparseResult?.error && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#ef4444' }}>Re-parse erro: {reparseResult.error}</div>
      )}
    </div>
  )
}


export default function HM3Page() {
  const [data, setData] = useState({ data: [], total: 0, pages: 1 })
  const [weekOffset, setWeekOffset] = useState(0)
  const [totalWeeks, setTotalWeeks] = useState(1)
  const [filters, setFilters] = useState({ study_state: '', site: '', search: '', date_from: '', tag: '', result_min: '', result_max: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [stats, setStats] = useState(null)

  const HM3_SITES = ['Winamax', 'PokerStars', 'WPN']

  // Calculate Monday-Sunday range for a given week offset (0 = current week)
  const getWeekRange = (offset) => {
    const now = new Date()
    const day = now.getDay()
    const diffToMonday = day === 0 ? 6 : day - 1
    const monday = new Date(now)
    monday.setDate(now.getDate() - diffToMonday - (offset * 7))
    monday.setHours(0, 0, 0, 0)
    const sunday = new Date(monday)
    sunday.setDate(monday.getDate() + 6)
    sunday.setHours(23, 59, 59, 999)
    return {
      from: monday.toISOString().slice(0, 10),
      to: sunday.toISOString().slice(0, 10),
      label: `${monday.toLocaleDateString('pt-PT', { day: '2-digit', month: 'short' })} — ${sunday.toLocaleDateString('pt-PT', { day: '2-digit', month: 'short', year: 'numeric' })}`
    }
  }

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    const week = getWeekRange(weekOffset)
    const params = { ...filters, page: 1, page_size: 2000, date_from: week.from, date_to: week.to }
    if (!params.site) delete params.site
    if (!params.tag) delete params.tag
    if (!params.search) delete params.search
    if (!params.study_state) delete params.study_state
    if (!params.result_min) delete params.result_min
    if (!params.result_max) delete params.result_max
    hands.list(params)
      .then(d => {
        const filtered = (d.data || []).filter(h => HM3_SITES.includes(h.site))
        setData({ ...d, data: filtered })
        // Estimate total weeks from total hands
        const tw = Math.max(1, Math.ceil((d.total || 0) / Math.max(1, filtered.length || 50)))
        setTotalWeeks(Math.min(tw, 52))
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [weekOffset, filters])

  const loadStats = useCallback(() => {
    hm3.stats().then(setStats).catch(() => {})
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => { loadStats() }, [loadStats])

  function set(key, val) {
    setFilters(f => ({ ...f, [key]: val }))
    setWeekOffset(0)
  }

  async function openDetail(id) {
    try { setSelected(await hands.get(id)) }
    catch (e) { setError(e.message) }
  }

  async function deleteHand(id) {
    if (!confirm('Apagar esta mão?')) return
    try { await hands.delete(id); load(); loadStats() }
    catch (e) { setError(e.message) }
  }

  const rows = data.data || []
  const totalBysite = stats?.by_site || []

  return (
    <>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: -0.5 }}>HM3</div>
        <div style={{ color: '#64748b', fontSize: 13, marginTop: 3 }}>Mãos importadas do Holdem Manager 3</div>
      </div>

      {/* Stats — clickable to filter */}
      {totalBysite.length > 0 && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          {totalBysite.map(s => (
            <div key={s.site} onClick={() => set('site', filters.site === s.site ? '' : s.site)} style={{
              background: filters.site === s.site ? 'rgba(139,92,246,0.12)' : '#1a1d27',
              border: `1px solid ${filters.site === s.site ? 'rgba(139,92,246,0.4)' : '#2a2d3a'}`,
              borderRadius: 8, padding: '8px 16px', cursor: 'pointer', transition: 'all 0.15s',
            }}>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 4 }}>{s.site}</div>
              <div style={{ display: 'flex', gap: 12, fontSize: 12 }}>
                <span style={{ fontWeight: 700, color: '#e2e8f0' }}>{s.total}</span>
                <span style={{ color: '#3b82f6' }}>{s.new} novas</span>
                {s.review > 0 && <span style={{ color: '#f59e0b' }}>{s.review} rev</span>}
                {s.studying > 0 && <span style={{ color: '#8b5cf6' }}>{s.studying} est</span>}
                {s.resolved > 0 && <span style={{ color: '#22c55e' }}>{s.resolved} res</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Import with date/nota filter */}
      <HM3ImportPanel onImported={() => { load(); loadStats() }} />

      {/* Time filters */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
        {[
          { label: 'Todas', value: '' },
          { label: 'Hoje', value: (() => { const d = new Date(); d.setHours(0,0,0,0); return d.toISOString().slice(0,10) })() },
          { label: '3 dias', value: (() => { const d = new Date(); d.setDate(d.getDate()-3); return d.toISOString().slice(0,10) })() },
          { label: 'Semana', value: (() => { const d = new Date(); d.setDate(d.getDate()-7); return d.toISOString().slice(0,10) })() },
          { label: 'Mês', value: (() => { const d = new Date(); d.setDate(d.getDate()-30); return d.toISOString().slice(0,10) })() },
        ].map(({ label, value }) => (
          <button key={label} onClick={() => set('date_from', value)} style={{
            padding: '5px 14px', borderRadius: 20, fontSize: 12, fontWeight: 500, border: '1px solid',
            borderColor: filters.date_from === value ? '#8b5cf6' : '#2a2d3a',
            background: filters.date_from === value ? 'rgba(139,92,246,0.15)' : 'transparent',
            color: filters.date_from === value ? '#a78bfa' : '#64748b',
            cursor: 'pointer',
          }}>{label}</button>
        ))}
      </div>

      {/* Tag filter panels */}
      {(() => {
        // Compute tag counts from loaded data
        const tagCounts = {}
        for (const h of rows) {
          for (const t of (h.tags || [])) {
            tagCounts[t] = (tagCounts[t] || 0) + 1
          }
        }
        const topTags = Object.entries(tagCounts).sort((a, b) => b[1] - a[1]).slice(0, 12)
        if (topTags.length === 0) return null

        const tagColors = ['#8b5cf6', '#6366f1', '#f59e0b', '#22c55e', '#06b6d4', '#ec4899', '#f97316', '#ef4444', '#a78bfa', '#34d399', '#fb923c', '#64748b']

        return (
          <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
            {topTags.map(([tag, cnt], i) => {
              const active = filters.tag === tag
              const color = tagColors[i % tagColors.length]
              return (
                <button key={tag} onClick={() => set('tag', active ? '' : tag)} style={{
                  padding: '4px 12px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                  border: `1px solid ${active ? color : '#2a2d3a'}`,
                  background: active ? `${color}20` : '#1a1d27',
                  color: active ? color : '#64748b',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}>
                  #{tag} <span style={{ fontSize: 11, opacity: 0.7 }}>({cnt})</span>
                </button>
              )
            })}
          </div>
        )
      })()}

      {/* Filters */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20, background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 10, padding: '12px 16px' }}>
        <select value={filters.study_state} onChange={e => set('study_state', e.target.value)} style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 10px', fontSize: 12 }}>
          {STATES.map(s => <option key={s.v} value={s.v}>{s.l}</option>)}
        </select>
        <select value={filters.site} onChange={e => set('site', e.target.value)} style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 10px', fontSize: 12 }}>
          <option value="">Todas as salas</option>
          <option value="Winamax">Winamax</option>
          <option value="PokerStars">PokerStars</option>
          <option value="WPN">WPN</option>
        </select>
        <input type="text" placeholder="Pesquisar torneio, tag..." value={filters.search} onChange={e => set('search', e.target.value)} style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 12px', fontSize: 12, flex: 1, minWidth: 140 }} />
        <input type="number" placeholder="BB min" value={filters.result_min} onChange={e => set('result_min', e.target.value)} style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 8px', fontSize: 12, width: 65 }} />
        <input type="number" placeholder="BB max" value={filters.result_max} onChange={e => set('result_max', e.target.value)} style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 8px', fontSize: 12, width: 65 }} />
        {(filters.study_state || filters.site || filters.search || filters.date_from || filters.tag || filters.result_min || filters.result_max) && (
          <button onClick={() => { setFilters({ study_state: '', site: '', search: '', date_from: '', tag: '', result_min: '', result_max: '' }); setWeekOffset(0) }} style={{ padding: '6px 12px', borderRadius: 6, fontSize: 12, background: 'transparent', color: '#64748b', border: '1px solid #2a2d3a', cursor: 'pointer' }}>&#10005; Limpar</button>
        )}
      </div>

      {error && <div style={{ color: '#ef4444', fontSize: 13, marginBottom: 12, padding: '8px 12px', background: 'rgba(239,68,68,0.08)', borderRadius: 6, border: '1px solid rgba(239,68,68,0.2)' }}>{error}</div>}

      {loading && <div style={{ textAlign: 'center', padding: '48px 0', color: '#64748b' }}>A carregar...</div>}

      {!loading && rows.length === 0 && (
        <div style={{ textAlign: 'center', padding: '64px 0', color: '#64748b' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>&#128202;</div>
          <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 6 }}>Sem mãos HM3</div>
          <div style={{ fontSize: 13 }}>Importa mãos na Inbox via "Importar HM3"</div>
        </div>
      )}

      {/* Hands grouped by day */}
      {!loading && rows.length > 0 && (() => {
        // Group by date
        const byDay = {}
        for (const h of rows) {
          const dk = h.played_at ? h.played_at.slice(0, 10) : 'sem-data'
          if (!byDay[dk]) byDay[dk] = []
          byDay[dk].push(h)
        }
        const sortedDays = Object.keys(byDay).sort((a, b) => b.localeCompare(a))
        const weekdays = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']

        return (
          <div style={{ marginBottom: 24 }}>
            {sortedDays.map(dk => {
              const dayHands = byDay[dk]
              const d = new Date(dk + 'T12:00:00')
              const label = dk === 'sem-data' ? 'Sem data' : `${weekdays[d.getDay()]}, ${d.toLocaleDateString('pt-PT', { day: '2-digit', month: 'long', year: 'numeric' })}`
              const wins = dayHands.filter(h => h.result != null && Number(h.result) > 0).length
              const losses = dayHands.filter(h => h.result != null && Number(h.result) < 0).length
              const totalBB = dayHands.reduce((a, h) => a + (Number(h.result) || 0), 0)

              return (
                <DayGroup
                  key={dk}
                  dateKey={dk}
                  dateLabel={label}
                  hands={dayHands}
                  wins={wins}
                  losses={losses}
                  totalBB={totalBB}
                  onOpenDetail={openDetail}
                  onDeleteHand={deleteHand}
                />
              )
            })}
          </div>
        )
      })()}

      {/* Pagination */}
      {data.pages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center', marginBottom: 24 }}>
          <button onClick={() => setWeekOffset(w => w + 1)} style={{ padding: '6px 14px', borderRadius: 6, fontSize: 12, background: '#1a1d27', color: '#e2e8f0', border: '1px solid #2a2d3a', cursor: 'pointer' }}>&#8592;</button>
          <span style={{ color: '#64748b', fontSize: 12 }}>{getWeekRange(weekOffset).label}</span>
          <button disabled={weekOffset <= 0} onClick={() => setWeekOffset(w => w - 1)} style={{ padding: '6px 14px', borderRadius: 6, fontSize: 12, background: weekOffset <= 0 ? 'transparent' : '#1a1d27', color: weekOffset <= 0 ? '#374151' : '#e2e8f0', border: '1px solid #2a2d3a', cursor: weekOffset <= 0 ? 'not-allowed' : 'pointer' }}>&#8594;</button>
        </div>
      )}

      {/* Detail Modal */}
      {selected && (
        <HandDetailModal
          hand={selected}
          onClose={() => setSelected(null)}
          onUpdate={() => { setSelected(null); load(); loadStats() }}
        />
      )}
    </>
  )
}
