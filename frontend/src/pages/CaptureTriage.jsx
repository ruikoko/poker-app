import { useState } from 'react'
import { Link } from 'react-router-dom'
import { captureTriage } from '../api/client'
import Worklist from '../components/Worklist'
import HandImage from '../components/HandImage'

// Marcadas por captura — worklist de resolução sobre o <Worklist> base (LEI 3): filtro
// ao-vivo embutido (resolvida sai na hora + re-confere no focus). Tags de 1 clique (canal
// Discord) + descartar; a tag integra a mão no fluxo normal (Estudo/Vilões).
const TAGS = [
  { tag: 'icm-pko', label: 'icm-pko', color: '#6366f1' },
  { tag: 'pos-pko', label: 'pos-pko', color: '#0ea5e9' },
  { tag: 'icm', label: 'icm', color: '#22c55e' },
  { tag: 'nota', label: 'nota', color: '#f59e0b' },
  { tag: '__discard__', label: 'descartar', color: '#ef4444' },
]

function fmtDate(iso) {
  if (!iso) return '—'
  return String(iso).replace('T', ' ').slice(0, 16)   // ISO sem offset = Lisboa naive (pt51)
}

function TriageCard({ h, onResolved }) {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const apply = async (tag) => {
    setBusy(true); setMsg(null)
    try {
      await captureTriage.tag(h.hand_id, tag)
      onResolved && onResolved()          // tagada/descartada → SAI DA LISTA NA HORA
    } catch (e) { setBusy(false); setMsg('Falha: ' + (e?.message || e)) }
  }
  return (
    <div style={{ display: 'flex', gap: 14, padding: 12, border: '1px solid var(--border)',
      borderRadius: 8, background: 'var(--surface)', opacity: busy ? 0.5 : 1 }}>
      <HandImage handDbId={h.id} alt="SS de mesa" style={{ width: 240 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <Link to={`/hand/${h.id}`} style={{ fontSize: 13, fontWeight: 600, color: '#60a5fa',
            textDecoration: 'none', fontFamily: 'ui-monospace,monospace' }}>{h.hand_id}</Link>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>{h.tournament_name || ''}</span>
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>{fmtDate(h.played_at)}</span>
          {h.deanon_partial && (
            <span title="Nem todos os bancos foram mapeados (ambíguos ficaram por mapear)"
              style={{ fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
                background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.3)', color: '#f59e0b' }}>parcial</span>
          )}
        </div>
        <div style={{ fontSize: 12, lineHeight: 1.5, marginTop: 6 }}>
          {(h.players || []).map((p, i) => (
            <span key={i} style={{ fontWeight: p === h.hero ? 700 : 400,
              color: p === h.hero ? 'var(--text)' : 'var(--muted)' }}>
              {p}{i < h.players.length - 1 ? ' · ' : ''}
            </span>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {TAGS.map(t => (
            <button key={t.tag} disabled={busy} onClick={() => apply(t.tag)}
              style={{ padding: '5px 12px', fontSize: 12, fontWeight: 600, borderRadius: 5,
                cursor: busy ? 'default' : 'pointer',
                background: t.tag === '__discard__' ? 'transparent' : `${t.color}1a`,
                border: `1px solid ${t.color}55`, color: t.color }}>{t.label}</button>
          ))}
          {msg && <span style={{ fontSize: 12, color: '#ef4444' }}>{msg}</span>}
        </div>
      </div>
    </div>
  )
}

export default function CaptureTriagePage() {
  return (
    <div style={{ padding: 24, maxWidth: 1180, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 4px' }}>Marcadas por captura</h1>
      <Worklist
        countLabel="por triar"
        subtitle={<div style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 8px' }}>
          Mãos GG desanonimizadas pela SS de mesa (sem entrada Discord). Escolhe UMA tag —
          integra-se no Estudo/Vilões como se viesse do Discord — ou descarta.
        </div>}
        emptyText="Nada para triar. Capturas novas do Intuitive Tables aparecem aqui."
        load={() => captureTriage.list().then(d => d?.hands || [])}
        keyOf={(h) => h.hand_id}
        renderCard={(h, { resolve }) => <TriageCard h={h} onResolved={resolve} />}
      />
    </div>
  )
}
