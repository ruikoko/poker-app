import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ggHealth, tableSs, API_ROOT } from '../api/client'

// Bounties recuperáveis (#CROWN-RECOVERY) — ETAPA 2: sugerir (Vision só-ao-verde) +
// carimbar (escrita SELADA). Grupo 1 = jogador bustou na HH E coroa NULL → o bounty
// dele está a VERDE na coroa do matador; grava-se TAL-E-QUAL (SEM ×2, unidade=coroa)
// com bounty_source='derived_green_ko'. A dourada do matador corrige-se à mão ('manual').
// Só a imagem arbitra os valores; a escrita só acontece por carimbo do Rui.

const C = {
  card: '#161d19', border: 'rgba(255,255,255,0.10)', text: '#e8ece9',
  muted: '#8b9691', green: '#46c98a', gold: '#e6b34a', red: '#e0705f',
}

export default function CrownRecovery() {
  const [st, setSt] = useState(null)
  const [busy, setBusy] = useState(false)
  const [showOver, setShowOver] = useState(false)
  const poll = useRef(null)

  const refresh = () => ggHealth.crownRecoveryState().then(setSt).catch(() => {})
  useEffect(() => { refresh(); return () => clearInterval(poll.current) }, [])
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

  return (
    <div style={{ padding: '18px 22px', color: C.text, maxWidth: 1000, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, fontWeight: 800, margin: '0 0 4px' }}>Bounties recuperáveis</h1>
      <p style={{ color: C.muted, fontSize: 13, margin: '0 0 14px', lineHeight: 1.5, maxWidth: '70ch' }}>
        Mãos onde um jogador <b style={{ color: C.red }}>bustou</b> (all-in + perdeu, da HH) e a
        coroa dourada dele ficou <b style={{ color: C.red }}>NULL</b> — o bounty está a{' '}
        <b style={{ color: C.green }}>verde</b> na coroa de quem o eliminou. <b>Etapa 2</b>: carrega{' '}
        <b>Sugerir</b> (a Vision lê só o verde) ou lê à mão da imagem, e <b>Carimbar</b> grava{' '}
        <b>selado</b> — o verde <b>tal-e-qual</b> (sem ×2) como <code>derived_green_ko</code>, a dourada
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

      {idle && <div style={{ color: C.muted, fontSize: 14 }}>Carrega em “Correr detetor” para varrer as KO/PKO com Gold.</div>}

      {/* grupo 1 — recuperáveis (Etapa 2: sugerir + carimbar) */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {g1.map(h => <Group1Card key={h.hand_db_id} h={h} C={C} onDone={refresh} />)}
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

// ── Coroas — revisão de quedas: worklist NA app (quedas mesmo-hash + fora-de-grelha) ──
function DropsWorklist({ C }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [zoom, setZoom] = useState(null)     // src da imagem ampliada
  const load = () => { setLoading(true); ggHealth.crownDrops().then(setData).catch(() => setData(null)).finally(() => setLoading(false)) }
  useEffect(() => { load() }, [])

  const drops = data?.drops || []
  const off = data?.off_grid || []
  const total = drops.length + off.length

  return (
    <div style={{ marginTop: 26 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6, flexWrap: 'wrap' }}>
        <h2 style={{ fontSize: 16, fontWeight: 800, margin: 0 }}>Coroas — revisão de quedas</h2>
        <span style={{ color: C.muted, fontSize: 12 }}>
          {loading ? 'a carregar…' : `${drops.length} quedas + ${off.length} fora-de-grelha = ${total} casos`}
        </span>
        <button onClick={load} disabled={loading} style={{ background: 'transparent', color: C.text,
          border: `1px solid ${C.border}`, borderRadius: 6, padding: '3px 10px', cursor: 'pointer', fontSize: 12 }}>
          Recarregar
        </button>
      </div>
      <p style={{ color: C.muted, fontSize: 12, margin: '0 0 12px', maxWidth: '74ch', lineHeight: 1.5 }}>
        A coroa do mesmo jogador <b>nunca desce</b> — uma queda é <b>leitura errada</b>. Vê a imagem,
        compara os dois valores e <b>corrige</b> (grava selado <code>manual</code>, intocável por automático).
        As fora-de-grelha são sinalizador leve. Só a imagem arbitra.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {drops.map((d, i) => (
          <DropCard key={'d' + i} C={C} kind="queda" player={d.player}
            handId={d.hand_id} handDb={d.hand_db_id} lowVal={d.low} refVal={d.ref}
            entryId={d.entry_id} refEntryId={d.ref_entry_id} refHandId={d.ref_hand_id}
            onZoom={setZoom} />
        ))}
        {off.map((o, i) => (
          <DropCard key={'o' + i} C={C} kind="fora-de-grelha" player={o.player}
            handId={o.hand_id} handDb={o.hand_db_id} lowVal={o.value} ratio={o.ratio}
            entryId={o.entry_id} onZoom={setZoom} />
        ))}
        {!loading && total === 0 && <div style={{ color: C.muted, fontSize: 13 }}>Nenhum caso — coroas limpas.</div>}
      </div>

      {zoom && (
        <div onClick={() => setZoom(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.85)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, cursor: 'zoom-out', padding: 20 }}>
          <img src={zoom} alt="zoom" style={{ maxWidth: '96vw', maxHeight: '92vh', objectFit: 'contain', borderRadius: 8 }} />
        </div>
      )}
    </div>
  )
}

function DropCard({ C, kind, player, handId, handDb, lowVal, refVal, ratio, entryId, refEntryId, refHandId, onZoom }) {
  const [val, setVal] = useState(refVal != null ? String(refVal) : '')
  const [stamping, setStamping] = useState(false)
  const [msg, setMsg] = useState(null)
  const [done, setDone] = useState(false)
  const imgUrl = entryId != null ? `${API_ROOT}/api/screenshots/image/${entryId}` : null
  const refImgUrl = refEntryId != null ? `${API_ROOT}/api/screenshots/image/${refEntryId}` : null

  const stamp = async () => {
    const v = parseFloat(val)
    if (isNaN(v)) { setMsg({ ok: false, t: 'Valor inválido' }); return }
    setStamping(true); setMsg(null)
    try {
      const r = await tableSs.setBounties(handId, { bounties: { [player]: v }, sources: { [player]: 'manual' } })
      if ((r?.updated || []).length) { setDone(true); setMsg({ ok: true, t: `Carimbado ✓ $${v} (manual)` }) }
      else setMsg({ ok: false, t: `Nome não encontrado no players_list${(r?.not_found || []).length ? ': ' + r.not_found.join(', ') : ''}` })
    } catch (e) { setMsg({ ok: false, t: 'Falha: ' + (e?.message || e) }) }
    finally { setStamping(false) }
  }

  const thumb = (src, label) => src && (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <img src={src} alt={label} loading="lazy" onClick={() => onZoom(src)}
        style={{ width: 200, maxWidth: '100%', borderRadius: 7, objectFit: 'contain', cursor: 'zoom-in',
          border: `1px solid ${C.border}`, background: '#000' }} />
      <span style={{ fontSize: 10, color: C.muted, textAlign: 'center' }}>{label} (clica p/ zoom)</span>
    </div>
  )

  return (
    <div style={{ background: C.card, border: `1px solid ${done ? C.green : C.border}`, borderRadius: 11,
      padding: 12, display: 'flex', gap: 14, flexWrap: 'wrap', opacity: done ? 0.65 : 1 }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {thumb(imgUrl, `$${lowVal} (a rever)`)}
        {kind === 'queda' && thumb(refImgUrl, `$${refVal} (referência)`)}
      </div>
      <div style={{ flex: 1, minWidth: 240 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
          <b style={{ fontSize: 14 }}>{player}</b>
          <span style={{ fontSize: 10, color: '#08130d', background: kind === 'queda' ? C.red : C.gold,
            borderRadius: 4, padding: '1px 6px', fontWeight: 700 }}>{kind}</span>
          <Link to={`/hand/${handDb}`} style={{ color: C.gold, fontSize: 12, textDecoration: 'none',
            fontFamily: 'ui-monospace,monospace' }}>{handId}</Link>
        </div>
        <div style={{ marginTop: 6, fontSize: 13 }}>
          {kind === 'queda'
            ? <>leu <b style={{ color: C.red }}>${lowVal}</b> (a rever) · referência anterior{' '}
                <b style={{ color: C.green }}>${refVal}</b> {refHandId && <span style={{ color: C.muted, fontSize: 11 }}>({refHandId})</span>}</>
            : <>leu <b style={{ color: C.gold }}>${lowVal}</b> = {ratio}B — fora da grelha das metades</>}
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ color: C.muted, fontSize: 13 }}>corrigir $</span>
          <input value={val} onChange={e => setVal(e.target.value)} inputMode="decimal" placeholder="valor da imagem"
            style={{ width: 100, background: '#0e1512', color: C.text, border: `1px solid ${C.border}`,
              borderRadius: 6, padding: '4px 7px', fontSize: 13, fontFamily: 'ui-monospace,monospace' }} />
          <button onClick={stamp} disabled={stamping || done}
            style={{ background: done ? '#2a2f37' : C.gold, color: done ? C.muted : '#08130d', border: 'none',
              borderRadius: 8, padding: '5px 13px', fontWeight: 800, fontSize: 13,
              cursor: stamping || done ? 'default' : 'pointer' }}>
            {done ? 'Carimbado ✓' : stamping ? '…' : 'Carimbar (manual)'}
          </button>
          {msg && <span style={{ fontSize: 12, color: msg.ok ? C.green : C.red }}>{msg.t}</span>}
        </div>
      </div>
    </div>
  )
}

// ── Etapa 2 — cartão do grupo 1 com sugerir (Vision só-ao-verde) + carimbar (selado) ──
function Group1Card({ h, C, onDone }) {
  const busted = h.busted || []
  const matadores = (h.matadores || []).filter(m => m.name)
  const [vals, setVals] = useState({})           // name -> string (valor a escrever)
  const [sugg, setSugg] = useState(null)         // name -> verde sugerido pela Vision
  const [suggesting, setSuggesting] = useState(false)
  const [stamping, setStamping] = useState(false)
  const [msg, setMsg] = useState(null)
  const [done, setDone] = useState(false)

  const setVal = (name, v) => setVals(s => ({ ...s, [name]: v }))

  const suggest = async () => {
    setSuggesting(true); setMsg(null)
    try {
      const r = await ggHealth.crownRecoverySuggest(h.hand_id)
      const item = (r?.report || []).find(x => x.hand_id === h.hand_id)
      const seats = item?.seats || []
      const next = {}
      seats.forEach(s => { if (s.bounty != null) next[s.name] = String(s.bounty) })
      if (Object.keys(next).length) {
        setSugg(next); setVals(v => ({ ...next, ...v }))   // prefill sem apagar edições
        setMsg({ ok: true, t: 'Vision leu o verde — confirma antes de carimbar.' })
      } else {
        setMsg({ ok: false, t: item?.expected === 'por rever'
          ? 'Sem Gold / verde não guardado — lê à mão da imagem.'
          : 'Vision não leu verde legível — lê à mão da imagem.' })
      }
    } catch (e) { setMsg({ ok: false, t: 'Falha a sugerir: ' + (e?.message || e) }) }
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
      const nf = (r?.not_found || [])
      setDone(true)
      setMsg({ ok: true, t: `Carimbado ✓ (${(r?.updated || []).length} selados${nf.length ? `, ${nf.length} não encontrados: ${nf.join(', ')}` : ''}).` })
      if (onDone) setTimeout(onDone, 1200)
    } catch (e) { setMsg({ ok: false, t: 'Falha a carimbar: ' + (e?.message || e) }) }
    finally { setStamping(false) }
  }

  const row = (name, tag, tagColor) => (
    <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
      <span style={{ fontSize: 13, minWidth: 130 }}><b>{name}</b></span>
      <span style={{ fontSize: 10, color: '#08130d', background: tagColor, borderRadius: 4, padding: '1px 6px', fontWeight: 700 }}>{tag}</span>
      <span style={{ color: C.muted, fontSize: 13 }}>$</span>
      <input value={vals[name] ?? ''} onChange={e => setVal(name, e.target.value)}
        placeholder={sugg?.[name] != null ? String(sugg[name]) : '—'} inputMode="decimal"
        style={{ width: 90, background: '#0e1512', color: C.text, border: `1px solid ${C.border}`,
          borderRadius: 6, padding: '4px 7px', fontSize: 13, fontFamily: 'ui-monospace,monospace' }} />
      {sugg?.[name] != null && <span style={{ color: C.green, fontSize: 11 }}>Vision: ${sugg[name]}</span>}
    </div>
  )

  return (
    <div style={{ background: C.card, border: `1px solid ${done ? C.green : C.border}`,
      borderRadius: 12, padding: 14, display: 'flex', gap: 16, flexWrap: 'wrap', opacity: done ? 0.7 : 1 }}>
      {h.entry_id != null && (
        <img src={`${API_ROOT}/api/screenshots/image/${h.entry_id}`} alt="gold" loading="lazy"
          onError={e => { e.currentTarget.style.display = 'none'
            const n = e.currentTarget.nextSibling; if (n) n.style.display = 'flex' }}
          style={{ width: 320, maxWidth: '100%', borderRadius: 9, objectFit: 'contain',
            border: `1px solid ${C.border}`, background: '#000' }} />
      )}
      {h.entry_id != null && (
        <div style={{ display: 'none', width: 320, maxWidth: '100%', minHeight: 120,
          alignItems: 'center', justifyContent: 'center', borderRadius: 9,
          border: `1px dashed ${C.border}`, color: C.muted, fontSize: 12 }}>imagem indisponível</div>
      )}
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
          <div style={lbl(C)}>Eliminado · bounty = verde (tal-e-qual, sem ×2)</div>
          {busted.map(b => row(b.name, 'verde', C.green))}
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
