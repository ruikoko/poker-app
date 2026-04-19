import { useState, useEffect, useCallback } from 'react'
import { equity } from '../api/client'
import { HERO_NAMES } from '../heroNames'
import { parseHH } from '../lib/handParser'

const SUIT_COLORS = { h: '#ef4444', d: '#3b82f6', c: '#22c55e', s: '#e2e8f0' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }
const SUIT_BG = { h: '#7f1d1d', d: '#1e3a5f', c: '#14532d', s: '#1e293b' }
const STREET_COLORS = { preflop: '#6366f1', flop: '#22c55e', turn: '#f59e0b', river: '#ef4444', showdown: '#8b5cf6' }
const SEAT_ORDER = ['UTG','UTG1','UTG2','MP','MP1','HJ','CO','BTN','SB','BB']

function RCard({ card, faceDown, size = 'md' }) {
  const w = size === 'lg' ? 44 : size === 'md' ? 34 : 26
  const h = size === 'lg' ? 60 : size === 'md' ? 46 : 36
  const fs = size === 'lg' ? 15 : size === 'md' ? 12 : 10
  if (faceDown || !card || card.length < 2) return <div style={{ width: w, height: h, borderRadius: 4, background: 'linear-gradient(135deg,#1e40af,#7c3aed,#1e40af)', border: '1.5px solid rgba(255,255,255,0.2)', boxShadow: '0 2px 8px rgba(0,0,0,0.5)' }} />
  const rank = card.slice(0, -1).toUpperCase(), suit = card.slice(-1).toLowerCase()
  return <div style={{ width: w, height: h, borderRadius: 4, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: SUIT_BG[suit] || '#1e293b', border: `1.5px solid ${SUIT_COLORS[suit]}40`, boxShadow: '0 2px 8px rgba(0,0,0,0.5)', fontFamily: "'Fira Code',monospace", fontWeight: 700, fontSize: fs, color: '#fff', lineHeight: 1, userSelect: 'none' }}><span>{rank}</span><span style={{ fontSize: fs * 0.75, color: SUIT_COLORS[suit] }}>{SUIT_SYMBOLS[suit]}</span></div>
}

const POSITIONS_9 = [
  { x: 50, y: 92 }, { x: 12, y: 75 }, { x: 5, y: 40 }, { x: 12, y: 10 },
  { x: 38, y: 2 }, { x: 62, y: 2 }, { x: 88, y: 10 }, { x: 95, y: 40 }, { x: 88, y: 75 },
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


const btn = { background: 'rgba(255,255,255,0.05)', border: '1px solid #2a2d3a', borderRadius: 4, padding: '4px 8px', color: '#94a3b8', cursor: 'pointer', fontSize: 12, lineHeight: 1 }

// ── Visual components: dealer button and bet chips ────────────────────────

function DealerButton() {
  return (
    <div style={{
      width: 20, height: 20, borderRadius: '50%',
      background: 'radial-gradient(circle at 30% 30%, #fff, #e2e8f0 60%, #94a3b8)',
      border: '1.5px solid #64748b',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 11, fontWeight: 800, color: '#0f172a',
      fontFamily: "'Fira Code',monospace",
      boxShadow: '0 2px 6px rgba(0,0,0,0.6)',
      userSelect: 'none',
    }}>D</div>
  )
}

function ChipStack({ amount, bb, label }) {
  // Stack of 3 tiny chips + amount in BB. Label optional (SB/BB).
  const amountBB = bb > 0 ? (amount / bb).toFixed(1) : '0'
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
      <div style={{ position: 'relative', width: 22, height: 14 }}>
        {/* 3 stacked chips */}
        <div style={{ position: 'absolute', left: 0, top: 6, width: 18, height: 6, borderRadius: '50%', background: 'radial-gradient(ellipse at 50% 30%, #fbbf24, #d97706 70%, #78350f)', border: '1px solid rgba(0,0,0,0.4)', boxShadow: '0 1px 2px rgba(0,0,0,0.5)' }} />
        <div style={{ position: 'absolute', left: 2, top: 3, width: 18, height: 6, borderRadius: '50%', background: 'radial-gradient(ellipse at 50% 30%, #ef4444, #b91c1c 70%, #450a0a)', border: '1px solid rgba(0,0,0,0.4)', boxShadow: '0 1px 2px rgba(0,0,0,0.5)' }} />
        <div style={{ position: 'absolute', left: 4, top: 0, width: 18, height: 6, borderRadius: '50%', background: 'radial-gradient(ellipse at 50% 30%, #e2e8f0, #94a3b8 70%, #334155)', border: '1px solid rgba(0,0,0,0.4)', boxShadow: '0 1px 2px rgba(0,0,0,0.5)' }} />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 3, background: 'rgba(0,0,0,0.75)', padding: '1px 5px', borderRadius: 3, border: '1px solid rgba(251,191,36,0.3)' }}>
        {label && <span style={{ fontSize: 8, fontWeight: 700, color: '#f59e0b', letterSpacing: 0.3 }}>{label}</span>}
        <span style={{ fontSize: 10, fontWeight: 700, color: '#fbbf24', fontFamily: "'Fira Code',monospace", lineHeight: 1 }}>{amountBB}bb</span>
      </div>
    </div>
  )
}

export default function Replayer({ hand }) {
  const { steps, heroIdx } = parseHH(hand?.raw, hand?.all_players_actions)
  const meta = hand?.all_players_actions?._meta || {}
  const [si, setSi] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [eq, setEq] = useState(null)
  const [eqLoading, setEqLoading] = useState(false)

  const step = steps[si] || steps[0]
  const ps = step?.ps || []
  const slots = getSlots(ps.length)
  const positions = ps.map((_, i) => { const idx = (i - (heroIdx >= 0 ? heroIdx : 0) + ps.length) % ps.length; return POSITIONS_9[slots[idx] || 0] })

  useEffect(() => {
    if (!playing || si >= steps.length - 1) { setPlaying(false); return }
    const t = setTimeout(() => setSi(i => i + 1), 1200)
    return () => clearTimeout(t)
  }, [playing, si, steps.length])

  const calcEq = useCallback(async () => {
    if (!hand?.hero_cards?.length || eqLoading) return
    setEqLoading(true)
    try { const d = await equity.calculate(hand.hero_cards, step.board || [], 'random', 8000); setEq(d) }
    catch (e) { console.error(e) }
    finally { setEqLoading(false) }
  }, [hand?.hero_cards, step?.board, si])

  useEffect(() => { setEq(null) }, [si])

  const streets = [...new Set(steps.map(s => s.street))]

  if (!steps.length) return <div style={{ padding: 20, textAlign: 'center', color: '#64748b' }}>Sem HH</div>

  return (
    <div style={{ background: '#0a0c14', borderRadius: 12, overflow: 'hidden', border: '1px solid #1e2130', marginBottom: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 16px', background: '#111420', borderBottom: '1px solid #1e2130' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0', letterSpacing: 0.5 }}>REPLAYER</span>
          {meta.sb && meta.bb && <span style={{ fontSize: 11, color: '#4b5563', fontFamily: 'monospace' }}>{Math.round(meta.sb)}/{Math.round(meta.bb)}{meta.ante ? `(${Math.round(meta.ante)})` : ''}{meta.level != null ? ` Lv${meta.level}` : ''}</span>}
          {hand?.stakes && <span style={{ fontSize: 11, color: '#374151', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{hand.stakes}</span>}
        </div>
        <span style={{ fontSize: 11, fontWeight: 600, color: STREET_COLORS[step.street], padding: '2px 8px', borderRadius: 4, background: `${STREET_COLORS[step.street]}15`, border: `1px solid ${STREET_COLORS[step.street]}30`, textTransform: 'uppercase' }}>{step.label}</span>
      </div>

      {/* Table */}
      <div style={{ position: 'relative', width: '100%', paddingTop: '55%', background: 'radial-gradient(ellipse at center,#0f2318,#0a1510 40%,#080d0f)' }}>
        <div style={{ position: 'absolute', top: '15%', left: '10%', width: '80%', height: '70%', borderRadius: '50%', border: '3px solid #1a3828', background: 'radial-gradient(ellipse at center,#14392a,#0d2b1e 60%,#091f15)', boxShadow: 'inset 0 0 60px rgba(0,0,0,0.5)' }} />

        {/* Pot */}
        <div style={{ position: 'absolute', top: '38%', left: '50%', transform: 'translate(-50%,-50%)', textAlign: 'center' }}>
          <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 2 }}>POT</div>
          <div style={{ fontSize: 20, fontWeight: 800, color: '#fbbf24', fontFamily: "'Fira Code',monospace", textShadow: '0 0 12px rgba(251,191,36,0.3)' }}>{step.potBB}BB</div>
          <div style={{ fontSize: 10, color: '#4b5563', fontFamily: 'monospace' }}>{step.pot?.toLocaleString()}</div>
        </div>

        {/* Board */}
        {step.board?.length > 0 && <div style={{ position: 'absolute', top: '55%', left: '50%', transform: 'translate(-50%,-50%)', display: 'flex', gap: 4 }}>{step.board.map((c, i) => <RCard key={i} card={c} size="md" />)}</div>}

        {/* Players */}
        {ps.map((p, i) => {
          const pos = positions[i]
          const active = step.actorIdx === i
          // Chip stack position: between player and pot (pot at 50%,38%)
          const potX = 50, potY = 38
          const chipX = pos.x + (potX - pos.x) * 0.35
          const chipY = pos.y + (potY - pos.y) * 0.35
          const showChips = (p.currentBet || 0) > 0 && !p.folded
          const blindLabel = p.position === 'SB' ? 'SB' : p.position === 'BB' ? 'BB' : null
          // Dealer button position: slightly offset from player toward pot
          const dbX = pos.x + (potX - pos.x) * 0.18
          const dbY = pos.y + (potY - pos.y) * 0.18
          return (
            <div key={i}>
              {/* Dealer button on BTN, or on SB in heads-up (no BTN position) */}
              {(p.position === 'BTN' || (p.position === 'SB' && !ps.some(x => x.position === 'BTN'))) && (
                <div style={{ position: 'absolute', left: `${dbX}%`, top: `${dbY}%`, transform: 'translate(-50%,-50%)', zIndex: 3 }}>
                  <DealerButton />
                </div>
              )}
              {/* Bet chips (blinds pre-flop, then raises/calls/bets per street) */}
              {showChips && (
                <div style={{ position: 'absolute', left: `${chipX}%`, top: `${chipY}%`, transform: 'translate(-50%,-50%)', zIndex: 2 }}>
                  <ChipStack amount={p.currentBet} bb={meta.bb || 1} label={step.street === 'preflop' ? blindLabel : null} />
                </div>
              )}
              {/* Player box */}
              <div style={{ position: 'absolute', left: `${pos.x}%`, top: `${pos.y}%`, transform: 'translate(-50%,-50%)', textAlign: 'center', minWidth: 85, transition: 'all 0.3s' }}>
                <div style={{ display: 'flex', gap: 2, justifyContent: 'center', marginBottom: 3 }}>
                  {p.cards?.length > 0 ? p.cards.map((c, ci) => <RCard key={ci} card={c} size={p.isHero ? 'lg' : 'sm'} />) : !p.folded ? <><RCard faceDown size="sm" /><RCard faceDown size="sm" /></> : null}
                </div>
                <div style={{ background: active ? 'rgba(251,191,36,0.15)' : p.isHero ? 'rgba(99,102,241,0.12)' : 'rgba(0,0,0,0.6)', border: `1px solid ${active ? '#fbbf24' : p.isHero ? '#6366f1' : '#2a2d3a'}`, borderRadius: 6, padding: '3px 8px', opacity: p.folded ? 0.35 : 1, transition: 'all 0.3s' }}>
                  <div style={{ fontSize: 9, fontWeight: 700, color: p.isHero ? '#818cf8' : '#94a3b8' }}>{p.position}</div>
                  <div style={{ fontSize: 11, fontWeight: p.isHero ? 700 : 500, color: p.isHero ? '#c7d2fe' : '#e2e8f0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 85 }}>{p.name}</div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#fbbf24', fontFamily: 'monospace' }}>{p.stackBB}BB</div>
                  {p.bounty != null && <div style={{ fontSize: 9, color: '#f59e0b' }}>{typeof p.bounty === 'string' ? p.bounty.replace('€', ' EUR') : `${p.bounty} EUR`}</div>}
                </div>
              </div>
            </div>
          )
        })}

        {/* Analysis overlay */}
        {step.analysis && (
          <div style={{ position: 'absolute', top: '15%', right: '2%', width: 120, background: 'rgba(0,0,0,0.85)', borderRadius: 8, padding: '8px 10px', border: '1px solid #2a2d3a' }}>
            {step.analysis.type === 'facing' ? <>
              <div style={{ fontSize: 9, fontWeight: 700, color: '#64748b', letterSpacing: 0.5, marginBottom: 4 }}>HERO DECISION</div>
              <Row l="Pot Odds" v={step.analysis.potOdds + '%'} c="#3b82f6" />
              <Row l="MDF" v={step.analysis.mdf + '%'} c="#8b5cf6" />
              <Row l="To Call" v={step.analysis.betBB + 'bb'} c="#f59e0b" />
            </> : <>
              <div style={{ fontSize: 9, fontWeight: 700, color: '#64748b', letterSpacing: 0.5, marginBottom: 4 }}>HERO BET</div>
              <Row l="Bet/Pot" v={step.analysis.betToPot + '%'} c="#22c55e" />
              <Row l="MBF" v={step.analysis.mbf + '%'} c="#ec4899" />
              <Row l="Size" v={step.analysis.betBB + 'bb'} c="#f59e0b" />
            </>}
          </div>
        )}

        {/* Equity overlay */}
        {eq && (
          <div style={{ position: 'absolute', top: '15%', left: '2%', width: 110, background: 'rgba(0,0,0,0.85)', borderRadius: 8, padding: '8px 10px', border: '1px solid #2a2d3a' }}>
            <div style={{ fontSize: 9, fontWeight: 700, color: '#64748b', letterSpacing: 0.5, marginBottom: 4 }}>EQUITY</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: eq.equity > 50 ? '#22c55e' : '#ef4444', fontFamily: 'monospace', textAlign: 'center' }}>{eq.equity}%</div>
            <div style={{ fontSize: 9, color: '#4b5563', textAlign: 'center' }}>vs random</div>
          </div>
        )}
      </div>

      {/* Action log */}
      <div style={{ padding: '8px 16px', background: '#0d0f18', borderTop: '1px solid #1e2130', display: 'flex', alignItems: 'center', gap: 10, minHeight: 36 }}>
        {step.actor ? <>
          <span style={{ fontSize: 11, fontWeight: 600, color: step.isHero ? '#818cf8' : '#94a3b8' }}>{step.actor}</span>
          <span style={{ fontSize: 12, fontWeight: 600, color: step.action.includes('fold') ? '#ef4444' : step.action.includes('call') || step.action.includes('check') ? '#22c55e' : '#f59e0b' }}>{step.action}</span>
        </> : <span style={{ fontSize: 11, color: '#4b5563' }}>{step.action}</span>}
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 16px', background: '#111420', borderTop: '1px solid #1e2130' }}>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <button onClick={() => setSi(0)} style={btn}>{'\u23EE'}</button>
          <button onClick={() => setSi(i => Math.max(0, i-1))} style={btn}>{'\u25C0'}</button>
          <button onClick={() => setPlaying(!playing)} style={{ ...btn, background: playing ? 'rgba(239,68,68,0.15)' : 'rgba(34,197,94,0.15)', color: playing ? '#ef4444' : '#22c55e', minWidth: 36 }}>{playing ? '\u23F8' : '\u25B6'}</button>
          <button onClick={() => setSi(i => Math.min(steps.length-1, i+1))} style={btn}>{'\u25B6'}</button>
          <button onClick={() => setSi(steps.length-1)} style={btn}>{'\u23ED'}</button>
          <span style={{ fontSize: 10, color: '#4b5563', fontFamily: 'monospace', marginLeft: 6 }}>{si+1}/{steps.length}</span>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {streets.filter(s => s !== 'showdown').map(s => (
            <button key={s} onClick={() => { const idx = steps.findIndex(st => st.street === s); if (idx >= 0) setSi(idx) }} style={{ ...btn, color: step.street === s ? STREET_COLORS[s] : '#4b5563', background: step.street === s ? `${STREET_COLORS[s]}15` : 'transparent', border: `1px solid ${step.street === s ? `${STREET_COLORS[s]}40` : '#2a2d3a'}`, fontSize: 10, fontWeight: 600, textTransform: 'uppercase' }}>{s === 'preflop' ? 'PF' : s.charAt(0).toUpperCase() + s.slice(1)}</button>
          ))}
        </div>
        <button onClick={calcEq} disabled={eqLoading || !hand?.hero_cards?.length} style={{ ...btn, background: 'rgba(34,197,94,0.1)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.25)', fontSize: 10, fontWeight: 600, opacity: !hand?.hero_cards?.length ? 0.3 : 1 }}>{eqLoading ? '...' : '\u2660 Equity'}</button>
      </div>
    </div>
  )
}

function Row({ l, v, c }) {
  return <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}><span style={{ fontSize: 9, color: '#64748b' }}>{l}</span><span style={{ fontSize: 12, fontWeight: 700, color: c, fontFamily: 'monospace' }}>{v}</span></div>
}
