import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ggHealth, absImageUrl } from '../api/client'

// Painel "Imagens sem tag — Gold e capturas" (read-only). Duas populações DISJUNTAS
// (A ∩ B = 0): Gold sem tag (315) · Capturas sem tag (314). Cada linha expande para a
// imagem (clique amplia). A etiqueta "vizinha" = mão tagada mais perto no tempo do mesmo
// torneio (≤3 min) — hipótese do print atrasado, é DADO, não conclusão. Só para ver.

const mono = "'Fira Code',monospace"
const fmtDate = (iso) => (iso ? String(iso).slice(0, 10) : '—')
const fmtTime = (iso) => (iso ? String(iso).slice(11, 16) : '—')

function Neighbor({ nt }) {
  if (!nt) return <span style={{ fontSize: 10, color: '#4b5563' }}>—</span>
  return (
    <span title={`mão tagada do mesmo torneio a ${nt.diff_seconds}s ${nt.is_after ? 'depois' : 'antes'}`}
      style={{ fontSize: 10, fontWeight: 700, color: '#000', background: '#a78bfa', padding: '1px 6px', borderRadius: 5, whiteSpace: 'nowrap' }}>
      vizinha {(nt.tags || []).join(',') || '?'} · {nt.diff_seconds}s {nt.is_after ? '↓' : '↑'}
    </span>
  )
}

function Row({ it, onZoom }) {
  const [open, setOpen] = useState(false)
  const src = absImageUrl(it.image_url)
  return (
    <div style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
      <div onClick={() => setOpen(o => !o)} style={{ display: 'grid', gridTemplateColumns: '14px auto 1fr auto', gap: 6, alignItems: 'center', padding: '7px 8px', cursor: 'pointer' }}>
        <span style={{ color: '#8b9691' }}>{open ? '▾' : '▸'}</span>
        <Link to={`/hand/${it.hand_db_id}`} onClick={e => e.stopPropagation()} style={{ color: '#60a5fa', fontFamily: mono, fontSize: 12, fontWeight: 700, textDecoration: 'none' }}>{it.hand_id}</Link>
        <span style={{ fontSize: 12, color: '#c9d1d9', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{it.tournament_name || '—'}</span>
        <Neighbor nt={it.nearest_tagged} />
      </div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', padding: '0 8px 6px 28px', fontSize: 11, color: '#8b9691' }}>
        <span>{it.buy_in || '—'}</span>
        <span style={{ fontFamily: mono }}>{fmtDate(it.played_at)} {fmtTime(it.played_at)}</span>
        <span style={{ color: '#eab308' }}>Hero {it.hero_position || '—'}</span>
      </div>
      {open && (
        <div style={{ padding: '2px 8px 10px 28px' }}>
          <img src={src} alt="" loading="lazy" onClick={() => onZoom(src)}
            style={{ maxWidth: 360, width: '100%', borderRadius: 6, border: '1px solid #2a2d3a', cursor: 'zoom-in', background: '#0b0d13', display: 'block' }} />
          {it.nearest_tagged && (
            <div style={{ fontSize: 11, color: '#a78bfa', marginTop: 6 }}>
              vizinha tagada:{' '}
              <Link to={`/hand/${it.nearest_tagged.hand_db_id}`} style={{ color: '#a78bfa', fontFamily: mono, fontWeight: 700 }}>{it.nearest_tagged.hand_id}</Link>
              {' · '}{(it.nearest_tagged.tags || []).join(', ')} · {it.nearest_tagged.diff_seconds}s {it.nearest_tagged.is_after ? 'depois' : 'antes'}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Column({ title, subtitle, items, onZoom }) {
  return (
    <div style={{ flex: 1, minWidth: 320, background: '#0f1117', borderRadius: 8, border: '1px solid #21262d' }}>
      <div style={{ padding: '10px 12px', borderBottom: '1px solid #21262d' }}>
        <div style={{ fontSize: 14, fontWeight: 800, color: '#c9d1d9' }}>{title} <span style={{ color: '#38bdf8' }}>({items.length})</span></div>
        <div style={{ fontSize: 11, color: '#8b9691', marginTop: 2 }}>{subtitle}</div>
      </div>
      <div>
        {items.length === 0
          ? <div style={{ padding: 16, fontSize: 12, color: '#22c55e' }}>✓ vazio</div>
          : items.map((it, i) => <Row key={`${it.hand_id}-${i}`} it={it} onZoom={onZoom} />)}
      </div>
    </div>
  )
}

export default function UntaggedImagesPage() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [zoom, setZoom] = useState(null)
  useEffect(() => { ggHealth.untaggedImages().then(setData).catch(e => setErr(e.message)) }, [])
  return (
    <div style={{ padding: 4 }}>
      <h2 style={{ fontSize: 18, margin: '0 0 4px' }}>Imagens sem tag — Gold e capturas</h2>
      <p style={{ fontSize: 12, color: '#8b9691', marginTop: 0, maxWidth: 860 }}>
        Todas as imagens na app <b>sem tag nenhuma</b>. Duas populações <b>disjuntas</b> (nada em
        comum). Cada linha expande para a imagem (clica para ampliar). A etiqueta
        <b style={{ color: '#a78bfa' }}> vizinha</b> mostra a mão tagada mais perto no tempo do mesmo
        torneio (≤ 3 min) — <i>hipótese do print atrasado; é dado, não conclusão</i>. Só para ver.
      </p>
      {err && <div style={{ color: '#ef4444', fontSize: 13 }}>Erro: {err}</div>}
      {!data && !err && <div style={{ color: '#64748b', fontSize: 13 }}>A carregar…</div>}
      {data && (
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <Column title="Gold sem tag" subtitle="Gold casada a uma mão que não tem tag de estudo."
            items={data.gold || []} onZoom={setZoom} />
          <Column title="Capturas sem tag" subtitle="Mão desanon pela captura (table-SS), por triar, sem tag."
            items={data.captures || []} onZoom={setZoom} />
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
