import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ggHealth } from '../api/client'
import HandImage from '../components/HandImage'

// LEI DO CRUZAMENTO — amostra do balde PREENCHER (validação do critério pelo Rui).
// READ-ONLY: nada se escreve. Cada caso mostra o seat com coroa vazia no gravado + o
// valor que a fonte IRMÃ leu, com AS DUAS imagens (a que falhou e a que leu) e a hora
// de cada uma → o olho do Rui confere na placa antes de carimbar seja o que for.

const fmt = (t) => t ? String(t).replace('T', ' ').replace('Z', '').slice(0, 16) : '—'
const srcLabel = (s) => s === 'gold' ? 'Gold' : 'SS de mesa'

function Cap({ cap, tag, tagColor }) {
  if (!cap) return (
    <div style={{ flex: 1, minWidth: 240 }}>
      <div style={{ fontSize: 11, color: '#8b9691', marginBottom: 4 }}>{tag}: (sem par)</div>
    </div>
  )
  return (
    <div style={{ flex: 1, minWidth: 240 }}>
      <div style={{ fontSize: 11, marginBottom: 4, display: 'flex', gap: 8, alignItems: 'center' }}>
        <span style={{ fontWeight: 700, color: tagColor }}>{tag}</span>
        <span style={{ color: '#8b9691' }}>{srcLabel(cap.source)} · {fmt(cap.captured_at)}</span>
      </div>
      <HandImage url={cap.image_url} alt={tag} style={{ width: '100%', maxWidth: 340 }} />
    </div>
  )
}

function CrossCard({ c }) {
  return (
    <div style={{ border: '1px solid #30363d', borderRadius: 10, background: '#161b22', padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
        <Link to={`/hand/${c.hand_db_id}`} style={{ color: '#60a5fa', fontFamily: 'ui-monospace,monospace', fontWeight: 700, fontSize: 14, textDecoration: 'none' }}>{c.hand_id}</Link>
        <span style={{ fontSize: 13 }}>
          <b style={{ color: '#fca5a5' }}>{c.seat}</b>
          <span style={{ color: '#8b9691' }}> — gravado </span>
          <b style={{ color: '#ef4444', fontFamily: 'ui-monospace,monospace' }}>{c.stored == null ? 'vazio' : `$${c.stored}`}</b>
          <span style={{ color: '#8b9691' }}> · fonte irmã leu </span>
          <b style={{ color: '#86efac', fontFamily: 'ui-monospace,monospace' }}>${c.value}</b>
          <span style={{ color: '#8b9691' }}> ({srcLabel(c.read.source)})</span>
        </span>
      </div>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        <Cap cap={c.read} tag="✓ LEU a coroa" tagColor="#86efac" />
        <Cap cap={c.failed} tag="✗ FALHOU (vazia)" tagColor="#f87171" />
      </div>
    </div>
  )
}

export default function CrossingSample() {
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const load = () => {
    setBusy(true); setErr(null)
    ggHealth.crossingFillSample(4).then(d => { setData(d); setBusy(false) })
      .catch(e => { setErr(e?.message || String(e)); setBusy(false) })
  }
  useEffect(() => { load() }, [])
  return (
    <div style={{ padding: 24, maxWidth: 1000 }}>
      <h1 style={{ fontSize: 20, margin: '0 0 4px' }}>Cruzamento — amostra (validar critério)</h1>
      <p style={{ fontSize: 12, color: '#8b9691', marginTop: 0, maxWidth: 780 }}>
        4 mãos ao acaso do balde <b>PREENCHER</b> ({data?.total_fill_seats ?? '…'} seats no total):
        coroa vazia no gravado, uma fonte irmã leu um valor. Confere na <b>placa</b> das duas imagens
        se o valor proposto é real. <b>Nada se escreve</b> — é só para o teu olho validar antes de carimbar.
      </p>
      <div style={{ margin: '10px 0 14px' }}>
        <button onClick={load} disabled={busy} style={{ background: 'transparent', border: '1px solid #30363d',
          color: '#c9d1d9', borderRadius: 8, padding: '6px 14px', fontWeight: 700, fontSize: 13,
          cursor: busy ? 'default' : 'pointer' }}>{busy ? '…' : '↻ Outras 4 ao acaso'}</button>
      </div>
      {err && <div style={{ color: '#ef4444', fontSize: 13 }}>Erro: {err}</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {(data?.sample || []).map((c, i) => <CrossCard key={`${c.hand_id}-${c.seat}-${i}`} c={c} />)}
      </div>
    </div>
  )
}
