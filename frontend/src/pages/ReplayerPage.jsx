import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { hands as handsApi, equity } from '../api/client'

const SUIT_COLORS = { h: '#ef4444', d: '#3b82f6', c: '#22c55e', s: '#e2e8f0' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }
const SUIT_BG = { h: '#7f1d1d', d: '#1e3a5f', c: '#14532d', s: '#1e293b' }
const STREET_COLORS = { preflop: '#6366f1', flop: '#22c55e', turn: '#f59e0b', river: '#ef4444', showdown: '#8b5cf6' }
const HERO_NAMES = new Set(['hero','schadenfreud','thinvalium','sapz','misterpoker1973','cringemeariver','flightrisk','karluz','koumpounophobia','lauro dermio'])
const SEAT_ORDER = ['UTG','UTG1','UTG2','MP','MP1','HJ','CO','BTN','SB','BB']

// Positions pulled INWARD so nothing clips
const POSITIONS_9 = [
  { x: 50, y: 88 }, { x: 14, y: 74 }, { x: 8, y: 42 }, { x: 14, y: 12 },
  { x: 36, y: 4 }, { x: 64, y: 4 }, { x: 86, y: 12 }, { x: 92, y: 42 }, { x: 86, y: 74 },
]
// Chip positions — between player and center
const CHIP_OFFSETS_9 = [
  { x: 50, y: 72 }, { x: 24, y: 64 }, { x: 20, y: 42 }, { x: 24, y: 22 },
  { x: 40, y: 16 }, { x: 60, y: 16 }, { x: 76, y: 22 }, { x: 80, y: 42 }, { x: 76, y: 64 },
]

function getSlots(n) {
  if (n <= 2) return [0, 4]
  if (n <= 3) return [0, 3, 6]
  if (n <= 4) return [0, 2, 4, 7]
  if (n <= 5) return [0, 1, 3, 6, 8]
  if (n <= 6) return [0, 1, 3, 5, 7, 8]
  if (n <= 7) return [0, 1, 2, 4, 5, 7, 8]
  if (n <= 8) return [0, 1, 2, 3, 5, 6, 7, 8]
  return [0, 1, 2, 3, 4, 5, 6, 7, 8]
}

function RCard({ card, faceDown, size = 'md' }) {
  const w = size === 'lg' ? 44 : size === 'md' ? 34 : 26
  const h = size === 'lg' ? 62 : size === 'md' ? 48 : 36
  const fs = size === 'lg' ? 15 : size === 'md' ? 12 : 10
  if (faceDown || !card || card.length < 2) return <div style={{ width: w, height: h, borderRadius: 4, background: 'linear-gradient(135deg,#1e40af,#7c3aed,#1e40af)', border: '1.5px solid rgba(255,255,255,0.2)', boxShadow: '0 2px 6px rgba(0,0,0,0.4)' }} />
  const rank = card.slice(0, -1).toUpperCase(), suit = card.slice(-1).toLowerCase()
  return <div style={{ width: w, height: h, borderRadius: 4, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: SUIT_BG[suit] || '#1e293b', border: `1.5px solid ${SUIT_COLORS[suit]}40`, boxShadow: '0 2px 6px rgba(0,0,0,0.4)', fontFamily: "'Fira Code',monospace", fontWeight: 700, fontSize: fs, color: '#fff', lineHeight: 1, userSelect: 'none' }}><span>{rank}</span><span style={{ fontSize: fs * 0.75, color: SUIT_COLORS[suit] }}>{SUIT_SYMBOLS[suit]}</span></div>
}

function parseHH(raw, apa) {
  if (!raw) return { steps: [], heroIdx: -1 }
  const meta = apa?._meta || {}
  const bb = meta.bb || 1
  const players = Object.entries(apa || {}).filter(([k]) => k !== '_meta')
    .map(([name, info]) => ({ name, ...info }))
    .sort((a, b) => (SEAT_ORDER.indexOf(a.position) === -1 ? 99 : SEAT_ORDER.indexOf(a.position)) - (SEAT_ORDER.indexOf(b.position) === -1 ? 99 : SEAT_ORDER.indexOf(b.position)))
  const heroIdx = players.findIndex(p => p.is_hero || HERO_NAMES.has(p.name.toLowerCase()))
  const pState = players.map(p => ({ name: p.name, position: p.position, stack: p.stack || 0, stackBB: p.stack_bb || 0, bounty: p.bounty, isHero: p.is_hero || HERO_NAMES.has(p.name.toLowerCase()), cards: [], folded: false, currentBet: 0 }))
  const dm = raw.match(/Dealt to (\S+) \[(.+?)\]/)
  if (dm && heroIdx >= 0) pState[heroIdx].cards = dm[2].split(' ')

  const isW = raw.includes('*** PRE-FLOP ***')
  const pfm = isW ? '*** PRE-FLOP ***' : '*** HOLE CARDS ***'
  const bc = []
  const fm = raw.match(/\*\*\* FLOP \*\*\* \[(.+?)\]/); if (fm) bc.push(...fm[1].split(' '))
  const tmW = raw.match(/\*\*\* TURN \*\*\* \[.+?\]\s*\[(.+?)\]/); if (tmW) bc.push(...tmW[1].split(' '))
  const rmW = raw.match(/\*\*\* RIVER \*\*\* \[.+?\]\s*\[(.+?)\]/); if (rmW) bc.push(...rmW[1].split(' '))

  let pot = 0
  const antes = raw.match(/posts the ante ([\d,]+)/g) || []
  for (const a of antes) { const n = a.match(/[\d,]+/); if (n) pot += parseFloat(n[0].replace(/,/g, '')) }
  const sbM = raw.match(/posts small blind ([\d,]+)/); if (sbM) pot += parseFloat(sbM[1].replace(/,/g, ''))
  const bbM = raw.match(/posts big blind ([\d,]+)/); if (bbM) pot += parseFloat(bbM[1].replace(/,/g, ''))

  const steps = [{ street: 'preflop', label: 'Pre-Flop', action: 'Blinds posted', actor: null, actorIdx: -1, isHero: false, pot, potBB: +(pot/bb).toFixed(1), board: [], ps: pState.map(p => ({...p})), analysis: null, villainAnalysis: null }]
  const sds = [
    { key: 'preflop', label: 'Pre-Flop', start: pfm, end: '*** FLOP ***' },
    { key: 'flop', label: 'Flop', start: '*** FLOP ***', end: '*** TURN ***' },
    { key: 'turn', label: 'Turn', start: '*** TURN ***', end: '*** RIVER ***' },
    { key: 'river', label: 'River', start: '*** RIVER ***', end: '*** SHOW' },
  ]

  for (const sd of sds) {
    const si = raw.indexOf(sd.start); if (si === -1) continue
    let ei = raw.indexOf(sd.end, si + sd.start.length); if (ei === -1) ei = raw.indexOf('*** SUMMARY ***', si); if (ei === -1) ei = raw.length
    const section = raw.slice(si, ei)
    const curBoard = sd.key === 'preflop' ? [] : sd.key === 'flop' ? bc.slice(0,3) : sd.key === 'turn' ? bc.slice(0,4) : bc.slice(0,5)

    if (sd.key !== 'preflop' && curBoard.length > 0) {
      pState.forEach(p => p.currentBet = 0)
      steps.push({ street: sd.key, label: sd.label, action: `${sd.label} dealt`, actor: null, actorIdx: -1, isHero: false, pot, potBB: +(pot/bb).toFixed(1), board: [...curBoard], ps: pState.map(p => ({...p})), analysis: null, villainAnalysis: null })
    }

    for (const line of section.split('\n')) {
      const t = line.trim(); if (!t || t.startsWith('***') || t.startsWith('Dealt')) continue
      const showM = t.match(/^(.+?)(?::)?\s+shows\s+\[(.+?)\]/i)
      if (showM) { const pi = pState.findIndex(p => p.name === showM[1].trim()); if (pi >= 0) pState[pi].cards = showM[2].split(' '); continue }
      const m = t.match(/^(.+?)(?::)?\s+(folds|checks|calls|bets|raises)(.*)$/i); if (!m) continue
      const actor = m[1].trim(), action = m[2].toLowerCase(), rest = m[3]
      let amount = 0; const amtM = rest.match(/([\d,]+)/); if (amtM) amount = parseFloat(amtM[1].replace(/,/g, ''))
      const allIn = /all-in/i.test(rest)
      const pi = pState.findIndex(p => p.name === actor)
      const isH = pi >= 0 && pState[pi].isHero

      if (action === 'folds' && pi >= 0) { pState[pi].folded = true; pState[pi].currentBet = 0 }
      else if (action === 'calls') { pot += amount; if (pi >= 0) pState[pi].currentBet = amount }
      else if (action === 'bets') { pot += amount; if (pi >= 0) pState[pi].currentBet = amount }
      else if (action === 'raises') { const toM = rest.match(/to ([\d,]+)/); const rt = toM ? parseFloat(toM[1].replace(/,/g, '')) : amount; pot += rt; if (pi >= 0) pState[pi].currentBet = rt }
      else if (action === 'checks' && pi >= 0) { pState[pi].currentBet = 0 }

      let analysis = null, villainAnalysis = null
      if (isH && (action === 'calls' || action === 'folds')) {
        const fb = amount; const pb = action === 'calls' ? pot - amount : pot
        if (fb > 0) analysis = { type: 'facing', potBefore: Math.round(pb), facingBet: Math.round(fb), potOdds: +(fb/(pb+fb)*100).toFixed(1), mdf: +(pb/(pb+fb)*100).toFixed(1), potBB: +(pb/bb).toFixed(1), betBB: +(fb/bb).toFixed(1) }
      } else if (isH && (action === 'bets' || action === 'raises')) {
        const pb = pot - amount
        analysis = { type: 'betting', potBefore: Math.round(pb), betSize: Math.round(amount), betToPot: pb > 0 ? +(amount/pb*100).toFixed(1) : 0, mbf: +(amount/(pb+amount)*100).toFixed(1), potBB: +(pb/bb).toFixed(1), betBB: +(amount/bb).toFixed(1) }
        villainAnalysis = { villainMDF: +(pb/(pb+amount)*100).toFixed(1), potBefore: Math.round(pb), heroBet: Math.round(amount) }
      } else if (!isH && (action === 'bets' || action === 'raises')) {
        const pb = pot - amount
        if (pb > 0) analysis = { type: 'facing', potBefore: Math.round(pb), facingBet: Math.round(amount), potOdds: +(amount/(pb+amount)*100).toFixed(1), mdf: +(pb/(pb+amount)*100).toFixed(1), potBB: +(pb/bb).toFixed(1), betBB: +(amount/bb).toFixed(1) }
      }

      const al = action === 'folds' ? 'folds' : action === 'checks' ? 'checks' : action === 'calls' ? `calls ${Math.round(amount).toLocaleString()}${allIn?' (all-in)':''}` : action === 'bets' ? `bets ${Math.round(amount).toLocaleString()}${allIn?' (all-in)':''}` : `raises to ${Math.round(amount).toLocaleString()}${allIn?' (all-in)':''}`
      steps.push({ street: sd.key, label: sd.label, action: al, actor, actorIdx: pi, isHero: isH, pot: Math.round(pot), potBB: +(pot/bb).toFixed(1), board: [...curBoard], ps: pState.map(p => ({...p})), analysis, villainAnalysis })
    }
  }

  // Parse showdown cards
  const sdSection = raw.match(/\*\*\* SHOW\s*DOWN \*\*\*([\s\S]*?)(\*\*\* SUMMARY|$)/i)
  if (sdSection) {
    for (const line of sdSection[1].split('\n')) {
      const sm = line.trim().match(/^(.+?)(?::)?\s+shows\s+\[(.+?)\]/i)
      if (sm) { const pi = pState.findIndex(p => p.name === sm[1].trim()); if (pi >= 0) pState[pi].cards = sm[2].split(' ') }
    }
  }
  if (pState.filter(p => p.cards.length > 0 && !p.folded).length >= 2) {
    steps.push({ street: 'showdown', label: 'Showdown', action: 'Showdown', actor: null, actorIdx: -1, isHero: false, pot, potBB: +(pot/bb).toFixed(1), board: bc, ps: pState.map(p => ({...p})), analysis: null, villainAnalysis: null })
  }
  return { steps, heroIdx }
}

// ── Range Grid Component ─────────────────────────────────────────────────────
const RANKS_GRID = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']

function cellLabel(r, c) {
  if (r === c) return RANKS_GRID[r] + RANKS_GRID[c]  // pair
  if (c > r) return RANKS_GRID[r] + RANKS_GRID[c] + 's'  // suited (above diagonal)
  return RANKS_GRID[c] + RANKS_GRID[r] + 'o'  // offsuit (below diagonal) — show higher rank first
}

function cellKey(r, c) {
  // Normalize: pairs = "AA", suited = "AKs", offsuit = "AKo"
  if (r === c) return RANKS_GRID[r] + RANKS_GRID[c]
  if (c > r) return RANKS_GRID[r] + RANKS_GRID[c] + 's'
  return RANKS_GRID[c] + RANKS_GRID[r] + 'o'
}

function selectedToRangeStr(selected) {
  if (selected.size === 0) return 'random'
  return [...selected].sort().join(',')
}

function RangeGrid({ selected, onToggle, onClear, onSelectAll }) {
  const [dragging, setDragging] = useState(false)
  const [dragMode, setDragMode] = useState(true) // true = selecting, false = deselecting

  function handleMouseDown(key) {
    const newMode = !selected.has(key)
    setDragging(true)
    setDragMode(newMode)
    onToggle(key, newMode)
  }
  function handleMouseEnter(key) {
    if (dragging) onToggle(key, dragMode)
  }
  function handleMouseUp() { setDragging(false) }

  const pct = selected.size > 0 ? ((selected.size / 169) * 100).toFixed(1) : '0'

  return (
    <div onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp} style={{ userSelect: 'none' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0' }}>Range: {pct}%</span>
        <div style={{ display: 'flex', gap: 4 }}>
          <button onClick={onSelectAll} style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(99,102,241,0.1)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.25)', cursor: 'pointer' }}>Todas</button>
          <button onClick={onClear} style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.25)', cursor: 'pointer' }}>Limpar</button>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(13, 1fr)', gap: 1 }}>
        {RANKS_GRID.map((_, r) =>
          RANKS_GRID.map((_, c) => {
            const key = cellKey(r, c)
            const label = cellLabel(r, c)
            const isSuited = c > r
            const isPair = r === c
            const isSelected = selected.has(key)
            return (
              <div
                key={key}
                onMouseDown={() => handleMouseDown(key)}
                onMouseEnter={() => handleMouseEnter(key)}
                style={{
                  width: '100%', aspectRatio: '1', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 9, fontWeight: 600, fontFamily: 'monospace', cursor: 'pointer',
                  background: isSelected
                    ? (isPair ? '#ca8a04' : isSuited ? '#2563eb' : '#0891b2')
                    : (isPair ? 'rgba(202,138,4,0.08)' : isSuited ? 'rgba(37,99,235,0.06)' : 'rgba(8,145,178,0.06)'),
                  color: isSelected ? '#fff' : '#4b5563',
                  borderRadius: 2,
                  border: `1px solid ${isSelected ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.04)'}`,
                  transition: 'background 0.05s',
                }}
              >{label}</div>
            )
          })
        )}
      </div>
    </div>
  )
}

function PRow({ l, v, c }) {
  return <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}><span style={{ fontSize: 11, color: '#64748b' }}>{l}</span><span style={{ fontSize: 13, fontWeight: 700, color: c, fontFamily: 'monospace' }}>{v}</span></div>
}

export default function ReplayerPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [hand, setHand] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [si, setSi] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [eq, setEq] = useState(null)
  const [eqLoading, setEqLoading] = useState(false)
  const [villainRange, setVillainRange] = useState('random')
  const [rangeInput, setRangeInput] = useState('')
  const [lastBoard, setLastBoard] = useState('')
  const [copied, setCopied] = useState(false)
  const [showRangeGrid, setShowRangeGrid] = useState(false)
  const [selectedCells, setSelectedCells] = useState(new Set())

  useEffect(() => { setLoading(true); handsApi.get(id).then(h => { setHand(h); setLoading(false) }).catch(e => { setError(e.message); setLoading(false) }) }, [id])

  const { steps, heroIdx } = hand ? parseHH(hand.raw, hand.all_players_actions) : { steps: [], heroIdx: -1 }
  const meta = hand?.all_players_actions?._meta || {}
  const step = steps[si] || steps[0]
  const ps = step?.ps || []
  const slots = getSlots(ps.length)
  const positions = ps.map((_, i) => { const idx = (i - (heroIdx >= 0 ? heroIdx : 0) + ps.length) % ps.length; return POSITIONS_9[slots[idx] || 0] })
  const chipPositions = ps.map((_, i) => { const idx = (i - (heroIdx >= 0 ? heroIdx : 0) + ps.length) % ps.length; return CHIP_OFFSETS_9[slots[idx] || 0] })

  useEffect(() => { if (!playing || si >= steps.length - 1) { setPlaying(false); return }; const t = setTimeout(() => setSi(i => i + 1), 1200); return () => clearTimeout(t) }, [playing, si, steps.length])

  const calcEq = useCallback(async (boardCards, range) => {
    if (!hand?.hero_cards?.length) return; setEqLoading(true)
    try { const d = await equity.calculate(hand.hero_cards, boardCards || [], range || 'random', 8000); setEq(d) } catch (e) { console.error(e) } finally { setEqLoading(false) }
  }, [hand?.hero_cards])

  useEffect(() => { if (!step || !hand?.hero_cards?.length) return; const bk = (step.board || []).join(','); if (bk !== lastBoard) { setLastBoard(bk); calcEq(step.board, villainRange) } }, [step?.board, hand?.hero_cards, lastBoard, calcEq, villainRange])

  useEffect(() => {
    const handler = (e) => { if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return; if (e.key === 'ArrowLeft') setSi(i => Math.max(0, i - 1)); else if (e.key === 'ArrowRight') setSi(i => Math.min(steps.length - 1, i + 1)); else if (e.key === ' ') { e.preventDefault(); setPlaying(p => !p) } else if (e.key === 'Home') setSi(0); else if (e.key === 'End') setSi(steps.length - 1) }
    window.addEventListener('keydown', handler); return () => window.removeEventListener('keydown', handler)
  }, [steps.length])

  const streets = [...new Set(steps.map(s => s.street))]
  const applyRange = () => { const r = rangeInput.trim() || 'random'; setVillainRange(r); calcEq(step?.board, r) }

  if (loading) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#0a0c14', color: '#64748b' }}>A carregar mão #{id}...</div>
  if (error) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#0a0c14', color: '#ef4444' }}>{error}</div>
  if (!steps.length) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#0a0c14', color: '#64748b' }}>Sem Hand History para replay</div>

  const btnS = { background: 'rgba(255,255,255,0.06)', border: '1px solid #2a2d3a', borderRadius: 6, padding: '6px 12px', color: '#94a3b8', cursor: 'pointer', fontSize: 14, lineHeight: 1 }
  const btnPlayerIdx = ps.findIndex(p => p.position === 'BTN')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#0a0c14', color: '#e2e8f0', overflow: 'hidden' }}>
      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 20px', background: '#111420', borderBottom: '1px solid #1e2130', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 14, padding: '4px 8px' }}>&larr; Voltar</button>
          <span style={{ fontSize: 14, fontWeight: 700 }}>REPLAYER</span>
          <span style={{ fontSize: 12, color: '#64748b' }}>Mão #{hand.id}</span>
          {meta.sb && meta.bb && <span style={{ fontSize: 12, color: '#4b5563', fontFamily: 'monospace' }}>{Math.round(meta.sb)}/{Math.round(meta.bb)}{meta.ante ? `(${Math.round(meta.ante)})` : ''}{meta.level != null ? ` Lv${meta.level}` : ''}</span>}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {hand.stakes && <span style={{ fontSize: 12, color: '#4b5563', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{hand.stakes}</span>}
          <a href={`/hand/${hand.id}`} style={{ fontSize: 11, color: '#818cf8', textDecoration: 'none', padding: '3px 10px', borderRadius: 5, background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.25)', fontWeight: 600 }}>Detalhe</a>
          {hand.raw && (
            <button onClick={() => { navigator.clipboard.writeText(hand.raw); setCopied(true); setTimeout(() => setCopied(false), 2000) }} style={{ fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 5, background: copied ? 'rgba(34,197,94,0.15)' : 'rgba(245,158,11,0.1)', color: copied ? '#22c55e' : '#f59e0b', border: `1px solid ${copied ? 'rgba(34,197,94,0.3)' : 'rgba(245,158,11,0.25)'}`, cursor: 'pointer' }}>{copied ? '✓ Copiado' : 'Copiar HH'}</button>
          )}
          <span style={{ fontSize: 13, fontWeight: 600, color: STREET_COLORS[step.street], padding: '3px 10px', borderRadius: 5, background: `${STREET_COLORS[step.street]}15`, border: `1px solid ${STREET_COLORS[step.street]}30`, textTransform: 'uppercase' }}>{step.label}</span>
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left Panel */}
        <div style={{ width: 190, padding: '16px 14px', borderRight: '1px solid #1e2130', background: '#0d0f18', overflowY: 'auto', flexShrink: 0 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: '#64748b', letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Equity Hero</div>
          <div style={{ fontSize: 9, color: '#374151', marginBottom: 8 }}>Probabilidade de ganhar vs range do vilão</div>
          {eq && (
            <div style={{ textAlign: 'center', marginBottom: 16, padding: '10px 0', background: 'rgba(0,0,0,0.3)', borderRadius: 6 }}>
              <div style={{ fontSize: 32, fontWeight: 800, color: eq.equity > 50 ? '#22c55e' : '#ef4444', fontFamily: 'monospace', lineHeight: 1 }}>{eq.equity}%</div>
              <div style={{ fontSize: 10, color: '#4b5563', marginTop: 4 }}>vs {villainRange === 'random' ? 'mão aleatória' : villainRange}</div>
              {eq.win != null && <div style={{ fontSize: 10, color: '#4b5563', marginTop: 2 }}>Win: {eq.win}% Tie: {eq.tie}%</div>}
            </div>
          )}
          {eqLoading && <div style={{ textAlign: 'center', fontSize: 11, color: '#4b5563', marginBottom: 12 }}>A calcular...</div>}
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: '#4b5563', marginBottom: 4, textTransform: 'uppercase' }}>Range vilão</div>
            <input type="text" value={rangeInput} onChange={e => setRangeInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') applyRange() }} placeholder="random" style={{ width: '100%', fontSize: 11, background: '#0a0c14', border: '1px solid #2a2d3a', borderRadius: 4, color: '#e2e8f0', padding: '5px 8px', fontFamily: 'monospace', boxSizing: 'border-box' }} />
            <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
              <button onClick={applyRange} style={{ flex: 1, fontSize: 10, fontWeight: 600, padding: '4px 0', borderRadius: 4, background: 'rgba(34,197,94,0.12)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.25)', cursor: 'pointer' }}>Calcular</button>
              <button onClick={() => setShowRangeGrid(true)} style={{ flex: 1, fontSize: 10, fontWeight: 600, padding: '4px 0', borderRadius: 4, background: 'rgba(99,102,241,0.12)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.25)', cursor: 'pointer' }}>Grelha</button>
            </div>
          </div>
          <div style={{ fontSize: 9, color: '#374151', lineHeight: 1.5 }}>Clica "Grelha" para seleccionar visualmente ou escreve: TT+,AKs,AKo</div>
        </div>

        {/* Center — Table */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ flex: 1, position: 'relative', background: 'radial-gradient(ellipse at center,#0f2318,#0a1510 40%,#080d0f)' }}>
            <div style={{ position: 'absolute', top: '14%', left: '14%', width: '72%', height: '72%', borderRadius: '50%', border: '3px solid #1a3828', background: 'radial-gradient(ellipse at center,#14392a,#0d2b1e 60%,#091f15)', boxShadow: 'inset 0 0 80px rgba(0,0,0,0.5)' }} />

            {/* Pot */}
            <div style={{ position: 'absolute', top: '35%', left: '50%', transform: 'translate(-50%,-50%)', textAlign: 'center', zIndex: 2 }}>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 2 }}>POT</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#fbbf24', fontFamily: "'Fira Code',monospace", textShadow: '0 0 12px rgba(251,191,36,0.3)' }}>{step.potBB}BB</div>
              <div style={{ fontSize: 10, color: '#4b5563', fontFamily: 'monospace' }}>{step.pot?.toLocaleString()}</div>
              {meta.sb && meta.bb && (
                <div style={{ marginTop: 4, fontSize: 11, color: '#64748b', fontFamily: 'monospace', background: 'rgba(0,0,0,0.4)', padding: '2px 10px', borderRadius: 4, display: 'inline-block' }}>
                  SB {Math.round(meta.sb)} / BB {Math.round(meta.bb)}{meta.ante ? ` / Ante ${Math.round(meta.ante)}` : ''}
                </div>
              )}
            </div>

            {/* Board */}
            {step.board?.length > 0 && (
              <div style={{ position: 'absolute', top: '54%', left: '50%', transform: 'translate(-50%,-50%)', display: 'flex', gap: 4, zIndex: 2 }}>
                {step.board.map((c, i) => <RCard key={i} card={c} size="md" />)}
              </div>
            )}

            {/* Dealer button */}
            {btnPlayerIdx >= 0 && positions[btnPlayerIdx] && (
              <div style={{ position: 'absolute', left: `${positions[btnPlayerIdx].x + (positions[btnPlayerIdx].x > 50 ? -6 : 6)}%`, top: `${positions[btnPlayerIdx].y + (positions[btnPlayerIdx].y > 50 ? -5 : 5)}%`, width: 32, height: 32, borderRadius: '50%', background: 'linear-gradient(135deg, #fbbf24, #f59e0b)', color: '#000', fontSize: 13, fontWeight: 900, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 3px 10px rgba(251,191,36,0.5), 0 0 0 2px rgba(0,0,0,0.3)', zIndex: 6, transform: 'translate(-50%,-50%)', letterSpacing: 0.5, border: '2px solid rgba(255,255,255,0.3)' }}>D</div>
            )}

            {/* Players */}
            {ps.map((p, i) => {
              const pos = positions[i]
              const chipPos = chipPositions[i]
              const active = step.actorIdx === i
              const bountyStr = p.bounty != null ? (typeof p.bounty === 'string' ? p.bounty.replace('€', ' EUR') : `${p.bounty} EUR`) : null
              return (
                <div key={i}>
                  {p.currentBet > 0 && !p.folded && (
                    <div style={{ position: 'absolute', left: `${chipPos.x}%`, top: `${chipPos.y}%`, transform: 'translate(-50%,-50%)', fontSize: 14, fontWeight: 800, color: '#fbbf24', fontFamily: "'Fira Code',monospace", background: 'rgba(0,0,0,0.88)', padding: '4px 12px', borderRadius: 6, border: '2px solid rgba(251,191,36,0.5)', whiteSpace: 'nowrap', zIndex: 6, boxShadow: '0 2px 8px rgba(0,0,0,0.6), 0 0 6px rgba(251,191,36,0.2)', letterSpacing: 0.5 }}>
                      {Math.round(p.currentBet).toLocaleString()}
                    </div>
                  )}
                  <div style={{ position: 'absolute', left: `${pos.x}%`, top: `${pos.y}%`, transform: 'translate(-50%,-50%)', textAlign: 'center', minWidth: 90, zIndex: 3, transition: 'all 0.3s' }}>
                    <div style={{ display: 'flex', gap: 2, justifyContent: 'center', marginBottom: 3 }}>
                      {p.cards?.length > 0 ? p.cards.map((c, ci) => <RCard key={ci} card={c} size={p.isHero ? 'lg' : 'sm'} />) : !p.folded ? <><RCard faceDown size="sm" /><RCard faceDown size="sm" /></> : null}
                    </div>
                    <div style={{ background: active ? 'rgba(251,191,36,0.15)' : p.isHero ? 'rgba(99,102,241,0.12)' : 'rgba(0,0,0,0.7)', border: `1.5px solid ${active ? '#fbbf24' : p.isHero ? '#6366f1' : '#2a2d3a'}`, borderRadius: 7, padding: '3px 8px', opacity: p.folded ? 0.3 : 1, transition: 'all 0.3s' }}>
                      <div style={{ fontSize: 9, fontWeight: 700, color: p.isHero ? '#818cf8' : '#94a3b8', letterSpacing: 0.3 }}>{p.position}</div>
                      <div style={{ fontSize: 11, fontWeight: p.isHero ? 700 : 500, color: p.isHero ? '#c7d2fe' : '#e2e8f0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 88 }}>{p.name}</div>
                      <div style={{ fontSize: 10, fontWeight: 700, color: '#fbbf24', fontFamily: 'monospace' }}>{p.stackBB}BB</div>
                      {bountyStr && <div style={{ fontSize: 9, color: '#f59e0b' }}>{bountyStr}</div>}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Action log */}
          <div style={{ padding: '8px 20px', background: '#0d0f18', borderTop: '1px solid #1e2130', display: 'flex', alignItems: 'center', gap: 10, minHeight: 38, flexShrink: 0 }}>
            {step.actor ? <>
              <span style={{ fontSize: 13, fontWeight: 600, color: step.isHero ? '#818cf8' : '#94a3b8' }}>{step.actor}</span>
              <span style={{ fontSize: 14, fontWeight: 600, color: step.action.includes('fold') ? '#ef4444' : step.action.includes('call') || step.action.includes('check') ? '#22c55e' : '#f59e0b' }}>{step.action}</span>
            </> : <span style={{ fontSize: 13, color: '#4b5563' }}>{step.action}</span>}
          </div>

          {/* Controls */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 20px', background: '#111420', borderTop: '1px solid #1e2130', flexShrink: 0 }}>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <button onClick={() => setSi(0)} style={btnS}>{'\u23EE'}</button>
              <button onClick={() => setSi(i => Math.max(0, i-1))} style={btnS}>{'\u25C0'}</button>
              <button onClick={() => setPlaying(!playing)} style={{ ...btnS, background: playing ? 'rgba(239,68,68,0.15)' : 'rgba(34,197,94,0.15)', color: playing ? '#ef4444' : '#22c55e', minWidth: 40 }}>{playing ? '\u23F8' : '\u25B6'}</button>
              <button onClick={() => setSi(i => Math.min(steps.length-1, i+1))} style={btnS}>{'\u25B6'}</button>
              <button onClick={() => setSi(steps.length-1)} style={btnS}>{'\u23ED'}</button>
              <span style={{ fontSize: 11, color: '#4b5563', fontFamily: 'monospace', marginLeft: 8 }}>{si+1}/{steps.length}</span>
            </div>
            <div style={{ display: 'flex', gap: 5 }}>
              {streets.filter(s => s !== 'showdown').map(s => (
                <button key={s} onClick={() => { const idx = steps.findIndex(st => st.street === s); if (idx >= 0) setSi(idx) }} style={{ ...btnS, color: step.street === s ? STREET_COLORS[s] : '#4b5563', background: step.street === s ? `${STREET_COLORS[s]}15` : 'transparent', border: `1px solid ${step.street === s ? `${STREET_COLORS[s]}40` : '#2a2d3a'}`, fontSize: 11, fontWeight: 600, textTransform: 'uppercase' }}>{s === 'preflop' ? 'PF' : s.charAt(0).toUpperCase() + s.slice(1)}</button>
              ))}
              {streets.includes('showdown') && (
                <button onClick={() => setSi(steps.length - 1)} style={{ ...btnS, color: step.street === 'showdown' ? STREET_COLORS.showdown : '#4b5563', background: step.street === 'showdown' ? `${STREET_COLORS.showdown}15` : 'transparent', border: `1px solid ${step.street === 'showdown' ? `${STREET_COLORS.showdown}40` : '#2a2d3a'}`, fontSize: 11, fontWeight: 600 }}>SD</button>
              )}
            </div>
          </div>
        </div>

        {/* Right Panel */}
        <div style={{ width: 190, padding: '16px 14px', borderLeft: '1px solid #1e2130', background: '#0d0f18', overflowY: 'auto', flexShrink: 0 }}>
          {step.analysis && (
            <div style={{ marginBottom: 20 }}>
              {step.analysis.type === 'facing' ? <>
                <div style={{ fontSize: 10, fontWeight: 700, color: '#64748b', letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>{step.isHero ? 'Hero Decision' : 'Hero Faces'}</div>
                <PRow l="Pot Odds" v={step.analysis.potOdds + '%'} c="#3b82f6" />
                <PRow l="MDF" v={step.analysis.mdf + '%'} c="#8b5cf6" />
                <PRow l="To Call" v={step.analysis.betBB + ' BB'} c="#f59e0b" />
                <PRow l="Pot" v={step.analysis.potBB + ' BB'} c="#64748b" />
              </> : <>
                <div style={{ fontSize: 10, fontWeight: 700, color: '#64748b', letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Hero Bet</div>
                <PRow l="Bet/Pot" v={step.analysis.betToPot + '%'} c="#22c55e" />
                <PRow l="MBF" v={step.analysis.mbf + '%'} c="#ec4899" />
                <PRow l="Size" v={step.analysis.betBB + ' BB'} c="#f59e0b" />
                <PRow l="Pot" v={step.analysis.potBB + ' BB'} c="#64748b" />
              </>}
            </div>
          )}
          {step.villainAnalysis && (
            <div style={{ marginBottom: 20, padding: '10px', background: 'rgba(245,158,11,0.06)', borderRadius: 6, border: '1px solid rgba(245,158,11,0.15)' }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: '#f59e0b', letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Villain Must Defend</div>
              <PRow l="MDF" v={step.villainAnalysis.villainMDF + '%'} c="#f59e0b" />
              <PRow l="vs Bet" v={Math.round(step.villainAnalysis.heroBet).toLocaleString()} c="#64748b" />
            </div>
          )}
          {!step.analysis && !step.villainAnalysis && (
            <div style={{ fontSize: 11, color: '#374151', textAlign: 'center', padding: '20px 0' }}>Navega para uma acção para ver análise</div>
          )}
        </div>
      </div>

      {/* Range Grid Popup */}
      {showRangeGrid && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, backdropFilter: 'blur(4px)' }} onClick={() => setShowRangeGrid(false)}>
          <div style={{ background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12, padding: 24, width: 520, maxWidth: '95vw' }} onClick={e => e.stopPropagation()}>
            <RangeGrid
              selected={selectedCells}
              onToggle={(key, mode) => {
                setSelectedCells(prev => {
                  const next = new Set(prev)
                  if (mode) next.add(key); else next.delete(key)
                  return next
                })
              }}
              onClear={() => setSelectedCells(new Set())}
              onSelectAll={() => {
                const all = new Set()
                for (let r = 0; r < 13; r++) for (let c = 0; c < 13; c++) all.add(cellKey(r, c))
                setSelectedCells(all)
              }}
            />
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <button onClick={() => {
                const rangeStr = selectedToRangeStr(selectedCells)
                setRangeInput(rangeStr)
                setVillainRange(rangeStr)
                calcEq(step?.board, rangeStr)
                setShowRangeGrid(false)
              }} style={{ flex: 1, padding: '8px 0', borderRadius: 6, fontSize: 13, fontWeight: 600, background: '#22c55e', color: '#000', border: 'none', cursor: 'pointer' }}>Aplicar e Calcular</button>
              <button onClick={() => setShowRangeGrid(false)} style={{ padding: '8px 16px', borderRadius: 6, fontSize: 13, fontWeight: 600, background: 'transparent', color: '#64748b', border: '1px solid #2a2d3a', cursor: 'pointer' }}>Fechar</button>
            </div>
            <div style={{ marginTop: 8, display: 'flex', gap: 12, fontSize: 10, color: '#4b5563' }}>
              <span><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: '#ca8a04', marginRight: 3 }}></span>Pares</span>
              <span><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: '#2563eb', marginRight: 3 }}></span>Suited</span>
              <span><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: '#0891b2', marginRight: 3 }}></span>Offsuit</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
