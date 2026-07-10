// frontend/src/components/HandCard.jsx
//
// Carta com DUAS estéticas (o Rui escolhe antes do fecho):
//   variant "hm3"  — quadrado colorido (rank + naipe), deck de 4 cores (estilo HM3/refs)
//   variant "real" — carta de baralho realista (branca, rank+naipe nos cantos + pip central)
// Deck 4 cores: ♠ cinza · ♥ vermelho · ♦ azul · ♣ verde.
// Props: card ("Ah"/"Tc"/"Ks"), size ('sm'|'md'|'lg'), variant, faceDown.

import React from 'react'

const SUIT = { h: '♥', d: '♦', c: '♣', s: '♠' }
// hm3: cor forte no símbolo/rank sobre fundo escuro tingido
const HM3 = {
  h: { fg: '#ff6b6b', bg: '#2a1214', bd: '#5a2328' },
  d: { fg: '#4dabf7', bg: '#0f2033', bd: '#1d4a70' },
  c: { fg: '#51cf66', bg: '#0f2417', bd: '#1f5834' },
  s: { fg: '#cbd5e1', bg: '#1a2028', bd: '#33404f' },
}
// real: cor do rank/naipe sobre carta branca
const REAL = { h: '#e01e37', d: '#1173d4', c: '#0f9d58', s: '#20242b' }

const SZ = {
  sm: { w: 26, h: 36, r: 4, rank: 13, suit: 8, pip: 15 },
  md: { w: 34, h: 46, r: 6, rank: 17, suit: 11, pip: 22 },
  lg: { w: 46, h: 64, r: 8, rank: 23, suit: 15, pip: 32 },
}

export default function HandCard({ card, size = 'md', variant = 'hm3', faceDown = false }) {
  const s = SZ[size] || SZ.md
  if (faceDown) {
    return <span style={{ display: 'inline-block', width: s.w, height: s.h, borderRadius: s.r,
      background: 'linear-gradient(135deg,#1e40af,#7c3aed,#1e40af)', border: '1.5px solid rgba(255,255,255,.2)',
      boxShadow: '0 2px 6px rgba(0,0,0,.4)' }} />
  }
  if (!card || card.length < 2) {
    return <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: s.w, height: s.h,
      borderRadius: s.r, background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.10)', fontSize: s.suit + 4, color: '#4b5563' }}>?</span>
  }
  const rankRaw = card.slice(0, -1).toUpperCase()
  const rank = rankRaw === 'T' ? '10' : rankRaw
  const su = card.slice(-1).toLowerCase()
  const sym = SUIT[su] || '?'

  if (variant === 'real') {
    const col = REAL[su] || '#20242b'
    const corner = (br) => (
      <span style={{ position: 'absolute', lineHeight: .85, textAlign: 'center', color: col,
        ...(br ? { bottom: '7%', right: '9%', transform: 'rotate(180deg)' } : { top: '7%', left: '9%' }) }}>
        <span style={{ display: 'block', fontSize: s.rank, fontWeight: 800 }}>{rank}</span>
        <span style={{ display: 'block', fontSize: s.suit }}>{sym}</span>
      </span>
    )
    return (
      <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: s.w * 1.02, height: s.h, borderRadius: s.r + 1, background: '#fdfdfb',
        boxShadow: '0 4px 12px rgba(0,0,0,.5), inset 0 0 0 1px rgba(0,0,0,.08)',
        fontFamily: 'ui-sans-serif,system-ui,sans-serif', userSelect: 'none' }}>
        {corner(false)}<span style={{ fontSize: s.pip, color: col }}>{sym}</span>{corner(true)}
      </span>
    )
  }
  // hm3 — SÓ o rank (sem naipe), cor = naipe (4 cores). Tipo de letra com serifas
  // (traços nas pernas do K / ponta do J), menos arredondado que o sans.
  const c = HM3[su] || HM3.s
  const two = rank.length > 1               // "10" — encolhe + aperta
  const rankFs = Math.round(s.pip * (two ? 0.7 : 0.92))
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: s.w, height: s.h, borderRadius: s.r, background: c.bg, border: `1px solid ${c.bd}`,
      boxShadow: 'inset 0 0 0 1px rgba(255,255,255,.03), 0 2px 6px rgba(0,0,0,.4)',
      fontFamily: '"Times New Roman", Georgia, "Liberation Serif", serif', lineHeight: 1, userSelect: 'none' }}>
      <span style={{ fontSize: rankFs, fontWeight: 400, color: c.fg, letterSpacing: two ? '-0.06em' : 0 }}>{rank}</span>
    </span>
  )
}
