import { useState, useEffect } from 'react'
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
      const r = await tableSs.setBounties(h.hand_id, { bounties: { [h.name]: v },
        stamps: { [h.name]: 'placa' }, origin: 'live_zero_crowns' })
      // escrita ALINHADA: se o nome não casou em nenhuma gaveta, NÃO sai da lista (LEI 1).
      // not_found/partial são ARRAYS — testar .length (um [] é truthy em JS). Distingue
      // partial (gravou numa gaveta) de not_found (não gravou nada) — Peça 1.
      if (r?.not_found?.length || r?.partial?.length) {
        setBusy(false)
        setMsg(r.not_found?.length ? `não gravou nada — nome não encontrado ("${h.name}")`
          : `gravado só numa gaveta (${(r.partial || []).join(', ')}) — a outra tem grafia diferente`)
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

function WholeTableConfirmCard({ r, onStamped }) {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [done, setDone] = useState(false)      // LEI 1: card carimbado fica inerte
  const readable = (r.seats || []).filter(s => s.read && Number(s.read) > 0)
  const nTotal = r.n_total ?? r.n_seats        // Y = lugares da captura (X de Y)
  const stamp = async () => {
    if (done) return
    if (!readable.length) { setMsg('Nada legível para carimbar.'); return }
    if (!window.confirm(`Carimbar ${readable.length} coroas relidas em ${r.hand_id} (selado manual)?`)) return
    setBusy(true); setMsg(null)
    try {
      const bounties = Object.fromEntries(readable.map(s => [s.name, Number(s.read)]))
      // valores RELIDOS pela máquina, aprovados em lote → aceitacao (DOIS CARIMBOS)
      const res = await tableSs.setBounties(r.hand_id, { bounties,
        stamps: Object.fromEntries(readable.map(s => [s.name, 'aceitacao'])),
        origin: 'live_zero_crowns.whole_table_reread' })
      const nf = res?.not_found || [], part = res?.partial || []
      if (nf.length || part.length) {        // Peça 1: partial ≠ not_found
        setBusy(false)
        setMsg(nf.length ? `não gravou nada — nome não encontrado: ${nf.join(', ')}`
          : `gravado só numa gaveta (${part.join(', ')}) — a outra tem grafia diferente`)
        return
      }
      setDone(true); setBusy(false)
      setMsg(`✓ ${readable.length} carimbadas — selado.`)
      onStamped && onStamped(r.hand_id)      // LEI 1: sai da lista + a lista re-confere a BD
    } catch (e) { setBusy(false); setMsg('Falha: ' + (e?.message || e)) }
  }
  return (
    <div style={{ display: 'flex', gap: 14, padding: 12, border: '1px solid #30363d', borderRadius: 10, background: '#161b22', opacity: (busy || done) ? 0.5 : 1 }}>
      <HandImage handDbId={r.id} alt="mesa" style={{ width: 260 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
          <Link to={`/hand/${r.id}`} style={{ color: '#60a5fa', fontFamily: 'ui-monospace,monospace', fontWeight: 700, fontSize: 13, textDecoration: 'none' }}>{r.hand_id}</Link>
          <span style={{ fontSize: 12, color: '#8b9691' }}>{r.tournament_name}</span>
          <span style={{ fontSize: 11, color: r.n_read ? '#86efac' : '#f87171' }}>releu {r.n_read}/{r.n_seats}</span>
          <span style={{ fontSize: 11, color: '#8b9691' }}>a mostrar {r.n_seats} de {nTotal} lugares</span>
        </div>
        <div style={{ fontSize: 12, marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: '2px 12px' }}>
          {(r.seats || []).map((s, i) => (
            <span key={i} style={{ fontFamily: 'ui-monospace,monospace', color: s.read ? '#c9d1d9' : '#6b7280' }}>
              {s.name}: <span style={{ color: '#f87171' }}>$0</span>→<b style={{ color: s.read ? '#86efac' : '#6b7280' }}>{s.read ? `$${s.read}` : '—'}</b>
            </span>
          ))}
        </div>
        <div style={{ marginTop: 10, display: 'flex', gap: 8, alignItems: 'center' }}>
          <button onClick={stamp} disabled={busy || done || !readable.length} style={{ background: (readable.length && !done) ? 'rgba(34,197,94,0.14)' : '#21262d', border: `1px solid ${(readable.length && !done) ? 'rgba(34,197,94,0.5)' : '#30363d'}`, color: (readable.length && !done) ? '#86efac' : '#6b7280', borderRadius: 8, padding: '5px 12px', fontWeight: 700, fontSize: 13, cursor: (busy || done) ? 'default' : 'pointer' }}>
            {done ? '✓ selado' : `Carimbar os lidos (${readable.length})`}
          </button>
          {msg && <span style={{ fontSize: 12, color: msg.startsWith('✓') ? '#86efac' : '#ef4444' }}>{msg}</span>}
        </div>
      </div>
    </div>
  )
}

function WholeTablePanel() {
  const [st, setSt] = useState(null)
  const [stamped, setStamped] = useState(() => new Set())   // LEI 1: cards carimbados saem já
  const load = () => ggHealth.liveZeroWholeTable().then(setSt).catch(() => {})
  const onStamped = (handId) => {
    setStamped(prev => { const n = new Set(prev); n.add(handId); return n })  // remoção otimista
    load()                                                   // re-confere a BD ao vivo (LEI 1)
  }
  useEffect(() => { load() }, [])
  useEffect(() => {
    if (st?.status !== 'running') return
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [st?.status])
  const running = st?.status === 'running'
  const hands = st?.hands || []
  const reread = async () => {
    if (!window.confirm(`Reler ${hands.length} mesas via Vision? Custo = ${hands.length} chamadas. Não escreve — vais confirmar cada uma.`)) return
    await ggHealth.liveZeroWholeTableReread(); load()
  }
  if (!st || hands.length === 0) return null
  return (
    <div style={{ marginTop: 26 }}>
      <div style={{ fontSize: 14, fontWeight: 800, color: '#eab308', margin: '0 0 4px' }}>
        Mesas-toda-$0 — releitura dirigida ({hands.length} mãos)
      </div>
      <div style={{ fontSize: 12, color: '#8b9691', marginBottom: 10, maxWidth: 820 }}>
        A SS falhou as coroas em bloco. Relê a captura com a Vision (prompt atual) e confere:
        <b> nada escreve</b> — carimbas tu cada card. Custo = 1 chamada por mesa.
      </div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
        <button onClick={reread} disabled={running} style={{ background: running ? '#21262d' : 'rgba(234,179,8,0.14)', border: '1px solid rgba(234,179,8,0.5)', color: running ? '#6b7280' : '#eab308', borderRadius: 8, padding: '6px 14px', fontWeight: 700, fontSize: 13, cursor: running ? 'default' : 'pointer' }}>
          {running ? `A reler… ${st.done}/${st.total}` : `↻ Reler as ${hands.length} (Vision · ${hands.length} chamadas)`}
        </button>
        {running && <button onClick={() => ggHealth.liveZeroWholeTableCancel().then(load)} style={{ background: 'transparent', border: '1px solid #ef4444', color: '#f87171', borderRadius: 8, padding: '6px 14px', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}>Cancelar</button>}
        {st.status === 'cancelled' && <span style={{ fontSize: 12, color: '#f87171' }}>interrompida (parcial mantido)</span>}
        {st.status === 'done' && <span style={{ fontSize: 12, color: '#86efac' }}>releitura concluída</span>}
      </div>
      {(() => {
        const results = (st.results || []).filter(r => !stamped.has(r.hand_id))
        return results.length > 0
      })() ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {(st.results || []).filter(r => !stamped.has(r.hand_id)).map((r, i) => (
            <WholeTableConfirmCard key={`${r.hand_id}-${i}`} r={r} onStamped={onStamped} />
          ))}
        </div>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 14px' }}>
          {hands.map((h, i) => (
            <Link key={i} to={`/hand/${h.id}`} title={h.tournament_name} style={{ color: '#8b9691', fontSize: 12, fontFamily: 'ui-monospace,monospace', textDecoration: 'none' }}>{h.hand_id}</Link>
          ))}
        </div>
      )}
    </div>
  )
}

export default function LiveZeroCrownsPage() {
  const [elim, setElim] = useState(null)
  const [none, setNone] = useState(null)
  useEffect(() => {
    ggHealth.liveZeroEliminated().then(d => setElim(d)).catch(() => {})
    ggHealth.liveZeroNone().then(d => setNone(d)).catch(() => {})
  }, [])
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

      {/* ── BALDE 2: mesas-toda-$0 → releitura dirigida (cards de confirmação) ── */}
      <WholeTablePanel />

      {/* ── BALDE 3: NONE / sem identidade — leitura falhada do seat ── */}
      {none && none.count > 0 && (
        <div style={{ marginTop: 26 }}>
          <div style={{ fontSize: 14, fontWeight: 800, color: '#f87171', margin: '0 0 4px' }}>
            NONE / sem identidade — {none.count} seat(s)
          </div>
          <div style={{ fontSize: 12, color: '#8b9691', marginBottom: 8, maxWidth: 820 }}>
            O seat foi lido <b>sem nome</b> (leitura falhada) → não se carimba coroa num seat sem
            dono. Re-ler o seat da imagem, ou limpar o fantasma. Confere na imagem primeiro.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {none.items.map((n, i) => (
              <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', border: '1px solid #21262d', borderRadius: 8, background: '#0f1319', padding: 10 }}>
                <HandImage handDbId={n.id} alt="mão" style={{ width: 200 }} />
                <div>
                  <Link to={`/hand/${n.id}`} style={{ color: '#60a5fa', fontFamily: 'ui-monospace,monospace', fontWeight: 700, fontSize: 13, textDecoration: 'none' }}>{n.hand_id}</Link>
                  <div style={{ fontSize: 12, color: '#8b9691', marginTop: 4 }}>seat <b style={{ color: '#f87171' }}>{n.name}</b> · {n.tournament_name}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── BALDE 1 (informativo): eliminados cross-hand — saíram do painel ── */}
      {elim && elim.count > 0 && (
        <div style={{ marginTop: 26 }}>
          <div style={{ fontSize: 14, fontWeight: 800, color: '#8b9691', margin: '0 0 4px' }}>
            Eliminados (saíram do painel) — {elim.count} seats / {elim.hands_count} mãos
          </div>
          <div style={{ fontSize: 12, color: '#8b9691', marginBottom: 8, maxWidth: 820 }}>
            O hash destes seats <b>não reaparece</b> numa mão posterior do torneio → estão
            <b> eliminados</b> (a régua por-mão não os apanhava). O $0 deles é o padrão do bust —
            recupera-se pelo <b>verde×2</b> (fluxo dos recuperáveis), não com carimbo de coroa aqui.
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 14px' }}>
            {elim.items.map((e, i) => (
              <Link key={i} to={`/hand/${e.id}`} title={e.tournament_name}
                style={{ color: '#8b9691', fontSize: 12, fontFamily: 'ui-monospace,monospace', textDecoration: 'none' }}>
                {e.hand_id}·{e.name}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
