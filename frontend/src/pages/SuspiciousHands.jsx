import { useState } from 'react'
import { Link } from 'react-router-dom'
import { suspicious, tableSs } from '../api/client'
import Worklist from '../components/Worklist'
import HandImage from '../components/HandImage'

// "Mãos suspeitas" — worklist de RESOLUÇÃO sobre o <Worklist> base (LEI 1/3, decisão do Rui):
// venenos de identidade (hero-num-vilão / hero-alheio) → Reverter à anónima; qualquer card →
// Dispensar. Filtro ao-vivo embutido (resolvido sai na hora + re-confere no focus), imagem via
// HandImage, nº GG + link, escrita (revert/dismiss). Só a imagem arbitra.

function Chip({ children, color }) {
  return (
    <span style={{ fontSize: 11, fontWeight: 700, color: color || '#8b9691',
      background: `${color || '#64748b'}1f`, padding: '2px 8px', borderRadius: 5,
      whiteSpace: 'nowrap' }}>{children}</span>
  )
}
function fmt(ts) { return ts ? String(ts).replace('T', ' ').replace('Z', '').slice(0, 16) : '—' }

function BountyDetail({ detail }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {(detail.seats || []).map((s, i) => (
        <span key={i} style={{ fontSize: 11, fontFamily: 'ui-monospace,monospace', color: '#fca5a5',
          background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: 4, padding: '1px 6px' }}>
          {s.name}: <b>${s.value}</b> &lt; ${s.min}
        </span>
      ))}
    </div>
  )
}
function HeroVillainDetail({ detail }) {
  return (
    <div style={{ fontSize: 12 }}>
      <span style={{ color: '#8b9691' }}>Hero: </span><b style={{ color: '#818cf8' }}>{detail.hero || '—'}</b>
      {(detail.hits || []).map((h, i) => (
        <div key={i} style={{ marginTop: 2, fontFamily: 'ui-monospace,monospace', color: '#fca5a5' }}>
          vilão <code style={{ color: '#f59e0b' }}>{h.hash}</code> ficou com o nick <b>{h.nick}</b>
        </div>
      ))}
    </div>
  )
}
function HeroAlheioDetail({ detail }) {
  const poison = detail.kind === 'poison'
  return (
    <div style={{ fontSize: 12 }}>
      <span style={{ color: '#8b9691' }}>pn.hero: </span><b style={{ color: '#fca5a5' }}>{detail.hero || '—'}</b>
      <span style={{ color: '#8b9691', marginLeft: 8 }}>apa: </span>
      <b style={{ color: detail.apa_hero ? '#818cf8' : '#f59e0b' }}>{detail.apa_hero || '—'}</b>{' '}
      <Chip color={poison ? '#ef4444' : '#eab308'}>{poison ? 'veneno — reverter' : 'cosmético'}</Chip>
    </div>
  )
}

function SuspCard({ h, onResolved }) {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const isPoison = h._group === 'hero_name_on_villain' || h._group === 'hero_alheio'
  const revert = async () => {
    if (!window.confirm(`Reverter ${h.hand_id} à ANÓNIMA?\n\nLimpa os nomes desanon (um print COM o Rui re-desanon).`)) return
    setBusy(true); setMsg(null)
    try {
      const r = await tableSs.revertToAnon(h.hand_id)
      if (r?.reverted === false) { setBusy(false); setMsg(`não revertida (${r?.reason || 'não é table_ss'})`) }
      else onResolved && onResolved()
    } catch (e) { setBusy(false); setMsg('Falha: ' + (e?.message || e)) }
  }
  const dismiss = async () => {
    setBusy(true); setMsg(null)
    try { await suspicious.dismiss(h.hand_id); onResolved && onResolved() }
    catch (e) { setBusy(false); setMsg('Falha: ' + (e?.message || e)) }
  }
  const detail = h._group === 'bounty_below_half' ? <BountyDetail detail={h.detail} />
    : h._group === 'hero_alheio' ? <HeroAlheioDetail detail={h.detail} />
      : <HeroVillainDetail detail={h.detail} />
  const btn = (bg, bd, col) => ({ background: bg, border: `1px solid ${bd}`, color: col,
    borderRadius: 8, padding: '5px 12px', fontWeight: 700, fontSize: 13, cursor: busy ? 'default' : 'pointer' })
  return (
    <div style={{ display: 'flex', gap: 14, padding: 12, border: '1px solid #30363d', borderRadius: 10,
      background: '#161b22', opacity: busy ? 0.5 : 1 }}>
      <HandImage handDbId={h.id} alt="mão" style={{ width: 240 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
          <Chip color={h._group === 'bounty_below_half' ? '#f59e0b' : '#ef4444'}>{h._label}</Chip>
          <Link to={`/hand/${h.id}`} style={{ color: '#60a5fa', fontFamily: 'ui-monospace,monospace', textDecoration: 'none', fontSize: 13 }}>{h.hand_id}</Link>
          <span style={{ fontSize: 12, color: '#8b9691' }}>{h.tournament_name || ''}</span>
          <span style={{ fontSize: 11, color: '#8b9691' }}>{fmt(h.played_at)}</span>
        </div>
        <div style={{ marginTop: 8 }}>{detail}</div>
        <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {isPoison && <button onClick={revert} disabled={busy} style={btn('rgba(239,68,68,0.12)', 'rgba(239,68,68,0.4)', '#f87171')}>Reverter à anónima</button>}
          {h._group === 'bounty_below_half' && (
            <Link to={`/hand/${h.id}`} style={{ ...btn('rgba(245,158,11,0.12)', 'rgba(245,158,11,0.4)', '#f59e0b'), textDecoration: 'none' }}>Corrigir coroa na mão</Link>
          )}
          <button onClick={dismiss} disabled={busy} style={btn('transparent', '#30363d', '#c9d1d9')}>Dispensar (legítimo)</button>
          {msg && <span style={{ fontSize: 12, color: '#ef4444' }}>{msg}</span>}
        </div>
      </div>
    </div>
  )
}

export default function SuspiciousHands() {
  return (
    <div style={{ padding: 24, maxWidth: 1100 }}>
      <h1 style={{ fontSize: 20, margin: '0 0 4px' }}>Mãos suspeitas</h1>
      <Worklist
        countLabel="marcadas"
        subtitle={<p style={{ fontSize: 12, color: '#8b9691', marginTop: 0, maxWidth: 760 }}>
          Fila de revisão (GG 2026). Reverte os venenos de identidade à anónima, ou dispensa os
          legítimos. Cada card mostra a imagem — só a imagem arbitra.
        </p>}
        emptyText="✓ Nenhuma mão suspeita."
        load={() => suspicious.list().then(d => (d?.groups || [])
          .flatMap(g => (g.hands || []).map(h => ({ ...h, _group: g.key, _label: g.label }))))}
        keyOf={(h) => `${h._group}|${h.hand_id}`}
        renderCard={(h, { resolve }) => <SuspCard h={h} onResolved={resolve} />}
      />
    </div>
  )
}
