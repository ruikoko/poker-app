import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { suspicious } from '../api/client'

// "Mãos suspeitas" — fila de revisão viva (read-only, v1: só mostrar e apontar).
// Lista as mãos GG 2026 apanhadas pelos 2 venenos puros, agrupadas por motivo.
// Cada linha aponta para a mão (abre o detalhe/replayer p/ ver a imagem).

const card = {
  background: 'var(--card, #161b22)', border: '1px solid var(--border, #30363d)',
  borderRadius: 8, padding: 16, marginBottom: 20,
}
const th = { textAlign: 'left', padding: '6px 8px', color: 'var(--muted)', fontWeight: 600, fontSize: 11, borderBottom: '1px solid var(--border,#30363d)', whiteSpace: 'nowrap' }
const td = { padding: '6px 8px', fontSize: 12, borderBottom: '1px solid rgba(255,255,255,0.04)', verticalAlign: 'top' }

function Chip({ children, color }) {
  return (
    <span style={{
      fontSize: 11, fontWeight: 700, color: color || 'var(--muted)',
      background: `${color || '#64748b'}1f`, padding: '2px 8px', borderRadius: 5,
      whiteSpace: 'nowrap', marginRight: 6,
    }}>{children}</span>
  )
}

function fmt(ts) {
  if (!ts) return '—'
  return String(ts).replace('T', ' ').replace('Z', '').slice(0, 16)
}

function BountyDetail({ detail }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {(detail.seats || []).map((s, i) => (
        <span key={i} style={{
          fontSize: 11, fontFamily: "'Fira Code', monospace",
          color: '#fca5a5', background: 'rgba(239,68,68,0.10)',
          border: '1px solid rgba(239,68,68,0.25)', borderRadius: 4, padding: '1px 6px',
        }}>
          {s.name}: <b>${s.value}</b> &lt; ${s.min}
        </span>
      ))}
    </div>
  )
}

function HeroVillainDetail({ detail }) {
  return (
    <div style={{ fontSize: 12 }}>
      <span style={{ color: 'var(--muted)' }}>Hero: </span>
      <b style={{ color: '#818cf8' }}>{detail.hero || '—'}</b>
      {(detail.hits || []).map((h, i) => (
        <div key={i} style={{ marginTop: 2, fontFamily: "'Fira Code', monospace", color: '#fca5a5' }}>
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
      <span style={{ color: 'var(--muted)' }}>pn.hero: </span>
      <b style={{ color: '#fca5a5' }}>{detail.hero || '—'}</b>
      <span style={{ color: 'var(--muted)', marginLeft: 8 }}>apa: </span>
      <b style={{ color: detail.apa_hero ? '#818cf8' : '#f59e0b' }}>{detail.apa_hero || '—'}</b>
      <Chip color={poison ? '#ef4444' : '#eab308'}>{poison ? 'veneno — reverter' : 'cosmético — sincronizar'}</Chip>
    </div>
  )
}

function GroupCard({ group }) {
  const color = group.key === 'bounty_below_half' ? '#f59e0b' : '#ef4444'
  const renderDetail = (h) => {
    if (group.key === 'bounty_below_half') return <BountyDetail detail={h.detail} />
    if (group.key === 'hero_alheio') return <HeroAlheioDetail detail={h.detail} />
    return <HeroVillainDetail detail={h.detail} />
  }
  return (
    <div style={card}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 4 }}>
        <b style={{ fontSize: 15 }}>{group.label}</b>
        <Chip color={color}>{group.count}</Chip>
      </div>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12, maxWidth: 720 }}>
        {group.description}
      </div>

      {group.hands.length === 0 ? (
        <div style={{ fontSize: 13, color: '#22c55e' }}>✓ Nenhuma mão neste motivo.</div>
      ) : (
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              <th style={th}>Mão</th>
              <th style={th}>Torneio</th>
              <th style={th}>Jogada</th>
              <th style={th}>Detalhe</th>
            </tr>
          </thead>
          <tbody>
            {group.hands.map((h) => (
              <tr key={h.id}>
                <td style={td}>
                  <Link to={`/hand/${h.id}`} style={{ color: '#60a5fa', fontFamily: "'Fira Code', monospace", textDecoration: 'none' }}>
                    {h.hand_id}
                  </Link>
                </td>
                <td style={td}>{h.tournament_name || '—'}</td>
                <td style={{ ...td, whiteSpace: 'nowrap', color: 'var(--muted)' }}>{fmt(h.played_at)}</td>
                <td style={td}>
                  {renderDetail(h)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default function SuspiciousHands() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    suspicious.list().then(setData).catch((e) => setErr(e.message))
  }, [])

  return (
    <div style={{ padding: 24, maxWidth: 1100 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 4 }}>
        <h1 style={{ fontSize: 20, margin: 0 }}>Mãos suspeitas</h1>
        {data && <Chip color="#ef4444">{data.counts.total} marcadas</Chip>}
      </div>
      <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 0, maxWidth: 760 }}>
        Fila de revisão viva (só GG, 2026). Consulta na hora — cobre o histórico e as mãos novas.
        Só mostra e aponta; sem edição no sítio. Clica na mão para abrir e ver a imagem.
      </p>

      {err && <div style={{ ...card, color: '#ef4444' }}>Erro: {err}</div>}
      {!data && !err && <div style={{ color: 'var(--muted)' }}>A carregar…</div>}
      {data && data.groups.map((g) => <GroupCard key={g.key} group={g} />)}
    </div>
  )
}
