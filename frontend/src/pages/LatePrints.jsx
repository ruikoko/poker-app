import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ggHealth, tagDecisions, absImageUrl } from '../api/client'

// Painel "Prints fora de tempo — a mão não deu tempo". Régua na TAG (não na mão), print <9s,
// MESA FINAL fora de tudo. DUAS listas:
//  A (tag pos): aos 9s a mão não chegou ao flop → um print de spot pós-flop é IMPOSSÍVEL, com
//    ou sem flop na mão (a impossibilidade está na tag, não no flop).
//  B (tag nota): SEM impossibilidade — uma nota pode ser sobre o pré-flop. Lista para OLHAR.
// SELO DA TAG: seleção em lote → tirar a tag (da captura) de várias mãos de uma vez. A remoção
// fica SELADA e não volta no reprocessamento. A "mão anterior na mesma mesa" é HEURÍSTICA de
// dona — candidata, não provada.

const mono = "'Fira Code',monospace"
const fmt = (iso) => iso ? String(iso).replace('T', ' ').slice(0, 16) : '—'
const rowKey = (r) => `${r.hand_id}|${r.folder_tag}`   // uma mão pode estar em A (pos) e B (nota)

function Row({ r, onZoom, accent, checked, onToggle }) {
  const [open, setOpen] = useState(false)
  const src = absImageUrl(r.image_url)
  const p = r.prev
  return (
    <div style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', flexWrap: 'wrap' }}>
        <input type="checkbox" checked={checked} onChange={onToggle}
          title="Marcar para tirar a tag em lote"
          style={{ width: 15, height: 15, cursor: 'pointer', accentColor: accent }} />
        <span onClick={() => setOpen(o => !o)} style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', flexWrap: 'wrap', flex: 1 }}>
          <span style={{ color: '#8b9691', width: 12 }}>{open ? '▾' : '▸'}</span>
          <span style={{ fontWeight: 800, color: accent, fontFamily: mono, minWidth: 40, textAlign: 'right' }}>{r.interval_s}s</span>
          <Link to={`/hand/${r.hand_db_id}`} onClick={e => e.stopPropagation()} style={{ color: '#60a5fa', fontFamily: mono, fontSize: 12, fontWeight: 700, textDecoration: 'none' }}>{r.hand_id}</Link>
          <span style={{ fontSize: 10, fontWeight: 800, color: '#000', background: '#38bdf8', padding: '1px 6px', borderRadius: 5 }} title="tag da captura (pasta)">{r.folder_tag}</span>
          <span style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {(r.tags || []).map((t, i) => <span key={i} style={{ fontSize: 10, fontWeight: 700, color: '#000', background: '#a78bfa', padding: '1px 6px', borderRadius: 5 }} title="tags da mão">{t}</span>)}
          </span>
          <span style={{ fontSize: 10, fontWeight: 700, color: r.had_flop ? '#86efac' : '#f87171' }}>{r.had_flop ? 'mão teve flop' : 'mão sem flop'}</span>
          <span style={{ fontSize: 11, color: '#64748b', fontFamily: mono }}>{r.match_method}</span>
        </span>
      </div>
      {open && (
        <div style={{ padding: '0 10px 12px 34px', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <img src={src} alt="" loading="lazy" onClick={() => onZoom(src)}
            style={{ maxWidth: 320, width: '100%', borderRadius: 6, border: '1px solid #2a2d3a', cursor: 'zoom-in', background: '#0b0d13', display: 'block' }} />
          <div style={{ fontSize: 12, color: '#8b9691', minWidth: 240 }}>
            <div style={{ color: '#94a3b8', fontWeight: 700, marginBottom: 4 }}>
              mão anterior na mesma mesa <span style={{ color: '#f59e0b' }}>(candidata — NÃO dona provada)</span>
            </div>
            {p ? (
              <div>
                <Link to={`/hand/${p.hand_db_id}`} style={{ color: '#60a5fa', fontFamily: mono, fontWeight: 700 }}>{p.hand_id}</Link>
                <span> · {fmt(p.played_at)}</span> · <b style={{ color: p.had_flop ? '#86efac' : '#f87171' }}>{p.had_flop ? 'teve flop' : 'sem flop'}</b>
              </div>
            ) : <div>— nenhuma anterior na mesma mesa em BD</div>}
            <div style={{ marginTop: 6, fontStyle: 'italic', color: '#64748b' }}>
              a dona pode estar várias mãos atrás; o Rui re-taga tarde. É pista, não resposta — só a imagem arbitra.
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Section({ title, note, accent, items, onZoom, sel, toggle, selectAll, clearSection, emptyOk }) {
  const allSel = items.length > 0 && items.every(r => sel.has(rowKey(r)))
  return (
    <div style={{ marginBottom: 22, background: '#0f1117', borderRadius: 8, border: '1px solid #21262d' }}>
      <div style={{ padding: '10px 12px', borderBottom: '1px solid #21262d' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <div style={{ fontSize: 15, fontWeight: 800, color: accent }}>{title} <span style={{ color: '#8b9691' }}>({items.length})</span></div>
          {items.length > 0 && (
            <button onClick={() => allSel ? clearSection(items) : selectAll(items)}
              style={{ fontSize: 11, padding: '2px 8px', borderRadius: 4, background: 'transparent', border: `1px solid ${accent}55`, color: accent, cursor: 'pointer', fontWeight: 600 }}>
              {allSel ? 'Limpar esta lista' : 'Selecionar tudo'}
            </button>
          )}
        </div>
        <div style={{ fontSize: 12, color: '#8b9691', marginTop: 4, maxWidth: 820 }}>{note}</div>
      </div>
      {items.length === 0
        ? <div style={{ padding: 16, fontSize: 12, color: emptyOk ? '#22c55e' : '#8b9691' }}>{emptyOk ? '✓ vazio' : '— nada'}</div>
        : items.map((r, i) => <Row key={`${r.ssid}-${i}`} r={r} onZoom={onZoom} accent={accent}
            checked={sel.has(rowKey(r))} onToggle={() => toggle(r)} />)}
    </div>
  )
}

export default function LatePrintsPage() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [zoom, setZoom] = useState(null)
  const [sel, setSel] = useState(new Set())        // rowKey selecionadas
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  const load = () => ggHealth.latePrints().then(d => { setData(d); setSel(new Set()) }).catch(e => setErr(e.message))
  useEffect(() => { load() }, [])
  // Re-confere a BD ao vivo quando o separador volta ao foco (LEI 1).
  useEffect(() => {
    const onFocus = () => load()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [])

  const allRows = data ? [...(data.pos || []), ...(data.nota || [])] : []
  const byKey = Object.fromEntries(allRows.map(r => [rowKey(r), r]))

  const toggle = (r) => setSel(s => { const n = new Set(s); const k = rowKey(r); n.has(k) ? n.delete(k) : n.add(k); return n })
  const selectAll = (items) => setSel(s => { const n = new Set(s); items.forEach(r => n.add(rowKey(r))); return n })
  const clearSection = (items) => setSel(s => { const n = new Set(s); items.forEach(r => n.delete(rowKey(r))); return n })
  const clearAll = () => setSel(new Set())

  // Tirar a tag (da captura) das mãos selecionadas, em lote. Mostra o CUSTO antes (preview) +
  // Cancelar; nada se escreve sem carimbar. Falha honesta: reporta quais não deram.
  const removeSelected = async () => {
    const keys = [...sel]
    if (!keys.length) { setMsg('Marca pelo menos uma mão.'); return }
    const items = keys.map(k => { const r = byKey[k]; return { hand_id: r.hand_id, tag: r.folder_tag, action: 'remove' } })
    setBusy(true); setMsg('')
    try {
      const pv = await tagDecisions.preview(items)
      const willChange = pv.items.filter(i => i.will_change)
      const tagsOut = [...new Set(willChange.map(i => i.tag))].join(', ') || '—'
      const missing = pv.items.filter(i => !i.exists).length
      const noChange = pv.items.length - willChange.length - missing
      const detail = [`${pv.n_ops} tag(s) saem de ${pv.n_hands} mão(s): ${tagsOut}`,
        missing ? `${missing} mão(s) não encontrada(s)` : null,
        noChange ? `${noChange} sem alteração (já não têm a tag)` : null].filter(Boolean).join('\n')
      if (!window.confirm(`Tirar tags em lote — CUSTO:\n\n${detail}\n\nFica SELADO (não volta no reprocessamento). Confirmar?`)) {
        setBusy(false); return
      }
      const res = await tagDecisions.batch(items)
      // remoção otimista (LEI 1): tira da lista as que saíram; a lista re-confere no reload.
      const okKeys = new Set(res.results.filter(r => r.ok).map(r => `${r.hand_id}|${r.tag}`))
      setData(d => ({
        counts: { pos: (d.pos || []).filter(r => !okKeys.has(rowKey(r))).length,
                  nota: (d.nota || []).filter(r => !okKeys.has(rowKey(r))).length },
        pos: (d.pos || []).filter(r => !okKeys.has(rowKey(r))),
        nota: (d.nota || []).filter(r => !okKeys.has(rowKey(r))),
      }))
      setSel(new Set())
      if (res.n_failed) {
        const fails = res.results.filter(r => !r.ok).map(r => `${r.hand_id} (${r.tag}): ${r.error}`).join('; ')
        setMsg(`⚠️ ${res.n_ok} tirada(s), ${res.n_failed} FALHOU: ${fails}`)
      } else {
        setMsg(`✓ ${res.n_ok} tag(s) tirada(s) e seladas.`)
      }
      load()   // re-confere a BD ao vivo
    } catch (e) {
      setMsg('Erro: ' + (e.message || e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ padding: 4 }}>
      <h2 style={{ fontSize: 18, margin: '0 0 4px' }}>Prints fora de tempo — a mão não deu tempo</h2>
      <p style={{ fontSize: 12, color: '#8b9691', marginTop: 0, maxWidth: 900 }}>
        Capturas GG tiradas <b>&lt; 9 s</b> do início da mão (hora do print − hora do início). Régua na
        <b> tag da captura</b>, não na mão. <b>Mesa final (qualquer tag <code>-ft</code>) fica de fora de tudo.</b> Marca
        as mãos e tira a tag em lote — fica <b>selado</b> (não volta no reprocessamento).
      </p>
      <div style={{ fontSize: 12, color: '#f59e0b', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 6, padding: '8px 12px', margin: '8px 0 16px', maxWidth: 900 }}>
        ⚠️ A <b>mão anterior na mesma mesa</b> é uma <b>heurística de dona — candidata, não dona provada</b>.
        A dona real pode estar <b>várias mãos atrás</b> (o Rui re-taga tarde). Não é resposta; é pista. Só a imagem arbitra.
      </div>
      {err && <div style={{ color: '#ef4444', fontSize: 13 }}>Erro: {err}</div>}
      {!data && !err && <div style={{ color: '#64748b', fontSize: 13 }}>A carregar…</div>}
      {msg && <div style={{ fontSize: 12, color: msg.startsWith('⚠️') ? '#f59e0b' : msg.startsWith('Erro') ? '#ef4444' : '#22c55e', margin: '0 0 12px', maxWidth: 900, whiteSpace: 'pre-wrap' }}>{msg}</div>}
      {data && (
        <>
          <Section title="A · Impossíveis — tag pos (< 9 s)" accent="#ef4444" emptyOk
            note="Tag pos-pko/pos-nko = spot pós-flop. Aos 9 s a mão nem chegou ao flop → um print de spot pós-flop é IMPOSSÍVEL, tenha a mão ido ao flop ou não. A impossibilidade está na TAG. Provável print da mão anterior, casado à mão errada."
            items={data.pos || []} onZoom={setZoom} sel={sel} toggle={toggle} selectAll={selectAll} clearSection={clearSection} />
          <Section title="B · tag nota (< 9 s) — só para olhar" accent="#38bdf8"
            note="Tag nota = pode ser sobre o PRÉ-FLOP → aqui NÃO há impossibilidade nenhuma. As 3 verificadas pelo Rui estavam erradas, mas 3 casos não fazem regra: é lista para olhar, não veredito."
            items={data.nota || []} onZoom={setZoom} sel={sel} toggle={toggle} selectAll={selectAll} clearSection={clearSection} />
        </>
      )}
      {sel.size > 0 && (
        <div style={{ position: 'fixed', bottom: 18, left: '50%', transform: 'translateX(-50%)', zIndex: 1500,
          background: '#0f172a', border: '1px solid #334155', borderRadius: 10, boxShadow: '0 10px 30px rgba(0,0,0,0.6)',
          padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 14 }}>
          <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 700 }}>{sel.size} mão(s) marcada(s)</span>
          <button onClick={removeSelected} disabled={busy}
            style={{ fontSize: 13, fontWeight: 800, padding: '7px 16px', borderRadius: 6, border: 'none', cursor: busy ? 'wait' : 'pointer', background: '#ef4444', color: '#fff', opacity: busy ? 0.6 : 1 }}>
            {busy ? 'A tirar…' : 'Tirar tag em lote'}
          </button>
          <button onClick={clearAll} disabled={busy}
            style={{ fontSize: 12, padding: '7px 12px', borderRadius: 6, border: '1px solid #475569', cursor: 'pointer', background: 'transparent', color: '#cbd5e1' }}>
            Limpar seleção
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
