import { useEffect, useState, useCallback } from 'react'
import { hands, hm3 } from '../api/client'

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
  if (!card || card.length < 2) return <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 24, height: 34, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 3, fontSize: 10, color: '#4b5563' }}>?</span>
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
  return <span style={{ display: 'inline-block', padding: '2px 9px', borderRadius: 999, fontSize: 10, fontWeight: 600, letterSpacing: 0.3, color: meta.color, background: meta.bg }}>{meta.label}</span>
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ color: '#4b5563' }}>&mdash;</span>
  const colors = { BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa', SB: '#f59e0b', BB: '#ef4444', UTG: '#22c55e', UTG1: '#16a34a', UTG2: '#15803d', MP: '#06b6d4', MP1: '#0891b2' }
  const c = colors[pos] || '#64748b'
  return <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700, letterSpacing: 0.5, color: c, background: `${c}20`, border: `1px solid ${c}40` }}>{pos}</span>
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
  return <span style={{ display: 'inline-block', padding: '1px 7px', borderRadius: 999, fontSize: 10, fontWeight: 600, marginRight: 3, color: c, background: `${c}18`, border: `1px solid ${c}30` }}>#{t}</span>
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
  return <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600, fontFamily: 'monospace', color: s.color, background: s.bg, border: `1px solid ${s.color}25`, whiteSpace: 'nowrap' }}>{text}</span>
}

// ── HH Parser ────────────────────────────────────────────────────────────────

function parseRawHH(raw) {
  if (!raw) return null
  const heroNames = ['schadenfreud', 'thinvalium', 'sapz', 'misterpoker1973', 'cringemeariver']
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

        {/* Cards + Board */}
        <div style={{ background: '#0f1117', borderRadius: 10, padding: '16px 20px', marginBottom: 20, display: 'flex', gap: 32, alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Hero &middot; <PosBadge pos={hand.position} /></div>
            <div style={{ display: 'flex', gap: 5 }}>
              {hand.hero_cards?.length > 0 ? hand.hero_cards.map((c, i) => <PokerCard key={i} card={c} size="lg" />) : <span style={{ color: '#4b5563', fontSize: 13 }}>Cartas não visíveis</span>}
            </div>
          </div>
          {hand.board?.length > 0 && (
            <div>
              <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Board</div>
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
                    display: 'flex', alignItems: 'center', gap: 10, padding: '5px 12px',
                    background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)',
                    borderBottom: i < players.length - 1 ? '1px solid #1a1d27' : 'none',
                  }}>
                    <div style={{ minWidth: 40 }}><PosBadge pos={p.position} /></div>
                    <span style={{ fontSize: 12, minWidth: 110, color: p.is_hero ? '#818cf8' : '#94a3b8', fontWeight: p.is_hero ? 600 : 400 }}>
                      {p.name}{p.is_hero && <span style={{ fontSize: 9, color: '#6366f1', marginLeft: 4 }}>(HERO)</span>}
                    </span>
                    <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace', minWidth: 70 }}>
                      {p.stack ? Number(p.stack).toLocaleString() : '—'}
                    </span>
                    <span style={{ fontSize: 10, color: '#4b5563', fontFamily: 'monospace' }}>
                      {p.stack_bb ? `${p.stack_bb} BB` : ''}
                    </span>
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
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 10, textTransform: 'uppercase' }}>
              <span>Hand History</span>
              {(() => {
                const m = hand.all_players_actions?._meta
                return m ? <span style={{ fontFamily: 'monospace', color: '#4b5563', fontWeight: 600, fontSize: 10 }}>
                  {m.sb && m.bb ? `${Math.round(m.sb)}/${Math.round(m.bb)}${m.ante ? `(${Math.round(m.ante)})` : ''}` : ''}
                </span> : null
              })()}
            </div>
            {streets.map(({ key, actions }) => {
              const color = STREET_COLORS[key] || '#94a3b8'
              const isShowdown = key === 'showdown'
              return (
                <div key={key} style={{ marginBottom: 10 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 0.5, color, textTransform: 'uppercase', padding: '2px 8px', borderRadius: 4, background: `${color}15`, border: `1px solid ${color}30` }}>{STREET_LABELS[key]}</span>
                  <div style={{ display: 'flex', flexDirection: 'column', background: isShowdown ? '#0d1020' : '#0f1117', borderRadius: 8, padding: isShowdown ? '8px 12px' : '4px 12px', border: `1px solid ${isShowdown ? '#2a2050' : '#1e2130'}`, marginTop: 6 }}>
                    {actions.map((a, i) => {
                      const showCards = a.cards || []
                      const isShow = showCards.length > 0
                      const playerInfo = hand.all_players_actions?.[a.name]
                      const pos = playerInfo?.position
                      return (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: isShowdown ? '6px 0' : '3px 0', borderBottom: i < actions.length - 1 ? `1px solid ${isShowdown ? '#1e1840' : '#1a1d27'}` : 'none' }}>
                          {pos && <PosBadge pos={pos} />}
                          <span style={{ fontSize: 11, color: a.isHero ? '#818cf8' : '#94a3b8', fontWeight: a.isHero ? 600 : 400, minWidth: 100 }}>
                            {a.name}{a.isHero && <span style={{ fontSize: 9, color: '#6366f1', marginLeft: 4 }}>(HERO)</span>}
                          </span>
                          {playerInfo?.stack_bb && !isShowdown && (
                            <span style={{ fontSize: 9, color: '#374151', fontFamily: 'monospace', minWidth: 40 }}>{playerInfo.stack_bb}bb</span>
                          )}
                          <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
                            {isShow ? (
                              <>
                                <span style={{ fontSize: 10, color: '#8b5cf6', fontWeight: 600 }}>shows</span>
                                <div style={{ display: 'flex', gap: 3 }}>
                                  {showCards.map((c, ci) => <PokerCard key={ci} card={c} size="md" />)}
                                </div>
                                {a.action.includes('(') && <span style={{ fontSize: 10, color: '#4b5563', fontStyle: 'italic' }}>{a.action.match(/\((.+)\)/)?.[1] || ''}</span>}
                              </>
                            ) : (
                              <ActionBadge text={a.action} />
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
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

function HM3HandRow({ hand, onClick, onDelete, idx }) {
  const level = extractLevel(hand.raw)
  const meta = hand.all_players_actions?._meta
  const blindsLabel = meta ? `${Math.round(meta.sb)}/${Math.round(meta.bb)}` : null
  const zebra = idx % 2 === 0 ? '#1a1d27' : '#1e2130'
  const siteShort = hand.site === 'Winamax' ? 'WN' : hand.site === 'PokerStars' ? 'PS' : 'WPN'

  return (
    <div onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 8, padding: '7px 12px',
      background: zebra, borderBottom: '1px solid rgba(255,255,255,0.03)',
      cursor: 'pointer', transition: 'background 0.1s',
    }}
      onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.06)'}
      onMouseLeave={e => e.currentTarget.style.background = zebra}
    >
      <div style={{ minWidth: 48, flexShrink: 0 }}><StateBadge state={hand.study_state} /></div>
      <div style={{ display: 'flex', gap: 2, minWidth: 50, flexShrink: 0 }}>
        {hand.hero_cards?.length > 0 ? hand.hero_cards.map((c, i) => <PokerCard key={i} card={c} size="sm" />) : <span style={{ color: '#374151', fontSize: 11 }}>&mdash;</span>}
      </div>
      <div style={{ minWidth: 36, flexShrink: 0 }}><PosBadge pos={hand.position} /></div>
      <div style={{ minWidth: 60, flexShrink: 0 }}><ResultBadge result={hand.result} /></div>
      <div style={{ minWidth: 100, maxWidth: 180, fontSize: 10, color: '#64748b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flexShrink: 1 }}>{hand.stakes || ''}</div>
      <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
        {hand.board?.length > 0 ? hand.board.slice(0, 5).map((c, i) => <PokerCard key={i} card={c} size="sm" />) : <span style={{ color: '#374151', fontSize: 10 }}>&mdash;</span>}
      </div>
      <div style={{ minWidth: 55, flexShrink: 0, fontSize: 9, color: '#4b5563', fontFamily: 'monospace', fontWeight: 600 }}>
        {level || ''}{blindsLabel ? ` ${blindsLabel}` : ''}
      </div>
      <div style={{ minWidth: 22, flexShrink: 0, fontSize: 9, color: '#4b5563' }}>{siteShort}</div>
      <div style={{ minWidth: 32, flexShrink: 0, fontSize: 9, color: '#374151', fontFamily: 'monospace' }}>
        {hand.played_at ? hand.played_at.slice(11, 16) : ''}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2, flex: 1, minWidth: 0 }}>
        {hand.tags?.slice(0, 3).map(t => <Tag key={t} t={t} />)}
      </div>
      <button style={{ background: 'transparent', border: 'none', color: '#374151', cursor: 'pointer', fontSize: 11, padding: '0 3px', flexShrink: 0 }}
        onClick={e => { e.stopPropagation(); onDelete(hand.id) }}
        onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
        onMouseLeave={e => e.currentTarget.style.color = '#374151'}>&#10005;</button>
    </div>
  )
}

function DayGroup({ dateKey, dateLabel, hands, wins, losses, totalBB, onOpenDetail, onDeleteHand }) {
  const [open, setOpen] = useState(false)

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
          <span style={{ display: 'inline-block', fontSize: 10, color: '#8b5cf6', transform: open ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>&#9654;</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0' }}>{dateLabel}</span>
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
          {hands.map((h, idx) => (
            <HM3HandRow key={h.id} hand={h} idx={idx} onClick={() => onOpenDetail(h.id)} onDelete={onDeleteHand} />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function HM3Page() {
  const [data, setData] = useState({ data: [], total: 0, pages: 1 })
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ study_state: '', site: '', search: '', date_from: '', tag: '', result_min: '', result_max: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [stats, setStats] = useState(null)

  const HM3_SITES = ['Winamax', 'PokerStars', 'WPN']

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    const params = { ...filters, page, page_size: 200 }
    if (!params.site) delete params.site
    if (!params.date_from) delete params.date_from
    if (!params.tag) delete params.tag
    if (!params.search) delete params.search
    if (!params.study_state) delete params.study_state
    if (!params.result_min) delete params.result_min
    if (!params.result_max) delete params.result_max
    hands.list(params)
      .then(d => {
        // Filter to HM3 sites only
        const filtered = (d.data || []).filter(h => HM3_SITES.includes(h.site))
        setData({ ...d, data: filtered })
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [page, filters])

  const loadStats = useCallback(() => {
    hm3.stats().then(setStats).catch(() => {})
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => { loadStats() }, [loadStats])

  function set(key, val) {
    setFilters(f => ({ ...f, [key]: val }))
    setPage(1)
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
              <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 4 }}>{s.site}</div>
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
                  #{tag} <span style={{ fontSize: 10, opacity: 0.7 }}>({cnt})</span>
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
          <button onClick={() => { setFilters({ study_state: '', site: '', search: '', date_from: '', tag: '', result_min: '', result_max: '' }); setPage(1) }} style={{ padding: '6px 12px', borderRadius: 6, fontSize: 12, background: 'transparent', color: '#64748b', border: '1px solid #2a2d3a', cursor: 'pointer' }}>&#10005; Limpar</button>
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
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} style={{ padding: '6px 14px', borderRadius: 6, fontSize: 12, background: page <= 1 ? 'transparent' : '#1a1d27', color: page <= 1 ? '#374151' : '#e2e8f0', border: '1px solid #2a2d3a', cursor: page <= 1 ? 'not-allowed' : 'pointer' }}>&#8592;</button>
          <span style={{ color: '#64748b', fontSize: 12 }}>Pág. {page} / {data.pages}</span>
          <button disabled={page >= data.pages} onClick={() => setPage(p => p + 1)} style={{ padding: '6px 14px', borderRadius: 6, fontSize: 12, background: page >= data.pages ? 'transparent' : '#1a1d27', color: page >= data.pages ? '#374151' : '#e2e8f0', border: '1px solid #2a2d3a', cursor: page >= data.pages ? 'not-allowed' : 'pointer' }}>&#8594;</button>
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
