import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ggHealth, tableSs, API_ROOT } from '../api/client'

// "Saúde das mãos GG" — Fase 1 (mostrar) + Fase 2 (AÇÕES). Vista por IMAGEM.
// Só GG. Ação 1: tagar (multi-select). Ação 2: ligar órfã à mão. Ação 3:
// aceitar/rejeitar/rever suspeita. Confirmação nas Ações 2/3 (mexem em ligações).

const NEEDS = [
  { key: 'gold_no_tag', label: 'Gold sem tag', color: '#eab308' },
  { key: 'orphans', label: 'Órfãs (sem mão)', color: '#f59e0b' },
  { key: 'swap_suspects', label: 'Suspeitas de troca', color: '#f59e0b' },
  { key: 'tag_conflicts', label: 'Conflito de tags', color: '#ef4444' },
]
const HEALTHY = [
  { key: 'gold_matched', label: 'Gold que casou', color: '#22c55e' },
  { key: 'it_matched', label: 'IT desanon', color: '#22c55e' },
]
const LABELS = Object.fromEntries([...NEEDS, ...HEALTHY].map(g => [g.key, g.label]))
// As 11 tags canónicas (Ação 1) — espelho de _TAG_BUTTONS no backend.
const CANONICAL_TAGS = ['icm', 'icm-pko', 'pos-pko', 'pos-nko', 'speed-racer',
  'icm-ft', 'icm-pko-ft', 'pos-pko-ft', 'pos-nko-ft', 'speed-racer-ft', 'nota']

const card = { background: 'var(--card,#161b22)', border: '1px solid var(--border,#30363d)', borderRadius: 8 }
const btn = { background: '#21262d', border: '1px solid #30363d', color: '#c9d1d9', borderRadius: 5, cursor: 'pointer', fontSize: 12, padding: '3px 8px' }

function Panel({ g, value, onClick }) {
  return (
    <button onClick={onClick} style={{
      ...card, padding: '16px 18px', minWidth: 160, cursor: 'pointer', textAlign: 'left',
      borderLeft: `3px solid ${g.color}`,
    }}>
      <div style={{ fontSize: 32, fontWeight: 800, color: g.color, lineHeight: 1 }}>{value ?? '—'}</div>
      <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 6 }}>{g.label} →</div>
    </button>
  )
}

function TipoBadge({ source }) {
  const gold = source === 'gold'
  return <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 5,
    color: gold ? '#eab308' : '#22c55e', background: gold ? 'rgba(234,179,8,0.12)' : 'rgba(34,197,94,0.12)' }}>
    {gold ? '🟡 Gold' : '🟢 IT'}</span>
}

function NumBadge({ im }) {
  if (im.num_matches === true) return <span style={{ fontSize: 11, color: '#22c55e' }}>✓ bate</span>
  if (im.num_matches === false) return <span style={{ fontSize: 11, fontWeight: 700, color: '#000', background: '#f59e0b', padding: '1px 7px', borderRadius: 5 }}>⚠ nº≠mão</span>
  return <span style={{ fontSize: 11, color: '#64748b' }}>—</span>
}

function imgSrc(im) { return API_ROOT + im.image_url }

function Row({ im, group, onZoom, selected, onToggleSel, onLink, onSwap }) {
  const src = imgSrc(im)
  const [orph, setOrph] = useState('')
  const isGoldNoTag = group === 'gold_no_tag'
  const isOrphan = group === 'orphans'
  const isSwap = group === 'swap_suspects'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 10px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
      {isGoldNoTag && (
        <input type="checkbox" checked={selected.has(im.hand_id)} onChange={() => onToggleSel(im.hand_id)}
          style={{ width: 16, height: 16, flexShrink: 0, cursor: 'pointer' }} />
      )}
      {/* Miniatura → clica abre a IMAGEM ampliada (lightbox). */}
      <img src={src} alt="" loading="lazy" onClick={() => onZoom(src)}
        style={{ width: 96, height: 60, objectFit: 'cover', borderRadius: 4, border: '1px solid #2a2d3a', flexShrink: 0, background: '#0b0d13', cursor: 'zoom-in' }} />
      <TipoBadge source={im.source} />
      <span style={{ fontFamily: "'Fira Code',monospace", fontSize: 12, color: '#94a3b8', minWidth: 96 }}>{im.filename_num || '—'}</span>
      {im.hand_db_id
        ? <Link to={`/hand/${im.hand_db_id}`} style={{ fontFamily: "'Fira Code',monospace", fontSize: 12, color: '#60a5fa', minWidth: 130, textDecoration: 'none' }}>{im.hand_id}</Link>
        : <span style={{ fontFamily: "'Fira Code',monospace", fontSize: 12, color: '#64748b', minWidth: 130 }}>sem mão</span>}
      <NumBadge im={im} />
      <span style={{ display: 'flex', gap: 4, flexWrap: 'wrap', flex: 1 }}>
        {(im.tags || []).map((t, i) => <span key={i} style={{ fontSize: 10, color: '#a5b4fc', background: 'rgba(99,102,241,0.12)', padding: '1px 6px', borderRadius: 4 }}>{t}</span>)}
        {(im.conflicts || []).map((c, i) => <span key={'c' + i} style={{ fontSize: 10, fontWeight: 700, color: '#fff', background: '#ef4444', padding: '1px 6px', borderRadius: 4 }}>conflito {c}</span>)}
      </span>
      {/* Ação 2 — ligar órfã à mão escolhida pelo Rui. */}
      {isOrphan && (
        <span style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
          <input value={orph} onChange={e => setOrph(e.target.value)} placeholder="GG-..."
            style={{ width: 130, fontFamily: "'Fira Code',monospace", fontSize: 12, background: '#0b0d13', color: '#c9d1d9', border: '1px solid #30363d', borderRadius: 4, padding: '3px 6px' }} />
          <button style={btn} onClick={() => onLink(im.ss_id, orph.trim())} disabled={!orph.trim()}>Ligar</button>
        </span>
      )}
      {/* Ação 3 — decisão sobre a suspeita de troca. */}
      {isSwap && (
        <span style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
          <button style={{ ...btn, borderColor: '#22c55e', color: '#22c55e' }}
            onClick={() => onSwap(im.ss_id, 'accept', im.filename_num)}>Aceitar</button>
          <button style={{ ...btn, borderColor: '#ef4444', color: '#f87171' }}
            onClick={() => onSwap(im.ss_id, 'reject')}>Rejeitar</button>
          <button style={btn} onClick={() => onSwap(im.ss_id, 'review')}>Rever</button>
        </span>
      )}
      <span style={{ fontSize: 11, color: im.state === 'órfã' ? '#f59e0b' : '#64748b', minWidth: 50, textAlign: 'right' }}>{im.state}</span>
    </div>
  )
}

function Lightbox({ src, onClose }) {
  if (!src) return null
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.92)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000, cursor: 'zoom-out' }}>
      <img src={src} alt="" style={{ maxWidth: '95vw', maxHeight: '95vh', borderRadius: 8 }} onClick={e => e.stopPropagation()} />
      <button onClick={onClose} style={{ position: 'absolute', top: 20, right: 20, background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff', fontSize: 24, cursor: 'pointer', borderRadius: 8, padding: '4px 12px' }}>✕</button>
    </div>
  )
}

export default function GGHealth() {
  const [sum, setSum] = useState(null)
  const [err, setErr] = useState(null)
  const [group, setGroup] = useState(null)
  const [list, setList] = useState(null)
  const [page, setPage] = useState(1)
  const [zoom, setZoom] = useState(null)
  const [selected, setSelected] = useState(new Set())   // Ação 1: hand_ids marcados
  const [msg, setMsg] = useState(null)

  const loadSummary = () => ggHealth.summary().then(setSum).catch(e => setErr(e.message))
  useEffect(() => { loadSummary() }, [])
  useEffect(() => {
    if (!group) { setList(null); return }
    setList(null)
    ggHealth.list(group, page).then(setList).catch(e => setErr(e.message))
  }, [group, page])

  const open = (k) => { setGroup(k); setPage(1); setSelected(new Set()); setMsg(null) }
  const reload = () => {
    loadSummary()
    ggHealth.list(group, page).then(setList).catch(e => setErr(e.message))
  }
  const toggleSel = (hid) => setSelected(s => {
    const n = new Set(s); n.has(hid) ? n.delete(hid) : n.add(hid); return n
  })

  // Ação 1 — tagar as mãos selecionadas.
  const applyTag = async (tag) => {
    const ids = [...selected]
    if (!ids.length) { setMsg('Seleciona pelo menos uma mão.'); return }
    try {
      let res = await ggHealth.tag(ids, tag, false)
      if (res.needs_confirm) {
        const w = (res.warnings || []).map(x => `${x.hand_id} (${x.tournament_format})`).join(', ')
        if (!window.confirm(`A tag "${tag}" contradiz o formato do torneio em: ${w}.\nAplicar mesmo assim?`)) return
        res = await ggHealth.tag(ids, tag, true)
      }
      setMsg(`${res.applied} mão(s) tagada(s) com "${tag}".`)
      setSelected(new Set())
      reload()
    } catch (e) { setMsg('Erro: ' + e.message) }
  }

  // Ação 2 — ligar órfã à mão (com confirmação).
  const linkOrphan = async (ssId, handId) => {
    if (!handId) return
    if (!window.confirm(`Ligar esta captura à mão ${handId}? (a Gold não é sobrescrita)`)) return
    try { await tableSs.link(ssId, handId); setMsg(`Ligada a ${handId}.`); reload() }
    catch (e) { setMsg('Erro: ' + e.message) }
  }

  // Ação 3 — decisão sobre suspeita (com confirmação nas que escrevem).
  const swapAction = async (ssId, decision, fnum) => {
    const prompts = {
      accept: `ACEITAR: mover a captura para GG-${fnum}? (respeita a Gold)`,
      reject: 'REJEITAR: manter onde está e tirar do painel?',
    }
    if (prompts[decision] && !window.confirm(prompts[decision])) return
    try { await tableSs.swapReview(ssId, decision); setMsg('Feito.'); reload() }
    catch (e) { setMsg('Erro: ' + (e.message || 'falhou')) }
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
        <h1 style={{ fontSize: 20, margin: 0 }}>Saúde das mãos GG</h1>
        {sum && <span style={{ fontSize: 13, color: 'var(--muted)' }}>{sum.total_images} imagens · {sum.total_hands_with_image} mãos com imagem</span>}
      </div>
      {err && <div style={{ ...card, padding: 16, color: '#ef4444', marginTop: 12 }}>Erro: {err}</div>}

      {!group && sum && (
        <>
          <div style={{ fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5, margin: '20px 0 8px' }}>Precisa de ti</div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {NEEDS.map(g => <Panel key={g.key} g={g} value={sum.needs_you[g.key]} onClick={() => open(g.key)} />)}
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5, margin: '24px 0 8px' }}>Saudável</div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {HEALTHY.map(g => <Panel key={g.key} g={g} value={sum.healthy[g.key]} onClick={() => open(g.key)} />)}
          </div>
        </>
      )}

      {group && (
        <div style={{ marginTop: 16 }}>
          <button onClick={() => setGroup(null)} style={{ background: 'none', border: 'none', color: '#818cf8', cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>&larr; Dashboard</button>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, margin: '6px 0 12px' }}>
            <h2 style={{ fontSize: 16, margin: 0 }}>{LABELS[group]}</h2>
            {list && <span style={{ fontSize: 13, color: 'var(--muted)' }}>{list.total} imagens</span>}
          </div>

          {/* Ação 1 — barra de tags (só no grupo "Gold sem tag"). */}
          {group === 'gold_no_tag' && (
            <div style={{ ...card, padding: '10px 12px', marginBottom: 10 }}>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>
                Selecionadas: <b>{selected.size}</b> — carrega numa tag para aplicar a todas:
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {CANONICAL_TAGS.map(t => (
                  <button key={t} style={{ ...btn, opacity: selected.size ? 1 : 0.4 }}
                    disabled={!selected.size} onClick={() => applyTag(t)}>{t}</button>
                ))}
              </div>
            </div>
          )}
          {msg && <div style={{ ...card, padding: '8px 12px', marginBottom: 10, color: '#93c5fd', fontSize: 13 }}>{msg}</div>}

          {!list ? <div style={{ color: 'var(--muted)' }}>A carregar…</div> : (
            <>
              <div style={{ ...card, overflow: 'hidden' }}>
                {list.images.map((im, i) => (
                  <Row key={i} im={im} group={group} onZoom={setZoom}
                    selected={selected} onToggleSel={toggleSel}
                    onLink={linkOrphan} onSwap={swapAction} />
                ))}
                {list.images.length === 0 && <div style={{ padding: 16, color: '#22c55e' }}>✓ Nenhuma imagem neste grupo.</div>}
              </div>
              {list.total > list.page_size && (
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 12 }}>
                  <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Anterior</button>
                  <span style={{ fontSize: 12, color: 'var(--muted)' }}>página {page} / {Math.ceil(list.total / list.page_size)}</span>
                  <button disabled={page >= Math.ceil(list.total / list.page_size)} onClick={() => setPage(p => p + 1)}>Seguinte →</button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      <Lightbox src={zoom} onClose={() => setZoom(null)} />
    </div>
  )
}
