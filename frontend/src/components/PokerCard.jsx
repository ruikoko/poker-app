// frontend/src/components/PokerCard.jsx
//
// Componente Card visual partilhado.
// Variantes:
//   - sm: 26x36 (listas, HandRow)
//   - md: 36x50 (accoes inline, showdown row, board mid)
//   - lg: 48x66 (Hero cards, board grande, bloco SHOWDOWN dedicado)
// Props:
//   - card     string  formato "Ah" / "Tc" / "Ks" - nulo/curto -> placeholder "?"
//   - size     'sm' | 'md' | 'lg'  (default 'md')
//   - faceDown boolean - se true, ignora card e mostra dorso azul/purpura
//
// Paleta de naipes (polida da HandDetailPage:8-10):
//   heart red  diamond blue  club green  spade slate
//
// Origem: extraido de HandDetailPage:15 (matriz red/blue/green/slate)
// + faceDown gradient de Replayer:12 + sm size de Replayer:13.

import React from 'react'

const SUIT_COLORS = { h: '#ef4444', d: '#3b82f6', c: '#22c55e', s: '#e2e8f0' }
const SUIT_SYMBOLS = { h: '♥', d: '♦', c: '♣', s: '♠' }
const SUIT_BG = { h: '#7f1d1d', d: '#1e3a5f', c: '#14532d', s: '#1e293b' }

const SIZES = {
  sm: { w: 26, h: 36, fs: 11 },
  md: { w: 36, h: 50, fs: 15 },
  lg: { w: 48, h: 66, fs: 19 },
}

export default function PokerCard({ card, size = 'md', faceDown = false }) {
  const { w, h, fs } = SIZES[size] || SIZES.md

  if (faceDown) {
    return (
      <span style={{
        display: 'inline-block', width: w, height: h, borderRadius: 5,
        background: 'linear-gradient(135deg,#1e40af,#7c3aed,#1e40af)',
        border: '1.5px solid rgba(255,255,255,0.2)',
        boxShadow: '0 2px 6px rgba(0,0,0,0.4)',
      }} />
    )
  }

  if (!card || card.length < 2) {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: w, height: h, borderRadius: 5,
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.1)',
        fontSize: fs, color: '#4b5563',
      }}>?</span>
    )
  }

  const rank = card.slice(0, -1).toUpperCase()
  const suit = card.slice(-1).toLowerCase()
  const suitColor = SUIT_COLORS[suit] || '#e2e8f0'
  const suitBg = SUIT_BG[suit] || '#1e293b'
  const suitSym = SUIT_SYMBOLS[suit] || suit

  return (
    <span style={{
      display: 'inline-flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      width: w, height: h, borderRadius: 5,
      background: suitBg,
      border: `1.5px solid ${suitColor}50`,
      fontFamily: "'Fira Code',monospace",
      fontWeight: 700, fontSize: fs, color: '#fff',
      lineHeight: 1, userSelect: 'none',
      boxShadow: '0 2px 6px rgba(0,0,0,0.4)',
    }}>
      <span>{rank}</span>
      <span style={{ fontSize: fs * 0.8, color: suitColor }}>{suitSym}</span>
    </span>
  )
}
