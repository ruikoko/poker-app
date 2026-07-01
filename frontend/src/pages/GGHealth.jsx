import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ggHealth } from '../api/client'

// "Saúde das mãos GG" — Fase 1 (só mostrar). Dashboard de números + listas por
// imagem. Só GG. Lê, não escreve. Absorve (Fase 2) a "Marcadas por captura".

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

const card = { background: 'var(--card,#161b22)', border: '1px solid var(--border,#30363d)', borderRadius: 8 }

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

function Row({ im }) {
  const body = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 10px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
      <img src={im.image_url} alt="" loading="lazy" style={{ width: 96, height: 60, objectFit: 'cover', borderRadius: 4, border: '1px solid #2a2d3a', flexShrink: 0, background: '#0b0d13' }} />
      <TipoBadge source={im.source} />
      <span style={{ fontFamily: "'Fira Code',monospace", fontSize: 12, color: '#94a3b8', minWidth: 96 }}>{im.filename_num || '—'}</span>
      <span style={{ fontFamily: "'Fira Code',monospace", fontSize: 12, color: im.hand_id ? '#60a5fa' : '#64748b', minWidth: 130 }}>{im.hand_id || 'sem mão'}</span>
      <NumBadge im={im} />
      <span style={{ display: 'flex', gap: 4, flexWrap: 'wrap', flex: 1 }}>
        {(im.tags || []).map((t, i) => <span key={i} style={{ fontSize: 10, color: '#a5b4fc', background: 'rgba(99,102,241,0.12)', padding: '1px 6px', borderRadius: 4 }}>{t}</span>)}
        {(im.conflicts || []).map((c, i) => <span key={'c' + i} style={{ fontSize: 10, fontWeight: 700, color: '#fff', background: '#ef4444', padding: '1px 6px', borderRadius: 4 }}>conflito {c}</span>)}
      </span>
      <span style={{ fontSize: 11, color: im.state === 'órfã' ? '#f59e0b' : '#64748b', minWidth: 50, textAlign: 'right' }}>{im.state}</span>
    </div>
  )
  return im.hand_db_id
    ? <Link to={`/hand/${im.hand_db_id}`} style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>{body}</Link>
    : <div style={{ opacity: 0.85 }}>{body}</div>
}

export default function GGHealth() {
  const [sum, setSum] = useState(null)
  const [err, setErr] = useState(null)
  const [group, setGroup] = useState(null)
  const [list, setList] = useState(null)
  const [page, setPage] = useState(1)

  useEffect(() => { ggHealth.summary().then(setSum).catch(e => setErr(e.message)) }, [])
  useEffect(() => {
    if (!group) { setList(null); return }
    setList(null)
    ggHealth.list(group, page).then(setList).catch(e => setErr(e.message))
  }, [group, page])

  const open = (k) => { setGroup(k); setPage(1) }

  return (
    <div style={{ padding: 24, maxWidth: 1150 }}>
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
          <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 20, maxWidth: 720 }}>
            Vista por IMAGEM (uma mão pode ter Gold + IT = 2 imagens). "Suspeitas de troca" é o sinal
            BRUTO nº≠mão (só IT) — badge amarelo, <b>não veredicto</b> (por fit só ~72 são reais). Clica num painel para ver a lista.
          </p>
        </>
      )}

      {group && (
        <div style={{ marginTop: 16 }}>
          <button onClick={() => setGroup(null)} style={{ background: 'none', border: 'none', color: '#818cf8', cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>&larr; Dashboard</button>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, margin: '6px 0 12px' }}>
            <h2 style={{ fontSize: 16, margin: 0 }}>{LABELS[group]}</h2>
            {list && <span style={{ fontSize: 13, color: 'var(--muted)' }}>{list.total} imagens</span>}
          </div>
          {!list ? <div style={{ color: 'var(--muted)' }}>A carregar…</div> : (
            <>
              <div style={{ ...card, overflow: 'hidden' }}>
                {list.images.map((im, i) => <Row key={i} im={im} />)}
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
    </div>
  )
}
