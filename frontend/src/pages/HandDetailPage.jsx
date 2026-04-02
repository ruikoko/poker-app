import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { hands as handsApi } from '../api/client'

const SUIT_COLORS = { h: '#ef4444', d: '#3b82f6', c: '#22c55e', s: '#e2e8f0' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }
const SUIT_BG = { h: '#7f1d1d', d: '#1e3a5f', c: '#14532d', s: '#1e293b' }
const HERO_NAMES = new Set(['hero','schadenfreud','thinvalium','sapz','misterpoker1973','cringemeariver','flightrisk','karluz','koumpounophobia','lauro dermio','kokonakueka'])
const SEAT_ORDER = ['SB','BB','UTG','UTG1','UTG+1','UTG2','UTG+2','MP','MP1','MP+1','HJ','CO','BTN']
const STREET_COLORS = { 'PRE-FLOP': '#6366f1', 'FLOP': '#22c55e', 'TURN': '#f59e0b', 'RIVER': '#ef4444', 'SHOWDOWN': '#8b5cf6' }
const POS_COLORS = { BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa', SB: '#f59e0b', BB: '#ef4444', UTG: '#22c55e', 'UTG1': '#16a34a', 'UTG+1': '#16a34a', 'UTG2': '#15803d', 'UTG+2': '#15803d', MP: '#06b6d4', 'MP1': '#0891b2', 'MP+1': '#0891b2' }
const BLIND_POSITIONS = new Set(['SB', 'BB'])

function RCard({ card, size = 'md' }) {
  if (!card || card.length < 2) return <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 36, height: 50, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 5, fontSize: 14, color: '#4b5563' }}>?</span>
  const w = size === 'lg' ? 48 : 36, h = size === 'lg' ? 66 : 50, fs = size === 'lg' ? 19 : 15
  const rank = card.slice(0, -1).toUpperCase(), suit = card.slice(-1).toLowerCase()
  return <span style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', width: w, height: h, background: SUIT_BG[suit] || '#1e293b', border: `1.5px solid ${SUIT_COLORS[suit]}50`, borderRadius: 5, fontFamily: "'Fira Code',monospace", fontWeight: 700, fontSize: fs, color: '#fff', lineHeight: 1, userSelect: 'none', boxShadow: '0 2px 6px rgba(0,0,0,0.4)' }}><span>{rank}</span><span style={{ fontSize: fs * 0.8, color: SUIT_COLORS[suit] }}>{SUIT_SYMBOLS[suit]}</span></span>
}

// PosBadge: SB/BB with colored bg, rest white bg with colored text
function PosBadge({ pos }) {
  if (!pos) return <span style={{ display: 'inline-block', width: 52, textAlign: 'center', color: '#4b5563' }}>—</span>
  const norm = pos.replace('+', '')
  const c = POS_COLORS[pos] || POS_COLORS[norm] || '#64748b'
  const isBlind = BLIND_POSITIONS.has(pos)
  return <span style={{
    display: 'inline-block', width: 52, padding: '4px 0', borderRadius: 5,
    fontSize: 13, fontWeight: 700, letterSpacing: 0.5, textAlign: 'center',
    color: isBlind ? '#fff' : c,
    background: isBlind ? c : '#e2e8f0',
    border: `1px solid ${isBlind ? c : '#e2e8f0'}`,
  }}>{pos}</span>
}

function parseStreets(raw, nameMap = {}) {
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
      if (showM) { const actor = nameMap[showM[1].trim()] || showM[1].trim(); actions.push({ actor, action: 'shows', cards: showM[2].split(' ') }); continue }
      const m = t.match(/^(.+?)(?::)?\s+(folds|checks|calls|bets|raises)(.*)$/i)
      if (m) {
        const rawActor = m[1].trim()
        const actor = nameMap[rawActor] || rawActor
        const act = m[2].toLowerCase(), rest = m[3]
        let amount = 0; const amtM = rest.match(/([\d,]+)/); if (amtM) amount = parseFloat(amtM[1].replace(/,/g, ''))
        const allIn = /all-in/i.test(rest)
        const toM = rest.match(/to ([\d,]+)/)
        const raiseTo = toM ? parseFloat(toM[1].replace(/,/g, '')) : 0
        let label = act.charAt(0).toUpperCase() + act.slice(1)
        if (act === 'calls') label = `calls ${Math.round(amount).toLocaleString()}`
        else if (act === 'bets') label = `bets ${Math.round(amount).toLocaleString()}`
        else if (act === 'raises') label = `raises ${Math.round(amount).toLocaleString()} to ${Math.round(raiseTo || amount).toLocaleString()}`
        else if (act === 'folds') label = 'folds'
        else if (act === 'checks') label = 'checks'
        if (allIn) label += ' and is all-in'
        actions.push({ actor, action: act, label, amount, raiseTo, allIn })
      }
      const wonM = t.match(/^(.+?) collected ([\d,]+)/i)
      if (wonM) { const actor = nameMap[wonM[1].trim()] || wonM[1].trim(); actions.push({ actor, action: 'collected', label: `collected ${parseFloat(wonM[2].replace(/,/g, '')).toLocaleString()}`, amount: parseFloat(wonM[2].replace(/,/g, '')) }) }
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

  const nameMap = {}
  const apa = hand.all_players_actions || {}
  const seatLines = (hand.raw || '').match(/Seat \d+: .+? \([\d,]+(?:\s+in chips)?\)/g) || []
  for (const line of seatLines) {
    const sm = line.match(/Seat (\d+): (.+?) \(/)
    if (sm) {
      const anonName = sm[2].trim()
      for (const [realName, info] of Object.entries(apa)) {
        if (realName === '_meta') continue
        if (info && info.seat === parseInt(sm[1])) {
          if (realName !== anonName) nameMap[anonName] = realName
          break
        }
      }
    }
  }
  const pnAnon = (hand.player_names || {}).anon_map || {}
  for (const [k, v] of Object.entries(pnAnon)) { if (k !== v) nameMap[k] = v }

  const streets = parseStreets(hand.raw, nameMap)
  const blindsLabel = meta.sb && meta.bb ? `${Math.round(meta.sb)}/${Math.round(meta.bb)}${meta.ante ? `(${Math.round(meta.ante)})` : ''}` : ''

  // Initial pot = antes + blinds only
  let initialPot = 0
  const anteMatches = (hand.raw || '').match(/posts\s+(?:the\s+)?ante\s+([\d,]+)/gi) || []
  for (const a of anteMatches) { const n = a.match(/([\d,]+)/); if (n) initialPot += parseFloat(n[0].replace(/,/g, '')) }
  const sbMatch = (hand.raw || '').match(/posts\s+(?:the\s+)?small blind\s+([\d,]+)/i)
  if (sbMatch) initialPot += parseFloat(sbMatch[1].replace(/,/g, ''))
  const bbMatch = (hand.raw || '').match(/posts\s+(?:the\s+)?big blind\s+([\d,]+)/i)
  if (bbMatch) initialPot += parseFloat(bbMatch[1].replace(/,/g, ''))

  const pNames = hand.player_names || {}
  const playerBounties = {}
  for (const p of (pNames.players_list || [])) {
    if (p.name && p.bounty != null) playerBounties[p.name] = p.bounty
    if (p.name && p.bounty_pct != null) playerBounties[p.name] = p.bounty_pct
  }
  // Also get bounties from raw HH
  const bountyLines = (hand.raw || '').match(/Seat \d+: .+?\([\d,]+.*?(\d+(?:\.\d+)?)\s*[€$]?\s*bounty\)/gi) || []
  for (const bl of bountyLines) {
    const bm = bl.match(/Seat \d+: (.+?)\s*\([\d,]+.*?(\d+(?:\.\d+)?)\s*[€$]?\s*bounty\)/i)
    if (bm) {
      const pName = nameMap[bm[1].trim()] || bm[1].trim()
      if (!playerBounties[pName]) playerBounties[pName] = parseFloat(bm[2])
    }
  }

  const tourneyName = hand.stakes || ''
  const playedDate = hand.played_at ? hand.played_at.slice(0, 10) + ', ' + hand.played_at.slice(11, 16) : ''
  const resultColor = hand.result > 0 ? '#22c55e' : hand.result < 0 ? '#ef4444' : '#64748b'

  // Extract tournament ID for HRC Ninja (Winamax)
  const isWinamax = hand.site === 'Winamax'
  let tournamentId = ''
  if (isWinamax) {
    const tidM = (hand.raw || '').match(/\((\d{8,})\)#/)
    if (tidM) tournamentId = tidM[1]
  }

  return (
    <div style={{ maxWidth: 880, margin: '0 auto', padding: '28px 24px' }}>

      {/* ── HEADER ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <button onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', color: '#818cf8', cursor: 'pointer', fontSize: 16, fontWeight: 600 }}>&larr; Voltar</button>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {hand.raw && hand.all_players_actions && (
            <a href={`/replayer/${hand.id}`} style={{ padding: '8px 20px', borderRadius: 6, fontSize: 14, fontWeight: 700, background: '#6366f1', color: '#fff', textDecoration: 'none' }}>&#9654; Replayer</a>
          )}
          {hand.raw && (
            <button onClick={() => { navigator.clipboard.writeText(hand.raw); setCopied(true); setTimeout(() => setCopied(false), 2000) }} style={{ padding: '8px 20px', borderRadius: 6, fontSize: 14, fontWeight: 700, background: copied ? 'rgba(34,197,94,0.15)' : 'rgba(245,158,11,0.1)', color: copied ? '#22c55e' : '#f59e0b', border: `1px solid ${copied ? 'rgba(34,197,94,0.3)' : 'rgba(245,158,11,0.25)'}`, cursor: 'pointer' }}>{copied ? '✓ Copiado' : 'Copiar HH'}</button>
          )}
          {isWinamax && tournamentId && (
            <button onClick={() => { navigator.clipboard.writeText(tournamentId); window.open('https://hrc.ninja/create-structure/', '_blank') }} style={{ padding: '8px 16px', borderRadius: 6, fontSize: 14, fontWeight: 700, background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.25)', cursor: 'pointer' }}>W HRC Ninja</button>
          )}
          <a href={`/hand/${hand.id}`} target="_blank" rel="noopener noreferrer" style={{ padding: '8px 20px', borderRadius: 6, fontSize: 14, fontWeight: 700, background: 'rgba(245,158,11,0.1)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.25)', textDecoration: 'none' }}>Detalhe</a>
        </div>
      </div>

      {/* ── INFO GRID ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 14 }}>
        {[
          { l: 'SALA', v: hand.site },
          { l: 'DATA', v: playedDate },
          { l: 'RESULTADO', v: hand.result != null ? `${hand.result > 0 ? '+' : ''}${Number(hand.result).toFixed(1)} BB` : '—', c: resultColor, big: true },
          { l: 'POSIÇÃO', v: null, badge: hand.position },
          { l: 'TORNEIO', v: tourneyName },
          { l: 'HAND ID', v: hand.hand_id },
          { l: 'BLINDS', v: blindsLabel || '—' },
          { l: 'LEVEL', v: meta.level != null ? `Lv ${meta.level}` : '—' },
          { l: 'JOGADORES', v: players.length },
        ].map(({ l, v, c, badge, big }) => (
          <div key={l} style={{ background: '#0f1117', borderRadius: 6, padding: '12px 16px' }}>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 700, letterSpacing: 0.5, marginBottom: 4 }}>{l}</div>
            {badge ? <PosBadge pos={badge} /> : <div style={{ fontSize: big ? 18 : 15, color: c || '#f1f5f9', fontWeight: 700, wordBreak: 'break-all' }}>{v || '—'}</div>}
          </div>
        ))}
      </div>

      {/* ── HERO CARDS + BOARD ── */}
      <div style={{ background: '#0f1117', borderRadius: 8, padding: '16px 20px', marginBottom: 14, display: 'flex', gap: 40, alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 13, color: '#94a3b8', fontWeight: 700, marginBottom: 8 }}>HERO &middot; <PosBadge pos={hand.position} /></div>
          <div style={{ display: 'flex', gap: 6 }}>
            {hand.hero_cards?.length > 0 ? hand.hero_cards.map((c, i) => <RCard key={i} card={c} size="lg" />) : <span style={{ color: '#4b5563' }}>—</span>}
          </div>
        </div>
        {hand.board?.length > 0 && (
          <div>
            <div style={{ fontSize: 13, color: '#94a3b8', fontWeight: 700, marginBottom: 8 }}>BOARD</div>
            <div style={{ display: 'flex', gap: 5 }}>{hand.board.map((c, i) => <RCard key={i} card={c} size="lg" />)}</div>
          </div>
        )}
      </div>

      {/* ── MESA + HAND HISTORY ── */}
      <div style={{ background: '#0f1117', borderRadius: 8, overflow: 'hidden' }}>
        {/* Mesa — aligned columns */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #1a1d2a' }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#94a3b8', marginBottom: 12 }}>MESA ({players.length} JOGADORES)</div>
          {players.map((p, i) => {
            const isHero = p.is_hero || HERO_NAMES.has(p.name.toLowerCase())
            const realName = p.real_name || p.name
            const bounty = playerBounties[realName] || p.bounty || p.bounty_pct
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', padding: '8px 14px',
                borderBottom: i < players.length - 1 ? '1px solid #14171f' : 'none',
                background: isHero ? 'rgba(99,102,241,0.05)' : 'transparent', borderRadius: 4,
              }}>
                <div style={{ width: 58, flexShrink: 0 }}><PosBadge pos={p.position} /></div>
                <div style={{ width: 170, flexShrink: 0 }}>
                  <span style={{ fontSize: 15, fontWeight: isHero ? 700 : 600, color: '#0a0c14', background: isHero ? '#a5b4fc' : '#fbbf24', padding: '2px 8px', borderRadius: 4, display: 'inline-block' }}>
                    {realName}{isHero && <span style={{ fontSize: 9, fontWeight: 700, color: '#4338ca', marginLeft: 4 }}>HERO</span>}
                  </span>
                </div>
                <div style={{ width: 80, flexShrink: 0, textAlign: 'right', fontSize: 14, color: '#64748b', fontFamily: 'monospace' }}>{p.stack ? Math.round(p.stack).toLocaleString() : '—'}</div>
                <div style={{ width: 70, flexShrink: 0, textAlign: 'right', fontSize: 15, color: '#f97316', fontFamily: 'monospace', fontWeight: 700 }}>{p.stack_bb ? p.stack_bb.toFixed(1) : '—'} BB</div>
                <div style={{ width: 70, flexShrink: 0, textAlign: 'right' }}>
                  {bounty != null && <span style={{ fontSize: 13, color: '#1e3a5f', fontWeight: 700, padding: '2px 8px', borderRadius: 4, background: 'rgba(30,58,95,0.15)', border: '1px solid rgba(30,58,95,0.25)' }}>{typeof bounty === 'number' && bounty < 10 ? `${bounty}%` : `${bounty}€`}</span>}
                </div>
              </div>
            )
          })}
        </div>

        {/* Tags */}
        {hand.tags?.length > 0 && (
          <div style={{ padding: '10px 20px', borderBottom: '1px solid #1a1d2a', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {hand.tags.map(t => <span key={t} style={{ fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 4, color: '#22c55e', background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.2)' }}>#{t}</span>)}
          </div>
        )}

        {/* HAND HISTORY — with correct pot and stack tracking */}
        <div style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#94a3b8', marginBottom: 6 }}>HAND HISTORY <span style={{ fontWeight: 400, color: '#4b5563', fontSize: 12 }}>{blindsLabel} LV {meta.level || '?'}</span></div>
          {(() => {
            // Stack tracking
            const stacks = {}
            players.forEach(p => { stacks[p.name] = { stack: p.stack || 0, invested: 0 } })
            const resolve = (n) => nameMap[n] || n

            // Deduct antes and blinds from stacks
            const anteLines = (hand.raw || '').match(/(.+?)(?::)?\s+posts\s+(?:the\s+)?ante\s+([\d,]+)/gi) || []
            for (const line of anteLines) {
              const m = line.match(/^(.+?)(?::)?\s+posts\s+(?:the\s+)?ante\s+([\d,]+)/i)
              if (m) { const rn = resolve(m[1].trim()); if (stacks[rn]) stacks[rn].stack -= parseFloat(m[2].replace(/,/g, '')) }
            }
            const sbLine = (hand.raw || '').match(/(.+?)(?::)?\s+posts\s+(?:the\s+)?small blind\s+([\d,]+)/i)
            if (sbLine) { const rn = resolve(sbLine[1].trim()); if (stacks[rn]) { stacks[rn].stack -= parseFloat(sbLine[2].replace(/,/g, '')); stacks[rn].invested = parseFloat(sbLine[2].replace(/,/g, '')) } }
            const bbLine = (hand.raw || '').match(/(.+?)(?::)?\s+posts\s+(?:the\s+)?big blind\s+([\d,]+)/i)
            if (bbLine) { const rn = resolve(bbLine[1].trim()); if (stacks[rn]) { stacks[rn].stack -= parseFloat(bbLine[2].replace(/,/g, '')); stacks[rn].invested = parseFloat(bbLine[2].replace(/,/g, '')) } }

            // Calculate pot BEFORE each street
            let runningPot = initialPot
            const streetPots = []
            for (let si = 0; si < streets.length; si++) {
              streetPots.push(runningPot)
              // Add all actions in this street to running pot for next street
              for (const a of streets[si].actions) {
                if (a.action === 'calls') runningPot += a.amount
                else if (a.action === 'bets') runningPot += a.amount
                else if (a.action === 'raises') runningPot += (a.raiseTo || a.amount)
              }
            }

            return streets.map((st, si) => {
              const potBeforeStreet = streetPots[si] || 0
              const potBB = (potBeforeStreet / bb).toFixed(1)

              // Reset invested per street (except preflop)
              if (si > 0) {
                Object.keys(stacks).forEach(n => { stacks[n].invested = 0 })
              }

              return (
                <div key={st.name} style={{ marginBottom: si < streets.length - 1 ? 18 : 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                    <span style={{ padding: '4px 14px', borderRadius: 5, fontSize: 14, fontWeight: 800, color: STREET_COLORS[st.name] || '#f1f5f9', background: `${STREET_COLORS[st.name] || '#64748b'}15`, border: `1px solid ${STREET_COLORS[st.name] || '#64748b'}30` }}>{st.name}</span>
                    {st.board?.length > 0 && <div style={{ display: 'flex', gap: 4 }}>{st.board.map((c, i) => <RCard key={i} card={c} />)}</div>}
                    <span style={{ fontSize: 14, fontWeight: 700, fontFamily: 'monospace', marginLeft: 'auto', color: '#94a3b8', background: 'rgba(255,255,255,0.03)', padding: '3px 12px', borderRadius: 4 }}>Pot: {Math.round(potBeforeStreet).toLocaleString()} ({potBB}bb)</span>
                  </div>
                  <div style={{ paddingLeft: 16, borderLeft: `3px solid ${STREET_COLORS[st.name] || '#2a2d3a'}30` }}>
                    {st.actions.map((a, ai) => {
                      const isHero = HERO_NAMES.has(a.actor.toLowerCase())
                      const player = players.find(p => p.name === a.actor)
                      const pos = player?.position
                      const bounty = player ? (playerBounties[player.real_name || player.name] || player.bounty) : null

                      // Update stack BEFORE displaying
                      const s = stacks[a.actor]
                      let raiseTo = a.raiseTo || 0
                      if (s && a.action === 'calls') { s.stack -= a.amount; s.invested += a.amount }
                      else if (s && a.action === 'bets') { s.stack -= a.amount; s.invested += a.amount }
                      else if (s && a.action === 'raises') {
                        if (!raiseTo) { const toM = a.label.match(/to ([\d,]+)/); raiseTo = toM ? parseFloat(toM[1].replace(/,/g, '')) : a.amount }
                        const additional = raiseTo - s.invested
                        if (additional > 0) s.stack -= additional
                        s.invested = raiseTo
                      }

                      const currentStackBB = s ? (s.stack / bb).toFixed(1) : '—'

                      // BB label for actions
                      let bbLabel = ''
                      if (a.action === 'calls' && a.amount) bbLabel = ` (${(a.amount / bb).toFixed(1)}bb)`
                      else if (a.action === 'bets' && a.amount) bbLabel = ` (${(a.amount / bb).toFixed(1)}bb)`
                      else if (a.action === 'raises' && raiseTo) bbLabel = ` (${(raiseTo / bb).toFixed(1)}bb)`
                      else if (a.action === 'collected' && a.amount) bbLabel = ` (${(a.amount / bb).toFixed(1)}bb)`

                      let actionColor = '#94a3b8', actionBg = 'rgba(148,163,184,0.06)'
                      if (a.action === 'folds') { actionColor = '#e2e8f0'; actionBg = 'rgba(226,232,240,0.06)' }
                      else if (a.action === 'checks') { actionColor = '#64748b'; actionBg = 'rgba(100,116,139,0.06)' }
                      else if (a.action === 'calls') { actionColor = '#22c55e'; actionBg = 'rgba(34,197,94,0.08)' }
                      else if (a.action === 'bets' || a.action === 'raises') { actionColor = '#ef4444'; actionBg = 'rgba(239,68,68,0.08)' }
                      else if (a.action === 'collected') { actionColor = '#22c55e'; actionBg = 'rgba(34,197,94,0.1)' }
                      else if (a.action === 'shows') { actionColor = '#8b5cf6'; actionBg = 'rgba(139,92,246,0.06)' }
                      if (a.allIn) { actionColor = '#ef4444'; actionBg = 'rgba(239,68,68,0.12)' }

                      return (
                        <div key={ai} style={{ display: 'flex', alignItems: 'center', padding: '7px 0', borderBottom: ai < st.actions.length - 1 ? '1px solid rgba(255,255,255,0.02)' : 'none' }}>
                          <div style={{ width: 58, flexShrink: 0 }}>{pos && <PosBadge pos={pos} />}</div>
                          <div style={{ width: 170, flexShrink: 0 }}>
                            <span style={{ fontSize: 14, fontWeight: 600, color: '#0a0c14', background: isHero ? '#a5b4fc' : '#fbbf24', padding: '2px 8px', borderRadius: 4, display: 'inline-block' }}>
                              {a.actor}{isHero && <span style={{ fontSize: 9, fontWeight: 700, color: '#4338ca', marginLeft: 4 }}>HERO</span>}
                            </span>
                          </div>
                          <div style={{ width: 55, flexShrink: 0, textAlign: 'right', fontSize: 13, color: '#f1f5f9', fontFamily: 'monospace', fontWeight: 600 }}>{currentStackBB}bb</div>
                          {(st.name === 'PRE-FLOP' || st.name === 'FLOP') && bounty != null ? (
                            <div style={{ width: 50, flexShrink: 0, textAlign: 'right', fontSize: 11, color: '#1e40af', fontWeight: 700 }}>{typeof bounty === 'number' && bounty < 10 ? `${bounty}%` : `${bounty}€`}</div>
                          ) : <div style={{ width: 50, flexShrink: 0 }} />}
                          <div style={{ flex: 1, paddingLeft: 10 }}>
                            <span style={{ fontSize: 14, fontWeight: 700, color: actionColor, padding: '4px 14px', borderRadius: 5, background: actionBg, border: `1px solid ${actionColor}25` }}>{a.label}{bbLabel}</span>
                          </div>
                          {a.cards && <div style={{ display: 'flex', gap: 3 }}>{a.cards.map((c, i) => <RCard key={i} card={c} />)}</div>}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })
          })()}
        </div>
      </div>
    </div>
  )
}
