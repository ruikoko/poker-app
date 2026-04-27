// frontend/src/components/HandHistoryViewer.jsx
//
// Renderer canónico único para Hand Histories (Tech Debt #8).
// Substitui (commits 4-6):
//   - Bloco MESA+Acções de HandDetailPage (linhas 209-338)
//   - ParsedHandHistory + parseRawHH local em Hands.jsx (318-656)
//   - Bloco render + parseRawHH local em HM3.jsx (123-184 + 359-507)
//
// Spec aprovada Rui (29-Abr):
//   - Stacks MESA: "19,520 (32 BB)" — fichas + BB maiúsculas
//   - Acções via formatActionLabel (folds/checks/calls/bets/raises/collected)
//   - Posição SEMPRE antes do nick
//   - Stack pós-acção: "→ 17bb" via formatBB
//   - Showdown: bloco SHOWDOWN dedicado abaixo com cards lg
//
// Regra global formatBB: inteiro "Nbb", decimal "N.Xbb".
//
// Props:
//   hand: objecto vindo de GET /api/hands/{id}
//         { raw, raw_resolved, all_players_actions, player_names, hero_cards, board, ... }

import React from 'react'
import { parseHH, formatBB, formatActionLabel } from '../lib/handParser'
import { HERO_NAMES_ALL } from '../heroNames'
import PokerCard from './PokerCard'

const STREET_COLORS = {
  preflop: '#6366f1',
  flop: '#22c55e',
  turn: '#f59e0b',
  river: '#ef4444',
  showdown: '#8b5cf6',
}
const STREET_LABELS = {
  preflop: 'PRE-FLOP',
  flop: 'FLOP',
  turn: 'TURN',
  river: 'RIVER',
  showdown: 'SHOWDOWN',
}
const POS_COLORS = {
  BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa',
  SB: '#f59e0b', BB: '#ef4444',
  UTG: '#22c55e', UTG1: '#16a34a', 'UTG+1': '#16a34a',
  UTG2: '#15803d', 'UTG+2': '#15803d',
  MP: '#06b6d4', MP1: '#0891b2', 'MP+1': '#0891b2',
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ color: '#4b5563', minWidth: 38, display: 'inline-block', textAlign: 'center' }}>—</span>
  const c = POS_COLORS[pos] || POS_COLORS[String(pos).replace('+', '')] || '#64748b'
  return (
    <span style={{
      display: 'inline-block', padding: '4px 12px', borderRadius: 5,
      fontSize: 13, fontWeight: 700, letterSpacing: 0.5,
      color: c, background: `${c}18`, border: `1px solid ${c}30`,
      minWidth: 38, textAlign: 'center',
    }}>{pos}</span>
  )
}

function NickBadge({ name, isHero }) {
  return (
    <span style={{
      fontSize: 14, fontWeight: 600, color: '#0a0c14',
      background: isHero ? '#a5b4fc' : '#e2e8f0',
      padding: '3px 10px', borderRadius: 4,
      display: 'inline-block', minWidth: 120,
    }}>
      {name}
      {isHero && <span style={{ fontSize: 9, fontWeight: 700, color: '#4338ca', marginLeft: 4 }}>HERO</span>}
    </span>
  )
}

// MESA stack format: "19,520 (32 BB)" — fichas + BB maiúsculas.
// formatBB devolve "Nbb"/"N.Xbb"; substituímos para " BB" maiúsc.
function formatTableStack(chips, bb) {
  if (chips == null) return '—'
  const chipStr = Math.round(chips).toLocaleString('en-US')
  if (!bb || bb <= 1) return chipStr
  const bbLower = formatBB(chips / bb)
  if (!bbLower) return chipStr
  const bbUpper = bbLower.replace('bb', ' BB').trim()
  return `${chipStr} (${bbUpper})`
}

function actionColor(type, allIn) {
  if (allIn) return { c: '#ef4444', bg: 'rgba(239,68,68,0.12)' }
  if (type === 'folds') return { c: '#e2e8f0', bg: 'rgba(226,232,240,0.06)' }
  if (type === 'checks') return { c: '#64748b', bg: 'rgba(100,116,139,0.06)' }
  if (type === 'calls') return { c: '#22c55e', bg: 'rgba(34,197,94,0.08)' }
  if (type === 'bets' || type === 'raises') return { c: '#ef4444', bg: 'rgba(239,68,68,0.08)' }
  if (type === 'collected' || type === 'wins') return { c: '#22c55e', bg: 'rgba(34,197,94,0.1)' }
  return { c: '#94a3b8', bg: 'rgba(148,163,184,0.06)' }
}

export default function HandHistoryViewer({ hand }) {
  if (!hand?.raw) return null
  const apa = hand.all_players_actions || {}
  const meta = apa._meta || {}
  const bb = meta.bb || 1

  const { steps, players } = parseHH(hand.raw_resolved || hand.raw, apa)
  if (!players || players.length === 0) return null

  // ── Group steps by street ──
  const streetMap = {}
  for (const step of steps) {
    if (!step.street) continue
    if (!streetMap[step.street]) {
      streetMap[step.street] = {
        key: step.street,
        label: STREET_LABELS[step.street] || step.label,
        color: STREET_COLORS[step.street] || '#94a3b8',
        board: [],
        potBefore: step.pot,
        actions: [],
      }
    }
    const g = streetMap[step.street]
    if (step.board && step.board.length > g.board.length) g.board = [...step.board]
    if (step.actor && step.actionType) g.actions.push(step)
  }

  const streetOrder = ['preflop', 'flop', 'turn', 'river']
  const streetsToShow = streetOrder
    .map(k => streetMap[k])
    .filter(s => s && (s.actions.length > 0 || s.board.length > 0 || s.key === 'preflop'))

  // ── Showdown players (último step com cards reveladas) ──
  const finalStep = steps[steps.length - 1] || null
  const finalBoard = finalStep?.board || []
  const showdownPlayers = (finalStep?.ps || [])
    .filter(p => p.cards && p.cards.length > 0 && !p.folded)

  return (
    <div style={{ background: '#0f1117', borderRadius: 8, overflow: 'hidden' }}>

      {/* ── MESA ── */}
      <div style={{ padding: '16px 20px', borderBottom: '1px solid #1a1d2a' }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#94a3b8', marginBottom: 12, letterSpacing: 0.5 }}>
          MESA ({players.length} {players.length === 1 ? 'JOGADOR' : 'JOGADORES'})
        </div>
        {players.map((p, i) => {
          const isHero = p.is_hero || HERO_NAMES_ALL.has(String(p.name).toLowerCase())
          const stackLabel = formatTableStack(p.stack, bb)
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 14, padding: '8px 14px',
              borderBottom: i < players.length - 1 ? '1px solid #14171f' : 'none',
              background: isHero ? 'rgba(99,102,241,0.05)' : 'transparent', borderRadius: 4,
            }}>
              <PosBadge pos={p.position} />
              <NickBadge name={p.name} isHero={isHero} />
              <span style={{
                fontSize: 14, color: '#fbbf24', fontFamily: 'monospace',
                fontWeight: 700, marginLeft: 'auto',
              }}>{stackLabel}</span>
              {p.bounty != null && (
                <span style={{
                  fontSize: 13, color: '#7dd3fc', fontWeight: 700,
                  padding: '2px 8px', borderRadius: 4,
                  background: 'rgba(125,211,252,0.08)',
                  border: '1px solid rgba(125,211,252,0.15)',
                }}>
                  {typeof p.bounty === 'number' && p.bounty < 10 ? `${p.bounty}%` : `${p.bounty}€`}
                </span>
              )}
            </div>
          )
        })}
      </div>

      {/* ── Acções por street ── */}
      <div style={{ padding: '16px 20px' }}>
        {streetsToShow.map((st, si) => (
          <div key={st.key} style={{ marginBottom: si < streetsToShow.length - 1 ? 18 : 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <span style={{
                padding: '4px 14px', borderRadius: 5,
                fontSize: 14, fontWeight: 800, letterSpacing: 0.5,
                color: st.color, background: `${st.color}15`, border: `1px solid ${st.color}30`,
              }}>{st.label}</span>
              {st.board.length > 0 && (
                <div style={{ display: 'flex', gap: 4 }}>
                  {st.board.map((c, i) => <PokerCard key={i} card={c} size="md" />)}
                </div>
              )}
              <span style={{
                fontSize: 14, fontWeight: 700, fontFamily: 'monospace',
                marginLeft: 'auto', color: '#94a3b8',
                background: 'rgba(255,255,255,0.03)', padding: '3px 12px', borderRadius: 4,
              }}>
                Pot: {Math.round(st.potBefore).toLocaleString('en-US')} ({formatBB(st.potBefore / bb)})
              </span>
            </div>

            <div style={{ paddingLeft: 16, borderLeft: `3px solid ${st.color}30` }}>
              {st.actions.map((step, ai) => {
                const isHero = step.isHero
                const player = step.actorIdx >= 0 ? step.ps[step.actorIdx] : null
                const pos = player?.position
                const stackAfterBB = player ? formatBB(player.stack / bb) : ''
                const label = formatActionLabel(step, bb)
                const ac = actionColor(step.actionType, step.allIn)
                return (
                  <div key={ai} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '7px 0', flexWrap: 'wrap',
                    borderBottom: ai < st.actions.length - 1 ? '1px solid rgba(255,255,255,0.02)' : 'none',
                  }}>
                    <PosBadge pos={pos} />
                    <NickBadge name={step.actor} isHero={isHero} />
                    <span style={{
                      fontSize: 14, fontWeight: 700,
                      color: ac.c, background: ac.bg,
                      padding: '4px 14px', borderRadius: 5,
                      border: `1px solid ${ac.c}25`,
                    }}>{label}</span>
                    {stackAfterBB && (
                      <span style={{
                        fontSize: 13, color: '#fbbf24', fontFamily: 'monospace', fontWeight: 700,
                      }}>→ {stackAfterBB}</span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      {/* ── SHOWDOWN bloco dedicado ── */}
      {showdownPlayers.length >= 2 && (
        <div style={{
          padding: '16px 20px',
          borderTop: '1px solid #1a1d2a',
          background: 'linear-gradient(180deg, rgba(139,92,246,0.04), rgba(139,92,246,0))',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <span style={{
              padding: '4px 14px', borderRadius: 5,
              fontSize: 14, fontWeight: 800, letterSpacing: 0.5,
              color: STREET_COLORS.showdown,
              background: `${STREET_COLORS.showdown}15`,
              border: `1px solid ${STREET_COLORS.showdown}30`,
            }}>SHOWDOWN</span>
            {finalBoard.length > 0 && (
              <div style={{ display: 'flex', gap: 4 }}>
                {finalBoard.map((c, i) => <PokerCard key={i} card={c} size="md" />)}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {showdownPlayers.map((p, i) => {
              const isHero = p.isHero || HERO_NAMES_ALL.has(String(p.name).toLowerCase())
              return (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 14, padding: '6px 0',
                }}>
                  <PosBadge pos={p.position} />
                  <NickBadge name={p.name} isHero={isHero} />
                  <span style={{ fontSize: 12, color: '#8b5cf6', fontWeight: 700, marginRight: 4 }}>shows</span>
                  <div style={{ display: 'flex', gap: 5 }}>
                    {p.cards.map((c, j) => <PokerCard key={j} card={c} size="lg" />)}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
