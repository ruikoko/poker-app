import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ggHealth, API_ROOT } from '../api/client'
import ZoomImg from '../components/ZoomImg'

// Amostrador de coroas Gold — #CROWN-SAMPLE-VERIFY.
// Modo por defeito: "Ver candidatas" (177 mãos com IMAGEM + coroas GRAVADAS por
// seat + selo do grupo + link) SEM Vision, sem custo, sem escrita. A releitura
// Vision (botão Correr) é um passo OPCIONAL por cima, que sobrepõe a divergência.

const C = {
  card: '#171b21', border: 'rgba(255,255,255,0.10)', text: '#e6e9ee',
  muted: '#8a93a0', yellow: '#f2c14e', red: '#d05a5a', green: '#4ea86b',
}
const PAGE = 12

export default function CrownSample() {
  const [cands, setCands] = useState(null)   // {total, sliver, candidates}
  const [st, setSt] = useState(null)         // estado do run (releitura)
  const [busy, setBusy] = useState(false)
  const [page, setPage] = useState(0)
  const poll = useRef(null)

  const loadCands = () => ggHealth.crownSampleCandidates().then(setCands).catch(() => {})
  const refresh = () => ggHealth.crownSampleState().then(setSt).catch(() => {})
  useEffect(() => { loadCands(); refresh(); return () => clearInterval(poll.current) }, [])

  useEffect(() => {
    clearInterval(poll.current)
    if (st?.status === 'running') poll.current = setInterval(refresh, 3000)
    return () => clearInterval(poll.current)
  }, [st?.status])

  const run = async () => {
    setBusy(true)
    try { await ggHealth.crownSampleRun(); await refresh() } finally { setBusy(false) }
  }
  const cancel = async () => {
    setBusy(true)
    try { await ggHealth.crownSampleCancel(); await refresh() } finally { setBusy(false) }
  }

  const running = st?.status === 'running'
  const cancelled = st?.status === 'cancelled'

  // reread por mão+seat (sobreposição): hand_db_id -> {seat -> reread}
  const rereadByHand = useMemo(() => {
    const m = {}
    for (const d of (st?.divergences || [])) {
      m[d.hand_db_id] = Object.fromEntries(d.seats.map(s => [s.seat, s.reread]))
    }
    return m
  }, [st?.divergences])

  const list = cands?.candidates || []
  const nPages = Math.max(1, Math.ceil(list.length / PAGE))
  const pageItems = list.slice(page * PAGE, page * PAGE + PAGE)

  return (
    <div style={{ padding: '18px 22px', color: C.text, maxWidth: 1000, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, fontWeight: 800, margin: '0 0 4px' }}>Amostrador de coroas Gold</h1>
      <p style={{ color: C.muted, fontSize: 13, margin: '0 0 14px', lineHeight: 1.5 }}>
        <b>Ver candidatas</b> — as Golds KO/PKO <b>pré-refinamento de 9 Jul</b> + uma amostra
        sorteada do in-band (sorteio fixo, lista estável). Revê à vista as coroas
        <b>gravadas</b>. A releitura pela Vision é <b>opcional</b>, por cima — e não escreve nada.
      </p>

      <div style={{ background: 'rgba(242,193,78,0.09)', border: `1px solid ${C.yellow}`,
        borderRadius: 8, padding: '10px 12px', marginBottom: 16, fontSize: 12.5,
        color: C.text, lineHeight: 1.5 }}>
        ⚠️ <b>Limitação (só afeta a releitura):</b> a Vision corre sobre a cópia
        <b> comprimida</b> guardada (o original não é retido). Um <b>"—"</b> na releitura
        pode ser degradação, não prova; os pares <b>valor→valor</b> pesam.
      </div>

      {/* controlos */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <button onClick={run} disabled={busy || running}
          style={{ background: running ? '#2a2f37' : 'transparent', color: running ? C.muted : C.yellow,
            border: `1px solid ${C.yellow}`, borderRadius: 8, padding: '8px 14px', fontWeight: 700,
            cursor: busy || running ? 'default' : 'pointer', fontSize: 13 }}>
          {running ? 'A reler…' : busy ? '…' : 'Correr releitura (opcional)'}
        </button>
        {running && (
          <button onClick={cancel} disabled={busy}
            style={{ background: 'transparent', color: C.red, border: `1px solid ${C.red}`,
              borderRadius: 8, padding: '8px 14px', fontWeight: 700,
              cursor: busy ? 'default' : 'pointer', fontSize: 13 }}>
            Cancelar
          </button>
        )}
        {cands && (
          <span style={{ color: C.muted, fontSize: 13 }}>
            {cands.total} candidatas · {cands.sliver} pré-refinamento 9 Jul
          </span>
        )}
        {st && st.total > 0 && (running || st.status === 'done' || cancelled) && (
          <span style={{ fontSize: 13, color: C.muted }}>
            releitura {st.done}/{st.total}{cancelled && <b style={{ color: C.red }}> · interrompida</b>}
            {' · '}<b style={{ color: st.divergent_hands ? C.red : C.green }}>{st.divergent_hands}</b> mãos c/ divergência
          </span>
        )}
      </div>

      {/* paginação */}
      {list.length > PAGE && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
            style={pgBtn(page === 0)}>← anterior</button>
          <span style={{ color: C.muted, fontSize: 13 }}>página {page + 1}/{nPages}</span>
          <button onClick={() => setPage(p => Math.min(nPages - 1, p + 1))} disabled={page >= nPages - 1}
            style={pgBtn(page >= nPages - 1)}>seguinte →</button>
        </div>
      )}

      {!cands && <div style={{ color: C.muted }}>A carregar candidatas…</div>}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {pageItems.map(c => {
          const rr = rereadByHand[c.hand_db_id] || {}
          return (
            <div key={c.hand_db_id} style={{ background: C.card, border: `1px solid ${C.border}`,
              borderRadius: 10, padding: 12, display: 'flex', gap: 14, flexWrap: 'wrap' }}>
              {c.entry_id != null && (
                <ZoomImg src={`${API_ROOT}/api/screenshots/image/${c.entry_id}`} alt="gold"
                  onError={e => { e.currentTarget.style.display = 'none'
                    const n = e.currentTarget.nextSibling; if (n) n.style.display = 'flex' }}
                  style={{ width: 300, maxWidth: '100%', borderRadius: 8, objectFit: 'contain',
                    border: `1px solid ${C.border}`, background: '#000' }} />
              )}
              {c.entry_id != null && (
                <div style={{ display: 'none', width: 300, maxWidth: '100%', minHeight: 110,
                  alignItems: 'center', justifyContent: 'center', borderRadius: 8,
                  border: `1px dashed ${C.border}`, color: C.muted, fontSize: 12 }}>
                  imagem indisponível — abre a mão
                </div>
              )}
              <div style={{ flex: 1, minWidth: 240 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                  <Link to={`/hrc-results/hand/${c.hand_db_id}`}
                    style={{ color: C.yellow, fontWeight: 700, fontSize: 14, textDecoration: 'none' }}>
                    {c.hand_id}
                  </Link>
                  <span style={{ color: C.muted, fontSize: 12 }}>{c.tournament}</span>
                  {c.sliver && <span style={{ fontSize: 11, color: '#0b0d10', background: C.yellow,
                    borderRadius: 4, padding: '1px 6px', fontWeight: 700 }}>pré-refinamento 9 Jul</span>}
                </div>
                {c.crowns.length === 0
                  ? <div style={{ color: C.muted, fontSize: 12, marginTop: 8 }}>sem coroas lidas</div>
                  : (
                    <table style={{ marginTop: 8, fontSize: 13, borderCollapse: 'collapse', width: '100%' }}>
                      <thead>
                        <tr style={{ color: C.muted, textAlign: 'left' }}>
                          <th style={{ padding: '2px 8px 2px 0' }}>Seat</th>
                          <th style={{ padding: '2px 8px' }}>Gravado</th>
                          <th style={{ padding: '2px 8px' }}>Releitura</th>
                        </tr>
                      </thead>
                      <tbody>
                        {c.crowns.map((cr, i) => {
                          const hasRR = Object.prototype.hasOwnProperty.call(rr, cr.seat)
                          return (
                            <tr key={i}>
                              <td style={{ padding: '2px 8px 2px 0' }}>{cr.seat}</td>
                              <td style={{ padding: '2px 8px' }}>{cr.stored == null ? '—' : `$${cr.stored}`}</td>
                              <td style={{ padding: '2px 8px', color: hasRR ? C.red : C.muted,
                                fontWeight: hasRR ? 700 : 400 }}>
                                {hasRR ? (rr[cr.seat] == null ? '—' : `$${rr[cr.seat]}`) : ''}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function pgBtn(disabled) {
  return {
    background: 'transparent', border: `1px solid ${C.border}`,
    color: disabled ? '#3a3f47' : C.text, borderRadius: 6, padding: '4px 10px',
    cursor: disabled ? 'default' : 'pointer', fontSize: 13,
  }
}
