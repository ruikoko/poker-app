import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { hrcResults } from '../api/client'

// Página da mão (Wizard) — Resultados HRC Fase 2 (primeira versão).
// Barra de posições/stacks · navegação da árvore · grelha 13×13 (paleta do Rui) ·
// cartões de ação (%/combos/EV) · abre neutra · EV real vs HRC.

const C = {
  bg: '#0f1216', card: '#171b21', border: 'rgba(255,255,255,0.09)',
  text: '#e6e9ee', muted: '#8a93a0', yellow: '#f2c14e',
}
// paleta do Rui por tipo de ação
const KIND = {
  fold:  { c: '#4e79c1', label: 'Fold' },   // azul
  call:  { c: '#4ea86b', label: 'Call' },   // verde
  check: { c: '#4ea86b', label: 'Check' },  // verde
  raise: { c: '#f2c14e', label: 'Open' },   // amarelo
  '3bet':{ c: '#d05a5a', label: '3-Bet' },  // vermelho
  allin: { c: '#e8873a', label: 'All-in' }, // laranja
  other: { c: '#555b66', label: '—' },
}
const RANKS = 'AKQJT98765432'.split('')

function classKey(i, j) {
  if (i === j) return RANKS[i] + RANKS[i]
  return i < j ? RANKS[i] + RANKS[j] + 's' : RANKS[j] + RANKS[i] + 'o'
}

export default function HRCHandPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [path, setPath] = useState([])          // pilha de nós (navegação)
  const [node, setNode] = useState(null)        // detalhe do nó atual
  const [loadingNode, setLoadingNode] = useState(false)

  useEffect(() => {
    hrcResults.hand(id)
      .then(d => { setData(d); setPath([d.tree.root]) })   // abre no nó-raiz (neutra)
      .catch(e => setErr(e.message))
  }, [id])

  const cur = path.length ? path[path.length - 1] : null
  useEffect(() => {
    if (cur == null) return
    setLoadingNode(true)
    hrcResults.handNode(id, cur)
      .then(setNode).catch(() => setNode(null)).finally(() => setLoadingNode(false))
  }, [id, cur])

  if (err) return <div style={{ padding: 24, color: '#d05a5a' }}>Erro: {err}</div>
  if (!data) return <div style={{ padding: 24, color: C.muted }}>A carregar…</div>

  const tree = data.tree
  const nodeMeta = (tree.nodes || []).find(n => n.idx === cur)
  const ev = data.ev_loss
  const heroNode = ev && ev.ok ? ev.node_idx : null

  return (
    <div style={{ padding: '18px 22px', color: C.text, maxWidth: 1200, margin: '0 auto' }}>
      {/* topo */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
        <button onClick={() => navigate('/hrc-results')} style={{ background: 'transparent',
          border: `1px solid ${C.border}`, color: C.muted, borderRadius: 6, padding: '4px 10px',
          cursor: 'pointer', fontSize: 13 }}>← Resultados</button>
        <h1 style={{ fontSize: 19, fontWeight: 800, margin: 0 }}>{data.tournament}</h1>
        <span style={{ color: C.muted, fontSize: 13 }}>{data.format} · {data.hand_id}</span>
      </div>

      {/* EV real vs HRC (discreto) */}
      {ev && ev.ok && (
        <div style={{ marginTop: 10, fontSize: 13, color: C.muted }}>
          Jogada do Hero (<b style={{ color: C.yellow }}>{ev.hero_pos} {ev.hero_class}</b>):{' '}
          <b>{ev.real_label}</b> · HRC prefere <b>{ev.best_label}</b> ·{' '}
          EV perdido <b style={{ color: ev.loss_eq_pct > 0 ? '#d05a5a' : C.muted }}>
            −{(ev.loss_eq_pct ?? 0).toFixed(ev.loss_eq_pct >= 0.1 ? 2 : 4)}%</b> equity ICM
          {heroNode != null && cur !== heroNode &&
            <button onClick={() => setPath([heroNode])} style={{ marginLeft: 10, background: 'transparent',
              border: `1px solid ${C.border}`, color: C.yellow, borderRadius: 5, padding: '2px 8px',
              cursor: 'pointer', fontSize: 12 }}>ir ao spot do Hero</button>}
        </div>
      )}

      {/* barra de posições / stacks */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '14px 0 6px' }}>
        {(tree.positions || []).map(p => {
          const isActor = nodeMeta && nodeMeta.actor === p.pos
          const isHero = p.idx === tree.hero_idx
          return (
            <div key={p.idx} style={{ padding: '6px 12px', borderRadius: 8,
              border: `1px solid ${isActor ? C.yellow : C.border}`,
              background: isActor ? 'rgba(242,193,78,0.10)' : C.card, minWidth: 70, textAlign: 'center' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: isHero ? C.yellow : C.text }}>
                {p.pos}{isHero ? ' ★' : ''}
              </div>
              <div style={{ fontSize: 12, color: C.muted }}>{p.stack_bb}bb</div>
            </div>
          )
        })}
      </div>

      {/* breadcrumb / voltar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '10px 0' }}>
        <button disabled={path.length <= 1} onClick={() => setPath(path.slice(0, -1))}
          style={{ background: 'transparent', border: `1px solid ${C.border}`,
            color: path.length <= 1 ? '#3a3f47' : C.text, borderRadius: 6, padding: '3px 10px',
            cursor: path.length <= 1 ? 'default' : 'pointer', fontSize: 13 }}>← Voltar</button>
        <span style={{ fontSize: 13, color: C.muted }}>
          {nodeMeta ? <>Vez de <b style={{ color: C.text }}>{nodeMeta.actor}</b>
            {' '}({node?.actor_stack_bb ?? nodeMeta.actor_stack_bb}bb) · face a{' '}
            <span style={{ fontFamily: 'monospace' }}>[{nodeMeta.facing}]</span></> : '—'}
        </span>
      </div>

      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
        {/* grelha 13×13 */}
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(13, 26px)', gap: 2 }}>
            {RANKS.map((_, i) => RANKS.map((__, j) => {
              const k = classKey(i, j)
              const cell = node?.grid?.[k]
              const col = cell ? KIND[cell.k]?.c : '#20242b'
              return (
                <div key={k} title={cell ? `${k}: ${KIND[cell.k]?.label} ${cell.pct}%` : k}
                  style={{ width: 26, height: 26, background: col, borderRadius: 3,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 8.5, color: cell ? '#0b0d10' : '#4a4f57', fontWeight: 700 }}>
                  {k.replace('s', '').replace('o', '')}
                </div>
              )
            }))}
          </div>
          {loadingNode && <div style={{ fontSize: 12, color: C.muted, marginTop: 6 }}>a carregar nó…</div>}
        </div>

        {/* cartões de ação */}
        <div style={{ flex: 1, minWidth: 240 }}>
          <div style={{ fontSize: 12, color: C.muted, textTransform: 'uppercase',
            fontWeight: 700, marginBottom: 8 }}>Resposta do HRC neste nó</div>
          {(node?.actions || []).map((a, i) => {
            const meta = KIND[a.kind] || KIND.other
            const clickable = a.child != null
            return (
              <div key={i} onClick={() => clickable && setPath([...path, a.child])}
                style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px',
                  marginBottom: 6, borderRadius: 8, background: C.card,
                  borderLeft: `4px solid ${meta.c}`, border: `1px solid ${C.border}`,
                  cursor: clickable ? 'pointer' : 'default' }}
                onMouseEnter={e => { if (clickable) e.currentTarget.style.background = 'rgba(255,255,255,0.05)' }}
                onMouseLeave={e => e.currentTarget.style.background = C.card}>
                <span style={{ width: 74, fontWeight: 700, color: meta.c }}>{meta.label}</span>
                <span style={{ flex: 1, fontSize: 13 }}>{a.label}</span>
                <span style={{ fontWeight: 800, fontSize: 15 }}>{a.pct}%</span>
                <span style={{ width: 66, textAlign: 'right', fontSize: 11, color: C.muted }}>
                  {a.combos} combos
                </span>
                {clickable && <span style={{ color: C.muted, fontSize: 14 }}>›</span>}
              </div>
            )
          })}
          {!node && !loadingNode && <div style={{ color: C.muted, fontSize: 13 }}>—</div>}
        </div>
      </div>
    </div>
  )
}
