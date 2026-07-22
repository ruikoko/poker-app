import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ggHealth, tableSs, tagDecisions, absImageUrl } from '../api/client'

// Painel "Prints fora de tempo" + RECONCILIAÇÃO (régua do Rui, 22 Jul).
// Gatilho: captura com tag pos/nota tirada <9s da mão → candidata a pertencer à ANTERIOR.
// Confirmação pela HH (helpers únicos hh_facts): pos → ronda de apostas pós-flop do Hero
// na anterior ("chegou ao flop" NÃO chega — all-in pré com board a correr é SEM pós-flop);
// nota → showdown REAL (linhas "shows", não o marcador). FT fora de tudo.
// PROVADO = a HH confirma dos DOIS lados; SUSPEITA = a régua não decide (razão à vista).
// MOVER = selo (remove na atual + add na anterior, preview+batch) → pipeline (Fase 1).
// NUNCA move sozinho — toda a escrita é clique+confirmação do Rui.

const mono = "'Fira Code',monospace"
const fmt = (iso) => iso ? String(iso).replace('T', ' ').slice(0, 16) : '—'
const rowKey = (r) => `${r.hand_id}|${r.folder_tag}`
const isPos = (r) => String(r.folder_tag || '').startsWith('pos')
const factName = (r) => isPos(r) ? 'pós-flop do Hero' : 'showdown real'
const curFact = (r) => isPos(r) ? r.hero_postflop : r.real_showdown
const prevFact = (r) => r.prev ? (isPos(r) ? r.prev.hero_postflop : r.prev.real_showdown) : null

function FactChip({ label, val }) {
  return (
    <span style={{ fontSize: 10.5, fontWeight: 800, padding: '1px 7px', borderRadius: 5,
      color: val ? '#86efac' : '#f87171',
      background: val ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
      border: `1px solid ${val ? 'rgba(34,197,94,0.35)' : 'rgba(239,68,68,0.35)'}` }}>
      {label}: {val ? 'sim ✓' : 'não ✗'}
    </span>
  )
}

function PairRow({ r, onZoom, checked, onToggle, onMovePair, onDismiss, busy }) {
  const [open, setOpen] = useState(false)
  const src = absImageUrl(r.image_url)
  const p = r.prev
  const provado = r.verdict === 'provado'
  const accent = provado ? '#22c55e' : '#f59e0b'
  return (
    <div style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', flexWrap: 'wrap' }}>
        <input type="checkbox" checked={checked} onChange={onToggle}
          title="Marcar para ações em lote (barra em baixo)"
          style={{ width: 15, height: 15, cursor: 'pointer', accentColor: accent }} />
        <span onClick={() => setOpen(o => !o)} style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', flexWrap: 'wrap', flex: 1 }}>
          <span style={{ color: '#8b9691', width: 12 }}>{open ? '▾' : '▸'}</span>
          <span style={{ fontWeight: 800, color: accent, fontFamily: mono, minWidth: 34, textAlign: 'right' }}>{r.interval_s}s</span>
          <Link to={`/hand/${r.hand_db_id}`} onClick={e => e.stopPropagation()} style={{ color: '#60a5fa', fontFamily: mono, fontSize: 12, fontWeight: 700, textDecoration: 'none' }}>{r.hand_id}</Link>
          <span style={{ fontSize: 10, fontWeight: 800, color: '#000', background: '#38bdf8', padding: '1px 6px', borderRadius: 5 }} title="tag da captura (pasta)">{r.folder_tag}</span>
          <FactChip label={`atual · ${factName(r)}`} val={curFact(r)} />
          {p
            ? <>
                <span style={{ color: '#8b9691', fontSize: 11 }}>→ anterior</span>
                <Link to={`/hand/${p.hand_db_id}`} onClick={e => e.stopPropagation()} style={{ color: '#60a5fa', fontFamily: mono, fontSize: 12, fontWeight: 700, textDecoration: 'none' }}>{p.hand_id}</Link>
                <FactChip label={factName(r)} val={prevFact(r)} />
              </>
            : <span style={{ fontSize: 11, color: '#f87171', fontWeight: 700 }}>sem anterior na base</span>}
          {!provado && <span style={{ fontSize: 10.5, color: '#f59e0b' }} title="razão">({r.verdict_reason})</span>}
        </span>
        {p && (
          <button onClick={() => onMovePair(r)} disabled={busy}
            title={`Mover '${r.folder_tag}' desta mão para a anterior (${p.hand_id}) — selado + pipeline`}
            style={{ fontSize: 11, fontWeight: 800, padding: '4px 10px', borderRadius: 5, cursor: busy ? 'wait' : 'pointer',
              border: `1px solid ${accent}66`, background: 'transparent', color: accent }}>
            Mover → anterior
          </button>
        )}
        <button onClick={() => onDismiss(r)} disabled={busy}
          title="Dispensar (legítimo): a tag fica onde está; a captura sai deste painel (persistido)"
          style={{ fontSize: 11, padding: '4px 10px', borderRadius: 5, cursor: busy ? 'wait' : 'pointer',
            border: '1px solid #47556966', background: 'transparent', color: '#cbd5e1' }}>
          Dispensar
        </button>
      </div>
      {open && (
        <div style={{ padding: '0 10px 12px 34px', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 700, marginBottom: 3 }}>captura (casada à mão atual)</div>
            <img src={src} alt="" loading="lazy" onClick={() => onZoom(src)}
              style={{ maxWidth: 300, width: '100%', borderRadius: 6, border: '1px solid #2a2d3a', cursor: 'zoom-in', background: '#0b0d13', display: 'block' }} />
          </div>
          {p?.image_url && (
            <div>
              <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 700, marginBottom: 3 }}>Gold da anterior ({p.hand_id})</div>
              <img src={absImageUrl(p.image_url)} alt="" loading="lazy" onClick={() => onZoom(absImageUrl(p.image_url))}
                style={{ maxWidth: 300, width: '100%', borderRadius: 6, border: '1px solid #2a2d3a', cursor: 'zoom-in', background: '#0b0d13', display: 'block' }} />
            </div>
          )}
          <div style={{ fontSize: 12, color: '#8b9691', minWidth: 240, maxWidth: 380 }}>
            <div style={{ color: '#94a3b8', fontWeight: 700, marginBottom: 4 }}>o par, lado a lado</div>
            <div>· <b>{r.hand_id}</b> (onde a tag está): {factName(r)} <b style={{ color: curFact(r) ? '#86efac' : '#f87171' }}>{curFact(r) ? 'SIM' : 'NÃO'}</b>
              {' '}· mão às {fmt(null) && ''}{r.interval_s}s do print</div>
            {p
              ? <div>· <b>{p.hand_id}</b> (anterior, {fmt(p.played_at)}): {factName(r)} <b style={{ color: prevFact(r) ? '#86efac' : '#f87171' }}>{prevFact(r) ? 'SIM' : 'NÃO'}</b>
                  {p.tags?.length ? <span> · tags: {p.tags.join(', ')}</span> : <span> · sem tags</span>}</div>
              : <div>· anterior: — não existe na base</div>}
            <div style={{ marginTop: 6, fontStyle: 'italic', color: '#64748b' }}>
              a "anterior" é heurística — a dona pode estar várias mãos atrás. Só a imagem arbitra;
              o Mover é sempre teu (selado, com rasto; o pipeline corre no re-tag).
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// (a) À ESPERA DE TAG — imagens que a régua dos 6s moveu SOZINHA para a anterior;
// a dona ainda não tem tag: o Rui escolhe-a aqui (selo + pipeline). Sai ao tagar.
function AwaitingRow({ r, onZoom, onDone, busy, setBusy, setMsg, tagOptions }) {
  const [tag, setTag] = useState('')
  const [open, setOpen] = useState(false)
  const src = absImageUrl(r.image_url)
  const aplicar = async () => {
    if (!tag) { setMsg('Escolhe a tag.'); return }
    if (!window.confirm(`Tagar ${r.hand_id} com '${tag}'?\n\nFica SELADO e o pipeline corre (funil, vilões, propagação).`)) return
    setBusy(true); setMsg('')
    try {
      await tagDecisions.add(r.hand_id, tag)
      onDone(r)
      setMsg(`✓ '${tag}' em ${r.hand_id} (selado).`)
    } catch (e) { setMsg('Erro: ' + (e?.message || e)) } finally { setBusy(false) }
  }
  return (
    <div style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', flexWrap: 'wrap' }}>
        <span onClick={() => setOpen(o => !o)} style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', flexWrap: 'wrap', flex: 1 }}>
          <span style={{ color: '#8b9691', width: 12 }}>{open ? '▾' : '▸'}</span>
          <Link to={`/hand/${r.hand_db_id}`} onClick={e => e.stopPropagation()} style={{ color: '#60a5fa', fontFamily: mono, fontSize: 12, fontWeight: 700, textDecoration: 'none' }}>{r.hand_id}</Link>
          <span style={{ fontSize: 11, color: '#8b9691' }}>{r.tournament_name} · {fmt(r.played_at)}</span>
          <span style={{ fontSize: 10, fontWeight: 700, color: '#38bdf8' }}
            title="a imagem foi movida para esta mão pela régua dos 6s">{r.moved_by === 'auto_moved' ? 'movida pela régua' : 'movida à mão'}</span>
        </span>
        <select value={tag} onChange={e => setTag(e.target.value)} disabled={busy}
          style={{ fontSize: 11, background: '#0b0d13', color: '#e2e8f0', border: '1px solid #2a3550', borderRadius: 5, padding: '3px 6px' }}>
          <option value="">tag…</option>
          {tagOptions.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <button onClick={aplicar} disabled={busy || !tag}
          style={{ fontSize: 11, fontWeight: 800, padding: '4px 10px', borderRadius: 5, cursor: busy ? 'wait' : 'pointer',
            border: '1px solid #22c55e66', background: 'transparent', color: '#86efac' }}>
          Tagar
        </button>
        <button onClick={() => onDone(r, true)} disabled={busy}
          title="Dispensar: fica sem tag de propósito; sai da lista (persistido)"
          style={{ fontSize: 11, padding: '4px 10px', borderRadius: 5, cursor: busy ? 'wait' : 'pointer',
            border: '1px solid #47556966', background: 'transparent', color: '#cbd5e1' }}>
          Dispensar
        </button>
      </div>
      {open && (
        <div style={{ padding: '0 10px 12px 34px' }}>
          <img src={src} alt="" loading="lazy" onClick={() => onZoom(src)}
            style={{ maxWidth: 320, width: '100%', borderRadius: 6, border: '1px solid #2a2d3a', cursor: 'zoom-in', background: '#0b0d13', display: 'block' }} />
        </div>
      )}
    </div>
  )
}

// (b) RÉGUA DOS 6s — o que a régua NÃO decidiu sozinha (sem anterior na base /
// anterior FT). Mover manual (mesma mecânica do automático) ou Dispensar.
function R6Row({ r, onZoom, onMoved, onDismiss, busy, setBusy, setMsg, tagOptions }) {
  const [open, setOpen] = useState(false)
  const [tag, setTag] = useState('')
  const src = absImageUrl(r.image_url)
  const p = r.prev
  const accent = '#38bdf8'
  const move = async () => {
    if (!p) { setMsg('Sem mão anterior na base — usa Dispensar ou trata à mão.'); return }
    const t = r.folder_tag || tag
    if (!r.folder_tag && !tag) { setMsg('Escolhe a tag para a anterior (a app não adivinha).'); return }
    const det = [`Imagem → ${p.hand_id} (casada como testemunha; SEM re-desanon).`,
      r.folder_tag ? `Tag '${r.folder_tag}' sai de ${r.hand_id} e aplica-se a ${p.hand_id} (selado).`
                   : `Tag '${tag}' entra em ${p.hand_id} (selado).`,
      `Cruzamento disparado: coroas em falta/contraditórias da anterior viram propostas (Cruzamento/Olho).`].join('\n')
    if (!window.confirm(`RÉGUA DOS 6s — mover para a anterior?\n\n${det}\n\nConfirmar?`)) return
    setBusy(true); setMsg('')
    try {
      const res = await tableSs.moveToPrev(r.ssid, p.hand_id, r.folder_tag ? undefined : tag)
      onMoved(r)
      setMsg(`✓ imagem movida ${res.from} → ${res.to}; tag '${res.tag_applied_to_prev || t}' na anterior (selada).`)
    } catch (e) { setMsg('Erro: ' + (e?.message || e)) } finally { setBusy(false) }
  }
  return (
    <div style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', flexWrap: 'wrap' }}>
        <span onClick={() => setOpen(o => !o)} style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', flexWrap: 'wrap', flex: 1 }}>
          <span style={{ color: '#8b9691', width: 12 }}>{open ? '▾' : '▸'}</span>
          <span style={{ fontWeight: 800, color: accent, fontFamily: mono, minWidth: 34, textAlign: 'right' }}>{r.interval_s}s</span>
          <Link to={`/hand/${r.hand_db_id}`} onClick={e => e.stopPropagation()} style={{ color: '#60a5fa', fontFamily: mono, fontSize: 12, fontWeight: 700, textDecoration: 'none' }}>{r.hand_id}</Link>
          {r.folder_tag
            ? <span style={{ fontSize: 10, fontWeight: 800, color: '#000', background: '#38bdf8', padding: '1px 6px', borderRadius: 5 }}>{r.folder_tag}</span>
            : <span style={{ fontSize: 10, fontWeight: 800, color: '#f59e0b', border: '1px solid #f59e0b66', padding: '1px 6px', borderRadius: 5 }}>SEM TAG</span>}
          {p
            ? <><span style={{ color: '#8b9691', fontSize: 11 }}>→ anterior</span>
                <Link to={`/hand/${p.hand_db_id}`} onClick={e => e.stopPropagation()} style={{ color: '#60a5fa', fontFamily: mono, fontSize: 12, fontWeight: 700, textDecoration: 'none' }}>{p.hand_id}</Link></>
            : <span style={{ fontSize: 11, color: '#f87171', fontWeight: 700 }}>sem anterior na base</span>}
          {r.verdict && <span style={{ fontSize: 10.5, fontWeight: 800, color: r.verdict === 'provado' ? '#86efac' : '#f59e0b' }}>({r.verdict})</span>}
        </span>
        {!r.folder_tag && (
          <select value={tag} onChange={e => setTag(e.target.value)} disabled={busy}
            style={{ fontSize: 11, background: '#0b0d13', color: '#e2e8f0', border: '1px solid #2a3550', borderRadius: 5, padding: '3px 6px' }}>
            <option value="">tag p/ a anterior…</option>
            {tagOptions.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        )}
        <button onClick={move} disabled={busy || !p}
          style={{ fontSize: 11, fontWeight: 800, padding: '4px 10px', borderRadius: 5, cursor: busy ? 'wait' : 'pointer',
            border: `1px solid ${accent}66`, background: 'transparent', color: accent }}>
          Mover → anterior
        </button>
        <button onClick={() => onDismiss(r)} disabled={busy}
          style={{ fontSize: 11, padding: '4px 10px', borderRadius: 5, cursor: busy ? 'wait' : 'pointer',
            border: '1px solid #47556966', background: 'transparent', color: '#cbd5e1' }}>
          Dispensar
        </button>
      </div>
      {open && (
        <div style={{ padding: '0 10px 12px 34px', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 700, marginBottom: 3 }}>captura (hoje casada à {r.hand_id})</div>
            <img src={src} alt="" loading="lazy" onClick={() => onZoom(src)}
              style={{ maxWidth: 300, width: '100%', borderRadius: 6, border: '1px solid #2a2d3a', cursor: 'zoom-in', background: '#0b0d13', display: 'block' }} />
          </div>
          {p?.image_url && (
            <div>
              <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 700, marginBottom: 3 }}>Gold da anterior ({p.hand_id})</div>
              <img src={absImageUrl(p.image_url)} alt="" loading="lazy" onClick={() => onZoom(absImageUrl(p.image_url))}
                style={{ maxWidth: 300, width: '100%', borderRadius: 6, border: '1px solid #2a2d3a', cursor: 'zoom-in', background: '#0b0d13', display: 'block' }} />
            </div>
          )}
          <div style={{ fontSize: 12, color: '#8b9691', minWidth: 240, maxWidth: 380 }}>
            aos {r.interval_s}s a mão {r.hand_id} mal começou — o print retrata o FIM da anterior.
            Mover: a imagem vira <b>testemunha</b> da {p ? p.hand_id : 'anterior'} (o cruzamento
            propõe coroas em falta e leva contradições ao Olho — nada se escreve em silêncio),
            e a tag viaja pelo selo.
          </div>
        </div>
      )}
    </div>
  )
}

function Section({ title, note, accent, items, header, children }) {
  return (
    <div style={{ marginBottom: 22, background: '#0f1117', borderRadius: 8, border: '1px solid #21262d' }}>
      <div style={{ padding: '10px 12px', borderBottom: '1px solid #21262d' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <div style={{ fontSize: 15, fontWeight: 800, color: accent }}>{title} <span style={{ color: '#8b9691' }}>({items.length})</span></div>
          {header}
        </div>
        <div style={{ fontSize: 12, color: '#8b9691', marginTop: 4, maxWidth: 860 }}>{note}</div>
      </div>
      {items.length === 0
        ? <div style={{ padding: 16, fontSize: 12, color: '#22c55e' }}>✓ vazio</div>
        : children}
    </div>
  )
}

export default function LatePrintsPage() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [zoom, setZoom] = useState(null)
  const [sel, setSel] = useState(new Set())
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [dest, setDest] = useState('')
  const [tagOptions, setTagOptions] = useState([])

  const load = () => ggHealth.latePrints().then(d => { setData(d); setSel(new Set()) }).catch(e => setErr(e.message))
  useEffect(() => { load() }, [])
  useEffect(() => {
    ggHealth.tagButtons().then(r => setTagOptions(r.tags || [])).catch(() => setTagOptions([]))
  }, [])
  useEffect(() => {   // re-confere a BD ao vivo no foco (LEI 1)
    const onFocus = () => load()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [])

  const regra6s = data ? (data.regra6s || []) : []
  const awaiting = data ? (data.awaiting_tag || []) : []
  const allRows = data ? [...(data.pos || []), ...(data.nota || [])] : []
  const provados = allRows.filter(r => r.verdict === 'provado')
  const suspeitas = allRows.filter(r => r.verdict !== 'provado')
  const byKey = Object.fromEntries(allRows.map(r => [rowKey(r), r]))

  const toggle = (r) => setSel(s => { const n = new Set(s); const k = rowKey(r); n.has(k) ? n.delete(k) : n.add(k); return n })
  const clearAll = () => setSel(new Set())

  const dropRows = (keys) => {   // remoção otimista (LEI 1) + re-load
    const gone = new Set(keys)
    setData(d => {
      const pos = (d.pos || []).filter(r => !gone.has(rowKey(r)))
      const nota = (d.nota || []).filter(r => !gone.has(rowKey(r)))
      const r6 = (d.regra6s || []).filter(r => !gone.has(rowKey(r)))
      const prov = [...pos, ...nota].filter(r => r.verdict === 'provado').length
      return { counts: { pos: pos.length, nota: nota.length, provados: prov,
                         suspeitas: pos.length + nota.length - prov, regra6s: r6.length },
               regra6s: r6, pos, nota }
    })
    setSel(new Set())
    load()
  }

  // MOVER um PAR (a régua): remove na atual + add na anterior, pelo selo (preview→batch).
  const movePairs = async (rows, titulo) => {
    const pairs = rows.filter(r => r.prev)
    if (!pairs.length) { setMsg('Nenhum par com mão anterior.'); return }
    const items = pairs.flatMap(r => [
      { hand_id: r.hand_id, tag: r.folder_tag, action: 'remove' },
      { hand_id: r.prev.hand_id, tag: r.folder_tag, action: 'add' },
    ])
    setBusy(true); setMsg('')
    try {
      const pv = await tagDecisions.preview(items)
      const nRem = pv.items.filter(i => i.action === 'remove' && i.will_change).length
      const nAdd = pv.items.filter(i => i.action === 'add' && i.will_change).length
      const dup = pv.items.filter(i => i.action === 'add' && i.exists && !i.will_change).length
      const detail = [`${titulo}: ${pairs.length} par(es).`,
        `Saem ${nRem} tag(s) das mãos atuais; entram ${nAdd} nas anteriores.`,
        dup ? `${dup} anterior(es) já tinham a tag (não escrevo em duplicado).` : null,
        `Fica SELADO (rasto por linha) e o pipeline corre nas mãos tocadas.`].filter(Boolean).join('\n')
      if (!window.confirm(`Mover tags para as mãos anteriores — CUSTO:\n\n${detail}\n\nConfirmar?`)) { setBusy(false); return }
      const res = await tagDecisions.batch(items)
      const okKeys = pairs
        .filter(r => res.results.some(x => x.ok && x.action === 'remove' && x.hand_id === r.hand_id && x.tag === r.folder_tag))
        .map(rowKey)
      dropRows(okKeys)
      const fails = res.results.filter(x => !x.ok)
      setMsg(fails.length
        ? `⚠️ ${res.n_ok} operação(ões) ok, ${fails.length} FALHOU: ${fails.map(x => `${x.hand_id} (${x.tag}): ${x.error}`).join('; ')}`
        : `✓ ${pairs.length} par(es) movido(s) e selado(s).`)
    } catch (e) { setMsg('Erro: ' + (e.message || e)) } finally { setBusy(false) }
  }

  // Forçar a régua dos 6s JÁ (sem esperar pelo próximo import) — o mesmo varrimento.
  const runRegra6s = async () => {
    setBusy(true); setMsg('')
    try {
      const r = await tableSs.regra6sApply()
      const moved = (r.moved_tagged || 0) + (r.moved_untagged || 0)
      setMsg(`✓ régua corrida: ${moved} movida(s) (${r.moved_tagged || 0} tag+imagem, ` +
        `${r.moved_untagged || 0} só imagem); ${r.undecided || 0} ficaram por decidir ` +
        `(sem anterior na base / anterior de mesa final). O cruzamento corre a seguir.`)
      load()
    } catch (e) { setMsg('Erro: ' + (e.message || e)) } finally { setBusy(false) }
  }

  const dismissRow = async (r) => {
    if (!window.confirm(`Dispensar (legítimo)?\n\nA tag '${r.folder_tag}' fica em ${r.hand_id}; esta captura sai do painel (persistido).`)) return
    setBusy(true); setMsg('')
    try {
      await ggHealth.latePrintsDismiss(r.ssid)
      dropRows([rowKey(r)])
      setMsg(`✓ dispensada (${r.hand_id}).`)
    } catch (e) { setMsg('Erro: ' + (e.message || e)) } finally { setBusy(false) }
  }

  // lote antigo (mantido): só tirar a tag das marcadas / mover para um destino manual
  const removeSelected = async () => {
    const keys = [...sel]
    if (!keys.length) { setMsg('Marca pelo menos uma mão.'); return }
    const items = keys.map(k => { const r = byKey[k]; return { hand_id: r.hand_id, tag: r.folder_tag, action: 'remove' } })
    setBusy(true); setMsg('')
    try {
      const pv = await tagDecisions.preview(items)
      const willChange = pv.items.filter(i => i.will_change)
      if (!window.confirm(`Tirar ${pv.n_ops} tag(s) de ${pv.n_hands} mão(s): ${[...new Set(willChange.map(i => i.tag))].join(', ') || '—'}\n\nFica SELADO. Confirmar?`)) { setBusy(false); return }
      const res = await tagDecisions.batch(items)
      dropRows(res.results.filter(x => x.ok).map(x => `${x.hand_id}|${x.tag}`))
      setMsg(res.n_failed ? `⚠️ ${res.n_ok} ok, ${res.n_failed} falhou.` : `✓ ${res.n_ok} tag(s) tirada(s).`)
    } catch (e) { setMsg('Erro: ' + (e.message || e)) } finally { setBusy(false) }
  }

  const moveSelectedToDest = async () => {
    const keys = [...sel]
    const d = dest.trim()
    if (!keys.length || !d) { setMsg('Marca mão(s) e escreve o nº GG de destino.'); return }
    const rows = keys.map(k => byKey[k])
    const items = [...rows.map(r => ({ hand_id: r.hand_id, tag: r.folder_tag, action: 'remove' })),
      ...[...new Set(rows.map(r => r.folder_tag))].map(tag => ({ hand_id: d, tag, action: 'add' }))]
    setBusy(true); setMsg('')
    try {
      const pv = await tagDecisions.preview(items)
      if (pv.items.some(i => i.action === 'add' && !i.exists)) { setMsg(`A mão de destino ${d} não existe.`); setBusy(false); return }
      if (!window.confirm(`Mover ${rows.length} tag(s) para ${d}?\n\nFica SELADO. Confirmar?`)) { setBusy(false); return }
      const res = await tagDecisions.batch(items)
      dropRows(res.results.filter(x => x.ok && x.action === 'remove').map(x => `${x.hand_id}|${x.tag}`))
      setMsg(res.n_failed ? `⚠️ ${res.n_failed} falhou.` : `✓ movido para ${d}.`)
    } catch (e) { setMsg('Erro: ' + (e.message || e)) } finally { setBusy(false) }
  }

  return (
    <div style={{ padding: 4 }}>
      <h2 style={{ fontSize: 18, margin: '0 0 4px' }}>Prints fora de tempo — reconciliação</h2>
      <p style={{ fontSize: 12, color: '#8b9691', marginTop: 0, maxWidth: 900 }}>
        Capturas com tag <b>pos/nota</b> tiradas <b>&lt; 9 s</b> do início da mão → candidatas a pertencer à
        <b> mão anterior</b>. A app confirma pela HH: <b>pos</b> → ronda de apostas pós-flop do Hero
        (all-in pré com board a correr <b>não conta</b>); <b>nota</b> → showdown <b>real</b> (linhas
        "shows", não o marcador — regra só deste exercício). <b>Mesa final fora de tudo.</b> Mover =
        selo (remove+add) + pipeline. Nada se move sem o teu clique.
      </p>
      {err && <div style={{ color: '#ef4444', fontSize: 13 }}>Erro: {err}</div>}
      {!data && !err && <div style={{ color: '#64748b', fontSize: 13 }}>A carregar…</div>}
      {msg && <div style={{ fontSize: 12, color: msg.startsWith('⚠️') ? '#f59e0b' : msg.startsWith('Erro') ? '#ef4444' : '#22c55e', margin: '0 0 12px', maxWidth: 900, whiteSpace: 'pre-wrap' }}>{msg}</div>}
      {data && (
        <>
          <Section title="À ESPERA DE TAG — a régua moveu, falta a tua tag" accent="#22c55e" items={awaiting}
            note="A régua dos 6s moveu estas imagens SOZINHA para a mão anterior (com rasto no selo). A dona ainda não tem tag de estudo — escolhe-a quando quiseres (selo + pipeline). Sai da lista ao tagar.">
            {awaiting.map((r, i) => <AwaitingRow key={`aw-${r.ssid}-${i}`} r={r} onZoom={setZoom}
              onDone={async (row, dismiss) => {
                if (dismiss) { await ggHealth.latePrintsDismiss(row.ssid).catch(() => null) }
                setData(d => ({ ...d, awaiting_tag: (d.awaiting_tag || []).filter(x => x.ssid !== row.ssid),
                  counts: { ...d.counts, awaiting_tag: Math.max(0, (d.counts.awaiting_tag || 1) - 1) } }))
                load()
              }}
              busy={busy} setBusy={setBusy} setMsg={setMsg} tagOptions={tagOptions} />)}
          </Section>
          <Section title="RÉGUA DOS 6s — o que a régua não decidiu" accent="#38bdf8" items={regra6s}
            note="A régua corre SOZINHA no processamento (≤6s pertence à anterior; FT fora; rasto no selo). Aqui fica só o que ela não decide: sem mão anterior na base, anterior de mesa final, ou ainda não varrido. Mover manual usa a mesma mecânica (imagem sem re-desanon + tag pelo selo + cruzamento)."
            header={
              <button onClick={runRegra6s} disabled={busy}
                style={{ fontSize: 12, fontWeight: 800, padding: '4px 12px', borderRadius: 5, border: 'none', cursor: busy ? 'wait' : 'pointer', background: '#38bdf8', color: '#082f49' }}>
                ▶ Correr a régua agora
              </button>
            }>
            {regra6s.map((r, i) => <R6Row key={`${r.ssid}-${i}`} r={r} onZoom={setZoom}
              onMoved={(row) => dropRows([rowKey(row)])} onDismiss={dismissRow}
              busy={busy} setBusy={setBusy} setMsg={setMsg} tagOptions={tagOptions} />)}
          </Section>
          <Section title="PROVADOS — a HH confirma dos dois lados" accent="#22c55e" items={provados}
            note="Na mão atual o facto da tag NÃO existe; na anterior existe. É o retrato do print atrasado. «Aceitar todos» move pelo selo (preview antes; rasto por linha; pipeline nas mãos tocadas)."
            header={provados.filter(r => r.prev).length > 0 && (
              <button onClick={() => movePairs(provados, 'Aceitar todos os PROVADOS')} disabled={busy}
                style={{ fontSize: 12, fontWeight: 800, padding: '4px 12px', borderRadius: 5, border: 'none', cursor: busy ? 'wait' : 'pointer', background: '#22c55e', color: '#052e16' }}>
                Aceitar todos ({provados.filter(r => r.prev).length})
              </button>
            )}>
            {provados.map((r, i) => <PairRow key={`${r.ssid}-${i}`} r={r} onZoom={setZoom}
              checked={sel.has(rowKey(r))} onToggle={() => toggle(r)}
              onMovePair={(row) => movePairs([row], 'Mover 1 par')} onDismiss={dismissRow} busy={busy} />)}
          </Section>
          <Section title="SÓ-SUSPEITAS — a régua não decide" accent="#f59e0b" items={suspeitas}
            note="O gatilho (<9s) disparou mas a HH não confirma dos dois lados (razão em cada linha: pós-flop nas duas, anterior sem o facto, anterior inexistente). Uma a uma: só a imagem arbitra.">
            {suspeitas.map((r, i) => <PairRow key={`${r.ssid}-${i}`} r={r} onZoom={setZoom}
              checked={sel.has(rowKey(r))} onToggle={() => toggle(r)}
              onMovePair={(row) => movePairs([row], 'Mover 1 par (SUSPEITA)')} onDismiss={dismissRow} busy={busy} />)}
          </Section>
        </>
      )}
      {sel.size > 0 && (
        <div style={{ position: 'fixed', bottom: 18, left: '50%', transform: 'translateX(-50%)', zIndex: 1500,
          background: '#0f172a', border: '1px solid #334155', borderRadius: 10, boxShadow: '0 10px 30px rgba(0,0,0,0.6)',
          padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', maxWidth: '94vw' }}>
          <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 700 }}>{sel.size} marcada(s)</span>
          <button onClick={removeSelected} disabled={busy}
            style={{ fontSize: 13, fontWeight: 800, padding: '7px 16px', borderRadius: 6, border: 'none', cursor: busy ? 'wait' : 'pointer', background: '#ef4444', color: '#fff' }}>
            Só tirar
          </button>
          <span style={{ width: 1, height: 24, background: '#334155' }} />
          <span style={{ fontSize: 12, color: '#94a3b8' }}>ou mover para</span>
          <input value={dest} onChange={e => setDest(e.target.value)} placeholder="GG-…"
            style={{ fontSize: 12, fontFamily: mono, padding: '6px 8px', borderRadius: 5, width: 140,
              background: '#0b0d13', border: '1px solid #2a3550', color: '#e2e8f0', outline: 'none' }} />
          <button onClick={moveSelectedToDest} disabled={busy || !dest.trim()}
            style={{ fontSize: 13, fontWeight: 800, padding: '7px 16px', borderRadius: 6, border: 'none', cursor: (busy || !dest.trim()) ? 'not-allowed' : 'pointer', background: '#22c55e', color: '#052e16' }}>
            Tirar e pôr aqui
          </button>
          <button onClick={clearAll} disabled={busy}
            style={{ fontSize: 12, padding: '7px 12px', borderRadius: 6, border: '1px solid #475569', cursor: 'pointer', background: 'transparent', color: '#cbd5e1' }}>
            Limpar
          </button>
        </div>
      )}
      {zoom && (
        <div onClick={() => setZoom(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.92)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000, cursor: 'zoom-out' }}>
          <img src={zoom} alt="" style={{ maxWidth: '95vw', maxHeight: '95vh', borderRadius: 8 }} />
        </div>
      )}
    </div>
  )
}
