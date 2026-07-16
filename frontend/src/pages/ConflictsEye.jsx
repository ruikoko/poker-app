import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ggHealth, tableSs } from '../api/client'
import HandImage from '../components/HandImage'

// LEI DO CRUZAMENTO — CONFLITOS (decisão (B) do Rui). Auto: crescimento óbvio (mais
// recente = max e ≥ base) resolve pela física (botão de carimbo). Eye: incompatíveis →
// cada card mostra os valores lidos com fonte/hora/IMAGEM; o Rui escolhe → /set-bounties
// (manual, selado) → sai da lista. Selos intocáveis.

const fmt = (t) => t ? String(t).replace('T', ' ').replace('Z', '').slice(0, 16) : '—'
const src = (s) => s === 'gold' ? 'Gold' : 'SS'
const reasonLabel = (r) => r === 'recent_below_max' ? 'a leitura mais recente é MENOR (misread/queda)'
  : r === 'below_floor' ? 'o maior é < coroa fresca (base÷2) — provável chama/misread'
    : r === 'descends_vs_earlier' ? 'desce vs leitura anterior (a coroa só sobe)'
      : r === 'exceeds_later' ? 'excede leitura posterior'
        : r === 'split_arbitra' ? 'valor de SPLIT° em jogo (pote dividido) — arbitra tu'
          : r === 'ambas_impossiveis' ? 'ambas fora-da-grelha (nenhuma possível)'
            : r === 'ambos_possiveis' ? 'ambas possíveis (na grelha) — decide'
              : r === 'off_nao_chama' ? 'o valor a descartar é DECIMAL (não é chama) — arbitra tu'
                : r === 'fails_physics' ? 'falha a física da trajetória'
                  : r || '—'

function distinctVals(readings) {
  const m = new Map()
  for (const r of readings || []) {
    const k = Number(r.value)
    if (!m.has(k)) m.set(k, r)   // uma imagem representante por valor
  }
  return [...m.entries()].sort((a, b) => a[0] - b[0])
}

function EyeCard({ c, onResolved }) {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [free, setFree] = useState('')
  const seal = async (val) => {
    if (!(Number(val) > 0)) { setMsg('Valor inválido.'); return }
    if (!window.confirm(`Selar ${c.seat} = $${val} (manual)?`)) return
    setBusy(true); setMsg(null)
    try {
      const r = await tableSs.setBounties(c.hand_id, { bounties: { [c.seat]: Number(val) } })
      if (r?.not_found?.length || r?.partial?.length) {
        setBusy(false); setMsg('nome não casou — verifica'); return
      }
      onResolved && onResolved()
    } catch (e) { setBusy(false); setMsg('Falha: ' + (e?.message || e)) }
  }
  const dv = distinctVals(c.readings)
  const storedInReadings = dv.some(([v]) => Math.abs(v - c.stored) < 0.01)
  return (
    <div style={{ border: '1px solid rgba(239,68,68,0.35)', borderRadius: 10, background: 'rgba(239,68,68,0.05)',
      padding: 14, opacity: busy ? 0.5 : 1 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
        <Link to={`/hand/${c.hand_db_id}`} style={{ color: '#60a5fa', fontFamily: 'ui-monospace,monospace', fontWeight: 700, fontSize: 14, textDecoration: 'none' }}>{c.hand_id}</Link>
        <b style={{ color: '#fca5a5' }}>{c.seat}</b>
        <span style={{ fontSize: 11, fontWeight: 700, color: '#f87171', background: 'rgba(239,68,68,0.14)', border: '1px solid rgba(239,68,68,0.35)', borderRadius: 5, padding: '1px 7px' }}>{reasonLabel(c.reason)}</span>
        <span style={{ fontSize: 11, color: '#8b9691', width: '100%' }}>
          gravado <b style={{ color: '#c9d1d9' }}>${c.stored}</b> <span style={{ opacity: 0.8 }}>(fonte: {c.stored_source || '—'}{c.stored_seen_in_hands > 1 ? ` · visto em ${c.stored_seen_in_hands} mãos do torneio` : ''})</span>
          {' · '}{c.tournament} · coroa fresca ${c.floor}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        {/* o GRAVADO como opção (com proveniência) quando não é uma das leituras à vista */}
        {!storedInReadings && c.stored > 0 && (
          <div style={{ minWidth: 180 }}>
            <div style={{ fontSize: 12, marginBottom: 4 }}>
              <b style={{ color: '#e6e9ee', fontFamily: 'ui-monospace,monospace' }}>${c.stored}</b>
              <span style={{ color: '#8b9691' }}> · gravado ({c.stored_source}{c.stored_seen_in_hands > 1 ? `, ${c.stored_seen_in_hands} mãos` : ''})</span>
            </div>
            <div style={{ width: '100%', maxWidth: 300, minHeight: 60, borderRadius: 7, border: '1px dashed rgba(255,255,255,0.15)', color: '#8b9691', fontSize: 11, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 8 }}>sem imagem própria (leitura/propagação)</div>
            <button onClick={() => seal(c.stored)} disabled={busy} style={{ marginTop: 6, width: '100%', background: 'rgba(34,197,94,0.14)', border: '1px solid rgba(34,197,94,0.5)', color: '#86efac', borderRadius: 8, padding: '5px 10px', fontWeight: 700, fontSize: 13, cursor: busy ? 'default' : 'pointer' }}>Mantém ${c.stored} (selar)</button>
          </div>
        )}
        {dv.map(([val, r]) => (
          <div key={val} style={{ minWidth: 200 }}>
            <div style={{ fontSize: 12, marginBottom: 4 }}>
              <b style={{ color: '#e6e9ee', fontFamily: 'ui-monospace,monospace' }}>${val}</b>
              <span style={{ color: '#8b9691' }}> · {src(r.source)} · {fmt(r.captured_at)}</span>
            </div>
            <HandImage url={r.image_url} alt={`$${val}`} style={{ width: '100%', maxWidth: 300 }} />
            <button onClick={() => seal(val)} disabled={busy} style={{ marginTop: 6, width: '100%',
              background: 'rgba(34,197,94,0.14)', border: '1px solid rgba(34,197,94,0.5)', color: '#86efac',
              borderRadius: 8, padding: '5px 10px', fontWeight: 700, fontSize: 13, cursor: busy ? 'default' : 'pointer' }}>
              Fica ${val} (selar)
            </button>
          </div>
        ))}
      </div>
      {/* CAMPO LIVRE: nenhum dos valores é o da placa → corrige tu */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, color: '#8b9691' }}>Nenhum bate a placa? Corrige:</span>
        <input type="number" step="0.01" placeholder="$___" value={free} onChange={e => setFree(e.target.value)} disabled={busy}
          style={{ width: 100, fontFamily: 'ui-monospace,monospace', fontSize: 13, background: '#0b0d13', color: '#c9d1d9', border: '1px solid #30363d', borderRadius: 6, padding: '4px 8px' }} />
        <button onClick={() => seal(free)} disabled={busy || !(Number(free) > 0)} style={{ background: 'rgba(56,189,248,0.14)', border: '1px solid rgba(56,189,248,0.5)', color: '#38bdf8', borderRadius: 8, padding: '5px 12px', fontWeight: 700, fontSize: 13, cursor: busy ? 'default' : 'pointer' }}>Corrigir e selar</button>
        {msg && <span style={{ color: '#ef4444', fontSize: 12 }}>{msg}</span>}
      </div>
    </div>
  )
}

function AutoSelectCard({ c, checked, onToggle, value, onValue }) {
  const dv = distinctVals(c.readings)
  return (
    <div style={{ border: `1px solid ${checked ? 'rgba(34,197,94,0.4)' : '#30363d'}`, borderRadius: 10,
      background: checked ? 'rgba(34,197,94,0.05)' : '#0f1319', padding: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
        <input type="checkbox" checked={checked} onChange={onToggle} style={{ width: 16, height: 16 }} />
        <Link to={`/hand/${c.hand_db_id}`} style={{ color: '#60a5fa', fontFamily: 'ui-monospace,monospace', fontWeight: 700, fontSize: 13, textDecoration: 'none' }}>{c.hand_id}</Link>
        <b style={{ color: '#fca5a5' }}>{c.seat}</b>
        <span style={{ fontSize: 12, color: '#8b9691' }}>vai selar</span>
        <input type="number" step="0.01" value={value} onChange={e => onValue(e.target.value)}
          disabled={!checked} style={{ width: 92, fontFamily: 'ui-monospace,monospace', fontSize: 13,
            background: '#0b0d13', color: '#86efac', border: '1px solid #30363d', borderRadius: 6, padding: '3px 7px' }} />
        <span style={{ fontSize: 11, color: '#8b9691', width: '100%' }}>
          {c.tournament} · B (coroa fresca) ${c.floor} · gravado ${c.stored}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        {dv.map(([val, r]) => (
          <div key={val} style={{ minWidth: 190 }}>
            <div style={{ fontSize: 12, marginBottom: 4 }}>
              <b style={{ color: Math.abs(val - c.winner) < 0.5 ? '#86efac' : '#e6e9ee', fontFamily: 'ui-monospace,monospace' }}>leu ${val}</b>
              <span style={{ color: '#8b9691' }}> · {src(r.source)} · {fmt(r.captured_at)}{Math.abs(val - c.winner) < 0.5 ? ' ◀ vencedor' : ''}</span>
            </div>
            <HandImage url={r.image_url} alt={`$${val}`} style={{ width: '100%', maxWidth: 280 }} />
          </div>
        ))}
      </div>
    </div>
  )
}

export default function ConflictsEye() {
  const [plan, setPlan] = useState(null)
  const [eye, setEye] = useState(null)
  const [autoList, setAutoList] = useState(null)       // os 33 AUTO p/ seleção em lote
  const [sel, setSel] = useState({})                   // key -> bool (pré-marcados)
  const [edit, setEdit] = useState({})                 // key -> valor a selar (default winner)
  const [exclusion, setExclusion] = useState(null)     // painel informativo (resolvidos por exclusão)
  const [applying, setApplying] = useState(false)
  const [msg, setMsg] = useState(null)
  const keyOf = (c) => `${c.hand_id}|${c.seat}`
  const load = () => {
    ggHealth.crossingConflictsPlan().then(setPlan).catch(() => {})
    ggHealth.crossingConflictsEye(40).then(d => setEye(d.conflicts || [])).catch(() => {})
    ggHealth.crossingConflictsAutoList().then(d => {
      const items = d.items || []
      setAutoList(items)
      setSel(Object.fromEntries(items.map(c => [keyOf(c), true])))       // pré-marcados
      setEdit(Object.fromEntries(items.map(c => [keyOf(c), String(c.winner)])))
    }).catch(() => {})
    ggHealth.crossingConflictsExclusion().then(d => setExclusion(d.items || [])).catch(() => {})
  }
  useEffect(() => {
    load()
    const onFocus = () => load()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [])
  const applySelected = async () => {
    const items = (autoList || []).filter(c => sel[keyOf(c)]).map(c => ({
      hand_id: c.hand_id, seat: c.seat, value: Number(edit[keyOf(c)]),
    })).filter(x => x.value > 0)
    if (!items.length) { setMsg('Nada selecionado.'); return }
    if (!window.confirm(`Carimbar ${items.length} conflitos selecionados (selado manual)? Os desmarcados ficam para correção individual.`)) return
    setApplying(true); setMsg(null)
    try {
      const r = await ggHealth.crossingConflictsApplySelected(items)
      setMsg(`✓ ${r.sealed} selados em ${r.hands_touched} mãos.`)
      load()
    } catch (e) { setMsg('Falha: ' + (e?.message || e)) } finally { setApplying(false) }
  }
  const nSel = (autoList || []).filter(c => sel[keyOf(c)]).length
  const resolveOne = (handId, seat) => {
    setEye(list => (list || []).filter(c => !(c.hand_id === handId && c.seat === seat)))
    ggHealth.crossingConflictsPlan().then(setPlan).catch(() => {})
  }
  return (
    <div style={{ padding: 24, maxWidth: 1040 }}>
      <h1 style={{ fontSize: 20, margin: '0 0 4px' }}>Conflitos de coroa (cruzamento)</h1>
      <p style={{ fontSize: 12, color: '#8b9691', marginTop: 0, maxWidth: 840 }}>
        Duas fontes leram valores diferentes para o mesmo seat. A <b>exclusão</b> (grelha) e a
        tolerância de cêntimos resolvem-se sozinhas. Os <b>candidatos a crescimento óbvio</b> (2
        valores possíveis) já <b>NÃO</b> se carimbam às cegas — o $40=2×B pode ser chama on-grid
        que nenhuma régua apanha. <b>Seleção em lote:</b> vês os cards pré-marcados, <b>desmarcas os
        podres</b>, editas o valor se preciso, e carimbas os selecionados.
      </p>

      {/* ── SELEÇÃO EM LOTE dos AUTO (o lote cego morreu) ── */}
      {autoList && autoList.length > 0 && (
        <div style={{ border: '1px solid rgba(34,197,94,0.35)', borderRadius: 10, background: 'rgba(34,197,94,0.05)', padding: '12px 14px', margin: '8px 0 18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 4 }}>
            <div style={{ fontSize: 14, fontWeight: 800, color: '#86efac' }}>
              Crescimento óbvio — seleção em lote ({nSel}/{autoList.length} marcados)
            </div>
            <button onClick={() => setSel(Object.fromEntries(autoList.map(c => [keyOf(c), true])))}
              style={{ background: 'transparent', border: '1px solid #30363d', color: '#c9d1d9', borderRadius: 6, padding: '3px 10px', fontSize: 12, cursor: 'pointer' }}>marcar todos</button>
            <button onClick={() => setSel({})}
              style={{ background: 'transparent', border: '1px solid #30363d', color: '#c9d1d9', borderRadius: 6, padding: '3px 10px', fontSize: 12, cursor: 'pointer' }}>desmarcar todos</button>
            <button onClick={applySelected} disabled={applying || !nSel}
              style={{ marginLeft: 'auto', background: nSel ? 'rgba(34,197,94,0.15)' : '#21262d', border: `1px solid ${nSel ? 'rgba(34,197,94,0.5)' : '#30363d'}`,
                color: nSel ? '#86efac' : '#6b7280', borderRadius: 8, padding: '7px 16px', fontWeight: 800, fontSize: 13, cursor: (applying || !nSel) ? 'default' : 'pointer' }}>
              {applying ? 'A carimbar…' : `Carimbar selecionados (${nSel})`}
            </button>
            {msg && <span style={{ fontSize: 13, color: msg.startsWith('✓') ? '#86efac' : '#ef4444' }}>{msg}</span>}
          </div>
          <div style={{ fontSize: 12, color: '#8b9691', marginBottom: 10 }}>
            Confere a placa de cada imagem. Desmarca os podres (ficam para correção individual). Os
            marcados selam-se com o valor à esquerda (edita-o se a placa disser outro).
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {autoList.map((c) => {
              const k = keyOf(c)
              return <AutoSelectCard key={k} c={c} checked={!!sel[k]}
                onToggle={() => setSel(s => ({ ...s, [k]: !s[k] }))}
                value={edit[k] ?? String(c.winner)}
                onValue={(v) => setEdit(e => ({ ...e, [k]: v }))} />
            })}
          </div>
        </div>
      )}

      <div style={{ fontSize: 14, fontWeight: 800, color: '#f87171', margin: '6px 0 10px' }}>
        Para o teu olho ({eye?.length ?? '…'})
      </div>
      {eye && eye.length === 0 && <div style={{ color: '#86efac', fontSize: 13 }}>✓ Nenhum conflito por decidir.</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {(eye || []).map((c, i) => (
          <EyeCard key={`${c.hand_id}-${c.seat}-${i}`} c={c} onResolved={() => resolveOne(c.hand_id, c.seat)} />
        ))}
      </div>

      {/* ── PAINEL INFORMATIVO: resolvidos por exclusão de partes (não é worklist) ── */}
      {exclusion && exclusion.length > 0 && (
        <div style={{ marginTop: 26 }}>
          <div style={{ fontSize: 14, fontWeight: 800, color: '#8b9691', margin: '0 0 4px' }}>
            Resolvidos por exclusão de partes ({exclusion.length})
          </div>
          <div style={{ fontSize: 12, color: '#8b9691', marginBottom: 10, maxWidth: 820 }}>
            A leitura era uma <b>chama abaixo do KO inicial</b> (impossível) → morreu; ficou o valor
            são (≥ base÷2, na grelha). <b>Registo, não trabalho</b> — não prende nada, não conta como
            pendência. Selam-se sozinhos (<code>cross_exclusion</code>) no reconcile de import.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {exclusion.map((x, i) => (
              <div key={`x-${x.hand_id}-${x.seat}-${i}`} style={{ display: 'flex', gap: 10, alignItems: 'center',
                flexWrap: 'wrap', border: '1px solid #21262d', borderRadius: 8, background: '#0f1319', padding: '7px 10px' }}>
                <Link to={`/hand/${x.hand_db_id}`} style={{ color: '#60a5fa', fontFamily: 'ui-monospace,monospace', fontWeight: 700, fontSize: 12.5, textDecoration: 'none' }}>{x.hand_id}</Link>
                <b style={{ color: '#c9d1d9', fontSize: 12.5 }}>{x.seat}</b>
                <span style={{ fontSize: 12, color: '#f87171' }}>
                  fora-da-grelha {(x.readings || []).map(r => r.value).filter(v => Math.abs(v - x.kept) >= 0.5).map(v => `$${v}`).join(' ') || '✗'} ✗
                </span>
                <span style={{ fontSize: 12, color: '#86efac' }}>ficou <b>${x.kept}</b> ✓</span>
                <span style={{ fontSize: 11, color: '#8b9691' }}>{x.tournament} · fresca ${x.floor}</span>
                <div style={{ display: 'flex', gap: 6, marginLeft: 'auto' }}>
                  {(x.readings || []).map((r, j) => (
                    <HandImage key={j} url={r.image_url} alt="" style={{ width: 90 }} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
