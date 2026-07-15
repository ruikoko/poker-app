import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ggHealth, tableSs } from '../api/client'
import Worklist from '../components/Worklist'
import HandImage from '../components/HandImage'

// Vivo-$0 — worklist de RESOLUÇÃO sobre o <Worklist> base (LEI 1/3). Um jogador VIVO
// (não bustado pela HH) ficou com coroa $0 GRAVADA calada num torneio KO — o valor
// impossível (a coroa nunca é < base÷2). Carimba a coroa real (à vista na imagem) via
// /set-bounties, que ALINHA as duas gavetas (apa + players_list) pelo nome normalizado —
// é esse fix do desalinhamento que torna a escrita real (antes falhava calada). Ou
// dispensa. Campo vazio (nunca a referência como default); só a imagem arbitra.

function fmt(ts) { return ts ? String(ts).replace('T', ' ').replace('Z', '').slice(0, 16) : '—' }

function LiveZeroCard({ h, onResolved }) {
  const [val, setVal] = useState('')       // prefill VAZIO (nunca o floor como palpite)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const seal = async () => {
    const v = Number(val)
    if (!val || !(v > 0)) { setMsg('Escreve a coroa real (> 0).'); return }
    if (v < h.floor) {
      if (!window.confirm(`$${v} é MENOR que o piso $${h.floor} (base÷2). A coroa nunca é menor. Selar mesmo assim?`)) return
    }
    setBusy(true); setMsg(null)
    try {
      const r = await tableSs.setBounties(h.hand_id, { bounties: { [h.name]: v } })
      // escrita ALINHADA: se o nome não casou em nenhuma gaveta, NÃO sai da lista (LEI 1).
      // not_found/partial são ARRAYS — testar .length (um [] é truthy em JS).
      if (r?.not_found?.length || r?.partial?.length) {
        setBusy(false)
        setMsg(r.not_found?.length ? `nome não encontrado ("${h.name}") — não escreveu`
          : `escrita PARCIAL (${(r.partial || []).join(', ')}) — verifica o nome`)
        return
      }
      onResolved && onResolved()          // coroa > 0 selada → SAI DA LISTA NA HORA
    } catch (e) { setBusy(false); setMsg('Falha: ' + (e?.message || e)) }
  }
  const dismiss = async () => {
    setBusy(true); setMsg(null)
    try { await ggHealth.liveZeroDismiss(h.hand_id, h.name); onResolved && onResolved() }
    catch (e) { setBusy(false); setMsg('Falha: ' + (e?.message || e)) }
  }
  return (
    <div style={{ display: 'flex', gap: 14, padding: 12, border: '1px solid #30363d',
      borderRadius: 10, background: '#161b22', opacity: busy ? 0.5 : 1 }}>
      <HandImage handDbId={h.id} alt="mão" style={{ width: 260 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
          <Link to={`/hand/${h.id}`} style={{ color: '#60a5fa', fontFamily: 'ui-monospace,monospace', textDecoration: 'none', fontSize: 13, fontWeight: 700 }}>{h.hand_id}</Link>
          <span style={{ fontSize: 12, color: '#8b9691' }}>{h.tournament_name || ''}</span>
          <span style={{ fontSize: 11, color: '#8b9691' }}>{fmt(h.played_at)}</span>
          <span style={{ fontSize: 11, color: '#eab308' }}>piso ${h.floor} (base÷2)</span>
          {h.bucket === 'silent'
            ? <span title="$0 gravado SEM marca de revisão = escrita calada (alarme do crivo)"
                style={{ fontSize: 10, fontWeight: 700, padding: '1px 7px', borderRadius: 5, color: '#ef4444', background: 'rgba(239,68,68,0.14)', border: '1px solid rgba(239,68,68,0.35)' }}>calado (alarme)</span>
            : <span title="a guarda leu a placa e não conseguiu a coroa → $0 honesto, à espera do carimbo"
                style={{ fontSize: 10, fontWeight: 700, padding: '1px 7px', borderRadius: 5, color: '#eab308', background: 'rgba(234,179,8,0.14)', border: '1px solid rgba(234,179,8,0.35)' }}>por ler</span>}
        </div>
        <div style={{ marginTop: 8, fontSize: 13 }}>
          <b style={{ color: '#fca5a5' }}>{h.name}</b>
          <span style={{ color: '#8b9691' }}> — vivo com coroa </span>
          <b style={{ color: '#ef4444', fontFamily: 'ui-monospace,monospace' }}>$0</b>
          <span style={{ color: '#8b9691' }}> gravada (impossível num KO).</span>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <input type="number" step="1" placeholder="coroa real $" value={val}
            onChange={e => setVal(e.target.value)} disabled={busy}
            style={{ fontFamily: 'ui-monospace,monospace', fontSize: 13, width: 110,
              background: '#0b0d13', color: '#c9d1d9', border: '1px solid #30363d', borderRadius: 6, padding: '5px 8px' }} />
          <button onClick={seal} disabled={busy} style={{ background: 'rgba(34,197,94,0.12)',
            border: '1px solid rgba(34,197,94,0.4)', color: '#86efac', borderRadius: 8,
            padding: '5px 12px', fontWeight: 700, fontSize: 13, cursor: busy ? 'default' : 'pointer' }}>Selar coroa</button>
          <button onClick={dismiss} disabled={busy} style={{ background: 'transparent',
            border: '1px solid #30363d', color: '#c9d1d9', borderRadius: 8,
            padding: '5px 12px', fontWeight: 700, fontSize: 13, cursor: busy ? 'default' : 'pointer' }}>Dispensar (legítimo)</button>
          {msg && <span style={{ fontSize: 12, color: '#ef4444' }}>{msg}</span>}
        </div>
      </div>
    </div>
  )
}

export default function LiveZeroCrownsPage() {
  return (
    <div style={{ padding: 24, maxWidth: 1100 }}>
      <h1 style={{ fontSize: 20, margin: '0 0 4px' }}>Vivo com coroa $0</h1>
      <Worklist
        countLabel="por carimbar"
        subtitle={<p style={{ fontSize: 12, color: '#8b9691', marginTop: 0, maxWidth: 780 }}>
          Jogadores VIVOS (não eliminados) com coroa <b>$0</b> gravada em torneio KO — valor
          impossível (a coroa nunca é menor que base÷2). Lê a coroa na imagem e sela; a escrita
          alinha as duas gavetas (nome). Ou dispensa. Só a imagem arbitra.
        </p>}
        emptyText="✓ Nenhum vivo-$0 por carimbar."
        load={() => ggHealth.liveZeroList().then(d => d?.hands || [])}
        keyOf={(h) => `${h.hand_id}|${h.name}`}
        renderCard={(h, { resolve }) => <LiveZeroCard h={h} onResolved={resolve} />}
      />
    </div>
  )
}
