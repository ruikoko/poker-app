// frontend/src/components/HandTimeline.jsx
//
// Vista de mão "Timeline" (direção 3b, escolhida pelo Rui, 10 Jul).
// Fundamentais protagonistas (posições/nomes/stacks/cartas/ações/streets/pote/coroas);
// resto recuado. Reutiliza o parser canónico (parseHH) e a edição que alimenta a BD
// (CrownCell → set-bounties; DeanonBanner → verificar nomes). Backend: zero alterações.
//
// Regras do Rui: retrato da mesa em 2 colunas (BB·SB·BTN·CO à esquerda);
// pré-flop (e todas as streets) uma ação por linha com POS·nome·ação·stack-atrás;
// coroa com convenção da casa (bounty_value_usd = instantâneo). 2 estéticas de carta.

import React, { useState } from 'react'
import { parseHH, formatBB, formatActionLabel } from '../lib/handParser'
import { CrownCell, NameEditor } from './HandHistoryViewer'
import { DeanonBanner } from './DeanonBadge'
import HandCard from './HandCard'

const N = n => (n == null ? '—' : Math.round(n).toLocaleString('pt-PT'))
const POS_C = { BTN: '#818cf8', CO: '#a78bfa', HJ: '#c4b5fd', SB: '#fbbf24', BB: '#fb7185',
  UTG: '#4ade80', 'UTG+1': '#34d399', UTG1: '#34d399', 'UTG+2': '#2dd4bf', UTG2: '#2dd4bf',
  MP: '#22d3ee', MP1: '#38bdf8', 'MP+1': '#38bdf8', LJ: '#60a5fa' }
// prioridade p/ o retrato: BB·SB·BTN·CO à esquerda (metade da frente)
const PRIO = ['BB', 'SB', 'BTN', 'CO', 'HJ', 'LJ', 'MP+1', 'MP1', 'MP', 'UTG+2', 'UTG2', 'UTG+1', 'UTG1', 'UTG']
const prioIdx = p => { const i = PRIO.indexOf(p); return i === -1 ? 90 : i }

function Pos({ pos, big }) {
  const c = POS_C[pos] || POS_C[String(pos || '').replace('+', '')] || '#94a3b8'
  return <span style={{ display: 'inline-block', minWidth: big ? 46 : 40, textAlign: 'center',
    fontSize: big ? 12 : 11, fontWeight: 800, letterSpacing: .5, color: c, background: `${c}1e`,
    border: `1px solid ${c}3a`, borderRadius: 7, padding: big ? '3px 8px' : '2px 7px' }}>{pos || '—'}</span>
}

const ACT = {
  raises: { t: 'sobe p/', c: '#fb7185' }, bets: { t: 'aposta', c: '#fb7185' },
  calls: { t: 'paga', c: '#cbd5e1' }, checks: { t: 'passa', c: '#7d8aa3' },
  folds: { t: 'desiste', c: '#63708a' }, collected: { t: 'ganha', c: '#4ade80' },
  wins: { t: 'ganha', c: '#4ade80' }, posts: { t: 'posta', c: '#94a3b8' },
}

export default function HandTimeline({ hand, onEdited }) {
  const [variant, setVariant] = useState('hm3')   // 'hm3' | 'real' — o Rui escolhe
  if (!hand?.raw) return null
  const apa = hand.all_players_actions || {}
  const meta = apa._meta || {}
  const bb = meta.bb || 1
  const { steps, players } = parseHH(hand.raw_resolved || hand.raw, apa)
  if (!players || players.length === 0) return null

  // ── ganhos (collected) via raw, mapeado hash→jogador por name_key ──
  const wonBy = {}
  const re = /(\S+) collected ([\d,]+) from pot/g
  let m
  while ((m = re.exec(hand.raw)) !== null) wonBy[m[1]] = (wonBy[m[1]] || 0) + parseInt(m[2].replace(/,/g, ''), 10)
  players.forEach(p => { p.won = wonBy[p.name_key] || wonBy[p.name] || 0 })
  const potM = /Total pot ([\d,]+)/.exec(hand.raw)
  const pot = potM ? parseInt(potM[1].replace(/,/g, ''), 10) : null
  const winner = players.reduce((a, b) => (b.won > (a?.won || 0) ? b : a), null)
  const hero = players.find(p => p.isHero)

  // ── streets ──
  const sm = {}
  for (const st of steps) {
    if (!st.street) continue
    if (!sm[st.street]) sm[st.street] = { key: st.street, board: [], actions: [] }
    const g = sm[st.street]
    if (st.board && st.board.length > g.board.length) g.board = [...st.board]
    if (st.actor && st.actionType && !['collected', 'wins', 'posts'].includes(st.actionType)) g.actions.push(st)
  }
  const streets = ['preflop', 'flop', 'turn', 'river']
    .map(k => sm[k]).filter(s => s && (s.actions.length > 0 || s.board.length > 0 || s.key === 'preflop'))
  const finalStep = steps[steps.length - 1] || null
  const showdown = (finalStep?.ps || []).filter(p => p.cards && p.cards.length > 0 && !p.folded)
  const anon = hand.site === 'GGPoker' && !(hand.player_names?.match_method)

  // ── retrato: ordenar por PRIO, dividir em 2 colunas (esquerda = 1ª metade) ──
  const sorted = [...players].sort((a, b) => prioIdx(a.position) - prioIdx(b.position))
  const half = Math.ceil(sorted.length / 2)
  const cols = [sorted.slice(0, half), sorted.slice(half)]

  const card = (c, size) => <HandCard card={c} size={size} variant={variant} />
  const S_LAB = { preflop: 'PRÉ-FLOP', flop: 'FLOP', turn: 'TURN', river: 'RIVER' }

  function Seat({ p }) {
    const ire = !p.isHero && hand.ire?.per_opponent?.find(o => o.nick === p.name)
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '9px 11px', borderRadius: 11,
        background: p.isHero ? 'rgba(34,211,238,.09)' : '#0e131d',
        border: `1px solid ${p.isHero ? '#17414a' : '#232c3d'}` }}>
        <Pos pos={p.position} />
        <span style={{ fontWeight: 500, fontSize: 14, letterSpacing: '.3px', color: p.isHero ? '#67e8f9' : '#e8eef7',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1, minWidth: 0 }}>
          {p.name}{p.isHero && <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '.5px', color: '#22d3ee', marginLeft: 5 }}>HERO</span>}
        </span>
        {!p.isHero && <NameEditor handId={hand.hand_id} position={p.position} name={p.name_key || p.name} onEdited={onEdited} />}
        <span style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 12.5, color: '#fbbf24', fontWeight: 700, whiteSpace: 'nowrap' }}>
          {N(p.startStack)}<span style={{ display: 'block', color: '#7d8aa3', fontSize: 11 }}>{formatBB(p.startStack / bb)}</span>
        </span>
        <CrownCell crown={p.bountyUsd} ire={ire} isHero={p.isHero} handId={hand.hand_id} nameKey={p.name_key || p.name} onEdited={onEdited} />
      </div>
    )
  }

  function ActLine({ st }) {
    const pl = st.actorIdx >= 0 ? st.ps[st.actorIdx] : null
    const a = ACT[st.actionType] || { t: st.actionType, c: '#94a3b8' }
    const behindChips = pl ? pl.stack : null
    const allIn = st.allIn || behindChips === 0
    const label = formatActionLabel(st, bb)
    return (
      <div style={{ display: 'grid', gridTemplateColumns: '46px minmax(0,1fr) auto', gap: 10, alignItems: 'center',
        padding: '8px 6px', borderTop: '1px solid #10151f',
        background: st.isHero ? 'linear-gradient(90deg,rgba(34,211,238,.09),transparent)' : 'transparent',
        boxShadow: allIn ? 'inset 3px 0 0 #fb7185' : 'none' }}>
        <Pos pos={pl?.position} />
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 500, fontSize: 14.5, letterSpacing: '.3px', color: st.isHero ? '#67e8f9' : '#e8eef7', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{st.actor}</div>
          <div style={{ fontSize: 13.5, fontWeight: 700, color: a.c, marginTop: 1 }}>{label}</div>
        </div>
        <div style={{ textAlign: 'right', fontSize: 12, whiteSpace: 'nowrap',
          color: allIn ? '#fb7185' : '#7d8aa3', fontWeight: allIn ? 800 : 400 }}>
          {allIn ? '★ ALL-IN' : <>resta <b style={{ color: '#dfe8f2', fontFamily: 'monospace' }}>{N(behindChips)}</b> <span style={{ color: '#5f6b82' }}>({formatBB(behindChips / bb)})</span></>}
        </div>
      </div>
    )
  }

  return (
    <div style={{ color: '#eaf0fb' }}>
      {/* toggle de estética das cartas (temporário — o Rui escolhe) */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6, marginBottom: 10, fontSize: 12 }}>
        <span style={{ color: '#5f6b82', alignSelf: 'center' }}>cartas:</span>
        {['hm3', 'real'].map(v => (
          <button key={v} onClick={() => setVariant(v)} style={{ cursor: 'pointer', borderRadius: 7, padding: '4px 10px', fontWeight: 700,
            background: variant === v ? 'rgba(34,211,238,.15)' : '#141a26', color: variant === v ? '#67e8f9' : '#8b97ad',
            border: `1px solid ${variant === v ? '#22d3ee55' : '#222c3e'}` }}>{v === 'hm3' ? 'estilo HM3' : 'réplica real'}</button>
        ))}
      </div>

      <DeanonBanner status={hand.deanon_status} handId={hand.hand_id} />
      {anon && <div style={{ background: 'rgba(148,163,184,.08)', border: '1px solid #2a3444', borderRadius: 10, padding: '10px 14px', marginBottom: 12, color: '#93a0b4', fontSize: 13 }}>Mão GG <b>anónima</b> — sem nomes reais (falta captura/desanon). Mostram-se posições, stacks e ações; sem cartas de vilão.</div>}

      {/* HERO + BOARD */}
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'center', background: 'linear-gradient(180deg,#0e1a1c,#0c1518)',
        border: '1px solid #17414a', borderRadius: 16, padding: '14px 18px', marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: 10, letterSpacing: 2, color: '#22d3ee', textTransform: 'uppercase' }}>Hero {hero && <>· {hero.position}</>}</div>
          <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: '.3px', margin: '2px 0 8px' }}>{hero?.name || hand.player_names?.hero || 'Hero'}</div>
          <div style={{ display: 'flex', gap: 6 }}>{(hand.hero_cards || []).length ? hand.hero_cards.map((c, i) => <HandCard key={i} card={c} size="lg" variant={variant} />) : <span style={{ color: '#5f6b82' }}>—</span>}</div>
        </div>
        {hand.board?.length > 0 && (
          <div><div style={{ fontSize: 10, letterSpacing: 2, color: '#7d8aa3', textTransform: 'uppercase', marginBottom: 8 }}>Board</div>
            <div style={{ display: 'flex', gap: 6 }}>{hand.board.map((c, i) => <HandCard key={i} card={c} size="lg" variant={variant} />)}</div></div>
        )}
        <div style={{ marginLeft: 'auto', textAlign: 'right', fontSize: 12, color: '#7d8aa3' }}>
          {hand.result != null && <div style={{ fontSize: 18, fontWeight: 800, color: hand.result > 0 ? '#4ade80' : hand.result < 0 ? '#fb7185' : '#94a3b8' }}>{hand.result > 0 ? '+' : ''}{Number(hand.result).toFixed(1)} BB</div>}
          {pot != null && <div style={{ marginTop: 4 }}>pote <b style={{ color: '#eaf0fb' }}>{N(pot)}</b></div>}
        </div>
      </div>

      {/* RETRATO DA MESA — 2 colunas (BB·SB·BTN·CO à esquerda) */}
      <div style={{ marginBottom: 6 }}>
        <div style={{ fontSize: 10, letterSpacing: 2, color: '#7d8aa3', textTransform: 'uppercase', marginBottom: 10 }}>Disposição da mesa — {players.length} jogadores</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {cols.map((col, ci) => <div key={ci} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>{col.map((p, i) => <Seat key={i} p={p} />)}</div>)}
        </div>
      </div>

      {/* RAIL — streets, uma ação por linha */}
      <div style={{ position: 'relative', margin: '22px 0 0', paddingLeft: 50 }}>
        <div style={{ position: 'absolute', left: 18, top: 8, bottom: 24, width: 2, background: 'linear-gradient(#22d3ee,#232c3d)' }} />
        {streets.map((st, i) => {
          const posts = st.key === 'preflop' ? (() => {
            const sb = players.find(p => p.position === 'SB'), bbp = players.find(p => p.position === 'BB')
            return `Ante ${N(meta.ante)} · SB ${sb ? sb.name + ' ' + N(meta.sb) : '—'} · BB ${bbp ? bbp.name + ' ' + N(meta.bb) : '—'}`
          })() : null
          return (
            <div key={st.key} style={{ position: 'relative', marginBottom: 14 }}>
              <div style={{ position: 'absolute', left: -50, top: 2, width: 38, height: 38, borderRadius: 12, background: '#171d2b',
                border: '1px solid #232c3d', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 12, color: '#22d3ee' }}>{i + 1}</div>
              <div style={{ background: '#121722', border: '1px solid #232c3d', borderRadius: 16, padding: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: st.board.length || posts ? 8 : 2 }}>
                  <span style={{ fontSize: 15, fontWeight: 800, letterSpacing: .5 }}>{S_LAB[st.key]}</span>
                  {st.board.length > 0 && <div style={{ display: 'flex', gap: 5 }}>{st.board.map((c, j) => card(c, 'sm'))}</div>}
                  <span style={{ marginLeft: 'auto', fontSize: 11, color: '#7d8aa3' }}>{st.actions.length} {st.actions.length === 1 ? 'ação' : 'ações'}</span>
                </div>
                {posts && <div style={{ fontSize: 12, color: '#93a0b4', borderBottom: '1px dashed #232c3d', paddingBottom: 8 }}>{posts}</div>}
                {st.actions.length ? st.actions.map((s, j) => <ActLine key={j} st={s} />)
                  : <div style={{ fontSize: 13, color: '#7d8aa3', fontStyle: 'italic', padding: '6px 4px' }}>Sem ação nesta street.</div>}
              </div>
            </div>
          )
        })}
      </div>

      {/* SHOWDOWN / VENCEDOR */}
      {winner && winner.won > 0 && (
        <div style={{ marginTop: 8, background: 'linear-gradient(135deg,#0f2417,#0b1a12)', border: '1px solid #1c5836', borderRadius: 18,
          padding: '16px 18px', display: 'flex', alignItems: 'center', gap: 14, boxShadow: '0 0 40px rgba(81,207,102,.10)' }}>
          <span style={{ fontSize: 26 }}>🏆</span>
          <div><div style={{ fontSize: 10, letterSpacing: 2, color: '#4ade80', textTransform: 'uppercase' }}>{showdown.length >= 2 ? 'Ganha o pote principal' : 'Levou o pote'}</div>
            <div style={{ fontSize: 19, fontWeight: 800 }}>{winner.name}</div></div>
          <div style={{ marginLeft: 'auto', textAlign: 'right' }}><b style={{ fontSize: 22, color: '#4ade80' }}>{N(winner.won)}</b>{pot != null && <div style={{ color: '#7d8aa3', fontSize: 11 }}>de {N(pot)} total</div>}</div>
        </div>
      )}
      {showdown.length >= 2 && (
        <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: 8 }}>
          {[...showdown].sort((a, b) => (players.find(x => x.name === b.name)?.won || 0) - (players.find(x => x.name === a.name)?.won || 0)).map((p, i) => {
            const w = players.find(x => x.name === p.name)?.won || 0
            return (
              <div key={i} style={{ background: '#121722', border: '1px solid #232c3d', borderRadius: 12, padding: '9px 11px', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Pos pos={p.position} />
                <div style={{ display: 'flex', gap: 4 }}>{(p.cards || []).map((c, j) => card(c, 'sm'))}</div>
                <span style={{ fontWeight: 500, fontSize: 13.5, letterSpacing: '.3px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1, minWidth: 0 }}>{p.name}</span>
                {w > 0 && <span style={{ color: '#4ade80', fontSize: 12, fontWeight: 700 }}>+{N(w)}</span>}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
