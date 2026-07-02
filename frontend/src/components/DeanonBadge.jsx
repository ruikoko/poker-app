// Aviso de desanonimização "por verificar" (pt76). Mostra-se SÓ quando
// deanon_status === 'unverified' (mão GG cujos nomes vieram do feltro/stack,
// não confirmados por posição). 'verified'/null → não mostra nada.
// Derivado no backend a partir do match_method (ver services/deanon_status.py).
import { useState } from 'react'
import { tableSs } from '../api/client'

const TOOLTIP =
  'Nomes atribuídos por aproximação de stacks (foto do feltro), ' +
  'não confirmados por posição — podem estar trocados'

// Chip compacto — lista de mãos (Estudo), linha do vilão.
export function DeanonBadge({ status }) {
  if (status !== 'unverified') return null
  return (
    <span
      title={TOOLTIP}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 3,
        padding: '2px 8px', borderRadius: 999,
        fontSize: 11, fontWeight: 600, letterSpacing: 0.3,
        color: '#fbbf24', background: 'rgba(251,191,36,0.14)',
        border: '1px solid rgba(251,191,36,0.35)', cursor: 'help',
        whiteSpace: 'nowrap',
      }}
    >⚠ Nomes por verificar</span>
  )
}

// Faixa única — por cima da mesa (replayer) / acima dos seats (viewer).
// Fase 1-E: se receber `handId`, mostra o botão "verificada por mim" (marca o flag
// aditivo verified_by_user → o badge some). Auto-esconde após confirmar.
export function DeanonBanner({ status, handId }) {
  const [hidden, setHidden] = useState(false)
  const [busy, setBusy] = useState(false)
  if (status !== 'unverified' || hidden) return null
  const verify = async () => {
    setBusy(true)
    try { await tableSs.verifyDeanon(handId, true); setHidden(true) }
    catch (e) { alert('Erro ao verificar: ' + (e.message || e)); setBusy(false) }
  }
  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '7px 14px', margin: '0 0 10px',
        borderRadius: 6, fontSize: 12, fontWeight: 600,
        color: '#fbbf24', background: 'rgba(251,191,36,0.10)',
        border: '1px solid rgba(251,191,36,0.30)',
      }}
    >
      <span style={{ fontSize: 14 }} title={TOOLTIP}>⚠</span>
      <span title={TOOLTIP} style={{ cursor: 'help' }}>
        Nomes por verificar — {TOOLTIP.charAt(0).toLowerCase() + TOOLTIP.slice(1)}
      </span>
      {handId && (
        <button onClick={verify} disabled={busy} style={{
          marginLeft: 'auto', flexShrink: 0, cursor: busy ? 'wait' : 'pointer',
          background: 'rgba(34,197,94,0.15)', border: '1px solid rgba(34,197,94,0.45)',
          color: '#4ade80', borderRadius: 5, fontSize: 11, fontWeight: 700, padding: '3px 10px',
        }}>{busy ? '…' : '✓ verificada por mim'}</button>
      )}
    </div>
  )
}

export default DeanonBadge
