import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { hands as handsApi, equity, gto as gtoApi } from '../api/client'
import { HERO_NAMES } from '../heroNames'

const SUIT_COLORS = { h: '#ef4444', d: '#3b82f6', c: '#22c55e', s: '#e2e8f0' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }
const SUIT_BG = { h: '#7f1d1d', d: '#1e3a5f', c: '#14532d', s: '#1e293b' }
const STREET_COLORS = { preflop: '#6366f1', flop: '#22c55e', turn: '#f59e0b', river: '#ef4444', showdown: '#8b5cf6' }
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
  const w = size === 'xl' ? 52 : size === 'lg' ? 44 : size === 'board' ? 42 : size === 'md' ? 34 : 28
  const h = size === 'xl' ? 72 : size === 'lg' ? 62 : size === 'board' ? 58 : size === 'md' ? 48 : 38
  const fs = size === 'xl' ? 18 : size === 'lg' ? 15 : size === 'board' ? 14 : size === 'md' ? 12 : 11
  if (faceDown || !card || card.length < 2) return <div style={{ width: w, height: h, borderRadius: 4, background: 'linear-gradient(135deg,#1e40af,#7c3aed,#1e40af)', border: '1.5px solid rgba(255,255,255,0.2)', boxShadow: '0 2px 6px rgba(0,0,0,0.4)' }} />
  const rank = card.slice(0, -1).toUpperCase(), suit = card.slice(-1).toLowerCase()
  return <div style={{ width: w, height: h, borderRadius: 4, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: SUIT_BG[suit] || '#1e293b', border: `1.5px solid ${SUIT_COLORS[suit]}40`, boxShadow: '0 2px 6px rgba(0,0,0,0.4)', fontFamily: "'Fira Code',monospace", fontWeight: 700, fontSize: fs, color: '#fff', lineHeight: 1, userSelect: 'none' }}><span>{rank}</span><span style={{ fontSize: fs * 0.75, color: SUIT_COLORS[suit] }}>{SUIT_SYMBOLS[suit]}</span></div>
}

// ── Parse HH with correct stack tracking and pot calculation ────────────────
function parseHH(raw, apa) {
  if (!raw) return { steps: [], heroIdx: -1 }
  const meta = apa?._meta || {}
  let bb = meta.bb || 0
  // Fallback: tentar parsear bb directamente do raw se meta está vazio.
  // Formatos comuns:
  //  - GG: "Level5(125/250(35))" → bb=250
  //  - WN/PS: "Level XXII (20000/40000)" → bb=40000
  if (!bb) {
    const m1 = raw.match(/Level\s*\d+\s*\(\s*\d+\s*\/\s*(\d+)/i)
    const m2 = raw.match(/\(\s*(\d+)\s*\/\s*(\d+)\s*\)/)
    if (m1) bb = parseInt(m1[1], 10)
    else if (m2) bb = parseInt(m2[2], 10)
  }
  if (!bb) bb = 1  // último recurso para não dividir por zero

  const players = Object.entries(apa || {}).filter(([k]) => k !== '_meta')
    .map(([name, info]) => ({ name, ...info }))
    .sort((a, b) => {
      const ai = SEAT_ORDER.indexOf(a.position) === -1 ? 99 : SEAT_ORDER.indexOf(a.position)
      const bi = SEAT_ORDER.indexOf(b.position) === -1 ? 99 : SEAT_ORDER.indexOf(b.position)
      return ai - bi
    })
  const heroIdx = players.findIndex(p => p.is_hero || HERO_NAMES.has(p.name.toLowerCase()))

  // Build nameMap: anon hash → real name (from seats in raw vs apa)
  const nameMap = {}
  const seatLines = raw.match(/Seat \d+: .+? \([\d,]+(?:\.\d+)?(?:\s+in chips)?\)/g) || []
  for (const line of seatLines) {
    const sm = line.match(/Seat (\d+): (.+?) \(/)
    if (sm) {
      const seatNum = parseInt(sm[1])
      const anonName = sm[2].trim()
      for (const p of players) {
        if (p.seat === seatNum && p.name !== anonName) {
          nameMap[anonName] = p.name
          break
        }
      }
    }
  }
  const resolve = (n) => nameMap[n] || n
  const findPlayer = (rawName) => {
    const realName = resolve(rawName)
    return pState.findIndex(p => p.name === realName)
  }

  // Initialize player state with original stacks
  const pState = players.map(p => ({
    name: p.name, position: p.position,
    startStack: p.stack || 0,
    stack: p.stack || 0,
    stackBB: p.stack_bb || (bb > 1 ? +((p.stack || 0) / bb).toFixed(1) : 0),
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
    const pi = findPlayer(name)
    if (pi >= 0) { pState[pi].stack -= amount; pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1) }
  }
  const sbMatch = raw.match(/(.+?)(?::)?\s+posts\s+(?:the\s+)?small blind\s+([\d,]+(?:\.\d+)?)/i)
  if (sbMatch) {
    const name = sbMatch[1].trim(), amount = parseFloat(sbMatch[2].replace(/,/g, ''))
    pot += amount
    const pi = findPlayer(name)
    if (pi >= 0) { pState[pi].stack -= amount; pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1); pState[pi].totalInvested = amount; pState[pi].currentBet = amount }
  }
  const bbMatch = raw.match(/(.+?)(?::)?\s+posts\s+(?:the\s+)?big blind\s+([\d,]+(?:\.\d+)?)/i)
  if (bbMatch) {
    const name = bbMatch[1].trim(), amount = parseFloat(bbMatch[2].replace(/,/g, ''))
    pot += amount
    const pi = findPlayer(name)
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
      if (showM) { const pi = findPlayer(showM[1].trim()); if (pi >= 0) pState[pi].cards = showM[2].split(' '); continue }

      // Uncalled bet return
      const uncalledM = t.match(/Uncalled bet \(([\d,]+(?:\.\d+)?)\) returned to (.+)/i)
      if (uncalledM) {
        const amount = parseFloat(uncalledM[1].replace(/,/g, ''))
        const name = uncalledM[2].trim()
        const pi = findPlayer(name)
        pot -= amount
        if (pi >= 0) { pState[pi].stack += amount; pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1); pState[pi].currentBet -= amount }
        continue
      }

      // Collected
      const collM = t.match(/^(.+?) collected ([\d,]+(?:\.\d+)?)/i)
      if (collM) {
        const name = collM[1].trim(), amount = parseFloat(collM[2].replace(/,/g, ''))
        const pi = findPlayer(name)
        if (pi >= 0) { pState[pi].stack += amount; pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1) }
        continue
      }

      const m = t.match(/^(.+?)(?::)?\s+(folds|checks|calls|bets|raises)(.*)$/i); if (!m) continue
      const actor = m[1].trim(), action = m[2].toLowerCase(), rest = m[3]
      let amount = 0; const amtM = rest.match(/([\d,]+(?:\.\d+)?)/); if (amtM) amount = parseFloat(amtM[1].replace(/,/g, ''))
      const allIn = /all-in/i.test(rest)
      const toM = rest.match(/to\s+([\d,]+(?:\.\d+)?)/)
      const pi = findPlayer(actor)
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
      
      if (isH && action === 'calls') {
        const facingBet = amount
        const potBefore = pot - amount
        if (facingBet > 0) analysis = { type: 'facing', potBefore: Math.round(potBefore), facingBet: Math.round(facingBet), potOdds: +(facingBet/(potBefore+facingBet)*100).toFixed(1), mdf: +(potBefore/(potBefore+facingBet)*100).toFixed(1), potBB: +(potBefore/bb).toFixed(1), betBB: +(facingBet/bb).toFixed(1) }
      } else if (isH && action === 'folds') {
        // Hero folds — show what they were facing (last villain bet/raise)
        const lastBetStep = [...steps].reverse().find(s => s.analysis?.type === 'facing')
        if (lastBetStep?.analysis) analysis = { ...lastBetStep.analysis, heroFolded: true }
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
      } else if (!isH && (action === 'calls' || action === 'checks' || action === 'folds')) {
        // Non-hero passive action — carry forward analysis if next to act is hero
        const lastBetStep = [...steps].reverse().find(s => s.analysis?.type === 'facing')
        if (lastBetStep?.analysis) analysis = lastBetStep.analysis
      }

      steps.push({
        street: sd.key, label: sd.label, action: actionLabel, actor: resolve(actor), actorIdx: pi, isHero: isH,
        pot: Math.round(pot), potBB: +(pot/bb).toFixed(1),
        board: [...curBoard], ps: snap(), analysis, villainAnalysis
      })
    }
  }

  // Showdown — parse cards from SHOW DOWN and SUMMARY sections
  const sdSection = raw.match(/\*\*\* SHOW\s*DOWN \*\*\*([\s\S]*?)(\*\*\* SUMMARY|$)/i)
  if (sdSection) {
    for (const line of sdSection[1].split('\n')) {
      const sm = line.trim().match(/^(.+?)(?::)?\s+shows\s+\[(.+?)\]/i)
      if (sm) {
        const name = sm[1].trim()
        const cards = sm[2].split(' ').filter(c => c.trim())
        // Try exact match first, then partial
        let pi = findPlayer(name)
        if (pi < 0) pi = pState.findIndex(p => p.name.startsWith(name) || name.startsWith(p.name))
        if (pi >= 0) pState[pi].cards = cards
      }
      const cm = line.trim().match(/^(.+?) collected ([\d,]+(?:\.\d+)?)/i)
      if (cm) {
        const name = cm[1].trim()
        let pi = findPlayer(name)
        if (pi < 0) pi = pState.findIndex(p => p.name.startsWith(name) || name.startsWith(p.name))
        if (pi >= 0) { const amt = parseFloat(cm[2].replace(/,/g, '')); pState[pi].stack += amt; pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1) }
      }
    }
  }
  // Also check SUMMARY section for "showed [cards]" lines (Winamax/PS format)
  const summarySection = raw.match(/\*\*\* SUMMARY \*\*\*([\s\S]*?)$/i)
  if (summarySection) {
    for (const line of summarySection[1].split('\n')) {
      const sm = line.trim().match(/:\s*(.+?)\s+showed\s+\[(.+?)\]/i)
      if (sm) {
        const name = sm[1].trim()
        const cards = sm[2].split(' ').filter(c => c.trim())
        let pi = findPlayer(name)
        if (pi < 0) pi = pState.findIndex(p => p.name.startsWith(name) || name.startsWith(p.name))
        if (pi >= 0 && pState[pi].cards.length === 0) pState[pi].cards = cards
      }
    }
  }
  // Show showdown if at least 2 non-folded players have cards, OR if any non-hero has cards
  const playersWithCards = pState.filter(p => p.cards.length > 0 && !p.folded)
  if (playersWithCards.length >= 2) {
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
  const [rightTab, setRightTab] = useState('analysis') // 'analysis' | 'gto'
  const [gtoMatch, setGtoMatch] = useState(null)
  const [gtoNode, setGtoNode] = useState(null)
  const [gtoLoading, setGtoLoading] = useState(false)
  const [heroGtoAction, setHeroGtoAction] = useState(null)

  useEffect(() => { setLoading(true); handsApi.get(id).then(h => { setHand(h); setLoading(false) }).catch(e => { setError(e.message); setLoading(false) }) }, [id])

  const { steps, heroIdx } = hand ? parseHH(hand.raw, hand.all_players_actions) : { steps: [], heroIdx: -1 }
  const meta = hand?.all_players_actions?._meta || {}
  const bbSize = meta.bb || 1
  const step = steps[si] || steps[0]
  const ps = step?.ps || []
  const slots = getSlots(ps.length)
  const positions = ps.map((_, i) => { const idx = (i - (heroIdx >= 0 ? heroIdx : 0) + ps.length) % ps.length; return POSITIONS_9[slots[idx] || 0] })
  const chipPositions = ps.map((_, i) => { const idx = (i - (heroIdx >= 0 ? heroIdx : 0) + ps.length) % ps.length; return CHIP_OFFSETS_9[slots[idx] || 0] })

  // GTO matching — find closest tree when hand loads
  useEffect(() => {
    if (!hand?.all_players_actions) return
    const m = hand.all_players_actions._meta
    if (!m) return
    const heroEntry = Object.entries(hand.all_players_actions).find(([k, v]) => k !== '_meta' && HERO_NAMES.has(k.toLowerCase()))
    if (!heroEntry) return
    const heroBB = heroEntry[1].stack_bb || (heroEntry[1].stack / (m.bb || 1))
    const heroPos = heroEntry[1].position || ''
    const isPKO = hand.raw && /bounty|PKO|KO|Progressive|Mystery/i.test(hand.raw)
    const fmt = isPKO ? 'PKO' : 'vanilla'
    
    // Get all players sorted by seat order
    const allPlayers = Object.entries(hand.all_players_actions)
      .filter(([k]) => k !== '_meta')
      .map(([name, info]) => ({ name, ...info }))
    
    // Determine active players (in pot) and remaining (yet to act after hero)
    const SEAT_ORD = ['UTG','UTG1','UTG+1','UTG2','UTG+2','MP','MP1','MP+1','HJ','CO','BTN','SB','BB']
    const heroSeatIdx = SEAT_ORD.indexOf(heroPos)
    const otherPlayers = allPlayers.filter(p => !HERO_NAMES.has(p.name.toLowerCase()))
    const activeStacks = otherPlayers.map(p => p.stack_bb || (p.stack / (m.bb || 1))).filter(s => s > 0)
    const activePositions = otherPlayers.map(p => p.position).filter(Boolean)
    
    // Remaining = players who act AFTER hero in preflop order (BTN, SB, BB if hero is CO)
    const remainingPlayers = otherPlayers.filter(p => {
      const pIdx = SEAT_ORD.indexOf(p.position)
      return pIdx > heroSeatIdx
    })
    const remainingPositions = remainingPlayers.map(p => p.position).filter(Boolean)
    const remainingStacks = remainingPlayers.map(p => p.stack_bb || (p.stack / (m.bb || 1))).filter(s => s > 0)
    
    // Extract level from raw
    let level = m.level || null
    if (!level && hand.raw) {
      const lvM = hand.raw.match(/level[:\s]+(\d+)/i) || hand.raw.match(/Level\s+([IVXLCDM]+)/i)
      if (lvM) {
        const v = lvM[1]
        if (/^\d+$/.test(v)) level = parseInt(v)
        else { // Roman
          const rv = {I:1,V:5,X:10,L:50}; let t=0
          for (let i=0;i<v.length;i++) { const c=rv[v[i]]||0; const n=rv[v[i+1]]||0; t+=c<n?-c:c }
          level = t
        }
      }
    }
    
    setGtoLoading(true)
    gtoApi.match({
      hero_stack_bb: Math.round(heroBB * 10) / 10,
      format: fmt,
      num_players: m.num_players || allPlayers.length || 6,
      hero_position: heroPos,
      level: level,
      site: hand.site || 'Winamax',
      active_positions: activePositions.join(','),
      active_stacks_bb: activeStacks.map(s => Math.round(s*10)/10).join(','),
      remaining_positions: remainingPositions.join(','),
      remaining_stacks_bb: remainingStacks.map(s => Math.round(s*10)/10).join(','),
    }).then(d => {
      setGtoMatch(d)
      if (d.matches && d.matches.length > 0) {
        const bestMatch = d.matches[0]
        
        // Build preflop action sequence for auto-navigation
        const preflopActions = []
        const raw = hand.raw || ''
        const isW = raw.includes('*** PRE-FLOP ***')
        const pfStart = isW ? '*** PRE-FLOP ***' : '*** HOLE CARDS ***'
        const pfEnd = '*** FLOP ***'
        const si2 = raw.indexOf(pfStart)
        if (si2 >= 0) {
          let ei2 = raw.indexOf(pfEnd, si2)
          if (ei2 === -1) ei2 = raw.indexOf('*** SUMMARY ***', si2)
          if (ei2 === -1) ei2 = raw.length
          const pfSection = raw.slice(si2 + pfStart.length, ei2)
          for (const line of pfSection.split('\n')) {
            const t2 = line.trim()
            if (!t2 || t2.includes('posts') || t2.startsWith('Dealt') || t2.startsWith('***')) continue
            const am = t2.match(/^(.+?)(?::)?\s+(folds|checks|calls|bets|raises)(.*)$/i)
            if (!am) continue
            const act2 = am[2].toLowerCase()
            const rest2 = am[3]
            const toM2 = rest2.match(/to\s+([\d,]+(?:\.\d+)?)/)
            let amtBB = 0
            if (act2 === 'raises' && toM2) amtBB = parseFloat(toM2[1].replace(/,/g, '')) / (m.bb || 1)
            else if (act2 === 'calls') { const amM = rest2.match(/([\d,]+(?:\.\d+)?)/); if (amM) amtBB = parseFloat(amM[1].replace(/,/g, '')) / (m.bb || 1) }
            else if (act2 === 'bets') { const amM = rest2.match(/([\d,]+(?:\.\d+)?)/); if (amM) amtBB = parseFloat(amM[1].replace(/,/g, '')) / (m.bb || 1) }
            
            let aType = 'F'
            if (act2 === 'folds') aType = 'F'
            else if (act2 === 'calls' || act2 === 'checks') aType = 'C'
            else if (act2 === 'bets' || act2 === 'raises') aType = 'R'
            
            preflopActions.push({ type: aType, amount_bb: Math.round(amtBB * 10) / 10 })
          }
        }
        
        // Find hero's action index in sequence
        const heroActionIdx = (() => {
          const SEAT_ORD2 = ['UTG','UTG1','UTG+1','UTG2','UTG+2','MP','MP1','MP+1','HJ','CO','BTN','SB','BB']
          const sorted = [...allPlayers].sort((a,b) => {
            const ai2 = SEAT_ORD2.indexOf(a.position); const bi2 = SEAT_ORD2.indexOf(b.position)
            return (ai2===-1?99:ai2) - (bi2===-1?99:bi2)
          })
          return sorted.findIndex(p => HERO_NAMES.has(p.name.toLowerCase()))
        })()
        
        // Navigate to hero's node: send all actions BEFORE hero
        const actionsBeforeHero = preflopActions.slice(0, heroActionIdx >= 0 ? heroActionIdx : preflopActions.length - 1)
        
        if (actionsBeforeHero.length > 0) {
          gtoApi.navigate({ tree_id: bestMatch.tree_id, actions: actionsBeforeHero }).then(node => {
            setGtoNode(node)
          }).catch(() => {
            // Fallback: load root
            gtoApi.getNode(bestMatch.tree_id, 0).then(setGtoNode).catch(() => {})
          })
        } else {
          gtoApi.getNode(bestMatch.tree_id, 0).then(setGtoNode).catch(() => {})
        }
        
        // Store hero's actual action for comparison
        if (heroActionIdx >= 0 && heroActionIdx < preflopActions.length) {
          setHeroGtoAction(preflopActions[heroActionIdx])
        }
      }
    }).catch(() => {}).finally(() => setGtoLoading(false))
  }, [hand])

  useEffect(() => { if (!playing || si >= steps.length - 1) { setPlaying(false); return }; const t = setTimeout(() => setSi(i => i + 1), 1200); return () => clearTimeout(t) }, [playing, si, steps.length])

  const calcEq = useCallback(async (boardCards, range) => {
    if (!hand?.hero_cards?.length) return; setEqLoading(true)
    console.log('EQUITY CALC:', { hero: hand.hero_cards, board: boardCards, range })
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
              <div style={{ position: 'absolute', top: '54%', left: '50%', transform: 'translate(-50%,-50%)', display: 'flex', gap: 5, zIndex: 2 }}>
                {step.board.map((c, i) => <RCard key={i} card={c} size="board" />)}
              </div>
            )}

            {/* Dealer button */}
            {btnPlayerIdx >= 0 && positions[btnPlayerIdx] && (
              <div style={{ position: 'absolute', left: `${positions[btnPlayerIdx].x + (positions[btnPlayerIdx].x > 50 ? -6 : 6)}%`, top: `${positions[btnPlayerIdx].y + (positions[btnPlayerIdx].y > 50 ? -5 : 5)}%`, width: 30, height: 30, borderRadius: '50%', background: 'linear-gradient(135deg, #fbbf24, #f59e0b)', color: '#000', fontSize: 12, fontWeight: 900, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 3px 10px rgba(251,191,36,0.5)', zIndex: 6, transform: 'translate(-50%,-50%)', border: '2px solid rgba(255,255,255,0.3)' }}>D</div>
            )}

            {/* SB badge — inside table */}
            {sbIdx >= 0 && positions[sbIdx] && (
              <div style={{ position: 'absolute', left: `${positions[sbIdx].x + (positions[sbIdx].x > 50 ? -8 : 8)}%`, top: `${positions[sbIdx].y + (positions[sbIdx].y > 50 ? -8 : 8)}%`, width: 28, height: 28, borderRadius: '50%', background: 'linear-gradient(135deg, #64748b, #475569)', color: '#fff', fontSize: 10, fontWeight: 900, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 6px rgba(0,0,0,0.4)', zIndex: 6, transform: 'translate(-50%,-50%)', border: '2px solid rgba(255,255,255,0.2)' }}>SB</div>
            )}

            {/* BB badge — inside table */}
            {bbIdx >= 0 && positions[bbIdx] && (
              <div style={{ position: 'absolute', left: `${positions[bbIdx].x + (positions[bbIdx].x > 50 ? -8 : 8)}%`, top: `${positions[bbIdx].y + (positions[bbIdx].y > 50 ? -8 : 8)}%`, width: 28, height: 28, borderRadius: '50%', background: 'linear-gradient(135deg, #ef4444, #dc2626)', color: '#fff', fontSize: 10, fontWeight: 900, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 6px rgba(0,0,0,0.4)', zIndex: 6, transform: 'translate(-50%,-50%)', border: '2px solid rgba(255,255,255,0.2)' }}>BB</div>
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
                      {p.actionLabel && <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 2, whiteSpace: 'nowrap' }}>{p.actionLabel}</div>}
                      <div onClick={() => setShowBB(v => !v)} style={{ fontSize: 14, fontWeight: 800, color: '#fbbf24', fontFamily: "'Fira Code',monospace", background: 'rgba(0,0,0,0.88)', padding: '4px 12px', borderRadius: 5, border: `2px solid ${isAllIn ? '#ef4444' : 'rgba(251,191,36,0.5)'}`, whiteSpace: 'nowrap', cursor: 'pointer', boxShadow: '0 2px 8px rgba(0,0,0,0.6)' }}>
                        {formatChip(p.currentBet)}
                      </div>
                      {isAllIn && <div style={{ fontSize: 10, fontWeight: 800, color: '#ef4444', marginTop: 2, letterSpacing: 1 }}>ALL-IN</div>}
                    </div>
                  )}
                  <div style={{ position: 'absolute', left: `${pos.x}%`, top: `${pos.y}%`, transform: 'translate(-50%,-50%)', textAlign: 'center', minWidth: 100, zIndex: 3, transition: 'all 0.3s' }}>
                    <div style={{ display: 'flex', gap: 3, justifyContent: 'center', marginBottom: 3 }}>
                      {p.cards?.length > 0 ? p.cards.map((c, ci) => <RCard key={ci} card={c} size={p.isHero ? 'xl' : 'md'} />) : !p.folded ? <><RCard faceDown size="md" /><RCard faceDown size="md" /></> : null}
                    </div>
                    <div style={{ background: active ? 'rgba(251,191,36,0.15)' : isAllIn ? 'rgba(239,68,68,0.12)' : p.isHero ? 'rgba(99,102,241,0.12)' : 'rgba(0,0,0,0.7)', border: `1.5px solid ${active ? '#fbbf24' : isAllIn ? '#ef4444' : p.isHero ? '#6366f1' : '#2a2d3a'}`, borderRadius: 7, padding: '4px 10px', opacity: p.folded ? 0.3 : 1, transition: 'all 0.3s' }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: p.isHero ? '#818cf8' : '#94a3b8', letterSpacing: 0.3 }}>{p.position}</div>
                      <div style={{ fontSize: 12, fontWeight: p.isHero ? 700 : 600, color: p.isHero ? '#c7d2fe' : '#e2e8f0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 100 }}>{p.name}</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: isAllIn ? '#ef4444' : '#fbbf24', fontFamily: 'monospace' }}>{isAllIn ? 'ALL-IN' : `${p.stackBB}BB`}</div>
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

        {/* Right Panel — Tabs */}
        <div style={{ width: 240, padding: '0', borderLeft: '1px solid #1e2130', background: '#0d0f18', overflowY: 'auto', flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
          {/* Tab switcher */}
          <div style={{ display: 'flex', borderBottom: '1px solid #1e2130', flexShrink: 0 }}>
            {[['analysis', 'Análise'], ['gto', 'GTO']].map(([k, l]) => (
              <button key={k} onClick={() => setRightTab(k)} style={{
                flex: 1, padding: '10px 0', fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
                background: rightTab === k ? 'rgba(99,102,241,0.08)' : 'transparent',
                color: rightTab === k ? '#818cf8' : '#4b5563',
                border: 'none', borderBottom: rightTab === k ? '2px solid #6366f1' : '2px solid transparent',
                cursor: 'pointer', textTransform: 'uppercase',
              }}>{l}</button>
            ))}
          </div>

          <div style={{ padding: '16px 14px', flex: 1, overflowY: 'auto' }}>
            {rightTab === 'analysis' && <>
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
            </>}

            {rightTab === 'gto' && <>
              {gtoLoading && <div style={{ fontSize: 11, color: '#64748b', textAlign: 'center', padding: '20px 0' }}>A procurar tree GTO...</div>}
              {!gtoLoading && (!gtoMatch?.matches || gtoMatch.matches.length === 0) && (
                <div style={{ fontSize: 11, color: '#4b5563', textAlign: 'center', padding: '20px 0' }}>
                  Nenhuma tree GTO encontrada para este spot.
                  <br /><br />
                  <span style={{ fontSize: 10, color: '#374151' }}>Importa trees na secção GTO Brain</span>
                </div>
              )}
              {!gtoLoading && gtoMatch?.matches?.length > 0 && (
                <div>
                  {/* Matches list */}
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: '#818cf8', letterSpacing: 0.5, marginBottom: 6, textTransform: 'uppercase' }}>Matches ({gtoMatch.matches.length})</div>
                    {gtoMatch.matches.map((m, mi) => (
                      <div key={mi} onClick={() => {
                        gtoApi.getNode(m.tree_id, 0).then(setGtoNode).catch(() => {})
                      }} style={{
                        padding: '6px 8px', marginBottom: 4, borderRadius: 5, cursor: 'pointer',
                        background: mi === 0 ? 'rgba(99,102,241,0.08)' : 'rgba(255,255,255,0.02)',
                        border: `1px solid ${mi === 0 ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.05)'}`,
                      }}>
                        <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600, marginBottom: 2 }}>{m.name}</div>
                        <div style={{ display: 'flex', gap: 6, fontSize: 9, color: '#64748b', flexWrap: 'wrap', marginBottom: 3 }}>
                          <span style={{ color: m.confidence > 70 ? '#22c55e' : m.confidence > 40 ? '#f59e0b' : '#ef4444', fontWeight: 700, fontSize: 11 }}>{m.confidence}%</span>
                          <span>{m.num_players}-max</span>
                          <span>{m.phase}</span>
                          <span>Δ{m.hero_stack_diff}bb</span>
                        </div>
                        {m.breakdown && (
                          <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                            {[['Fase', m.breakdown.phase], ['Pos', m.breakdown.position], ['Stack', m.breakdown.hero_stack], ['Adv.Pos', m.breakdown.active_pos], ['Adv.Stk', m.breakdown.active_stk]].map(([l, v]) => (
                              <span key={l} style={{ fontSize: 8, padding: '1px 4px', borderRadius: 2, background: v > 70 ? 'rgba(34,197,94,0.15)' : v > 40 ? 'rgba(245,158,11,0.15)' : 'rgba(239,68,68,0.15)', color: v > 70 ? '#22c55e' : v > 40 ? '#f59e0b' : '#ef4444' }}>{l}:{v}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* GTO Range Grid */}
                  {gtoNode?.hands && (() => {
                    const actions = gtoNode.actions || []
                    const actionLabels = actions.map(a => a.type === 'F' ? 'Fold' : a.type === 'C' ? 'Call' : `Raise ${a.amount ? Math.round(a.amount / (meta.bb || 1) / 100) : ''}`)
                    const actionColors = actions.map(a => a.type === 'F' ? '#ef4444' : a.type === 'C' ? '#3b82f6' : '#22c55e')
                    const RANKS = 'AKQJT98765432'

                    return (
                      <div>
                        {/* Legend */}
                        <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
                          {actions.map((a, i) => (
                            <span key={i} style={{ fontSize: 9, color: actionColors[i], background: `${actionColors[i]}15`, padding: '2px 6px', borderRadius: 3, border: `1px solid ${actionColors[i]}30` }}>
                              {actionLabels[i]}
                            </span>
                          ))}
                        </div>

                        {/* 13x13 Grid */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(13, 1fr)', gap: 1, fontSize: 7, lineHeight: 1 }}>
                          {RANKS.split('').map((r, row) =>
                            RANKS.split('').map((c, col) => {
                              let hand
                              if (row === col) hand = r + c  // pair
                              else if (row < col) hand = RANKS[row] + RANKS[col] + 's' // suited above diagonal
                              else hand = RANKS[col] + RANKS[row] + 'o' // offsuit below diagonal

                              const data = gtoNode.hands[hand]
                              if (!data) return <div key={`${row}-${col}`} style={{ width: '100%', aspectRatio: '1', background: '#111' }} />

                              const played = data.played || []
                              // Dominant action color
                              let maxIdx = 0, maxVal = 0
                              played.forEach((p, i) => { if (p > maxVal) { maxVal = p; maxIdx = i } })
                              const dominantColor = actionColors[maxIdx] || '#333'
                              const opacity = Math.max(0.15, maxVal)

                              // Mixed? Show gradient
                              const isMixed = played.filter(p => p > 0.05).length > 1

                              let bg
                              if (!isMixed) {
                                bg = `${dominantColor}${Math.round(opacity * 255).toString(16).padStart(2, '0')}`
                              } else {
                                // Create gradient segments
                                const segments = []
                                let pos = 0
                                played.forEach((p, i) => {
                                  if (p > 0.01) {
                                    segments.push(`${actionColors[i] || '#333'} ${pos * 100}% ${(pos + p) * 100}%`)
                                    pos += p
                                  }
                                })
                                bg = segments.length > 0 ? `linear-gradient(to right, ${segments.join(', ')})` : '#222'
                              }

                              return (
                                <div key={`${row}-${col}`} title={`${hand}: ${played.map((p, i) => `${actionLabels[i] || '?'} ${(p * 100).toFixed(0)}%`).join(', ')}`} style={{
                                  width: '100%', aspectRatio: '1',
                                  background: bg,
                                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                                  color: maxVal > 0.5 ? '#fff' : '#666',
                                  fontWeight: 600, fontSize: 6, borderRadius: 1,
                                  border: row === col ? '1px solid rgba(255,255,255,0.15)' : 'none',
                                }}>
                                  {hand.replace('o', '').replace('s', '')}
                                </div>
                              )
                            })
                          )}
                        </div>

                        {/* Node info */}
                        <div style={{ marginTop: 8, fontSize: 10, color: '#4b5563' }}>
                          Player {gtoNode.player} · Nó {gtoNode.node_index} · {gtoNode.is_terminal ? 'Terminal' : `${actions.length} acções`}
                          {gtoNode.path && <span> · Path: {gtoNode.path.join('→')}</span>}
                        </div>

                        {/* Hero vs GTO comparison */}
                        {heroGtoAction && gtoNode.hands && (() => {
                          const heroType = heroGtoAction.type
                          const heroTypeLabel = heroType === 'F' ? 'Fold' : heroType === 'C' ? 'Call' : 'Raise'
                          // Find the action index matching hero's action
                          const matchIdx = actions.findIndex(a => a.type === heroType)
                          // Get hero's specific hand from hand.hero_cards
                          let heroHandKey = null
                          if (hand?.hero_cards?.length === 2) {
                            const c1 = hand.hero_cards[0], c2 = hand.hero_cards[1]
                            const r1 = c1.slice(0,-1).toUpperCase(), r2 = c2.slice(0,-1).toUpperCase()
                            const s1 = c1.slice(-1).toLowerCase(), s2 = c2.slice(-1).toLowerCase()
                            const RANK_ORDER = 'AKQJT98765432'
                            const ri1 = RANK_ORDER.indexOf(r1), ri2 = RANK_ORDER.indexOf(r2)
                            if (ri1 === ri2) heroHandKey = r1 + r2
                            else if (ri1 < ri2) heroHandKey = r1 + r2 + (s1 === s2 ? 's' : 'o')
                            else heroHandKey = r2 + r1 + (s1 === s2 ? 's' : 'o')
                          }
                          const heroHandData = heroHandKey ? gtoNode.hands[heroHandKey] : null
                          let gtoFreq = 0
                          let verdict = 'unknown'
                          let verdictColor = '#64748b'
                          if (heroHandData && matchIdx >= 0) {
                            gtoFreq = (heroHandData.played[matchIdx] || 0) * 100
                            if (gtoFreq >= 70) { verdict = '✓ GTO'; verdictColor = '#22c55e' }
                            else if (gtoFreq >= 30) { verdict = '~ Misto'; verdictColor = '#f59e0b' }
                            else { verdict = '✗ Desvio'; verdictColor = '#ef4444' }
                          }
                          return (
                            <div style={{ marginTop: 10, padding: '8px 10px', borderRadius: 6, background: `${verdictColor}10`, border: `1px solid ${verdictColor}30` }}>
                              <div style={{ fontSize: 10, fontWeight: 700, color: verdictColor, letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 4 }}>Hero vs GTO</div>
                              <div style={{ fontSize: 12, color: '#f1f5f9' }}>
                                Hero: <span style={{ fontWeight: 700 }}>{heroTypeLabel}</span>
                                {heroHandKey && <span style={{ color: '#94a3b8' }}> ({heroHandKey})</span>}
                              </div>
                              {heroHandData && (
                                <div style={{ fontSize: 11, color: verdictColor, fontWeight: 700, marginTop: 2 }}>
                                  {verdict} — GTO {heroTypeLabel}: {gtoFreq.toFixed(0)}%
                                </div>
                              )}
                            </div>
                          )
                        })()}

                        {/* Navigate deeper */}
                        {actions.length > 0 && !gtoNode.is_terminal && (
                          <div style={{ marginTop: 8 }}>
                            <div style={{ fontSize: 10, fontWeight: 600, color: '#64748b', marginBottom: 4 }}>Navegar:</div>
                            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                              {actions.map((a, i) => (
                                <button key={i} onClick={() => {
                                  if (a.node != null) {
                                    gtoApi.getNode(gtoMatch.matches[0].tree_id, a.node).then(setGtoNode).catch(() => {})
                                  }
                                }} style={{
                                  padding: '3px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                                  background: `${actionColors[i]}15`, color: actionColors[i],
                                  border: `1px solid ${actionColors[i]}30`, cursor: 'pointer',
                                }}>
                                  {actionLabels[i]}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Back to root */}
                        {gtoNode.node_index !== 0 && (
                          <button onClick={() => gtoApi.getNode(gtoMatch.matches[0].tree_id, 0).then(setGtoNode).catch(() => {})} style={{
                            marginTop: 6, padding: '3px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                            background: 'rgba(255,255,255,0.04)', color: '#64748b',
                            border: '1px solid #2a2d3a', cursor: 'pointer', width: '100%',
                          }}>← Raiz</button>
                        )}
                      </div>
                    )
                  })()}
                </div>
              )}
            </>}
          </div>
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
