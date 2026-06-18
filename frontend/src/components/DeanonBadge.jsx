// Aviso de desanonimização "por verificar" (pt76). Mostra-se SÓ quando
// deanon_status === 'unverified' (mão GG cujos nomes vieram do feltro/stack,
// não confirmados por posição). 'verified'/null → não mostra nada.
// Derivado no backend a partir do match_method (ver services/deanon_status.py).

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
export function DeanonBanner({ status }) {
  if (status !== 'unverified') return null
  return (
    <div
      title={TOOLTIP}
      style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '7px 14px', margin: '0 0 10px',
        borderRadius: 6, fontSize: 12, fontWeight: 600,
        color: '#fbbf24', background: 'rgba(251,191,36,0.10)',
        border: '1px solid rgba(251,191,36,0.30)', cursor: 'help',
      }}
    >
      <span style={{ fontSize: 14 }}>⚠</span>
      <span>Nomes por verificar — {TOOLTIP.charAt(0).toLowerCase() + TOOLTIP.slice(1)}</span>
    </div>
  )
}

export default DeanonBadge
