import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ggHealth, tableSs } from '../api/client'
import HandImage from '../components/HandImage'

// Bounties recuperáveis (#CROWN-RECOVERY) — ETAPA 2: sugerir (Vision só-ao-verde) +
// carimbar (escrita SELADA). Grupo 1 = jogador bustou na HH E coroa NULL → o bounty
// dele está a VERDE na coroa do matador; a coroa da casa = VERDE × 2 (fórmula do Rui,
// 20 Jul) com bounty_source='derived_green_ko'. A dourada do matador corrige-se à mão
// ('manual'). Só a imagem arbitra os valores; a escrita só acontece por carimbo do Rui.

const C = {
  card: '#161d19', border: 'rgba(255,255,255,0.10)', text: '#e8ece9',
  muted: '#8b9691', green: '#46c98a', gold: '#e6b34a', red: '#e0705f',
}

export default function CrownRecovery() {
  const [st, setSt] = useState(null)
  const [busy, setBusy] = useState(false)
  const [showOver, setShowOver] = useState(false)
  const [suggestions, setSuggestions] = useState({})   // hand_id -> {busted, crowns}
  const [batch, setBatch] = useState({ running: false, done: 0, total: 0 })
  const poll = useRef(null)
  const cancelRef = useRef(false)

  const refresh = () => ggHealth.crownRecoveryState().then(setSt).catch(() => {})
  useEffect(() => { refresh(); return () => clearInterval(poll.current) }, [])
  // REGRA DA CASA: ao voltar ao separador, re-confere o estado contra a BD (o backend já
  // filtra os resolvidos ao vivo, b3d6c0f) → um caso corrigido por OUTRA via sai da lista.
  useEffect(() => {
    const onFocus = () => refresh()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [])
  // Recarrega as sugestões PAGAS do cache backend → o lote sobrevive ao refresh.
  useEffect(() => {
    ggHealth.crownSuggestionsCache()
      .then(r => { if (r?.cache) setSuggestions(s => ({ ...r.cache, ...s })) })
      .catch(() => {})
  }, [])
  useEffect(() => {
    clearInterval(poll.current)
    if (st?.status === 'running') poll.current = setInterval(refresh, 2500)
    return () => clearInterval(poll.current)
  }, [st?.status])

  const scan = async () => {
    setBusy(true)
    try { await ggHealth.crownRecoveryScan(); await refresh() } finally { setBusy(false) }
  }
  const cancel = async () => {
    setBusy(true)
    try { await ggHealth.crownRecoveryCancel(); await refresh() } finally { setBusy(false) }
  }

  const running = st?.status === 'running'
  const idle = !st || st.status === 'idle'
  const g1 = st?.group1 || []
  // Custo real por leitura Vision (claude-sonnet-4-6, preços oficiais $3/$15 por 1M):
  // imagem 1280px ~1229 tok + prompt ~1100 → input $0.0070 · output ~450 tok → $0.0068 = ~$0.014.
  const COST_PER_SUGGEST = 0.014
  const pending = g1.filter(h => !suggestions[h.hand_id])

  // LOTE "Sugerir todos": lê o verde+dourada de TODOS os pendentes, em lotes de 3, com
  // progresso e CANCELAR (regra permanente). NADA escreve — só pré-preenche os cards.
  const suggestAll = async () => {
    if (!pending.length || batch.running) return
    cancelRef.current = false
    setBatch({ running: true, done: 0, total: pending.length })
    const CONC = 3
    for (let i = 0; i < pending.length; i += CONC) {
      if (cancelRef.current) break
      await Promise.all(pending.slice(i, i + CONC).map(async h => {
        if (cancelRef.current) return
        try {
          const r = await ggHealth.crownRecoverySuggest(h.hand_id)
          setSuggestions(s => ({ ...s, [h.hand_id]: r }))
        } catch { /* falha individual não pára o lote */ }
        finally { setBatch(b => ({ ...b, done: b.done + 1 })) }
      }))
    }
    setBatch(b => ({ ...b, running: false }))
  }
  const cancelBatch = () => { cancelRef.current = true }

  return (
    <div style={{ padding: '18px 22px', color: C.text, maxWidth: 1000, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, fontWeight: 800, margin: '0 0 4px' }}>Bounties recuperáveis</h1>
      <p style={{ color: C.muted, fontSize: 13, margin: '0 0 14px', lineHeight: 1.5, maxWidth: '70ch' }}>
        Mãos onde um jogador <b style={{ color: C.red }}>bustou</b> (all-in + perdeu, da HH) e a
        coroa dourada dele ficou <b style={{ color: C.red }}>NULL</b> — o bounty está a{' '}
        <b style={{ color: C.green }}>verde</b> na coroa de quem o eliminou. <b>Etapa 2</b>: carrega{' '}
        <b>Sugerir</b> (a Vision lê só o verde) ou lê à mão da imagem, e <b>Carimbar</b> grava{' '}
        <b>selado</b> — a coroa = <b>verde × 2</b> como <code>derived_green_ko</code>, a dourada
        do matador como <code>manual</code>. Nenhum processo automático pisa um carimbo. Só a imagem arbitra.
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <button onClick={scan} disabled={busy || running}
          style={{ background: running ? '#2a2f37' : C.green, color: running ? C.muted : '#08130d',
            border: 'none', borderRadius: 8, padding: '9px 15px', fontWeight: 700,
            cursor: busy || running ? 'default' : 'pointer', fontSize: 14 }}>
          {running ? 'A varrer…' : busy ? '…' : idle ? 'Correr detetor' : 'Re-correr'}
        </button>
        {running && (
          <button onClick={cancel} disabled={busy}
            style={{ background: 'transparent', color: C.red, border: `1px solid ${C.red}`,
              borderRadius: 8, padding: '9px 15px', fontWeight: 700, cursor: 'pointer', fontSize: 14 }}>
            Cancelar
          </button>
        )}
        {st && st.total > 0 && (
          <span style={{ color: C.muted, fontSize: 13 }}>
            {st.done}/{st.total} varridas ·{' '}
            <b style={{ color: C.green }}>{st.group1_count}</b> recuperáveis ·{' '}
            <b style={{ color: C.gold }}>{st.misread_count ?? 0}</b> re-ler placa ·{' '}
            {st.group2_count} falha real · {st.over_read_count} over-read
          </span>
        )}
      </div>

      {/* Lote "Sugerir todos" — lê verde+dourada de todos os pendentes (Vision), com custo */}
      {g1.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
          <button onClick={suggestAll} disabled={batch.running || pending.length === 0}
            style={{ background: batch.running || !pending.length ? '#2a2f37' : 'transparent',
              color: batch.running || !pending.length ? C.muted : C.green,
              border: `1px solid ${batch.running || !pending.length ? C.border : C.green}`,
              borderRadius: 8, padding: '8px 14px', fontWeight: 700, fontSize: 13,
              cursor: batch.running || !pending.length ? 'default' : 'pointer' }}>
            {batch.running ? 'A sugerir…' : `Sugerir todos (${pending.length})`}
          </button>
          {!batch.running && pending.length > 0 && (
            <span style={{ color: C.muted, fontSize: 12 }}>
              {pending.length} leituras Vision (~${(pending.length * COST_PER_SUGGEST).toFixed(2)}) · nada se escreve
            </span>
          )}
          {batch.running && (
            <>
              <span style={{ color: C.muted, fontSize: 13 }}>{batch.done}/{batch.total}</span>
              <button onClick={cancelBatch}
                style={{ background: 'transparent', color: C.red, border: `1px solid ${C.red}`,
                  borderRadius: 8, padding: '6px 12px', fontWeight: 700, cursor: 'pointer', fontSize: 13 }}>
                Cancelar
              </button>
            </>
          )}
        </div>
      )}

      {idle && <div style={{ color: C.muted, fontSize: 14 }}>Carrega em “Correr detetor” para varrer as KO/PKO com Gold.</div>}

      {/* grupo 1 — recuperáveis (Etapa 2: sugerir + carimbar) */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {g1.map(h => <Group1Card key={h.hand_db_id} h={h} C={C} onDone={refresh}
          suggestion={suggestions[h.hand_id]} />)}
      </div>

      {/* Coroas — revisão de quedas (worklist na app; quedas mesmo-hash + fora-de-grelha) */}
      <DropsWorklist C={C} />

      {/* re-ler placa — all-in perdido MAS jogador VIVO (resto >= 1 BB) */}
      {st && (st.status === 'done' || st.status === 'cancelled') && (st.misread_count ?? 0) > 0 && (
        <div style={{ marginTop: 22 }}>
          <div style={{ ...lbl(C), color: C.gold, fontSize: 12 }}>
            Re-ler placa — {st.misread_count} vivos (all-in perdido mas ficaram com stack)
          </div>
          <p style={{ color: C.muted, fontSize: 12, margin: '4px 0 8px', maxWidth: '70ch' }}>
            Perderam o all-in mas <b>cobriram o adversário</b> (resto ≥ 1 BB) ou não bustaram —
            a coroa NULL é <b>leitura falhada da placa própria</b>. Recupera-se <b>re-lendo a placa</b>,
            <b> nunca</b> verde × 2. (Inclui os despromovidos pela contraprova da mão-seguinte.)
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {(st.misread || []).map(o => (
              <Link key={o.hand_db_id} to={`/hand/${o.hand_db_id}`}
                style={{ color: C.gold, textDecoration: 'none', border: `1px solid ${C.border}`,
                  borderRadius: 6, padding: '3px 8px', fontSize: 12, fontFamily: 'ui-monospace,monospace' }}>
                {o.hand_id}
                <span style={{ color: C.muted }}> {(o.seats || []).map(s => s.name).join(', ')}
                  {o.reason === 'seated_next_hand' ? ' · sentou-se na mão seguinte' : ''}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* grupo 2 + over-read (à parte) */}
      {st && (st.status === 'done' || st.status === 'cancelled') && (
        <div style={{ marginTop: 22, color: C.muted, fontSize: 13, display: 'flex',
          flexDirection: 'column', gap: 8 }}>
          <div>
            <b style={{ color: C.text }}>{st.group2_count}</b> coroas de <b>falha real</b>{' '}
            (não-bustou + não-Hero + NULL) → vão para o balde das coroas existente.
          </div>
          <div>
            <button onClick={() => setShowOver(v => !v)} style={{ background: 'transparent',
              border: `1px solid ${C.border}`, color: C.text, borderRadius: 6, padding: '3px 10px',
              cursor: 'pointer', fontSize: 12 }}>
              {showOver ? 'Esconder' : 'Ver'} {st.over_read_count} over-read (à parte)
            </button>
            {showOver && (
              <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {st.over_read.map(o => (
                  <Link key={o.hand_db_id} to={`/hand/${o.hand_db_id}`}
                    style={{ color: C.gold, textDecoration: 'none', border: `1px solid ${C.border}`,
                      borderRadius: 6, padding: '3px 8px', fontSize: 12, fontFamily: 'ui-monospace,monospace' }}>
                    {o.hand_id} <span style={{ color: C.muted }}>HH {o.num_hh}≠{o.num_extracted} Gold</span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Coroas — revisão de quedas: sobre o <Worklist> base (LEI 3; filtro ao-vivo embutido) ──
function DropsWorklist({ C }) {
  const subtitle = (
    <p style={{ color: C.muted, fontSize: 12, margin: '0 0 12px', maxWidth: '74ch', lineHeight: 1.5 }}>
      A coroa do mesmo jogador <b>nunca desce</b> — uma queda é <b>leitura errada</b>. Vê a imagem,
      compara os dois valores e <b>corrige</b> (grava selado <code>manual</code>, intocável por automático).
      As fora-de-grelha são sinalizador leve. Só a imagem arbitra.
    </p>
  )
  return (
    <Worklist
      title="Coroas — revisão de quedas" subtitle={subtitle} emptyText="Nenhum caso — coroas limpas."
      load={() => ggHealth.crownDrops().then(d => [
        ...(d.drops || []).map(x => ({ ...x, _kind: 'queda' })),
        ...(d.off_grid || []).map(x => ({ ...x, _kind: 'fora-de-grelha' })),
      ])}
      keyOf={(d) => `${d.hand_id}|${(d.player || '').toLowerCase()}`}
      renderCard={(d, { resolve }) => (
        <DropCard C={C} kind={d._kind} player={d.player} handId={d.hand_id} handDb={d.hand_db_id}
          lowVal={d._kind === 'queda' ? d.low : d.value} refVal={d.ref} ratio={d.ratio}
          refHandDb={d.ref_hand_db_id} refHandId={d.ref_hand_id} onResolved={resolve} />
      )}
    />
  )
}

function DropCard({ C, kind, player, handId, handDb, lowVal, refVal, ratio, refHandDb, refHandId, onResolved }) {
  // Fundamento validado pelo Rui: a leitura ISOLADA (a que salta) é o misread — pode ser a
  // ALTA ou a BAIXA. O card deixa corrigir QUALQUER das duas placas (preenche a errada).
  const [lowV, setLowV] = useState('')
  const [refV, setRefV] = useState('')
  const [stamping, setStamping] = useState(false)
  const [msg, setMsg] = useState(null)

  const stamp = async () => {
    const jobs = []
    const lv = parseFloat(lowV), rv = parseFloat(refV)
    if (!isNaN(lv)) jobs.push({ hand: handId, val: lv, tag: `$${lowVal}` })
    if (kind === 'queda' && !isNaN(rv)) jobs.push({ hand: refHandId, val: rv, tag: `$${refVal}` })
    if (!jobs.length) { setMsg({ ok: false, t: 'Preenche a placa errada (lê da imagem)' }); return }
    setStamping(true); setMsg(null)
    try {
      const probs = []
      for (const j of jobs) {
        const r = await tableSs.setBounties(j.hand, { bounties: { [player]: j.val }, sources: { [player]: 'manual' } })
        if ((r?.partial || []).length) probs.push(`${j.tag}: parcial (avisa o Code)`)
        else if (!(r?.updated || []).length) probs.push(`${j.tag}: não encontrado`)
      }
      if (probs.length) { setStamping(false); setMsg({ ok: false, t: '⚠ ' + probs.join(' · ') }) }
      else onResolved && onResolved()   // carimbado → SAI DA LISTA NA HORA
    } catch (e) { setStamping(false); setMsg({ ok: false, t: 'Falha: ' + (e?.message || e) }) }
  }
  const dismiss = async () => {
    setStamping(true); setMsg(null)
    try { await ggHealth.crownDropsDismiss(handId, player); onResolved && onResolved() }
    catch (e) { setStamping(false); setMsg({ ok: false, t: 'Falha: ' + (e?.message || e) }) }
  }
  const inp = (v, setV) => (
    <input value={v} onChange={e => setV(e.target.value)} inputMode="decimal" placeholder="valor da imagem"
      style={{ width: 96, background: '#0e1512', color: C.text, border: `1px solid ${C.border}`,
        borderRadius: 6, padding: '4px 7px', fontSize: 13, fontFamily: 'ui-monospace,monospace' }} />
  )

  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 11,
      padding: 12, display: 'flex', gap: 14, flexWrap: 'wrap' }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <HandImage handDbId={handDb} caption={`$${lowVal} · ${handId}`} />
        {kind === 'queda' && <HandImage handDbId={refHandDb} caption={`$${refVal} · ${refHandId || 'vizinha'}`} />}
      </div>
      <div style={{ flex: 1, minWidth: 260 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
          <b style={{ fontSize: 14 }}>{player}</b>
          <span style={{ fontSize: 10, color: '#08130d', background: kind === 'queda' ? C.red : C.gold,
            borderRadius: 4, padding: '1px 6px', fontWeight: 700 }}>{kind}</span>
          <Link to={`/hand/${handDb}`} style={{ color: C.gold, fontSize: 12, textDecoration: 'none',
            fontFamily: 'ui-monospace,monospace' }}>{handId}</Link>
        </div>
        <div style={{ marginTop: 6, fontSize: 13 }}>
          {kind === 'queda'
            ? <>a leitura <b>isolada</b> é o misread (a coroa não salta de ida-e-volta) — corrige a que
                a imagem <b>desmente</b>: a <b style={{ color: C.red }}>${lowVal}</b> OU a <b style={{ color: C.green }}>${refVal}</b>.</>
            : <>leu <b style={{ color: C.gold }}>${lowVal}</b> = {ratio}B — fora da grelha das metades</>}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ color: C.muted, fontSize: 13, minWidth: 168 }}>corrigir a <b style={{ color: C.red }}>${lowVal}</b> <span style={{ fontSize: 11 }}>({handId})</span></span>
            {inp(lowV, setLowV)}
          </div>
          {kind === 'queda' && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ color: C.muted, fontSize: 13, minWidth: 168 }}>corrigir a <b style={{ color: C.green }}>${refVal}</b> <span style={{ fontSize: 11 }}>({refHandId})</span></span>
              {inp(refV, setRefV)}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <button onClick={stamp} disabled={stamping}
            style={{ background: C.gold, color: '#08130d', border: 'none', borderRadius: 8,
              padding: '5px 13px', fontWeight: 800, fontSize: 13, cursor: stamping ? 'default' : 'pointer' }}>
            {stamping ? '…' : 'Carimbar (manual)'}
          </button>
          <button onClick={dismiss} disabled={stamping}
            style={{ background: 'transparent', color: C.text, border: `1px solid ${C.border}`, borderRadius: 8,
              padding: '5px 12px', fontWeight: 700, fontSize: 13, cursor: stamping ? 'default' : 'pointer' }}>
            Dispensar (legítimo)
          </button>
          {msg && <span style={{ fontSize: 12, color: msg.ok ? C.green : C.red }}>{msg.t}</span>}
        </div>
      </div>
    </div>
  )
}

// ── Etapa 2 — cartão do grupo 1 com sugerir (Vision só-ao-verde) + carimbar (selado) ──
function Group1Card({ h, C, onDone, suggestion }) {
  const busted = h.busted || []
  const matadores = (h.matadores || []).filter(m => m.name)
  const [vals, setVals] = useState({})           // name -> string (valor a escrever)
  const [sugg, setSugg] = useState(null)         // name -> valor sugerido pela Vision (COROA)
  const [bgreens, setBgreens] = useState({})     // name -> verde CRU lido (coroa = verde×2)
  const [meta, setMeta] = useState(null)         // {last:{nome:coroa}, base, greenTotal}
  const [suggesting, setSuggesting] = useState(false)
  const multi = busted.length > 1                // multi-eliminação (verde = soma)
  const [stamping, setStamping] = useState(false)
  const [msg, setMsg] = useState(null)
  const [done, setDone] = useState(false)

  const setVal = (name, v) => setVals(s => ({ ...s, [name]: v }))

  // aplica {busted, crowns, last_crowns, base, green_total} da Vision
  const applySuggestion = (r) => {
    setMeta({ last: r?.last_crowns || {}, base: r?.base ?? null, greenTotal: r?.green_total ?? null })
    setBgreens(r?.busted_greens || {})   // verde cru por eliminado → mostra "verde $X → coroa $Y"
    const next = {}
    // eliminado → verde derivado (KO limpo) OU, em multi-KO, a última coroa conhecida (esperado)
    Object.entries(r?.busted || {}).forEach(([name, v]) => { if (v != null) next[name] = String(v) })
    busted.forEach(b => {
      if (next[b.name] == null && r?.last_crowns?.[b.name] != null) next[b.name] = String(r.last_crowns[b.name])
    })
    // matador → coroa dourada (só os nomes que são matadores neste card)
    const matadorNames = new Set(matadores.map(m => m.name))
    Object.entries(r?.crowns || {}).forEach(([name, v]) => {
      if (v != null && matadorNames.has(name)) next[name] = String(v)
    })
    const hasHints = Object.keys(next).length || (r?.last_crowns && Object.keys(r.last_crowns).length)
    if (hasHints) {
      setSugg(next); setVals(v => ({ ...next, ...v }))   // prefill sem apagar edições
      setMsg({ ok: true, t: multi
        ? 'Multi-KO: cada eliminado pré-preenchido com a última coroa conhecida — contraprova: soma das coroas ÷ 2 = verde total.'
        : 'Vision leu o verde e a dourada — confere antes de carimbar.' })
      return true
    }
    setMsg({ ok: false, t: r?.image === 'none'
      ? 'Sem Gold — lê à mão da imagem.'
      : 'Vision não leu valores legíveis — lê à mão da imagem.' })
    return false
  }
  // valor ESPERADO de um eliminado: última coroa conhecida, ou "fresco ~$B"
  const expectedFor = (name) => (meta?.last?.[name] != null
    ? { v: meta.last[name], label: `esperado $${meta.last[name]}` }
    : (meta?.base != null ? { v: meta.base, label: `fresco ~$${meta.base}` } : null))

  // sugestão vinda do LOTE ("Sugerir todos") — pré-preenche quando chega
  useEffect(() => { if (suggestion && !done) applySuggestion(suggestion) }, [suggestion])

  const suggest = async () => {
    setSuggesting(true); setMsg(null)
    try { applySuggestion(await ggHealth.crownRecoverySuggest(h.hand_id)) }
    catch (e) { setMsg({ ok: false, t: 'Falha a sugerir: ' + (e?.message || e) }) }
    finally { setSuggesting(false) }
  }

  const stamp = async () => {
    // constrói o carimbo: eliminado(verde)→derived_green_ko ; matador(dourada)→manual
    const bounties = {}, sources = {}
    busted.forEach(b => {
      const v = parseFloat(vals[b.name]); if (!isNaN(v)) { bounties[b.name] = v; sources[b.name] = 'derived_green_ko' }
    })
    matadores.forEach(m => {
      const v = parseFloat(vals[m.name]); if (!isNaN(v)) { bounties[m.name] = v; sources[m.name] = 'manual' }
    })
    if (!Object.keys(bounties).length) { setMsg({ ok: false, t: 'Nada para carimbar — preenche pelo menos 1 valor.' }); return }
    setStamping(true); setMsg(null)
    try {
      const r = await tableSs.setBounties(h.hand_id, { bounties, sources })
      const nf = (r?.not_found || []), part = (r?.partial || [])
      if (nf.length || part.length) {   // NUNCA "feito" calado se algo não gravou nos 2 stores
        setMsg({ ok: false, t: `⚠ ${part.length ? 'parcial (só 1 store): ' + part.join(', ') : ''}${nf.length ? ' não encontrados: ' + nf.join(', ') : ''} — avisa o Code` })
        return
      }
      setDone(true)
      setMsg({ ok: true, t: `Carimbado ✓ (${(r?.updated || []).length} selados).` })
      if (onDone) setTimeout(onDone, 1200)
    } catch (e) { setMsg({ ok: false, t: 'Falha a carimbar: ' + (e?.message || e) }) }
    finally { setStamping(false) }
  }

  const row = (name, tag, tagColor, hint) => (
    <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
      <span style={{ fontSize: 13, minWidth: 130 }}><b>{name}</b></span>
      <span style={{ fontSize: 10, color: '#08130d', background: tagColor, borderRadius: 4, padding: '1px 6px', fontWeight: 700 }}>{tag}</span>
      <span style={{ color: C.muted, fontSize: 13 }}>$</span>
      <input value={vals[name] ?? ''} onChange={e => setVal(name, e.target.value)}
        placeholder={sugg?.[name] != null ? String(sugg[name]) : '—'} inputMode="decimal"
        style={{ width: 90, background: '#0e1512', color: C.text, border: `1px solid ${C.border}`,
          borderRadius: 6, padding: '4px 7px', fontSize: 13, fontFamily: 'ui-monospace,monospace' }} />
      {sugg?.[name] != null && (bgreens?.[name] != null
        ? <span style={{ color: C.green, fontSize: 11 }}>Vision: verde ${bgreens[name]} → coroa <b>${sugg[name]}</b></span>
        : <span style={{ color: C.green, fontSize: 11 }}>Vision: ${sugg[name]}</span>)}
      {hint && <span style={{ color: C.gold, fontSize: 11 }}>{hint.label}</span>}
    </div>
  )
  // soma dos valores esperados dos eliminados (contraprova do verde total, multi-KO)
  const sumExpected = busted.reduce((s, b) => {
    const e = expectedFor(b.name); return s + (e ? Number(e.v) : 0)
  }, 0)

  return (
    <div style={{ background: C.card, border: `1px solid ${done ? C.green : C.border}`,
      borderRadius: 12, padding: 14, display: 'flex', gap: 16, flexWrap: 'wrap', opacity: done ? 0.7 : 1 }}>
      <HandImage handDbId={h.hand_db_id} alt="gold" style={{ width: 320 }} />
      <div style={{ flex: 1, minWidth: 280 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
          <Link to={`/hand/${h.hand_db_id}`}
            style={{ color: C.gold, fontWeight: 700, fontSize: 14, textDecoration: 'none',
              fontFamily: 'ui-monospace,monospace' }}>{h.hand_id}</Link>
          <span style={{ color: C.muted, fontSize: 12 }}>{h.tournament}</span>
        </div>

        {/* editor de carimbo: eliminado (verde) + matador (dourada) */}
        <div style={{ marginTop: 10, padding: '9px 11px', borderRadius: 8,
          background: 'rgba(224,112,95,.07)', border: '1px solid rgba(224,112,95,.3)' }}>
          <div style={lbl(C)}>Eliminado · {multi ? 'MULTI-KO · coroa de cada = última conhecida' : 'coroa = verde × 2'}</div>
          {busted.map(b => row(b.name, 'verde', C.green, multi ? expectedFor(b.name) : null))}
          {multi && meta && (() => {
            // CANON regra 5: verde total = soma das coroas das vítimas ÷ 2 (não a soma inteira).
            const half = sumExpected / 2
            const gt = meta.greenTotal
            const ok = gt != null && Math.abs(half - gt) < 0.5
            return (
              <div style={{ marginTop: 6, fontSize: 12, color: C.muted }}>
                soma das coroas = <b style={{ color: C.gold }}>${sumExpected.toFixed(2)}</b> · ÷2 = <b style={{ color: C.gold }}>${half.toFixed(2)}</b>
                {gt != null && <> · verde total na placa = <b style={{ color: C.green }}>${gt}</b> {ok ? '✓' : '(confere na imagem)'}</>}
              </div>
            )
          })()}
        </div>
        {matadores.length > 0 && (
          <div style={{ marginTop: 8, padding: '9px 11px', borderRadius: 8,
            background: 'rgba(230,179,74,.07)', border: '1px solid rgba(230,179,74,.28)' }}>
            <div style={lbl(C)}>Matador · coroa dourada (correção à mão)</div>
            {matadores.map(m => row(m.name, m.is_hero ? 'HERO' : 'dourada', C.gold))}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <button onClick={suggest} disabled={suggesting || stamping || done}
            style={{ background: 'transparent', color: C.green, border: `1px solid ${C.green}`,
              borderRadius: 8, padding: '6px 12px', fontWeight: 700, fontSize: 13,
              cursor: suggesting || done ? 'default' : 'pointer' }}>
            {suggesting ? 'A ler o verde…' : 'Sugerir (Vision só-ao-verde)'}
          </button>
          <button onClick={stamp} disabled={stamping || done}
            style={{ background: done ? '#2a2f37' : C.gold, color: done ? C.muted : '#08130d', border: 'none',
              borderRadius: 8, padding: '6px 14px', fontWeight: 800, fontSize: 13,
              cursor: stamping || done ? 'default' : 'pointer' }}>
            {done ? 'Carimbado ✓' : stamping ? 'A carimbar…' : 'Carimbar (selar)'}
          </button>
          {msg && <span style={{ fontSize: 12, color: msg.ok ? C.green : C.red }}>{msg.t}</span>}
        </div>
      </div>
    </div>
  )
}

const lbl = (C) => ({ fontSize: 11, letterSpacing: '.05em', textTransform: 'uppercase',
  color: C.muted, fontWeight: 700, marginBottom: 4 })
const pos = (C) => ({ fontFamily: 'ui-monospace,monospace', fontSize: 12,
  background: 'rgba(255,255,255,.06)', borderRadius: 5, padding: '1px 7px', marginLeft: 4 })
