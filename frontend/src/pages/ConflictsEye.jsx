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
  const pick = async (val) => {
    if (!window.confirm(`Selar ${c.seat} = $${val} (manual)?`)) return
    setBusy(true); setMsg(null)
    try {
      const r = await tableSs.setBounties(c.hand_id, { bounties: { [c.seat]: val } })
      if (r?.not_found?.length || r?.partial?.length) {
        setBusy(false); setMsg('nome não casou — verifica'); return
      }
      onResolved && onResolved()
    } catch (e) { setBusy(false); setMsg('Falha: ' + (e?.message || e)) }
  }
  const dv = distinctVals(c.readings)
  return (
    <div style={{ border: '1px solid rgba(239,68,68,0.35)', borderRadius: 10, background: 'rgba(239,68,68,0.05)',
      padding: 14, opacity: busy ? 0.5 : 1 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
        <Link to={`/hand/${c.hand_db_id}`} style={{ color: '#60a5fa', fontFamily: 'ui-monospace,monospace', fontWeight: 700, fontSize: 14, textDecoration: 'none' }}>{c.hand_id}</Link>
        <b style={{ color: '#fca5a5' }}>{c.seat}</b>
        <span style={{ fontSize: 12, color: '#8b9691' }}>gravado ${c.stored}</span>
        <span style={{ fontSize: 11, fontWeight: 700, color: '#f87171', background: 'rgba(239,68,68,0.14)', border: '1px solid rgba(239,68,68,0.35)', borderRadius: 5, padding: '1px 7px' }}>{reasonLabel(c.reason)}</span>
        <span style={{ fontSize: 11, color: '#8b9691', width: '100%' }}>
          {c.tournament} · base ${c.base} <span style={{ opacity: 0.7 }}>(buy-in bounty, {c.base_source || 'TS'})</span> · coroa fresca ${c.floor}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        {dv.map(([val, r]) => (
          <div key={val} style={{ minWidth: 200 }}>
            <div style={{ fontSize: 12, marginBottom: 4 }}>
              <b style={{ color: '#e6e9ee', fontFamily: 'ui-monospace,monospace' }}>${val}</b>
              <span style={{ color: '#8b9691' }}> · {src(r.source)} · {fmt(r.captured_at)}</span>
            </div>
            <HandImage url={r.image_url} alt={`$${val}`} style={{ width: '100%', maxWidth: 300 }} />
            <button onClick={() => pick(val)} disabled={busy} style={{ marginTop: 6, width: '100%',
              background: 'rgba(34,197,94,0.14)', border: '1px solid rgba(34,197,94,0.5)', color: '#86efac',
              borderRadius: 8, padding: '5px 10px', fontWeight: 700, fontSize: 13, cursor: busy ? 'default' : 'pointer' }}>
              Fica ${val} (selar)
            </button>
          </div>
        ))}
      </div>
      {msg && <div style={{ color: '#ef4444', fontSize: 12, marginTop: 6 }}>{msg}</div>}
    </div>
  )
}

function AutoCard({ c }) {
  const dv = distinctVals(c.readings)
  return (
    <div style={{ border: '1px solid #30363d', borderRadius: 10, background: '#161b22', padding: 12 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
        <Link to={`/hand/${c.hand_db_id}`} style={{ color: '#60a5fa', fontFamily: 'ui-monospace,monospace', fontWeight: 700, fontSize: 13, textDecoration: 'none' }}>{c.hand_id}</Link>
        <b style={{ color: '#fca5a5' }}>{c.seat}</b>
        <span style={{ fontSize: 12 }}>
          <span style={{ color: '#8b9691' }}>AUTO escreveria </span>
          <b style={{ color: '#86efac', fontFamily: 'ui-monospace,monospace' }}>${c.winner}</b>
        </span>
        <span style={{ fontSize: 11, color: '#8b9691', width: '100%' }}>
          {c.tournament} · base ${c.base} · coroa fresca ${c.floor}
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
  const [autoSample, setAutoSample] = useState(null)   // trava dos rótulos
  const [autoOk, setAutoOk] = useState(false)          // o Rui validou a amostra
  const [applying, setApplying] = useState(false)
  const [msg, setMsg] = useState(null)
  const load = () => {
    ggHealth.crossingConflictsPlan().then(setPlan).catch(() => {})
    ggHealth.crossingConflictsEye(40).then(d => setEye(d.conflicts || [])).catch(() => {})
    ggHealth.crossingConflictsAutoSample(4).then(d => setAutoSample(d.sample || [])).catch(() => {})
  }
  useEffect(() => {
    load()
    const onFocus = () => load()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [])
  const applyAuto = async () => {
    if (!window.confirm(`Carimbar ${plan?.auto?.seats ?? '?'} conflitos AUTO (crescimento óbvio, fica o mais recente, selado)?`)) return
    setApplying(true); setMsg(null)
    try {
      const r = await ggHealth.crossingConflictsApply()
      setMsg(`✓ ${r.crowns_written} conflitos auto carimbados em ${r.hands_touched} mãos.`)
      load()
    } catch (e) { setMsg('Falha: ' + (e?.message || e)) } finally { setApplying(false) }
  }
  const resolveOne = (handId, seat) => {
    setEye(list => (list || []).filter(c => !(c.hand_id === handId && c.seat === seat)))
    ggHealth.crossingConflictsPlan().then(setPlan).catch(() => {})
  }
  return (
    <div style={{ padding: 24, maxWidth: 1040 }}>
      <h1 style={{ fontSize: 20, margin: '0 0 4px' }}>Conflitos de coroa (cruzamento)</h1>
      <p style={{ fontSize: 12, color: '#8b9691', marginTop: 0, maxWidth: 820 }}>
        Duas fontes leram valores diferentes para o mesmo seat. <b>(B)</b>: crescimento óbvio
        (o maior é o mais recente e ≥ <b>coroa fresca base÷2</b>, passa a física) resolve-se sozinho
        pelo CANON; os <b>incompatíveis</b> ficam para o teu olho. <b>Trava dos rótulos:</b> valida
        a amostra abaixo (os "leu $X" batem nas placas?) antes de carimbar o lote.
      </p>

      {/* ── TRAVA: amostra AUTO ao olho (os rótulos batem nas placas?) ── */}
      {autoSample && autoSample.length > 0 && (
        <div style={{ border: '1px solid rgba(234,179,8,0.4)', borderRadius: 10, background: 'rgba(234,179,8,0.06)', padding: '12px 14px', margin: '8px 0 14px' }}>
          <div style={{ fontSize: 14, fontWeight: 800, color: '#eab308', marginBottom: 4 }}>
            Amostra AUTO — valida os rótulos ({autoSample.length} ao acaso)
          </div>
          <div style={{ fontSize: 12, color: '#8b9691', marginBottom: 10 }}>
            Cada card mostra as leituras (valor + fonte + hora + imagem) e o <b>vencedor</b> que o AUTO
            escreveria. Confere na <b>placa</b> de cada imagem se o "leu $X" é verdade. Se algum mentir,
            NÃO valides — a regra AUTO morre e tudo vai ao olho.
          </div>
          <button onClick={() => ggHealth.crossingConflictsAutoSample(4).then(d => { setAutoSample(d.sample || []); setAutoOk(false) })}
            style={{ background: 'transparent', border: '1px solid #30363d', color: '#c9d1d9', borderRadius: 8, padding: '4px 12px', fontWeight: 700, fontSize: 12, cursor: 'pointer', marginBottom: 10 }}>↻ Outras 4</button>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {autoSample.map((c, i) => <AutoCard key={`${c.hand_id}-${c.seat}-${i}`} c={c} />)}
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12, fontSize: 13, cursor: 'pointer' }}>
            <input type="checkbox" checked={autoOk} onChange={e => setAutoOk(e.target.checked)} />
            <span>Vi a amostra — os rótulos <b>"leu $X" batem nas placas</b> (autorizo o carimbo AUTO).</span>
          </label>
        </div>
      )}

      {plan && (
        <div style={{ border: '1px solid rgba(56,189,248,0.4)', borderRadius: 10, background: 'rgba(56,189,248,0.06)',
          padding: '12px 14px', margin: '8px 0 18px' }}>
          <div style={{ fontSize: 13, lineHeight: 1.7 }}>
            <b style={{ color: '#86efac' }}>{plan.auto.seats}</b> conflitos AUTO (crescimento óbvio) / {plan.auto.hands} mãos
            {' · '}<b style={{ color: '#f87171' }}>{plan.eye.seats}</b> para o teu olho / {plan.eye.hands} mãos
          </div>
          <button onClick={applyAuto} disabled={applying || !plan.auto.seats || !autoOk}
            title={!autoOk ? 'Valida a amostra dos rótulos primeiro (checkbox acima)' : ''}
            style={{ marginTop: 10, background: autoOk ? 'rgba(34,197,94,0.15)' : '#21262d', border: `1px solid ${autoOk ? 'rgba(34,197,94,0.5)' : '#30363d'}`,
              color: autoOk ? '#86efac' : '#6b7280', borderRadius: 8, padding: '7px 16px', fontWeight: 800, fontSize: 13,
              cursor: (applying || !autoOk) ? 'default' : 'pointer' }}>
            {applying ? 'A carimbar…' : autoOk ? `Carimbar ${plan.auto.seats} conflitos AUTO (selado)` : `🔒 Valida a amostra primeiro`}
          </button>
          {msg && <span style={{ marginLeft: 12, fontSize: 13, color: msg.startsWith('✓') ? '#86efac' : '#ef4444' }}>{msg}</span>}
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
    </div>
  )
}
