import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { hands as handsApi, equity } from '../api/client'

// ── Constants ────────────────────────────────────────────────────────────────
const SUIT_COLORS = { h: '#ef4444', d: '#3b82f6', c: '#22c55e', s: '#e2e8f0' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }
const SUIT_BG = { h: '#7f1d1d', d: '#1e3a5f', c: '#14532d', s: '#1e293b' }
const STREET_COLORS = { preflop: '#6366f1', flop: '#22c55e', turn: '#f59e0b', river: '#ef4444', showdown: '#8b5cf6' }
const HERO_NAMES = new Set(['hero','schadenfreud','thinvalium','sapz','misterpoker1973','cringemeariver','flightrisk','karluz','koumpounophobia','lauro dermio'])
const SEAT_ORDER = ['UTG','UTG1','UTG2','MP','MP1','HJ','CO','BTN','SB','BB']

const POSITIONS_9 = [
  { x: 50, y: 93 }, { x: 10, y: 78 }, { x: 3, y: 42 }, { x: 10, y: 8 },
  { x: 35, y: 0 }, { x: 65, y: 0 }, { x: 90, y: 8 }, { x: 97, y: 42 }, { x: 90, y: 78 },
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

// ── Card Component ───────────────────────────────────────────────────────────
function RCard({ card, faceDown, size = 'md' }) {
  const w = size === 'lg' ? 48 : size === 'md' ? 36 : 28
  const h = size === 'lg' ? 66 : size === 'md' ? 50 : 38
  const fs = size === 'lg' ? 16 : size === 'md' ? 13 : 10
  if (faceDown || !card || card.length < 2) return <div style={{ width: w, height: h, borderRadius: 5, background: 'linear-gradient(135deg,#1e40af,#7c3aed,#1e40af)', border: '1.5px solid rgba(255,255,255,0.2)', boxShadow: '0 2px 8px rgba(0,0,0,0.5)' }} />
  const rank = card.slice(0, -1).toUpperCase(), suit = card.slice(-1).toLowerCase()
  return <div style={{ width: w, height: h, borderRadius: 5, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: SUIT_BG[suit] || '#1e293b', border: `1.5px solid ${SUIT_COLORS[suit]}40`, boxShadow: '0 2px 8px rgba(0,0,0,0.5)', fontFamily: "'Fira Code',monospace", fontWeight: 700, fontSize: fs, color: '#fff', lineHeight: 1, userSelect: 'none' }}><span>{rank}</span><span style={{ fontSize: fs * 0.75, color: SUIT_COLORS[suit] }}>{SUIT_SYMBOLS[suit]}</span></div>
}

// ── HH Parser ────────────────────────────────────────────────────────────────
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
  // Winamax/PokerStars turn/river patterns
  const tmW = raw.match(/\*\*\* TURN \*\*\* \[.+?\]\s*\[(.+?)\]/)
  const tmS = raw.match(/\*\*\* TURN \*\*\*\s*\[.+? (.+?)\]/)
  if (tmW) bc.push(...tmW[1].split(' '))
  else if (tmS) bc.push(...tmS[1].split(' '))
  const rmW = raw.match(/\*\*\* RIVER \*\*\* \[.+?\]\s*\[(.+?)\]/)
  const rmS = raw.match(/\*\*\* RIVER \*\*\*\s*\[.+? (.+?)\]/)
  if (rmW) bc.push(...rmW[1].split(' '))
  else if (rmS) bc.push(...rmS[1].split(' '))

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
      else if (action === 'raises') {
        const toM = rest.match(/to ([\d,]+)/)
        const raiseTotal = toM ? parseFloat(toM[1].replace(/,/g, '')) : amount
        pot += raiseTotal
        if (pi >= 0) pState[pi].currentBet = raiseTotal
      }
      else if (action === 'checks' && pi >= 0) { pState[pi].currentBet = 0 }

      let analysis = null
      let villainAnalysis = null

      if (isH && (action === 'calls' || action === 'folds')) {
        const fb = amount; const pb = action === 'calls' ? pot - amount : pot
        if (fb > 0) analysis = { type: 'facing', potBefore: Math.round(pb), facingBet: Math.round(fb), potOdds: +(fb/(pb+fb)*100).toFixed(1), mdf: +(pb/(pb+fb)*100).toFixed(1), potBB: +(pb/bb).toFixed(1), betBB: +(fb/bb).toFixed(1) }
      } else if (isH && (action === 'bets' || action === 'raises')) {
        const pb = pot - amount
        analysis = { type: 'betting', potBefore: Math.round(pb), betSize: Math.round(amount), betToPot: pb > 0 ? +(amount/pb*100).toFixed(1) : 0, mbf: +(amount/(pb+amount)*100).toFixed(1), potBB: +(pb/bb).toFixed(1), betBB: +(amount/bb).toFixed(1) }
        // MDF do vilão quando hero aposta
        villainAnalysis = { villainMDF: +(pb/(pb+amount)*100).toFixed(1), potBefore: Math.round(pb), heroBet: Math.round(amount) }
      } else if (!isH && (action === 'bets' || action === 'raises')) {
        // Villain bets — show hero's pot odds / MDF
        const pb = pot - amount
        if (pb > 0) analysis = { type: 'facing', potBefore: Math.round(pb), facingBet: Math.round(amount), potOdds: +(amount/(pb+amount)*100).toFixed(1), mdf: +(pb/(pb+amount)*100).toFixed(1), potBB: +(pb/bb).toFixed(1), betBB: +(amount/bb).toFixed(1) }
      }

      const al = action === 'folds' ? 'folds' : action === 'checks' ? 'checks' : action === 'calls' ? `calls ${Math.round(amount).toLocaleString()}${allIn?' (all-in)':''}` : action === 'bets' ? `bets ${Math.round(amount).toLocaleString()}${allIn?' (all-in)':''}` : `raises to ${Math.round(amount).toLocaleString()}${allIn?' (all-in)':''}`
      steps.push({ street: sd.key, label: sd.label, action: al, actor, actorIdx: pi, isHero: isH, pot: Math.round(pot), potBB: +(pot/bb).toFixed(1), board: [...curBoard], ps: pState.map(p => ({...p})), analysis, villainAnalysis })
    }
  }

  // Showdown
  if (pState.filter(p => p.cards.length > 0 && !p.folded).length >= 2) {
    steps.push({ street: 'showdown', label: 'Showdown', action: 'Showdown', actor: null, actorIdx: -1, isHero: false, pot, potBB: +(pot/bb).toFixed(1), board: bc, ps: pState.map(p => ({...p})), analysis: null, villainAnalysis: null })
  }

  return { steps, heroIdx }
}

// ── Panel Row ────────────────────────────────────────────────────────────────
function PRow({ l, v, c }) {
  return <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}><span style={{ fontSize: 11, color: '#64748b' }}>{l}</span><span style={{ fontSize: 13, fontWeight: 700, color: c, fontFamily: 'monospace' }}>{v}</span></div>
}

// ── Main Replayer Page ───────────────────────────────────────────────────────
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

  useEffect(() => {
    setLoading(true)
    handsApi.get(id)
      .then(h => { setHand(h); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [id])

  const { steps, heroIdx } = hand ? parseHH(hand.raw, hand.all_players_actions) : { steps: [], heroIdx: -1 }
  const meta = hand?.all_players_actions?._meta || {}
  const step = steps[si] || steps[0]
  const ps = step?.ps || []
  const slots = getSlots(ps.length)
  const positions = ps.map((_, i) => { const idx = (i - (heroIdx >= 0 ? heroIdx : 0) + ps.length) % ps.length; return POSITIONS_9[slots[idx] || 0] })

  // Auto-play
  useEffect(() => {
    if (!playing || si >= steps.length - 1) { setPlaying(false); return }
    const t = setTimeout(() => setSi(i => i + 1), 1200)
    return () => clearTimeout(t)
  }, [playing, si, steps.length])

  // Auto equity on street change
  const calcEq = useCallback(async (boardCards, range) => {
    if (!hand?.hero_cards?.length) return
    setEqLoading(true)
    try {
      const d = await equity.calculate(hand.hero_cards, boardCards || [], range || 'random', 8000)
      setEq(d)
    } catch (e) { console.error(e) }
    finally { setEqLoading(false) }
  }, [hand?.hero_cards])

  useEffect(() => {
    if (!step || !hand?.hero_cards?.length) return
    const boardKey = (step.board || []).join(',')
    if (boardKey !== lastBoard) {
      setLastBoard(boardKey)
      calcEq(step.board, villainRange)
    }
  }, [step?.board, hand?.hero_cards, lastBoard, calcEq, villainRange])

  // Keyboard controls
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
      if (e.key === 'ArrowLeft') setSi(i => Math.max(0, i - 1))
      else if (e.key === 'ArrowRight') setSi(i => Math.min(steps.length - 1, i + 1))
      else if (e.key === ' ') { e.preventDefault(); setPlaying(p => !p) }
      else if (e.key === 'Home') setSi(0)
      else if (e.key === 'End') setSi(steps.length - 1)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [steps.length])

  const streets = [...new Set(steps.map(s => s.street))]

  const applyRange = () => {
    const r = rangeInput.trim() || 'random'
    setVillainRange(r)
    calcEq(step?.board, r)
  }

  if (loading) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#0a0c14', color: '#64748b', fontSize: 16 }}>A carregar mão #{id}...</div>
  if (error) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#0a0c14', color: '#ef4444', fontSize: 16 }}>{error}</div>
  if (!steps.length) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#0a0c14', color: '#64748b', fontSize: 16 }}>Sem Hand History para replay</div>

  const btnS = { background: 'rgba(255,255,255,0.06)', border: '1px solid #2a2d3a', borderRadius: 6, padding: '6px 12px', color: '#94a3b8', cursor: 'pointer', fontSize: 14, lineHeight: 1 }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#0a0c14', color: '#e2e8f0', overflow: 'hidden' }}>
      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 20px', background: '#111420', borderBottom: '1px solid #1e2130', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 14, padding: '4px 8px' }}>&larr; Voltar</button>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#e2e8f0', letterSpacing: 0.5 }}>REPLAYER</span>
          <span style={{ fontSize: 12, color: '#64748b' }}>Mão #{hand.id}</span>
          {meta.sb && meta.bb && <span style={{ fontSize: 12, color: '#4b5563', fontFamily: 'monospace' }}>{Math.round(meta.sb)}/{Math.round(meta.bb)}{meta.ante ? `(${Math.round(meta.ante)})` : ''}{meta.level != null ? ` Lv${meta.level}` : ''}</span>}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {hand.stakes && <span style={{ fontSize: 12, color: '#4b5563', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{hand.stakes}</span>}
          <span style={{ fontSize: 13, fontWeight: 600, color: STREET_COLORS[step.street], padding: '3px 10px', borderRadius: 5, background: `${STREET_COLORS[step.street]}15`, border: `1px solid ${STREET_COLORS[step.street]}30`, textTransform: 'uppercase' }}>{step.label}</span>
        </div>
      </div>

      {/* Main area: left panel + table + right panel */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* Left Panel — Equity */}
        <div style={{ width: 200, padding: '16px 14px', borderRight: '1px solid #1e2130', background: '#0d0f18', overflowY: 'auto', flexShrink: 0 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: '#64748b', letterSpacing: 0.5, marginBottom: 10, textTransform: 'uppercase' }}>Equity</div>
          {eq && (
            <div style={{ textAlign: 'center', marginBottom: 16 }}>
              <div style={{ fontSize: 36, fontWeight: 800, color: eq.equity > 50 ? '#22c55e' : '#ef4444', fontFamily: 'monospace', lineHeight: 1 }}>{eq.equity}%</div>
              <div style={{ fontSize: 10, color: '#4b5563', marginTop: 4 }}>vs {villainRange === 'random' ? 'random' : 'range'}</div>
              {eq.win != null && <div style={{ fontSize: 10, color: '#4b5563', marginTop: 2 }}>W:{eq.win}% T:{eq.tie}%</div>}
            </div>
          )}
          {eqLoading && <div style={{ textAlign: 'center', fontSize: 11, color: '#4b5563', marginBottom: 12 }}>A calcular...</div>}

          {/* Range input */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: '#4b5563', marginBottom: 4, textTransform: 'uppercase' }}>Range vilão</div>
            <input
              type="text"
              value={rangeInput}
              onChange={e => setRangeInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') applyRange() }}
              placeholder="random"
              style={{ width: '100%', fontSize: 11, background: '#0a0c14', border: '1px solid #2a2d3a', borderRadius: 4, color: '#e2e8f0', padding: '5px 8px', fontFamily: 'monospace', boxSizing: 'border-box' }}
            />
            <button onClick={applyRange} style={{ width: '100%', marginTop: 4, fontSize: 10, fontWeight: 600, padding: '4px 0', borderRadius: 4, background: 'rgba(34,197,94,0.12)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.25)', cursor: 'pointer' }}>Calcular</button>
          </div>

          <div style={{ fontSize: 9, color: '#374151', lineHeight: 1.4 }}>
            Ex: TT+,AKs,AKo<br/>
            22+,A2s+,KQo<br/>
            random
          </div>
        </div>

        {/* Center — Table */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ flex: 1, position: 'relative', background: 'radial-gradient(ellipse at center,#0f2318,#0a1510 40%,#080d0f)' }}>
            {/* Felt */}
            <div style={{ position: 'absolute', top: '12%', left: '12%', width: '76%', height: '76%', borderRadius: '50%', border: '3px solid #1a3828', background: 'radial-gradient(ellipse at center,#14392a,#0d2b1e 60%,#091f15)', boxShadow: 'inset 0 0 80px rgba(0,0,0,0.5)' }} />

            {/* Pot */}
            <div style={{ position: 'absolute', top: '35%', left: '50%', transform: 'translate(-50%,-50%)', textAlign: 'center', zIndex: 2 }}>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 2 }}>POT</div>
              <div style={{ fontSize: 26, fontWeight: 800, color: '#fbbf24', fontFamily: "'Fira Code',monospace", textShadow: '0 0 16px rgba(251,191,36,0.3)' }}>{step.potBB}BB</div>
              <div style={{ fontSize: 11, color: '#4b5563', fontFamily: 'monospace' }}>{step.pot?.toLocaleString()}</div>
            </div>

            {/* Board */}
            {step.board?.length > 0 && (
              <div style={{ position: 'absolute', top: '55%', left: '50%', transform: 'translate(-50%,-50%)', display: 'flex', gap: 5, zIndex: 2 }}>
                {step.board.map((c, i) => <RCard key={i} card={c} size="md" />)}
              </div>
            )}

            {/* Players */}
            {ps.map((p, i) => {
              const pos = positions[i]
              const active = step.actorIdx === i
              const bountyStr = p.bounty != null ? (typeof p.bounty === 'string' ? p.bounty.replace('€', ' EUR') : `${p.bounty} EUR`) : null
              return (
                <div key={i} style={{ position: 'absolute', left: `${pos.x}%`, top: `${pos.y}%`, transform: 'translate(-50%,-50%)', textAlign: 'center', minWidth: 95, zIndex: 3, transition: 'all 0.3s' }}>
                  {/* Cards */}
                  <div style={{ display: 'flex', gap: 2, justifyContent: 'center', marginBottom: 3 }}>
                    {p.cards?.length > 0 ? p.cards.map((c, ci) => <RCard key={ci} card={c} size={p.isHero ? 'lg' : 'sm'} />) : !p.folded ? <><RCard faceDown size="sm" /><RCard faceDown size="sm" /></> : null}
                  </div>

                  {/* Bet chip */}
                  {p.currentBet > 0 && !p.folded && (
                    <div style={{ position: 'absolute', top: p.isHero ? -20 : 'auto', bottom: p.isHero ? 'auto' : -18, left: '50%', transform: 'translateX(-50%)', fontSize: 10, fontWeight: 700, color: '#fbbf24', fontFamily: 'monospace', background: 'rgba(0,0,0,0.7)', padding: '1px 6px', borderRadius: 4, border: '1px solid rgba(251,191,36,0.3)', whiteSpace: 'nowrap', zIndex: 4 }}>
                      {Math.round(p.currentBet).toLocaleString()}
                    </div>
                  )}

                  {/* Name plate */}
                  <div style={{ background: active ? 'rgba(251,191,36,0.15)' : p.isHero ? 'rgba(99,102,241,0.12)' : 'rgba(0,0,0,0.7)', border: `1.5px solid ${active ? '#fbbf24' : p.isHero ? '#6366f1' : '#2a2d3a'}`, borderRadius: 7, padding: '3px 10px', opacity: p.folded ? 0.3 : 1, transition: 'all 0.3s' }}>
                    <div style={{ fontSize: 9, fontWeight: 700, color: p.isHero ? '#818cf8' : '#94a3b8', letterSpacing: 0.3 }}>{p.position}</div>
                    <div style={{ fontSize: 12, fontWeight: p.isHero ? 700 : 500, color: p.isHero ? '#c7d2fe' : '#e2e8f0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 90 }}>{p.name}</div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#fbbf24', fontFamily: 'monospace' }}>{p.stackBB}BB</div>
                    {bountyStr && <div style={{ fontSize: 9, color: '#f59e0b' }}>{bountyStr}</div>}
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
              <button onClick={() => setSi(0)} style={btnS} title="Início (Home)">{'\u23EE'}</button>
              <button onClick={() => setSi(i => Math.max(0, i-1))} style={btnS} title="Anterior (←)">{'\u25C0'}</button>
              <button onClick={() => setPlaying(!playing)} style={{ ...btnS, background: playing ? 'rgba(239,68,68,0.15)' : 'rgba(34,197,94,0.15)', color: playing ? '#ef4444' : '#22c55e', minWidth: 40 }} title="Play/Pause (Espaço)">{playing ? '\u23F8' : '\u25B6'}</button>
              <button onClick={() => setSi(i => Math.min(steps.length-1, i+1))} style={btnS} title="Próximo (→)">{'\u25B6'}</button>
              <button onClick={() => setSi(steps.length-1)} style={btnS} title="Fim (End)">{'\u23ED'}</button>
              <span style={{ fontSize: 11, color: '#4b5563', fontFamily: 'monospace', marginLeft: 8 }}>{si+1}/{steps.length}</span>
            </div>
            <div style={{ display: 'flex', gap: 5 }}>
              {streets.filter(s => s !== 'showdown').map(s => (
                <button key={s} onClick={() => { const idx = steps.findIndex(st => st.street === s); if (idx >= 0) setSi(idx) }} style={{ ...btnS, color: step.street === s ? STREET_COLORS[s] : '#4b5563', background: step.street === s ? `${STREET_COLORS[s]}15` : 'transparent', border: `1px solid ${step.street === s ? `${STREET_COLORS[s]}40` : '#2a2d3a'}`, fontSize: 11, fontWeight: 600, textTransform: 'uppercase' }}>{s === 'preflop' ? 'PF' : s.charAt(0).toUpperCase() + s.slice(1)}</button>
              ))}
            </div>
          </div>
        </div>

        {/* Right Panel — Analysis */}
        <div style={{ width: 200, padding: '16px 14px', borderLeft: '1px solid #1e2130', background: '#0d0f18', overflowY: 'auto', flexShrink: 0 }}>
          {/* Hero analysis */}
          {step.analysis && (
            <div style={{ marginBottom: 20 }}>
              {step.analysis.type === 'facing' ? <>
                <div style={{ fontSize: 10, fontWeight: 700, color: '#64748b', letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>
                  {step.isHero ? 'Hero Decision' : 'Hero Faces'}
                </div>
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

          {/* Villain MDF when hero bets */}
          {step.villainAnalysis && (
            <div style={{ marginBottom: 20, padding: '10px', background: 'rgba(245,158,11,0.06)', borderRadius: 6, border: '1px solid rgba(245,158,11,0.15)' }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: '#f59e0b', letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Villain Must Defend</div>
              <PRow l="MDF" v={step.villainAnalysis.villainMDF + '%'} c="#f59e0b" />
              <PRow l="vs Bet" v={Math.round(step.villainAnalysis.heroBet).toLocaleString()} c="#64748b" />
            </div>
          )}

          {/* No analysis */}
          {!step.analysis && !step.villainAnalysis && (
            <div style={{ fontSize: 11, color: '#374151', textAlign: 'center', padding: '20px 0' }}>
              Navega para uma acção para ver análise
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
