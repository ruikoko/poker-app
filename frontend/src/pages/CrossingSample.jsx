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
const reasonLabel = (r) => r === 'below_floor' ? 'abaixo do piso (base÷2) — impossível'
  : r === 'descends_vs_earlier' ? 'desce vs leitura anterior (a coroa só sobe)'
    : r === 'exceeds_later' ? 'excede leitura posterior'
      : r || '—'

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

function CrossCard({ c, suspect }) {
  return (
    <div style={{ border: `1px solid ${suspect ? 'rgba(239,68,68,0.4)' : '#30363d'}`, borderRadius: 10,
      background: suspect ? 'rgba(239,68,68,0.05)' : '#161b22', padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
        <Link to={`/hand/${c.hand_db_id}`} style={{ color: '#60a5fa', fontFamily: 'ui-monospace,monospace', fontWeight: 700, fontSize: 14, textDecoration: 'none' }}>{c.hand_id}</Link>
        <span style={{ fontSize: 13 }}>
          <b style={{ color: '#fca5a5' }}>{c.seat}</b>
          <span style={{ color: '#8b9691' }}> — gravado </span>
          <b style={{ color: '#ef4444', fontFamily: 'ui-monospace,monospace' }}>{c.stored == null ? 'vazio' : `$${c.stored}`}</b>
          <span style={{ color: '#8b9691' }}> · fonte irmã leu </span>
          <b style={{ color: suspect ? '#f87171' : '#86efac', fontFamily: 'ui-monospace,monospace' }}>${c.value}</b>
          <span style={{ color: '#8b9691' }}> ({srcLabel(c.read.source)}) · piso ${c.floor}</span>
        </span>
        {suspect && (
          <span style={{ fontSize: 11, fontWeight: 700, color: '#f87171', background: 'rgba(239,68,68,0.14)',
            border: '1px solid rgba(239,68,68,0.35)', borderRadius: 5, padding: '1px 7px' }}>
            crivada: {reasonLabel(c.sieve_reason)}
          </span>
        )}
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
      <p style={{ fontSize: 12, color: '#8b9691', marginTop: 0, maxWidth: 820 }}>
        O balde PREENCHER passa agora pelo <b>crivo da física</b> ("outra captura leu" NÃO é prova).
        Só se propõe o valor da fonte irmã se passar: <b>floor</b> (nunca &lt; base÷2) + <b>não-desce</b>
        (a coroa só sobe na trajetória do jogador). Em baixo, 4 <b>propostas</b> (passaram) e 4 <b>irmãs
        suspeitas</b> (crivadas) — confere na placa das duas imagens. <b>Nada se escreve.</b>
      </p>
      {data?.counts && (
        <div style={{ fontSize: 13, margin: '4px 0 10px' }}>
          <b style={{ color: '#86efac' }}>{data.counts.passed}</b> passam o crivo
          {' · '}<b style={{ color: '#f87171' }}>{data.counts.suspect}</b> irmãs suspeitas
          {' · '}{data.counts.total} propostas brutas
        </div>
      )}
      <div style={{ margin: '10px 0 14px' }}>
        <button onClick={load} disabled={busy} style={{ background: 'transparent', border: '1px solid #30363d',
          color: '#c9d1d9', borderRadius: 8, padding: '6px 14px', fontWeight: 700, fontSize: 13,
          cursor: busy ? 'default' : 'pointer' }}>{busy ? '…' : '↻ Outras 4+4 ao acaso'}</button>
      </div>
      {err && <div style={{ color: '#ef4444', fontSize: 13 }}>Erro: {err}</div>}

      <div style={{ fontSize: 14, fontWeight: 800, color: '#86efac', margin: '6px 0 8px' }}>
        Propostas — passaram o crivo ({data?.counts?.passed ?? 0})
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {(data?.sample || []).map((c, i) => <CrossCard key={`p-${c.hand_id}-${c.seat}-${i}`} c={c} />)}
      </div>

      <div style={{ fontSize: 14, fontWeight: 800, color: '#f87171', margin: '22px 0 8px' }}>
        Irmã suspeita — crivadas pela física ({data?.counts?.suspect ?? 0})
        <span style={{ fontWeight: 400, color: '#8b9691', fontSize: 12, marginLeft: 8 }}>
          o que a física apanhou — não se propõe
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {(data?.suspects || []).map((c, i) => <CrossCard key={`s-${c.hand_id}-${c.seat}-${i}`} c={c} suspect />)}
      </div>
    </div>
  )
}
