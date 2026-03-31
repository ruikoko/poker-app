import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { hands as handsApi, equity } from '../api/client'

const SUIT_COLORS = { h: '#ef4444', d: '#3b82f6', c: '#22c55e', s: '#e2e8f0' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }
const SUIT_BG = { h: '#7f1d1d', d: '#1e3a5f', c: '#14532d', s: '#1e293b' }
const STREET_COLORS = { preflop: '#6366f1', flop: '#22c55e', turn: '#f59e0b', river: '#ef4444', showdown: '#8b5cf6' }
const HERO_NAMES = new Set(['hero','schadenfreud','thinvalium','sapz','misterpoker1973','cringemeariver','flightrisk','karluz','koumpounophobia','lauro dermio'])
const SEAT_ORDER = ['UTG','UTG1','UTG+1','UTG2','UTG+2','MP','MP1','MP+1','HJ','CO','BTN','SB','BB']

const POSITIONS_9 = [
  { x: 50, y: 88 }, { x: 14, y: 74 }, { x: 8, y: 42 }, { x: 14, y: 12 },
  { x: 36, y: 4 }, { x: 64, y: 4 }, { x: 86, y: 12 }, { x: 92, y: 42 }, { x: 86, y: 74 },
]
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

// ── Parse HH with correct stack tracking and pot calculation ────────────────
function parseHH(raw, apa) {
  if (!raw) return { steps: [], heroIdx: -1 }
  const meta = apa?._meta || {}
  const bb = meta.bb || 1
  const players = Object.entries(apa || {}).filter(([k]) => k !== '_meta')
    .map(([name, info]) => ({ name, ...info }))
    .sort((a, b) => {
      const ai = SEAT_ORDER.indexOf(a.position) === -1 ? 99 : SEAT_ORDER.indexOf(a.position)
      const bi = SEAT_ORDER.indexOf(b.position) === -1 ? 99 : SEAT_ORDER.indexOf(b.position)
      return ai - bi
    })
  const heroIdx = players.findIndex(p => p.is_hero || HERO_NAMES.has(p.name.toLowerCase()))

  // Initialize player state with original stacks
  const pState = players.map(p => ({
    name: p.name, position: p.position,
    startStack: p.stack || 0,
    stack: p.stack || 0,
    stackBB: p.stack_bb || 0,
    bounty: p.bounty,
    isHero: p.is_hero || HERO_NAMES.has(p.name.toLowerCase()),
    cards: [], folded: false,
    currentBet: 0,       // current bet this street
    totalInvested: 0,    // total invested this street (for raise tracking)
    actionLabel: '',     // last action label
  }))

  const dm = raw.match(/Dealt to (\S+)\s+\[(.+?)\]/)
  if (dm && heroIdx >= 0) pState[heroIdx].cards = dm[2].split(' ')

  const isW = raw.includes('*** PRE-FLOP ***')
  const pfm = isW ? '*** PRE-FLOP ***' : '*** HOLE CARDS ***'
  const bc = []
  const fm = raw.match(/\*\*\* FLOP \*\*\* \[(.+?)\]/); if (fm) bc.push(...fm[1].split(' '))
  const tmW = raw.match(/\*\*\* TURN \*\*\* \[.+?\]\s*\[(.+?)\]/); if (tmW) bc.push(...tmW[1].split(' '))
  const rmW = raw.match(/\*\*\* RIVER \*\*\* \[.+?\]\s*\[(.+?)\]/); if (rmW) bc.push(...rmW[1].split(' '))

  // Process antes and blinds - deduct from stacks
  let pot = 0
  const anteMatches = [...raw.matchAll(/(.+?)(?::)?\s+posts\s+(?:the\s+)?ante\s+([\d,]+(?:\.\d+)?)/gi)]
  for (const am of anteMatches) {
    const name = am[1].trim(), amount = parseFloat(am[2].replace(/,/g, ''))
    pot += amount
    const pi = pState.findIndex(p => p.name === name)
    if (pi >= 0) { pState[pi].stack -= amount; pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1) }
  }
  const sbMatch = raw.match(/(.+?)(?::)?\s+posts\s+(?:the\s+)?small blind\s+([\d,]+(?:\.\d+)?)/i)
  if (sbMatch) {
    const name = sbMatch[1].trim(), amount = parseFloat(sbMatch[2].replace(/,/g, ''))
    pot += amount
    const pi = pState.findIndex(p => p.name === name)
    if (pi >= 0) { pState[pi].stack -= amount; pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1); pState[pi].totalInvested = amount; pState[pi].currentBet = amount }
  }
  const bbMatch = raw.match(/(.+?)(?::)?\s+posts\s+(?:the\s+)?big blind\s+([\d,]+(?:\.\d+)?)/i)
  if (bbMatch) {
    const name = bbMatch[1].trim(), amount = parseFloat(bbMatch[2].replace(/,/g, ''))
    pot += amount
    const pi = pState.findIndex(p => p.name === name)
    if (pi >= 0) { pState[pi].stack -= amount; pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1); pState[pi].totalInvested = amount; pState[pi].currentBet = amount }
  }

  const snap = () => pState.map(p => ({ ...p }))
  const steps = [{ street: 'preflop', label: 'Pre-Flop', action: 'Blinds posted', actor: null, actorIdx: -1, isHero: false, pot, potBB: +(pot/bb).toFixed(1), board: [], ps: snap(), analysis: null, villainAnalysis: null }]

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
      // New street: reset bets and totalInvested
      pState.forEach(p => { p.currentBet = 0; p.totalInvested = 0; p.actionLabel = '' })
      steps.push({ street: sd.key, label: sd.label, action: `${sd.label} dealt`, actor: null, actorIdx: -1, isHero: false, pot, potBB: +(pot/bb).toFixed(1), board: [...curBoard], ps: snap(), analysis: null, villainAnalysis: null })
    }

    for (const line of section.split('\n')) {
      const t = line.trim(); if (!t || t.startsWith('***') || t.startsWith('Dealt') || t.startsWith('Main pot') || t.includes('posts')) continue
      
      // Showdown cards
      const showM = t.match(/^(.+?)(?::)?\s+shows\s+\[(.+?)\]/i)
      if (showM) { const pi = pState.findIndex(p => p.name === showM[1].trim()); if (pi >= 0) pState[pi].cards = showM[2].split(' '); continue }

      // Uncalled bet return
      const uncalledM = t.match(/Uncalled bet \(([\d,]+(?:\.\d+)?)\) returned to (.+)/i)
      if (uncalledM) {
        const amount = parseFloat(uncalledM[1].replace(/,/g, ''))
        const name = uncalledM[2].trim()
        const pi = pState.findIndex(p => p.name === name)
        pot -= amount
        if (pi >= 0) { pState[pi].stack += amount; pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1); pState[pi].currentBet -= amount }
        continue
      }

      // Collected
      const collM = t.match(/^(.+?) collected ([\d,]+(?:\.\d+)?)/i)
      if (collM) {
        const name = collM[1].trim(), amount = parseFloat(collM[2].replace(/,/g, ''))
        const pi = pState.findIndex(p => p.name === name)
        if (pi >= 0) { pState[pi].stack += amount; pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1) }
        continue
      }

      const m = t.match(/^(.+?)(?::)?\s+(folds|checks|calls|bets|raises)(.*)$/i); if (!m) continue
      const actor = m[1].trim(), action = m[2].toLowerCase(), rest = m[3]
      let amount = 0; const amtM = rest.match(/([\d,]+(?:\.\d+)?)/); if (amtM) amount = parseFloat(amtM[1].replace(/,/g, ''))
      const allIn = /all-in/i.test(rest)
      const toM = rest.match(/to\s+([\d,]+(?:\.\d+)?)/)
      const pi = pState.findIndex(p => p.name === actor)
      const isH = pi >= 0 && pState[pi].isHero

      let actionLabel = ''
      if (action === 'folds') {
        if (pi >= 0) { pState[pi].folded = true; pState[pi].currentBet = 0; pState[pi].actionLabel = '' }
        actionLabel = 'Fold'
      } else if (action === 'checks') {
        if (pi >= 0) { pState[pi].actionLabel = '' }
        actionLabel = 'Check'
      } else if (action === 'calls') {
        // Call: pay the difference between current bet and the bet we're calling
        const callAmount = amount
        pot += callAmount
        if (pi >= 0) {
          pState[pi].stack -= callAmount
          pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1)
          pState[pi].totalInvested += callAmount
          pState[pi].currentBet = pState[pi].totalInvested
          pState[pi].actionLabel = `Call ${(callAmount / bb).toFixed(1)}bb`
        }
        actionLabel = `calls ${Math.round(callAmount).toLocaleString()}${allIn ? ' (all-in)' : ''}`
      } else if (action === 'bets') {
        pot += amount
        if (pi >= 0) {
          pState[pi].stack -= amount
          pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1)
          pState[pi].totalInvested += amount
          pState[pi].currentBet = amount
          pState[pi].actionLabel = `Bet ${(amount / bb).toFixed(1)}bb`
        }
        actionLabel = `bets ${Math.round(amount).toLocaleString()}${allIn ? ' (all-in)' : ''}`
      } else if (action === 'raises') {
        // Raises: "raises X to Y" — player puts in Y total this street
        const raiseTo = toM ? parseFloat(toM[1].replace(/,/g, '')) : amount
        const prevInvested = pi >= 0 ? pState[pi].totalInvested : 0
        const additionalCost = raiseTo - prevInvested
        pot += additionalCost
        if (pi >= 0) {
          pState[pi].stack -= additionalCost
          pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1)
          pState[pi].totalInvested = raiseTo
          pState[pi].currentBet = raiseTo
          pState[pi].actionLabel = `Raise ${(raiseTo / bb).toFixed(1)}bb`
        }
        actionLabel = `raises to ${Math.round(raiseTo).toLocaleString()}${allIn ? ' (all-in)' : ''}`
      }

      // Analysis calculations
      let analysis = null, villainAnalysis = null
      const potBeforeAction = pot - (action === 'calls' ? amount : action === 'bets' ? amount : action === 'raises' ? (toM ? parseFloat(toM[1].replace(/,/g, '')) : amount) - (pi >= 0 ? pState[pi].totalInvested - (toM ? parseFloat(toM[1].replace(/,/g, '')) : amount) : 0) : 0)
      
      if (isH && (action === 'calls' || action === 'folds')) {
        const facingBet = amount
        const potBefore = action === 'calls' ? pot - amount : pot
        if (facingBet > 0) analysis = { type: 'facing', potBefore: Math.round(potBefore), facingBet: Math.round(facingBet), potOdds: +(facingBet/(potBefore+facingBet)*100).toFixed(1), mdf: +(potBefore/(potBefore+facingBet)*100).toFixed(1), potBB: +(potBefore/bb).toFixed(1), betBB: +(facingBet/bb).toFixed(1) }
      } else if (isH && (action === 'bets' || action === 'raises')) {
        const betAmount = action === 'raises' ? (toM ? parseFloat(toM[1].replace(/,/g, '')) : amount) : amount
        const prevInv = action === 'raises' ? (pState[pi]?.totalInvested - betAmount + (pState[pi]?.totalInvested || 0)) : 0
        const potBefore = pot - (betAmount - (pi >= 0 ? pState[pi].totalInvested - betAmount : 0))
        analysis = { type: 'betting', potBefore: Math.round(Math.abs(potBefore)), betSize: Math.round(betAmount), betToPot: potBefore > 0 ? +(betAmount/potBefore*100).toFixed(1) : 0, mbf: +(betAmount/(potBefore+betAmount)*100).toFixed(1), potBB: +(potBefore/bb).toFixed(1), betBB: +(betAmount/bb).toFixed(1) }
        villainAnalysis = { villainMDF: +(Math.abs(potBefore)/(Math.abs(potBefore)+betAmount)*100).toFixed(1), potBefore: Math.round(Math.abs(potBefore)), heroBet: Math.round(betAmount) }
      } else if (!isH && (action === 'bets' || action === 'raises')) {
        const betAmount = action === 'raises' ? (toM ? parseFloat(toM[1].replace(/,/g, '')) : amount) : amount
        const potBefore = pot - betAmount
        if (potBefore > 0) analysis = { type: 'facing', potBefore: Math.round(potBefore), facingBet: Math.round(betAmount), potOdds: +(betAmount/(potBefore+betAmount)*100).toFixed(1), mdf: +(potBefore/(potBefore+betAmount)*100).toFixed(1), potBB: +(potBefore/bb).toFixed(1), betBB: +(betAmount/bb).toFixed(1) }
      }

      steps.push({
        street: sd.key, label: sd.label, action: actionLabel, actor, actorIdx: pi, isHero: isH,
        pot: Math.round(pot), potBB: +(pot/bb).toFixed(1),
        board: [...curBoard], ps: snap(), analysis, villainAnalysis
      })
    }
  }

  // Showdown
  const sdSection = raw.match(/\*\*\* SHOW\s*DOWN \*\*\*([\s\S]*?)(\*\*\* SUMMARY|$)/i)
  if (sdSection) {
    for (const line of sdSection[1].split('\n')) {
      const sm = line.trim().match(/^(.+?)(?::)?\s+shows\s+\[(.+?)\]/i)
      if (sm) { const pi = pState.findIndex(p => p.name === sm[1].trim()); if (pi >= 0) pState[pi].cards = sm[2].split(' ') }
      const cm = line.trim().match(/^(.+?) collected ([\d,]+(?:\.\d+)?)/i)
      if (cm) { const pi = pState.findIndex(p => p.name === cm[1].trim()); if (pi >= 0) { const amt = parseFloat(cm[2].replace(/,/g, '')); pState[pi].stack += amt; pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1) } }
    }
  }
  if (pState.filter(p => p.cards.length > 0 && !p.folded).length >= 2) {
    steps.push({ street: 'showdown', label: 'Showdown', action: 'Showdown', actor: null, actorIdx: -1, isHero: false, pot, potBB: +(pot/bb).toFixed(1), board: bc, ps: snap(), analysis: null, villainAnalysis: null })
  }
  return { steps, heroIdx }
}

// ── Range Grid ──────────────────────────────────────────────────────────────
const RANKS_GRID = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']
function cellLabel(r, c) { if (r === c) return RANKS_GRID[r] + RANKS_GRID[c]; if (c > r) return RANKS_GRID[r] + RANKS_GRID[c] + 's'; return RANKS_GRID[c] + RANKS_GRID[r] + 'o' }
function cellKey(r, c) { if (r === c) return RANKS_GRID[r] + RANKS_GRID[c]; if (c > r) return RANKS_GRID[r] + RANKS_GRID[c] + 's'; return RANKS_GRID[c] + RANKS_GRID[r] + 'o' }
function selectedToRangeStr(selected) { if (selected.size === 0) return 'random'; return [...selected].sort().join(',') }

function RangeGrid({ selected, onToggle, onClear, onSelectAll }) {
  const [dragging, setDragging] = useState(false)
  const [dragMode, setDragMode] = useState(true)
  const handleMouseDown = (key) => { const newMode = !selected.has(key); setDragging(true); setDragMode(newMode); onToggle(key, newMode) }
  const handleMouseEnter = (key) => { if (dragging) onToggle(key, dragMode) }
  const pct = selected.size > 0 ? ((selected.size / 169) * 100).toFixed(1) : '0'
  return (
    <div onMouseUp={() => setDragging(false)} onMouseLeave={() => setDragging(false)} style={{ userSelect: 'none' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0' }}>Range: {pct}%</span>
        <div style={{ display: 'flex', gap: 4 }}>
          <button onClick={onSelectAll} style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(99,102,241,0.1)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.25)', cursor: 'pointer' }}>Todas</button>
          <button onClick={onClear} style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.25)', cursor: 'pointer' }}>Limpar</button>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(13, 1fr)', gap: 1 }}>
        {RANKS_GRID.map((_, r) => RANKS_GRID.map((_, c) => { const key = cellKey(r, c), label = cellLabel(r, c), isSuited = c > r, isPair = r === c, isSelected = selected.has(key); return (
          <div key={key} onMouseDown={() => handleMouseDown(key)} onMouseEnter={() => handleMouseEnter(key)} style={{ width: '100%', aspectRatio: '1', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, fontWeight: 600, fontFamily: 'monospace', cursor: 'pointer', background: isSelected ? (isPair ? '#ca8a04' : isSuited ? '#2563eb' : '#0891b2') : (isPair ? 'rgba(202,138,4,0.08)' : isSuited ? 'rgba(37,99,235,0.06)' : 'rgba(8,145,178,0.06)'), color: isSelected ? '#fff' : '#4b5563', borderRadius: 2, border: `1px solid ${isSelected ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.04)'}` }}>{label}</div>
        ) }))}
      </div>
    </div>
  )
}

function PRow({ l, v, c }) { return <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #1e2130' }}><span style={{ fontSize: 11, color: '#64748b' }}>{l}</span><span style={{ fontSize: 12, fontWeight: 700, color: c || '#e2e8f0', fontFamily: 'monospace' }}>{v}</span></div> }

// ── Main Component ──────────────────────────────────────────────────────────
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
  const [showBB, setShowBB] = useState(true) // toggle BB vs chips

  useEffect(() => { setLoading(true); handsApi.get(id).then(h => { setHand(h); setLoading(false) }).catch(e => { setError(e.message); setLoading(false) }) }, [id])

  const { steps, heroIdx } = hand ? parseHH(hand.raw, hand.all_players_actions) : { steps: [], heroIdx: -1 }
  const meta = hand?.all_players_actions?._meta || {}
  const bbSize = meta.bb || 1
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
  const sbIdx = ps.findIndex(p => p.position === 'SB')
  const bbIdx = ps.findIndex(p => p.position === 'BB')

  const formatChip = (val) => showBB ? `${(val / bbSize).toFixed(1)}bb` : Math.round(val).toLocaleString()

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
          {hand.raw && <button onClick={() => { navigator.clipboard.writeText(hand.raw); setCopied(true); setTimeout(() => setCopied(false), 2000) }} style={{ fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 5, background: copied ? 'rgba(34,197,94,0.15)' : 'rgba(245,158,11,0.1)', color: copied ? '#22c55e' : '#f59e0b', border: `1px solid ${copied ? 'rgba(34,197,94,0.3)' : 'rgba(245,158,11,0.25)'}`, cursor: 'pointer' }}>{copied ? '✓ Copiado' : 'Copiar HH'}</button>}
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
              <div style={{ fontSize: 24, fontWeight: 800, color: '#fbbf24', fontFamily: "'Fira Code',monospace", textShadow: '0 0 12px rgba(251,191,36,0.3)', cursor: 'pointer' }} onClick={() => setShowBB(v => !v)}>
                {showBB ? `${step.potBB}BB` : step.pot?.toLocaleString()}
              </div>
              <div style={{ fontSize: 10, color: '#4b5563', fontFamily: 'monospace' }}>{showBB ? step.pot?.toLocaleString() : `${step.potBB}BB`}</div>
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
              <div style={{ position: 'absolute', left: `${positions[btnPlayerIdx].x + (positions[btnPlayerIdx].x > 50 ? -6 : 6)}%`, top: `${positions[btnPlayerIdx].y + (positions[btnPlayerIdx].y > 50 ? -5 : 5)}%`, width: 30, height: 30, borderRadius: '50%', background: 'linear-gradient(135deg, #fbbf24, #f59e0b)', color: '#000', fontSize: 12, fontWeight: 900, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 3px 10px rgba(251,191,36,0.5)', zIndex: 6, transform: 'translate(-50%,-50%)', border: '2px solid rgba(255,255,255,0.3)' }}>D</div>
            )}

            {/* SB badge */}
            {sbIdx >= 0 && positions[sbIdx] && (
              <div style={{ position: 'absolute', left: `${positions[sbIdx].x + (positions[sbIdx].x > 50 ? 5 : -5)}%`, top: `${positions[sbIdx].y + (positions[sbIdx].y > 50 ? -4 : 4)}%`, width: 26, height: 26, borderRadius: '50%', background: 'linear-gradient(135deg, #64748b, #475569)', color: '#fff', fontSize: 9, fontWeight: 900, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 6px rgba(0,0,0,0.4)', zIndex: 6, transform: 'translate(-50%,-50%)', border: '2px solid rgba(255,255,255,0.2)' }}>SB</div>
            )}

            {/* BB badge */}
            {bbIdx >= 0 && positions[bbIdx] && (
              <div style={{ position: 'absolute', left: `${positions[bbIdx].x + (positions[bbIdx].x > 50 ? 5 : -5)}%`, top: `${positions[bbIdx].y + (positions[bbIdx].y > 50 ? -4 : 4)}%`, width: 26, height: 26, borderRadius: '50%', background: 'linear-gradient(135deg, #ef4444, #dc2626)', color: '#fff', fontSize: 9, fontWeight: 900, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 6px rgba(0,0,0,0.4)', zIndex: 6, transform: 'translate(-50%,-50%)', border: '2px solid rgba(255,255,255,0.2)' }}>BB</div>
            )}

            {/* Players */}
            {ps.map((p, i) => {
              const pos = positions[i]
              const chipPos = chipPositions[i]
              const active = step.actorIdx === i
              const bountyStr = p.bounty != null ? (typeof p.bounty === 'string' ? p.bounty : `${p.bounty}€`) : null
              const isAllIn = p.stack <= 0 && !p.folded && p.currentBet > 0
              return (
                <div key={i}>
                  {p.currentBet > 0 && !p.folded && (
                    <div style={{ position: 'absolute', left: `${chipPos.x}%`, top: `${chipPos.y}%`, transform: 'translate(-50%,-50%)', textAlign: 'center', zIndex: 6 }}>
                      {p.actionLabel && <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 2, whiteSpace: 'nowrap' }}>{p.actionLabel}</div>}
                      <div onClick={() => setShowBB(v => !v)} style={{ fontSize: 13, fontWeight: 800, color: '#fbbf24', fontFamily: "'Fira Code',monospace", background: 'rgba(0,0,0,0.88)', padding: '3px 10px', borderRadius: 5, border: `2px solid ${isAllIn ? '#ef4444' : 'rgba(251,191,36,0.5)'}`, whiteSpace: 'nowrap', cursor: 'pointer', boxShadow: '0 2px 8px rgba(0,0,0,0.6)' }}>
                        {formatChip(p.currentBet)}
                      </div>
                      {isAllIn && <div style={{ fontSize: 9, fontWeight: 800, color: '#ef4444', marginTop: 2, letterSpacing: 1 }}>ALL-IN</div>}
                    </div>
                  )}
                  <div style={{ position: 'absolute', left: `${pos.x}%`, top: `${pos.y}%`, transform: 'translate(-50%,-50%)', textAlign: 'center', minWidth: 90, zIndex: 3, transition: 'all 0.3s' }}>
                    <div style={{ display: 'flex', gap: 2, justifyContent: 'center', marginBottom: 3 }}>
                      {p.cards?.length > 0 ? p.cards.map((c, ci) => <RCard key={ci} card={c} size={p.isHero ? 'lg' : 'sm'} />) : !p.folded ? <><RCard faceDown size="sm" /><RCard faceDown size="sm" /></> : null}
                    </div>
                    <div style={{ background: active ? 'rgba(251,191,36,0.15)' : isAllIn ? 'rgba(239,68,68,0.12)' : p.isHero ? 'rgba(99,102,241,0.12)' : 'rgba(0,0,0,0.7)', border: `1.5px solid ${active ? '#fbbf24' : isAllIn ? '#ef4444' : p.isHero ? '#6366f1' : '#2a2d3a'}`, borderRadius: 7, padding: '3px 8px', opacity: p.folded ? 0.3 : 1, transition: 'all 0.3s' }}>
                      <div style={{ fontSize: 9, fontWeight: 700, color: p.isHero ? '#818cf8' : '#94a3b8', letterSpacing: 0.3 }}>{p.position}</div>
                      <div style={{ fontSize: 11, fontWeight: p.isHero ? 700 : 500, color: p.isHero ? '#c7d2fe' : '#e2e8f0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 88 }}>{p.name}</div>
                      <div style={{ fontSize: 10, fontWeight: 700, color: isAllIn ? '#ef4444' : '#fbbf24', fontFamily: 'monospace' }}>{isAllIn ? 'ALL-IN' : `${p.stackBB}BB`}</div>
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
              <span style={{ fontSize: 14, fontWeight: 600, color: step.action.includes('Fold') || step.action.includes('fold') ? '#ef4444' : step.action.includes('call') || step.action.includes('Call') || step.action.includes('check') || step.action.includes('Check') ? '#22c55e' : '#f59e0b' }}>{step.action}</span>
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
              <PRow l="vs Bet" v={formatChip(step.villainAnalysis.heroBet)} c="#64748b" />
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
            <RangeGrid selected={selectedCells} onToggle={(key, mode) => { setSelectedCells(prev => { const next = new Set(prev); if (mode) next.add(key); else next.delete(key); return next }) }} onClear={() => setSelectedCells(new Set())} onSelectAll={() => { const all = new Set(); for (let r = 0; r < 13; r++) for (let c = 0; c < 13; c++) all.add(cellKey(r, c)); setSelectedCells(all) }} />
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <button onClick={() => { const rangeStr = selectedToRangeStr(selectedCells); setRangeInput(rangeStr); setVillainRange(rangeStr); calcEq(step?.board, rangeStr); setShowRangeGrid(false) }} style={{ flex: 1, padding: '8px 0', borderRadius: 6, fontSize: 13, fontWeight: 600, background: '#22c55e', color: '#000', border: 'none', cursor: 'pointer' }}>Aplicar e Calcular</button>
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
