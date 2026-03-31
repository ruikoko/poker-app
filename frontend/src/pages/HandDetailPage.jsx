import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { hands as handsApi } from '../api/client'

const SUIT_COLORS = { h: '#ef4444', d: '#3b82f6', c: '#22c55e', s: '#e2e8f0' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }
const SUIT_BG = { h: '#7f1d1d', d: '#1e3a5f', c: '#14532d', s: '#1e293b' }
const HERO_NAMES = new Set(['hero','schadenfreud','thinvalium','sapz','misterpoker1973','cringemeariver','flightrisk','karluz','koumpounophobia','lauro dermio'])
const SEAT_ORDER = ['SB','BB','UTG','UTG1','UTG+1','UTG2','UTG+2','MP','MP1','MP+1','HJ','CO','BTN']
const STREET_COLORS = { 'PRE-FLOP': '#6366f1', 'FLOP': '#22c55e', 'TURN': '#f59e0b', 'RIVER': '#ef4444', 'SHOWDOWN': '#8b5cf6' }
const POS_COLORS = { BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa', SB: '#f59e0b', BB: '#ef4444', UTG: '#22c55e', 'UTG1': '#16a34a', 'UTG+1': '#16a34a', 'UTG2': '#15803d', 'UTG+2': '#15803d', MP: '#06b6d4', 'MP1': '#0891b2', 'MP+1': '#0891b2' }

function RCard({ card, size = 'md' }) {
  if (!card || card.length < 2) return <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 32, height: 44, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 5, fontSize: 13, color: '#4b5563' }}>?</span>
  const w = size === 'lg' ? 44 : 32, h = size === 'lg' ? 60 : 44, fs = size === 'lg' ? 17 : 13
  const rank = card.slice(0, -1).toUpperCase(), suit = card.slice(-1).toLowerCase()
  return <span style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', width: w, height: h, background: SUIT_BG[suit] || '#1e293b', border: `1.5px solid ${SUIT_COLORS[suit]}50`, borderRadius: 5, fontFamily: "'Fira Code',monospace", fontWeight: 700, fontSize: fs, color: '#fff', lineHeight: 1, userSelect: 'none', boxShadow: '0 2px 6px rgba(0,0,0,0.4)' }}><span>{rank}</span><span style={{ fontSize: fs * 0.8, color: SUIT_COLORS[suit] }}>{SUIT_SYMBOLS[suit]}</span></span>
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ color: '#4b5563' }}>—</span>
  const norm = pos.replace('+', '')
  const c = POS_COLORS[pos] || POS_COLORS[norm] || '#64748b'
  return <span style={{ display: 'inline-block', padding: '3px 10px', borderRadius: 5, fontSize: 13, fontWeight: 700, letterSpacing: 0.5, color: c, background: `${c}18`, border: `1px solid ${c}30`, minWidth: 36, textAlign: 'center' }}>{pos}</span>
}

function parseStreets(raw) {
  if (!raw) return []
  const isW = raw.includes('*** PRE-FLOP ***')
  const streetDefs = [
    { name: 'PRE-FLOP', start: isW ? '*** PRE-FLOP ***' : '*** HOLE CARDS ***', end: '*** FLOP ***' },
    { name: 'FLOP', start: '*** FLOP ***', end: '*** TURN ***' },
    { name: 'TURN', start: '*** TURN ***', end: '*** RIVER ***' },
    { name: 'RIVER', start: '*** RIVER ***', end: '*** SHOW' },
    { name: 'SHOWDOWN', start: /\*\*\* SHOW\s*DOWN \*\*\*/, end: '*** SUMMARY ***' },
  ]
  const streets = []
  for (const sd of streetDefs) {
    let si
    if (sd.start instanceof RegExp) { const m = raw.match(sd.start); si = m ? m.index : -1 }
    else { si = raw.indexOf(sd.start) }
    if (si === -1) continue
    const startLen = sd.start instanceof RegExp ? raw.match(sd.start)[0].length : sd.start.length
    let ei = raw.indexOf(sd.end, si + startLen)
    if (ei === -1) ei = raw.indexOf('*** SUMMARY ***', si)
    if (ei === -1) ei = raw.length
    const section = raw.slice(si + startLen, ei).trim()
    let board = []
    if (sd.name === 'FLOP') { const m = raw.match(/\*\*\* FLOP \*\*\* \[(.+?)\]/); if (m) board = m[1].split(' ') }
    else if (sd.name === 'TURN') { const m = raw.match(/\*\*\* TURN \*\*\* \[(.+?)\]\s*\[(.+?)\]/); if (m) board = [...m[1].split(' '), ...m[2].split(' ')] }
    else if (sd.name === 'RIVER') { const m = raw.match(/\*\*\* RIVER \*\*\* \[(.+?)\]\s*\[(.+?)\]/); if (m) board = [...m[1].split(' '), ...m[2].split(' ')] }
    const actions = []
    for (const line of section.split('\n')) {
      const t = line.trim()
      if (!t || t.startsWith('Dealt to') || t.startsWith('Main pot')) continue
      const showM = t.match(/^(.+?)(?::)?\s+shows\s+\[(.+?)\]/i)
      if (showM) { actions.push({ actor: showM[1].trim(), action: 'shows', cards: showM[2].split(' ') }); continue }
      const m = t.match(/^(.+?)(?::)?\s+(folds|checks|calls|bets|raises)(.*)$/i)
      if (m) {
        const actor = m[1].trim(), act = m[2].toLowerCase(), rest = m[3]
        let amount = 0; const amtM = rest.match(/([\d,]+)/); if (amtM) amount = parseFloat(amtM[1].replace(/,/g, ''))
        const allIn = /all-in/i.test(rest)
        const toM = rest.match(/to ([\d,]+)/)
        let label = act.charAt(0).toUpperCase() + act.slice(1)
        if (act === 'calls') label = `Call ${Math.round(amount).toLocaleString()}`
        else if (act === 'bets') label = `Bet ${Math.round(amount).toLocaleString()}`
        else if (act === 'raises') { const v = toM ? `${Math.round(amount).toLocaleString()} to ${Math.round(parseFloat(toM[1].replace(/,/g, ''))).toLocaleString()}` : Math.round(amount).toLocaleString(); label = `Raise ${v}` }
        else if (act === 'folds') label = 'Fold'
        else if (act === 'checks') label = 'Check'
        if (allIn) label += ' All-In'
        actions.push({ actor, action: act, label, amount, allIn })
      }
      const wonM = t.match(/^(.+?) collected ([\d,]+)/i)
      if (wonM) actions.push({ actor: wonM[1].trim(), action: 'collected', label: `Wins ${parseFloat(wonM[2].replace(/,/g, '')).toLocaleString()}`, amount: parseFloat(wonM[2].replace(/,/g, '')) })
    }
    streets.push({ name: sd.name, board, actions })
  }
  return streets
}

export default function HandDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [hand, setHand] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => { setLoading(true); handsApi.get(id).then(h => { setHand(h); setLoading(false) }).catch(e => { setError(e.message); setLoading(false) }) }, [id])

  if (loading) return <div style={{ padding: 60, textAlign: 'center', color: '#64748b', fontSize: 16 }}>A carregar...</div>
  if (error) return <div style={{ padding: 60, textAlign: 'center', color: '#ef4444', fontSize: 16 }}>{error}</div>
  if (!hand) return null

  const meta = hand.all_players_actions?._meta || {}
  const bb = meta.bb || 1
  const players = Object.entries(hand.all_players_actions || {})
    .filter(([k]) => k !== '_meta')
    .map(([name, info]) => ({ name, ...info }))
    .sort((a, b) => {
      const ai = SEAT_ORDER.indexOf(a.position) === -1 ? 99 : SEAT_ORDER.indexOf(a.position)
      const bi = SEAT_ORDER.indexOf(b.position) === -1 ? 99 : SEAT_ORDER.indexOf(b.position)
      return ai - bi
    })

  const streets = parseStreets(hand.raw)
  const blindsLabel = meta.sb && meta.bb ? `${Math.round(meta.sb)}/${Math.round(meta.bb)}${meta.ante ? `(${Math.round(meta.ante)})` : ''}` : ''

  let initialPot = 0
  const antes = (hand.raw || '').match(/posts the ante ([\d,]+)/g) || []
  for (const a of antes) { const n = a.match(/[\d,]+/); if (n) initialPot += parseFloat(n[0].replace(/,/g, '')) }
  const sbM = (hand.raw || '').match(/posts small blind ([\d,]+)/); if (sbM) initialPot += parseFloat(sbM[1].replace(/,/g, ''))
  const bbM2 = (hand.raw || '').match(/posts big blind ([\d,]+)/); if (bbM2) initialPot += parseFloat(bbM2[1].replace(/,/g, ''))

  const pNames = hand.player_names || {}
  const playerBounties = {}
  for (const p of (pNames.players_list || [])) {
    if (p.name && p.bounty_pct != null) playerBounties[p.name] = p.bounty_pct
    if (p.name && p.bounty != null) playerBounties[p.name] = p.bounty
  }

  const tourneyName = hand.stakes || ''
  const playedDate = hand.played_at ? new Date(hand.played_at).toLocaleString('pt-PT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''
  const resultColor = hand.result > 0 ? '#22c55e' : hand.result < 0 ? '#ef4444' : '#64748b'

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '28px 24px' }}>

      {/* ── HEADER: Back + Actions ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <button onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', color: '#818cf8', cursor: 'pointer', fontSize: 15, fontWeight: 600 }}>&larr; Voltar</button>
        <div style={{ display: 'flex', gap: 8 }}>
          {hand.raw && hand.all_players_actions && (
            <a href={`/replayer/${hand.id}`} style={{ padding: '8px 20px', borderRadius: 6, fontSize: 14, fontWeight: 700, background: '#6366f1', color: '#fff', textDecoration: 'none' }}>&#9654; Replayer</a>
          )}
          {hand.raw && (
            <button onClick={() => { navigator.clipboard.writeText(hand.raw); setCopied(true); setTimeout(() => setCopied(false), 2000) }} style={{ padding: '8px 20px', borderRadius: 6, fontSize: 14, fontWeight: 700, background: copied ? 'rgba(34,197,94,0.15)' : 'rgba(245,158,11,0.1)', color: copied ? '#22c55e' : '#f59e0b', border: `1px solid ${copied ? 'rgba(34,197,94,0.3)' : 'rgba(245,158,11,0.25)'}`, cursor: 'pointer' }}>{copied ? '✓ Copiado' : 'Copiar HH'}</button>
          )}
        </div>
      </div>

      {/* ── INFO GRID (top) ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 12 }}>
        {[
          { l: 'Torneio', v: tourneyName },
          { l: 'Blinds', v: blindsLabel || '—' },
          { l: 'Resultado', v: hand.result != null ? `${hand.result > 0 ? '+' : ''}${Number(hand.result).toFixed(1)} BB` : '—', c: resultColor },
          { l: 'Sala', v: hand.site },
          { l: 'Data', v: playedDate },
          { l: 'Posição', v: null, badge: hand.position },
          { l: 'Hand ID', v: hand.hand_id },
          { l: 'Level', v: meta.level != null ? `Lv ${meta.level}` : '—' },
          { l: 'Jogadores', v: players.length },
        ].map(({ l, v, c, badge }) => (
          <div key={l} style={{ background: '#0f1117', borderRadius: 6, padding: '10px 14px' }}>
            <div style={{ fontSize: 11, color: '#4b5563', fontWeight: 600, letterSpacing: 0.4, marginBottom: 3, textTransform: 'uppercase' }}>{l}</div>
            {badge ? <PosBadge pos={badge} /> : <div style={{ fontSize: 14, color: c || '#e2e8f0', fontWeight: 600, wordBreak: 'break-all' }}>{v || '—'}</div>}
          </div>
        ))}
      </div>

      {/* ── HERO CARDS + BOARD ── */}
      <div style={{ background: '#0f1117', borderRadius: 8, padding: '14px 20px', marginBottom: 12, display: 'flex', gap: 36, alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 12, color: '#64748b', fontWeight: 600, marginBottom: 6, textTransform: 'uppercase' }}>Hero &middot; <PosBadge pos={hand.position} /></div>
          <div style={{ display: 'flex', gap: 5 }}>
            {hand.hero_cards?.length > 0 ? hand.hero_cards.map((c, i) => <RCard key={i} card={c} size="lg" />) : <span style={{ color: '#4b5563' }}>—</span>}
          </div>
        </div>
        {hand.board?.length > 0 && (
          <div>
            <div style={{ fontSize: 12, color: '#64748b', fontWeight: 600, marginBottom: 6, textTransform: 'uppercase' }}>Board</div>
            <div style={{ display: 'flex', gap: 4 }}>{hand.board.map((c, i) => <RCard key={i} card={c} size="lg" />)}</div>
          </div>
        )}
      </div>

      {/* ── MESA ── */}
      <div style={{ background: '#0f1117', borderRadius: 8, padding: '14px 20px', marginBottom: 2 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#94a3b8', marginBottom: 10, textTransform: 'uppercase' }}>Mesa ({players.length} jogadores)</div>
        {players.map((p, i) => {
          const isHero = p.is_hero || HERO_NAMES.has(p.name.toLowerCase())
          const realName = p.real_name || p.name
          const bounty = playerBounties[realName] || p.bounty || p.bounty_pct
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px',
              borderBottom: i < players.length - 1 ? '1px solid #1e2130' : 'none',
              background: isHero ? 'rgba(99,102,241,0.05)' : 'transparent', borderRadius: 4,
            }}>
              <PosBadge pos={p.position} />
              <span style={{ fontSize: 14, fontWeight: isHero ? 700 : 500, color: isHero ? '#818cf8' : '#e2e8f0', minWidth: 140 }}>
                {realName}{isHero && <span style={{ fontSize: 9, color: '#6366f1', marginLeft: 5 }}>HERO</span>}
              </span>
              <span style={{ fontSize: 13, color: '#94a3b8', fontFamily: 'monospace', minWidth: 70, textAlign: 'right' }}>{p.stack ? Math.round(p.stack).toLocaleString() : '—'}</span>
              <span style={{ fontSize: 13, color: '#e2e8f0', fontFamily: 'monospace', fontWeight: 600, minWidth: 60, textAlign: 'right' }}>{p.stack_bb ? p.stack_bb.toFixed(1) : '—'} BB</span>
              {bounty != null && <span style={{ fontSize: 12, color: '#f59e0b', fontWeight: 700, padding: '1px 7px', borderRadius: 4, background: 'rgba(245,158,11,0.1)' }}>{typeof bounty === 'number' && bounty < 10 ? `${bounty}%` : `${bounty}€`}</span>}
            </div>
          )
        })}
      </div>

      {/* ── ACÇÕES POR STREET (continuous, no gap) ── */}
      <div style={{ background: '#0f1117', borderRadius: '0 0 8px 8px', padding: '14px 20px' }}>
        {streets.map((st, si) => {
          let streetPot = initialPot
          for (let s = 0; s < si; s++) {
            for (const a of streets[s].actions) {
              if (a.amount && (a.action === 'calls' || a.action === 'bets' || a.action === 'raises')) streetPot += a.amount
            }
          }
          const streetPotBB = (streetPot / bb).toFixed(1)
          return (
            <div key={st.name} style={{ marginBottom: si < streets.length - 1 ? 16 : 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <span style={{ padding: '3px 12px', borderRadius: 4, fontSize: 13, fontWeight: 800, color: STREET_COLORS[st.name] || '#e2e8f0', background: `${STREET_COLORS[st.name] || '#64748b'}15`, border: `1px solid ${STREET_COLORS[st.name] || '#64748b'}30` }}>{st.name}</span>
                {st.board?.length > 0 && <div style={{ display: 'flex', gap: 3 }}>{st.board.map((c, i) => <RCard key={i} card={c} />)}</div>}
                <span style={{ fontSize: 13, fontWeight: 600, fontFamily: 'monospace', marginLeft: 'auto', color: '#94a3b8', background: 'rgba(255,255,255,0.03)', padding: '2px 10px', borderRadius: 4 }}>Pot: {Math.round(streetPot).toLocaleString()} ({streetPotBB}bb)</span>
              </div>
              <div style={{ paddingLeft: 14, borderLeft: `2px solid ${STREET_COLORS[st.name] || '#2a2d3a'}35` }}>
                {st.actions.map((a, ai) => {
                  const isHero = HERO_NAMES.has(a.actor.toLowerCase())
                  const player = players.find(p => p.name === a.actor)
                  const pos = player?.position
                  const stackBB = player?.stack_bb
                  let actionColor = '#94a3b8', actionBg = 'rgba(148,163,184,0.06)'
                  if (a.action === 'folds') { actionColor = '#ef4444'; actionBg = 'rgba(239,68,68,0.06)' }
                  else if (a.action === 'checks') { actionColor = '#64748b'; actionBg = 'rgba(100,116,139,0.06)' }
                  else if (a.action === 'calls') { actionColor = '#22c55e'; actionBg = 'rgba(34,197,94,0.06)' }
                  else if (a.action === 'bets' || a.action === 'raises') { actionColor = '#f59e0b'; actionBg = 'rgba(245,158,11,0.06)' }
                  else if (a.action === 'collected') { actionColor = '#22c55e'; actionBg = 'rgba(34,197,94,0.1)' }
                  else if (a.action === 'shows') { actionColor = '#8b5cf6'; actionBg = 'rgba(139,92,246,0.06)' }
                  if (a.allIn) { actionColor = '#ef4444'; actionBg = 'rgba(239,68,68,0.12)' }
                  return (
                    <div key={ai} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderBottom: ai < st.actions.length - 1 ? '1px solid rgba(255,255,255,0.02)' : 'none' }}>
                      {pos && <PosBadge pos={pos} />}
                      <span style={{ fontSize: 14, fontWeight: isHero ? 700 : 500, color: isHero ? '#818cf8' : '#e2e8f0', minWidth: 130 }}>
                        {a.actor}{isHero && <span style={{ fontSize: 9, color: '#6366f1', marginLeft: 4 }}>HERO</span>}
                      </span>
                      {stackBB != null && <span style={{ fontSize: 12, color: '#4b5563', fontFamily: 'monospace', minWidth: 50, textAlign: 'right' }}>{stackBB.toFixed(1)}bb</span>}
                      <span style={{ fontSize: 13, fontWeight: 700, color: actionColor, padding: '2px 10px', borderRadius: 4, background: actionBg, border: `1px solid ${actionColor}15` }}>{a.label || a.action}</span>
                      {a.cards && <div style={{ display: 'flex', gap: 2 }}>{a.cards.map((c, i) => <RCard key={i} card={c} />)}</div>}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
