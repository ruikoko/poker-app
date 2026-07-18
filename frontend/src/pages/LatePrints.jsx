import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ggHealth, absImageUrl } from '../api/client'

// Painel "Prints fora de tempo — a mão não deu tempo" (read-only). Capturas em mãos que
// TIVERAM flop, tiradas <20s do início. Duas secções: Impossíveis (<10s, física) e
// Suspeitos (10-20s, provável). A "mão anterior na mesma mesa" é HEURÍSTICA de dona —
// candidata, não dona provada. Ordenado por intervalo. Não escreve nada.

const mono = "'Fira Code',monospace"
const fmt = (iso) => iso ? String(iso).replace('T', ' ').slice(0, 16) : '—'

function Row({ r, onZoom, accent }) {
  const [open, setOpen] = useState(false)
  const src = absImageUrl(r.image_url)
  const p = r.prev
  return (
    <div style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
      <div onClick={() => setOpen(o => !o)} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', cursor: 'pointer', flexWrap: 'wrap' }}>
        <span style={{ color: '#8b9691', width: 12 }}>{open ? '▾' : '▸'}</span>
        <span style={{ fontWeight: 800, color: accent, fontFamily: mono, minWidth: 40, textAlign: 'right' }}>{r.interval_s}s</span>
        <Link to={`/hand/${r.hand_db_id}`} onClick={e => e.stopPropagation()} style={{ color: '#60a5fa', fontFamily: mono, fontSize: 12, fontWeight: 700, textDecoration: 'none' }}>{r.hand_id}</Link>
        <span style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {(r.tags || []).map((t, i) => <span key={i} style={{ fontSize: 10, fontWeight: 700, color: '#000', background: '#a78bfa', padding: '1px 6px', borderRadius: 5 }}>{t}</span>)}
        </span>
        <span style={{ fontSize: 11, color: '#64748b', fontFamily: mono }}>{r.match_method}</span>
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

function Section({ title, note, accent, items, onZoom }) {
  return (
    <div style={{ marginBottom: 22, background: '#0f1117', borderRadius: 8, border: '1px solid #21262d' }}>
      <div style={{ padding: '10px 12px', borderBottom: '1px solid #21262d' }}>
        <div style={{ fontSize: 15, fontWeight: 800, color: accent }}>{title} <span style={{ color: '#8b9691' }}>({items.length})</span></div>
        <div style={{ fontSize: 12, color: '#8b9691', marginTop: 2, maxWidth: 820 }}>{note}</div>
      </div>
      {items.length === 0
        ? <div style={{ padding: 16, fontSize: 12, color: '#22c55e' }}>✓ vazio</div>
        : items.map((r, i) => <Row key={`${r.ssid}-${i}`} r={r} onZoom={onZoom} accent={accent} />)}
    </div>
  )
}

export default function LatePrintsPage() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [zoom, setZoom] = useState(null)
  useEffect(() => { ggHealth.latePrints().then(setData).catch(e => setErr(e.message)) }, [])
  return (
    <div style={{ padding: 4 }}>
      <h2 style={{ fontSize: 18, margin: '0 0 4px' }}>Prints fora de tempo — a mão não deu tempo</h2>
      <p style={{ fontSize: 12, color: '#8b9691', marginTop: 0, maxWidth: 900 }}>
        Capturas casadas a mãos que <b>tiveram flop</b>, mas tiradas <b>&lt; 20 s</b> do início da mão —
        cedo demais para ver o spot pós-flop, decidir e tirar o print. Provável print da mão <b>anterior</b>,
        casado à mão errada. Ordenado por intervalo. Só para ver.
      </p>
      <div style={{ fontSize: 12, color: '#f59e0b', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 6, padding: '8px 12px', margin: '8px 0 16px', maxWidth: 900 }}>
        ⚠️ A <b>mão anterior na mesma mesa</b> é uma <b>heurística de dona — candidata, não dona provada</b>.
        A dona real pode estar <b>várias mãos atrás</b> (o Rui re-taga tarde por não ter a certeza se já tinha tagado).
        Não é resposta; é pista. Só a imagem arbitra.
      </div>
      {err && <div style={{ color: '#ef4444', fontSize: 13 }}>Erro: {err}</div>}
      {!data && !err && <div style={{ color: '#64748b', fontSize: 13 }}>A carregar…</div>}
      {data && (<>
        <Section title="Impossíveis (< 10 s)" accent="#ef4444"
          note="Nos primeiros 10 segundos a mão nem chegou ao flop — mal se distribuíram as cartas e correu o pré-flop. Um print de spot pós-flop neste intervalo é fisicamente impossível. Sem dúvida."
          items={data.impossible || []} onZoom={setZoom} />
        <Section title="Suspeitos (10-20 s)" accent="#eab308"
          note="A mão teve flop, mas o print saiu cedo demais para ter visto o spot. Provável, não certo — pode ser reação rápida."
          items={data.suspect || []} onZoom={setZoom} />
      </>)}
      {zoom && (
        <div onClick={() => setZoom(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.92)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000, cursor: 'zoom-out' }}>
          <img src={zoom} alt="" style={{ maxWidth: '95vw', maxHeight: '95vh', borderRadius: 8 }} />
        </div>
      )}
    </div>
  )
}
