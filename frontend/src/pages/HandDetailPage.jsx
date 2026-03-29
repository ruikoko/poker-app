import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { hands as handsApi } from '../api/client'

const SUIT_COLORS = { h: '#ef4444', d: '#3b82f6', c: '#22c55e', s: '#e2e8f0' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }
const SUIT_BG = { h: '#7f1d1d', d: '#1e3a5f', c: '#14532d', s: '#1e293b' }
const HERO_NAMES = new Set(['hero','schadenfreud','thinvalium','sapz','misterpoker1973','cringemeariver','flightrisk','karluz','koumpounophobia','lauro dermio'])
const SEAT_ORDER = ['SB','BB','UTG','UTG1','UTG2','MP','MP1','HJ','CO','BTN']
const STREET_COLORS = { 'PRE-FLOP': '#6366f1', 'FLOP': '#22c55e', 'TURN': '#f59e0b', 'RIVER': '#ef4444', 'SHOWDOWN': '#8b5cf6' }
const POS_COLORS = { BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa', SB: '#f59e0b', BB: '#ef4444', UTG: '#22c55e', UTG1: '#16a34a', UTG2: '#15803d', MP: '#06b6d4', MP1: '#0891b2' }

function RCard({ card, size = 'md' }) {
  if (!card || card.length < 2) return <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 38, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 4, fontSize: 11, color: '#4b5563' }}>?</span>
  const w = size === 'lg' ? 38 : 28, h = size === 'lg' ? 52 : 38, fs = size === 'lg' ? 14 : 11
  const rank = card.slice(0, -1).toUpperCase(), suit = card.slice(-1).toLowerCase()
  return <span style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', width: w, height: h, background: SUIT_BG[suit] || '#1e293b', border: `1.5px solid ${SUIT_COLORS[suit]}40`, borderRadius: 4, fontFamily: "'Fira Code',monospace", fontWeight: 700, fontSize: fs, color: '#fff', lineHeight: 1, userSelect: 'none', boxShadow: '0 1px 4px rgba(0,0,0,0.3)' }}><span>{rank}</span><span style={{ fontSize: fs * 0.75, color: SUIT_COLORS[suit] }}>{SUIT_SYMBOLS[suit]}</span></span>
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ color: '#4b5563' }}>—</span>
  const c = POS_COLORS[pos] || '#64748b'
  return <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 12, fontWeight: 700, letterSpacing: 0.4, color: c, background: `${c}18`, border: `1px solid ${c}30` }}>{pos}</span>
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
    if (sd.start instanceof RegExp) {
      const m = raw.match(sd.start)
      si = m ? m.index : -1
    } else {
      si = raw.indexOf(sd.start)
    }
    if (si === -1) continue
    const startLen = sd.start instanceof RegExp ? raw.match(sd.start)[0].length : sd.start.length
    let ei = raw.indexOf(sd.end, si + startLen)
    if (ei === -1) ei = raw.indexOf('*** SUMMARY ***', si)
    if (ei === -1) ei = raw.length
    const section = raw.slice(si + startLen, ei).trim()

    // Parse board cards for this street
    let board = []
    if (sd.name === 'FLOP') { const m = raw.match(/\*\*\* FLOP \*\*\* \[(.+?)\]/); if (m) board = m[1].split(' ') }
    else if (sd.name === 'TURN') { const m = raw.match(/\*\*\* TURN \*\*\* \[(.+?)\]\s*\[(.+?)\]/); if (m) board = [...m[1].split(' '), ...m[2].split(' ')] }
    else if (sd.name === 'RIVER') { const m = raw.match(/\*\*\* RIVER \*\*\* \[(.+?)\]\s*\[(.+?)\]/); if (m) board = [...m[1].split(' '), ...m[2].split(' ')] }

    // Parse actions
    const actions = []
    for (const line of section.split('\n')) {
      const t = line.trim()
      if (!t || t.startsWith('Dealt to')) continue
      const showM = t.match(/^(.+?)(?::)?\s+shows\s+\[(.+?)\]/i)
      if (showM) { actions.push({ actor: showM[1].trim(), action: 'shows', cards: showM[2].split(' ') }); continue }
      const m = t.match(/^(.+?)(?::)?\s+(folds|checks|calls|bets|raises)(.*)$/i)
      if (m) {
        const actor = m[1].trim(), act = m[2].toLowerCase(), rest = m[3]
        let amount = 0; const amtM = rest.match(/([\d,]+)/); if (amtM) amount = parseFloat(amtM[1].replace(/,/g, ''))
        const allIn = /all-in/i.test(rest)
        const toM = rest.match(/to ([\d,]+)/)
        let label = act
        if (act === 'calls') label = `calls ${Math.round(amount).toLocaleString()}`
        else if (act === 'bets') label = `bets ${Math.round(amount).toLocaleString()}`
        else if (act === 'raises') label = `raises ${toM ? Math.round(parseFloat(toM[1].replace(/,/g, ''))).toLocaleString() : Math.round(amount).toLocaleString()}${toM ? '' : ''}`
        if (allIn) label += ' (all-in)'
        actions.push({ actor, action: act, label, amount, allIn })
      }
      // Collected/won lines
      const wonM = t.match(/^(.+?) collected ([\d,]+)/i)
      if (wonM) actions.push({ actor: wonM[1].trim(), action: 'collected', label: `collected ${parseFloat(wonM[2].replace(/,/g, '')).toLocaleString()}`, amount: parseFloat(wonM[2].replace(/,/g, '')) })
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

  useEffect(() => { setLoading(true); handsApi.get(id).then(h => { setHand(h); setLoading(false) }).catch(e => { setError(e.message); setLoading(false) }) }, [id])

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>A carregar mão #{id}...</div>
  if (error) return <div style={{ padding: 40, textAlign: 'center', color: '#ef4444' }}>{error}</div>
  if (!hand) return null

  const meta = hand.all_players_actions?._meta || {}
  const bb = meta.bb || 1
  const players = Object.entries(hand.all_players_actions || {})
    .filter(([k]) => k !== '_meta')
    .map(([name, info]) => ({ name, ...info }))
    .sort((a, b) => (SEAT_ORDER.indexOf(a.position) === -1 ? 99 : SEAT_ORDER.indexOf(a.position)) - (SEAT_ORDER.indexOf(b.position) === -1 ? 99 : SEAT_ORDER.indexOf(b.position)))

  const streets = parseStreets(hand.raw)
  const blindsLabel = meta.sb && meta.bb ? `${Math.round(meta.sb)}/${Math.round(meta.bb)}${meta.ante ? `(${Math.round(meta.ante)})` : ''}` : ''

  // Compute pot per street
  let runningPot = 0
  const antes = (hand.raw || '').match(/posts the ante ([\d,]+)/g) || []
  for (const a of antes) { const n = a.match(/[\d,]+/); if (n) runningPot += parseFloat(n[0].replace(/,/g, '')) }
  const sbM = (hand.raw || '').match(/posts small blind ([\d,]+)/); if (sbM) runningPot += parseFloat(sbM[1].replace(/,/g, ''))
  const bbM2 = (hand.raw || '').match(/posts big blind ([\d,]+)/); if (bbM2) runningPot += parseFloat(bbM2[1].replace(/,/g, ''))

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '24px 20px' }}>
      {/* Back */}
      <button onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 14, marginBottom: 16 }}>&larr; Voltar</button>

      {/* Hero cards + Board */}
      <div style={{ background: '#0f1117', borderRadius: 10, padding: '16px 20px', marginBottom: 20, display: 'flex', gap: 32, alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 12, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Hero &middot; <PosBadge pos={hand.position} /></div>
          <div style={{ display: 'flex', gap: 5 }}>
            {hand.hero_cards?.length > 0 ? hand.hero_cards.map((c, i) => <RCard key={i} card={c} size="lg" />) : <span style={{ color: '#4b5563' }}>—</span>}
          </div>
        </div>
        {hand.board?.length > 0 && (
          <div>
            <div style={{ fontSize: 12, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Board</div>
            <div style={{ display: 'flex', gap: 4 }}>{hand.board.map((c, i) => <RCard key={i} card={c} size="lg" />)}</div>
          </div>
        )}
      </div>

      {/* Hand History by street */}
      <div style={{ background: '#0f1117', borderRadius: 10, padding: '16px 20px', marginBottom: 20 }}>
        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
          HAND HISTORY
          {blindsLabel && <span style={{ fontSize: 12, color: '#4b5563', fontFamily: 'monospace' }}>{blindsLabel}</span>}
        </div>

        {streets.map((st, si) => {
          // Calculate pot at start of this street
          let streetPot = runningPot
          for (let s = 0; s < si; s++) {
            for (const a of streets[s].actions) {
              if (a.amount && (a.action === 'calls' || a.action === 'bets' || a.action === 'raises')) streetPot += a.amount
            }
          }

          return (
            <div key={st.name} style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <span style={{ display: 'inline-block', padding: '3px 10px', borderRadius: 4, fontSize: 12, fontWeight: 700, color: STREET_COLORS[st.name] || '#e2e8f0', background: `${STREET_COLORS[st.name] || '#64748b'}15`, border: `1px solid ${STREET_COLORS[st.name] || '#64748b'}30` }}>{st.name}</span>
                {st.board?.length > 0 && <div style={{ display: 'flex', gap: 3 }}>{st.board.map((c, i) => <RCard key={i} card={c} />)}</div>}
                <span style={{ fontSize: 11, color: '#4b5563', fontFamily: 'monospace' }}>Pot: {Math.round(streetPot).toLocaleString()} ({(streetPot/bb).toFixed(1)}bb)</span>
              </div>
              <div style={{ paddingLeft: 12, borderLeft: `2px solid ${STREET_COLORS[st.name] || '#2a2d3a'}30` }}>
                {st.actions.map((a, ai) => {
                  const isHero = HERO_NAMES.has(a.actor.toLowerCase())
                  const player = players.find(p => p.name === a.actor)
                  const pos = player?.position
                  const stackBB = player?.stack_bb

                  let actionColor = '#94a3b8'
                  if (a.action === 'folds') actionColor = '#ef4444'
                  else if (a.action === 'checks' || a.action === 'calls') actionColor = '#22c55e'
                  else if (a.action === 'bets' || a.action === 'raises') actionColor = '#f59e0b'
                  else if (a.action === 'collected') actionColor = '#22c55e'
                  else if (a.action === 'shows') actionColor = '#8b5cf6'

                  return (
                    <div key={ai} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: ai < st.actions.length - 1 ? '1px solid rgba(255,255,255,0.03)' : 'none' }}>
                      {pos && <PosBadge pos={pos} />}
                      <span style={{ fontSize: 13, fontWeight: isHero ? 700 : 500, color: isHero ? '#818cf8' : '#e2e8f0', minWidth: 110 }}>
                        {a.actor}{isHero && <span style={{ fontSize: 9, color: '#6366f1', marginLeft: 4 }}>(HERO)</span>}
                      </span>
                      {stackBB != null && <span style={{ fontSize: 11, color: '#4b5563', fontFamily: 'monospace', minWidth: 50 }}>{stackBB.toFixed(1)}bb</span>}
                      <span style={{ fontSize: 13, fontWeight: 600, color: actionColor, padding: '2px 8px', borderRadius: 4, background: `${actionColor}10` }}>
                        {a.label || a.action}
                      </span>
                      {a.cards && <div style={{ display: 'flex', gap: 2 }}>{a.cards.map((c, i) => <RCard key={i} card={c} />)}</div>}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      {/* Mesa — Players table */}
      <div style={{ background: '#0f1117', borderRadius: 10, padding: '16px 20px', marginBottom: 20 }}>
        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>MESA ({players.length} JOGADORES)</div>
        {players.map((p, i) => {
          const isHero = p.is_hero || HERO_NAMES.has(p.name.toLowerCase())
          const bountyStr = p.bounty != null ? (typeof p.bounty === 'string' ? p.bounty.replace('€', ' EUR') : `${p.bounty} EUR`) : null
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px', borderBottom: i < players.length - 1 ? '1px solid #1e2130' : 'none', background: isHero ? 'rgba(99,102,241,0.04)' : 'transparent', borderRadius: 4 }}>
              <PosBadge pos={p.position} />
              <span style={{ fontSize: 13, fontWeight: isHero ? 700 : 500, color: isHero ? '#818cf8' : '#e2e8f0', minWidth: 130 }}>
                {p.real_name || p.name}{isHero && <span style={{ fontSize: 10, color: '#6366f1', marginLeft: 4 }}>(HERO)</span>}
              </span>
              <span style={{ fontSize: 12, color: '#4b5563', fontFamily: 'monospace' }}>{p.stack ? Math.round(p.stack).toLocaleString() : '—'}</span>
              <span style={{ fontSize: 12, color: '#94a3b8', fontFamily: 'monospace' }}>{p.stack_bb ? p.stack_bb.toFixed(1) : '—'} BB</span>
              {bountyStr && <span style={{ fontSize: 12, color: '#f59e0b', fontWeight: 600 }}>{bountyStr}</span>}
            </div>
          )
        })}
      </div>

      {/* Info grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px', marginBottom: 20 }}>
        {[
          { l: 'Sala', v: hand.site },
          { l: 'Data', v: hand.played_at ? hand.played_at.slice(0, 10) : '—' },
          { l: 'Resultado', v: hand.result != null ? `${hand.result > 0 ? '+' : ''}${Number(hand.result).toFixed(1)} BB` : '—', c: hand.result > 0 ? '#22c55e' : hand.result < 0 ? '#ef4444' : '#64748b' },
          { l: 'Posição', v: hand.position },
          { l: 'Torneio', v: hand.stakes },
          { l: 'Hand ID', v: hand.hand_id },
          { l: 'Blinds', v: blindsLabel || '—' },
          { l: 'Level', v: meta.level != null ? `Lv${meta.level}` : '—' },
          { l: 'Jogadores', v: players.length },
        ].map(({ l, v, c }) => (
          <div key={l} style={{ background: '#0f1117', borderRadius: 6, padding: '10px 14px' }}>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.4, marginBottom: 4, textTransform: 'uppercase' }}>{l}</div>
            <div style={{ fontSize: 13, color: c || '#e2e8f0', fontWeight: 600 }}>{v || '—'}</div>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {hand.raw && hand.all_players_actions && (
          <a href={`/replayer/${hand.id}`} style={{ padding: '8px 18px', borderRadius: 6, fontSize: 13, fontWeight: 600, background: '#6366f1', color: '#fff', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 6 }}>&#9654; Replayer</a>
        )}
      </div>
    </div>
  )
}
