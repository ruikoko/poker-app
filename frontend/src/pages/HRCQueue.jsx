import { Fragment, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { API_ROOT, hands as handsApi, hrc, queue } from '../api/client'

// Cores por cenário do aggressor (espelha build_queue_zip / classify_aggressor_source).
const SRC_COLOR = {
  real: '#22c55e',
  fallback_root: '#eab308',
  fallback_unusable_position: '#f97316',
}

// Estilos partilhados da barra de filtros.
const SEL_STYLE = { background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: 4, padding: '3px 6px', fontSize: 12 }
const SEL_LABEL = { display: 'inline-flex', alignItems: 'center', gap: 6 }
// Badge "sem dado" (reutilizável nas células da tabela).
const SD = <span style={{ fontSize: 10, color: 'var(--muted)', opacity: 0.55, fontStyle: 'italic' }}>sem dado</span>
// Normaliza labels de posição para o vocabulário do Rui (#POSITION-LABELS-PYTHON-JS-DRIFT):
// BTN / BU/SB → BU; EP / EP1 / EP2 → UTG1; resto inalterado (UTG/UTG1/MP/HJ/CO/BU/SB/BB).
const normPos = p => {
  if (!p) return p
  const u = String(p).toUpperCase()
  if (u === 'BTN' || u === 'BU/SB') return 'BU'
  if (u === 'EP' || u === 'EP1' || u === 'EP2') return 'UTG1'
  return p
}

function fmtTs(iso) {
  if (!iso) return '—'
  // ISO UTC → "YYYY-MM-DD HH:MM" (UTC, consistente com played_at na BD)
  return iso.replace('T', ' ').slice(0, 16)
}

// pt83 — "enviada há Xh" a partir do released_at (TIMESTAMPTZ).
function fmtAge(iso) {
  if (!iso) return ''
  const ms = Date.now() - Date.parse(iso)
  if (isNaN(ms) || ms < 0) return ''
  const h = Math.floor(ms / 3.6e6)
  if (h < 1) return `há ${Math.max(1, Math.floor(ms / 6e4))}m`
  if (h < 48) return `há ${h}h`
  return `há ${Math.floor(h / 24)}d`
}

// pt83 — estado das Enviadas: cor + rótulo.
const SENT_STATE = {
  resolvida:    { c: '#22c55e', label: 'resolvida' },
  por_resolver: { c: '#eab308', label: 'por resolver' },
  cancelada:    { c: '#ef4444', label: 'cancelada' },
}

function Chip({ children, color }) {
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, color: color || 'var(--muted)',
      background: `${color || '#64748b'}1f`, padding: '2px 7px', borderRadius: 4,
      whiteSpace: 'nowrap',
    }}>{children}</span>
  )
}

// pt85 (#HRC-VERIFY) — veredicto da verificação C1-C5 HH-vs-HRC.
const VERIFY_VERDICT = {
  ok:   { c: '#22c55e', icon: '✓', label: 'OK' },
  warn: { c: '#eab308', icon: '⚠', label: 'aviso' },
  fail: { c: '#ef4444', icon: '✗', label: 'falha' },
}
// Rótulos PT dos checks (a chave vem do hrc_verify.py).
const CHECK_LABEL = {
  C1_players: 'C1 — nº de jogadores',
  C2_stacks:  'C2 — stacks',
  C3_blinds:  'C3 — blinds + ante',
  C4_equity:  'C4 — equity model',
  C5_bounty:  'C5 — bounty (PKO)',
  zip:        'zip — result_zip',
}
const CHECK_STATUS = {
  ok:   { c: '#22c55e', icon: '✓' },
  warn: { c: '#eab308', icon: '⚠' },
  fail: { c: '#ef4444', icon: '✗' },
}

// Badge clicável ✓/⚠/✗ por linha das Enviadas (alimentado pelo verify batch).
function VerifyBadge({ verdict, open, onClick }) {
  if (!verdict) return <span style={{ color: 'var(--muted)', opacity: 0.5 }}>—</span>
  const m = VERIFY_VERDICT[verdict] || { c: '#94a3b8', icon: '?', label: verdict }
  return (
    <button
      onClick={onClick}
      title={`Verificação HH↔HRC: ${m.label} — clica para ${open ? 'fechar' : 'conferir'}`}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4, cursor: 'pointer',
        fontSize: 12, fontWeight: 700, color: m.c, background: `${m.c}1f`,
        border: `1px solid ${m.c}55`, borderRadius: 4, padding: '2px 8px',
      }}
    >{m.icon} {open ? '▾' : '▸'}</button>
  )
}

// Cor por tipo de acção na vista da árvore HRC.
function actionColor(label) {
  if (label.startsWith('FOLD')) return '#ef4444'
  if (label.startsWith('CALL') || label.startsWith('CHECK')) return '#3b82f6'
  return '#22c55e'   // R … (raise/all-in)
}

// pt86 v2 (#HRC-VERIFY) — nó navegável da árvore HRC. Mostra TODAS as opções da
// posição (fold/call/raises com tamanho + frequência em barras); clicar numa
// opção com filho abre o nó seguinte (próxima posição a responder), recursivo
// até ao fim do preflop. `byIdx`: map idx→nó; `expanded`: Set de idxs abertos.
function HrcTreeNode({ idx, byIdx, expanded, toggle, depth = 0 }) {
  const nd = byIdx[idx]
  if (!nd) return null
  return (
    <div style={{
      marginLeft: depth ? 10 : 0, paddingLeft: depth ? 8 : 0,
      borderLeft: depth ? '1px solid rgba(129,140,248,0.25)' : 'none',
    }}>
      <div style={{ fontWeight: 700, color: nd.is_central ? '#a5b4fc' : 'var(--text)', marginTop: depth ? 2 : 0 }}>
        n{idx} {nd.actor}({nd.actor_stack_bb}bb)
        {nd.is_central && <span style={{ color: '#818cf8', fontWeight: 700 }}> ◄ âncora</span>}
      </div>
      {nd.actions.map((a, i) => {
        const hasChild = a.child != null
        const isOpen = hasChild && expanded.has(a.child)
        return (
          <div key={i}>
            <div
              onClick={hasChild ? () => toggle(a.child) : undefined}
              title={hasChild ? (isOpen ? 'fechar' : 'abrir a resposta seguinte') : undefined}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 4,
                cursor: hasChild ? 'pointer' : 'default',
                userSelect: 'none', borderRadius: 3,
                background: isOpen ? 'rgba(129,140,248,0.10)' : 'transparent',
              }}
            >
              <span style={{ width: 12, color: '#818cf8', textAlign: 'center' }}>
                {hasChild ? (isOpen ? '▾' : '▸') : ''}
              </span>
              <span style={{ color: actionColor(a.label), minWidth: 120 }}>{a.label}</span>
              <span style={{ minWidth: 44, textAlign: 'right', color: 'var(--text)' }}>{a.pct.toFixed(1)}%</span>
              <span style={{ flex: 1, height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden', maxWidth: 90 }}>
                <span style={{ display: 'block', height: '100%', width: `${Math.min(100, a.pct)}%`, background: actionColor(a.label) }} />
              </span>
            </div>
            {isOpen && (
              <HrcTreeNode idx={a.child} byIdx={byIdx} expanded={expanded} toggle={toggle} depth={depth + 1} />
            )}
          </div>
        )
      })}
    </div>
  )
}

// pt86 (#HRC-VERIFY) — bloco "HH ↔ HRC produziu". Esquerda: HH crua (intocada).
// Direita (pt86 v2): ÁRVORE NAVEGÁVEL — arranca no nó-âncora (Selected Subtree)
// e desce por qualquer ramo do subtree preflop. Sem veredicto — o Rui julga à vista.
function HrcTreeView({ tree }) {
  const [expanded, setExpanded] = useState(() => new Set())
  if (!tree) return null
  if (tree.error) {
    return (
      <div style={{ marginTop: 14, fontSize: 12, color: 'var(--muted)' }}>HRC: {tree.error}</div>
    )
  }
  const nodes = tree.nodes || []
  const byIdx = Object.fromEntries(nodes.map(n => [n.idx, n]))
  const root = tree.root
  const toggle = (childIdx) => setExpanded(s => {
    const n = new Set(s)
    n.has(childIdx) ? n.delete(childIdx) : n.add(childIdx)
    return n
  })
  return (
    <div style={{ marginTop: 16, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.4 }}>
        HH ↔ HRC produziu
        <span style={{ fontWeight: 400, textTransform: 'none', marginLeft: 8 }}>
          árvore {tree.n_nodes_total} nós{tree.tree_complete ? ' (completa)' : ''} · subárvore {tree.subtree_size} nós (só preflop) · âncora n{root}
          {tree.truncated ? ' · ⚠ truncada' : ''}
          {tree.positions?.length ? ` · ${tree.positions.map(p => `${p.pos}(${p.stack_bb}bb)`).join(' ')}` : ''}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        {/* Esquerda — a mão real (HH crua, preflop) — INTOCADA */}
        <div style={{ flex: '1 1 320px', minWidth: 280 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginBottom: 4 }}>HH (a mão real)</div>
          <pre style={{
            margin: 0, padding: 10, background: 'var(--bg)', border: '1px solid var(--border)',
            borderRadius: 6, fontSize: 11, lineHeight: 1.5, maxHeight: 420, overflow: 'auto',
            whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          }}>{tree.hh_preflop || '—'}</pre>
        </div>
        {/* Direita — árvore navegável HRC (clica numa opção para descer) */}
        <div style={{ flex: '1 1 420px', minWidth: 320 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginBottom: 4 }}>
            HRC produziu — árvore navegável <span style={{ opacity: 0.7 }}>(clica numa opção ▸ para ver a resposta seguinte)</span>
          </div>
          <div style={{
            padding: 10, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6,
            fontSize: 11, maxHeight: 460, overflow: 'auto', fontFamily: 'monospace',
          }}>
            {root != null && byIdx[root]
              ? <HrcTreeNode idx={root} byIdx={byIdx} expanded={expanded} toggle={toggle} />
              : <span style={{ color: 'var(--muted)' }}>sem nós para mostrar.</span>}
          </div>
        </div>
      </div>
    </div>
  )
}

// Vista expandida de verificação de uma mão (Origem SS/HH + checks C1-C5).
// `res` = resultado do single verify. `handDbId` p/ link ao replayer.
function VerifyDetail({ res, handDbId }) {
  if (res === 'busy') return <div style={{ padding: 14, color: 'var(--muted)', fontSize: 12 }}>A verificar…</div>
  if (res === 'err' || !res) return <div style={{ padding: 14, color: '#ef4444', fontSize: 12 }}>Erro a carregar a verificação.</div>
  const v = VERIFY_VERDICT[res.verdict] || { c: '#94a3b8', label: res.verdict }
  // capture_url vem relativo (/api/...); prefixar API_ROOT p/ bater no BACKEND em
  // prod (frontend e backend são domínios distintos) — igual às imagens que já
  // funcionam (BASE = API_ROOT + /api). Em dev API_ROOT='' → Vite proxy.
  const captureSrc = res.capture_url ? `${API_ROOT}${res.capture_url}` : null
  return (
    <div style={{ padding: '14px 16px', background: 'rgba(255,255,255,0.02)' }}>
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
      {/* Origem — o que o Rui confere à vista (SS de mesa ou HH em texto) */}
      <div style={{ flex: '0 0 320px', minWidth: 260 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.4 }}>
          Origem {res.origin_kind === 'ss' ? '· SS de mesa' : '· HH (texto)'}
        </div>
        {res.origin_kind === 'ss' && captureSrc ? (
          <a href={captureSrc} target="_blank" rel="noreferrer" title="Abrir captura em tamanho real">
            <img src={captureSrc} alt="captura SS de mesa"
              style={{ maxWidth: '100%', borderRadius: 6, border: '1px solid var(--border)', display: 'block' }} />
          </a>
        ) : (
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>
            Sem captura guardada — a fonte de verdade é a HH em texto.{' '}
            {handDbId != null && <Link to={`/replayer/${handDbId}`} style={{ color: 'var(--accent2, #818cf8)' }}>abrir no replayer →</Link>}
          </div>
        )}
      </div>

      {/* Checks C1-C5 — cada detail cruza Origem (HH) ↔ App ↔ HRC */}
      <div style={{ flex: '1 1 420px', minWidth: 320 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.4 }}>
            Origem ↔ App ↔ HRC
          </span>
          <Chip color={v.c}>{v.label}</Chip>
          {res.scale != null && <span style={{ fontSize: 11, color: 'var(--muted)' }}>scale ×{Math.round(res.scale)}</span>}
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <tbody>
            {(res.checks || []).map(c => {
              const cs = CHECK_STATUS[c.status] || { c: '#94a3b8', icon: '?' }
              return (
                <tr key={c.check} style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                  <td style={{ padding: '6px 8px', whiteSpace: 'nowrap', fontWeight: 600 }}>
                    <span style={{ color: cs.c, marginRight: 6 }}>{cs.icon}</span>
                    {CHECK_LABEL[c.check] || c.check}
                  </td>
                  <td style={{ padding: '6px 8px', color: 'var(--muted)', fontFamily: 'monospace', fontSize: 11 }}>{c.detail}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {(res.notes || []).length > 0 && (
          <div style={{ marginTop: 8, fontSize: 11, color: 'var(--muted)' }}>
            Notas: {res.notes.join(' · ')}
          </div>
        )}
      </div>
      </div>
      <HrcTreeView tree={res.tree} />
    </div>
  )
}

export default function HRCQueuePage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [site, setSite] = useState('')
  const [format, setFormat] = useState('')   // bucket: '' | vanilla | pko | sd
  const [heroPos, setHeroPos] = useState('')
  const [vpipPos, setVpipPos] = useState('')
  const [totalSel, setTotalSel] = useState('')
  const [leftSel, setLeftSel] = useState('')
  const [fieldSel, setFieldSel] = useState('')
  const [speedSel, setSpeedSel] = useState('')
  const [speedRacer, setSpeedRacer] = useState(false)
  const [dl, setDl] = useState({})  // hand_id -> 'busy' | 'err'
  const [marks, setMarks] = useState({})    // id -> 'new'|'resolved' (override optimista)
  const [stBusy, setStBusy] = useState({})  // id -> 'busy'|'err'
  const [pending, setPending] = useState(null)   // pt41 — banner D1 (PKO sem TS)
  const [pendingOpen, setPendingOpen] = useState(false)
  const [gate, setGate] = useState(null)         // pt92 — contadores da fila (manual)
  const [gateBusy, setGateBusy] = useState(false)
  const [sent, setSent] = useState(null)         // pt83 — Enviadas (released + estado)
  const [sentMarks, setSentMarks] = useState({}) // hand_id -> 'por_resolver' (flip otimista)
  const [rqBusy, setRqBusy] = useState({})       // hand_id -> 'busy'|'err'
  // pt85 (#HRC-VERIFY) — badge por linha (batch) + expand de detalhe (single)
  const [verify, setVerify] = useState(null)     // { total, summary, byId: {hand_id->entry} }
  const [vOpen, setVOpen] = useState(null)        // hand_id da linha expandida (1 de cada vez)
  const [vDetail, setVDetail] = useState({})      // hand_id -> result single | 'busy' | 'err'
  // pt69 — seleção manual mão-a-mão → release(hand_ids). PERSISTE ao filtrar
  // (o filtro é a lente; o X é seleção durável). Guarda hand_id strings.
  const [selected, setSelected] = useState(() => new Set())
  const [showSelected, setShowSelected] = useState(false)  // "ver só marcadas"
  const [sendBusy, setSendBusy] = useState(false)
  const [sendResult, setSendResult] = useState(null)       // {released, skipped, ...} | {error}

  // pt92 — limpar/pausar a fila: des-liberta tudo. O adapter para de puxar até
  // nova seleção manual ('Enviar ao HRC'). Não há mais "Disparar tudo".
  async function doClearReleased() {
    if (!window.confirm('Limpar a fila? Tira TODAS as mãos libertadas — o adapter '
      + 'deixa de puxar até enviares mãos manualmente.')) return
    setGateBusy(true)
    try {
      await queue.clearReleased()
      setGate(await queue.gate())
    } catch (e) {
      console.error('clear-released falhou:', e)
      setError(String(e.message || e))
    } finally {
      setGateBusy(false)
    }
  }

  // Estado actual da mão: override optimista > o que veio do backend > 'new'
  // (o /eligible só devolve mãos study_state='new', mas o fallback é defensivo).
  function curState(h) { return marks[h.id] ?? h.study_state ?? 'new' }

  // Alterna Nova(new) <-> Revista(resolved) reutilizando o MESMO PATCH do Estudo
  // (handsApi.update -> PATCH /hands/{id}). Optimista: a linha fica visível até ao
  // próximo Refresh (aí, as Revista saem do basket 'new' do gate /hrc).
  async function toggleState(h) {
    const next = curState(h) === 'resolved' ? 'new' : 'resolved'
    setStBusy(s => ({ ...s, [h.id]: 'busy' }))
    try {
      await handsApi.update(h.id, { study_state: next })
      setMarks(m => ({ ...m, [h.id]: next }))
      setStBusy(s => { const n = { ...s }; delete n[h.id]; return n })
    } catch (e) {
      setStBusy(s => ({ ...s, [h.id]: 'err' }))
      console.error('study_state toggle falhou:', e)
    }
  }

  async function downloadPack(handId) {
    setDl(d => ({ ...d, [handId]: 'busy' }))
    try {
      await queue.hrcHandDownload(handId)
      setDl(d => { const n = { ...d }; delete n[handId]; return n })
    } catch (e) {
      setDl(d => ({ ...d, [handId]: 'err' }))
      console.error('HRC pack download falhou:', e)
    }
  }

  // pt83 — estado actual da Enviada: flip otimista (após re-queue) > backend
  function curSentState(s) { return sentMarks[s.hand_id] ?? s.state }

  async function doRequeue(handId) {
    setRqBusy(b => ({ ...b, [handId]: 'busy' }))
    try {
      const res = await queue.requeue([handId])
      if (res.requeued?.includes(handId)) {
        setSentMarks(m => ({ ...m, [handId]: 'por_resolver' }))   // flip otimista
        setRqBusy(b => { const n = { ...b }; delete n[handId]; return n })
      } else {
        setRqBusy(b => ({ ...b, [handId]: 'err' }))
        console.warn('requeue skipped:', res.skipped)
      }
    } catch (e) {
      setRqBusy(b => ({ ...b, [handId]: 'err' }))
      console.error('requeue falhou:', e)
    }
  }

  // pt85 — abre/fecha o detalhe de verificação de uma Enviada; fetch single lazy.
  async function toggleVerify(handId) {
    if (vOpen === handId) { setVOpen(null); return }
    setVOpen(handId)
    if (vDetail[handId] && vDetail[handId] !== 'err') return  // já carregado
    setVDetail(d => ({ ...d, [handId]: 'busy' }))
    try {
      const res = await queue.verifyHand(handId)
      setVDetail(d => ({ ...d, [handId]: res }))
    } catch (e) {
      setVDetail(d => ({ ...d, [handId]: 'err' }))
      console.error('verify single falhou:', e)
    }
  }

  async function refresh() {
    setLoading(true)
    setError(null)
    setMarks({}); setStBusy({}); setSentMarks({}); setRqBusy({})
    setVOpen(null); setVDetail({})
    try {
      const [out, pend, g, snt, ver] = await Promise.all([
        hrc.eligible(), hrc.pendingTs(),
        queue.gate().catch(() => null), queue.sent().catch(() => null),
        queue.verify().catch(() => null),
      ])
      setData(out)
      // Poda marcadas órfãs (mãos que saíram da elegibilidade — enviadas/resolvidas)
      // para o contador "N marcadas" ficar honesto. As ainda-elegíveis persistem.
      setSelected(s => new Set([...s].filter(id => (out.hands || []).some(h => h.hand_id === id))))
      setPending(pend)
      setGate(g)
      setSent(snt)
      setVerify(ver && {
        total: ver.total, summary: ver.summary || {},
        byId: Object.fromEntries((ver.hands || []).map(v => [v.hand_id, v])),
      })
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  const hands = data?.hands || []
  const sites = useMemo(() => [...new Set(hands.map(h => h.site))].sort(), [hands])
  // Opções de posição DINÂMICAS (do data): robusto à convenção de labels do
  // backend (#POSITION-LABELS-PYTHON-JS-DRIFT — pode trazer EP/BTN, não só
  // UTG1/BU). O dropdown adapta-se sempre ao que existe.
  const heroPositions = useMemo(() => [...new Set(hands.map(h => normPos(h.position_hero)).filter(Boolean))].sort(), [hands])
  const vpipPositions = useMemo(() => [...new Set(hands.map(h => normPos(h.first_vpip_position)).filter(Boolean))].sort(), [hands])

  // ── buckets / normalizers dos filtros de torneio ──
  const fmtBucket = f => {
    if (!f || f === 'None' || f === '?') return 'sd'
    const lf = String(f).toLowerCase()
    if (lf.includes('ko')) return 'pko'
    if (lf === 'vanilla') return 'vanilla'
    return 'sd'
  }
  const totalBucket = n => n == null ? 'sd' : n < 100 ? '<100' : n < 500 ? '100-500' : n < 1000 ? '500-1000' : '1000+'
  const leftBucket = n => n == null ? 'sd' : n <= 50 ? '1-50' : n <= 200 ? '51-200' : n <= 1000 ? '201-1000' : '1000+'
  // FT = restantes-no-torneio == sentados-à-mesa (só resta 1 mesa). Checa FT
  // PRIMEIRO; senão %; sem players_left (ou sem total p/ o %) → "sem dado".
  const fieldBucket = h => {
    const pl = h.players_left, tp = h.total_players, s = h.seats_occupied
    if (pl == null) return 'sd'
    if (s != null && pl === s) return 'FT'
    if (tp == null || tp <= 0) return 'sd'
    const pct = pl / tp * 100
    return pct <= 10 ? '<=10' : pct <= 25 ? '10-25' : pct <= 50 ? '25-50' : '>50'
  }
  const speedBucket = s => {
    if (!s) return 'sd'
    const ls = String(s).toLowerCase()
    if (ls.includes('hyper')) return 'hyper'
    if (ls.includes('turbo')) return 'turbo'
    if (ls.includes('normal')) return 'normal'
    return 'sd'
  }
  const isSpeedRacer = h => {
    const norm = t => String(t).toLowerCase().replace(/-/g, ' ').trim()
    const tags = [...(h.hm3_tags || []), ...(h.discord_tags || [])].map(norm)
    return tags.includes('speed racer') || tags.includes('speed racer ft')
  }

  // "sem dado" (sd) aparece por defeito: só restringe quando se escolhe um
  // valor concreto; escolher "sd" mostra SÓ as null.
  const filtered = useMemo(() => hands.filter(h =>
    (!site || h.site === site) &&
    (!heroPos || (heroPos === 'sd' ? !h.position_hero : normPos(h.position_hero) === heroPos)) &&
    (!vpipPos || (vpipPos === 'sd' ? !h.first_vpip_position : normPos(h.first_vpip_position) === vpipPos)) &&
    (!format || fmtBucket(h.tournament_format) === format) &&
    (!totalSel || totalBucket(h.total_players) === totalSel) &&
    (!leftSel || leftBucket(h.players_left) === leftSel) &&
    (!fieldSel || fieldBucket(h) === fieldSel) &&
    (!speedSel || speedBucket(h.tournament_speed) === speedSel) &&
    (!speedRacer || isSpeedRacer(h))
  ), [hands, site, heroPos, vpipPos, format, totalSel, leftSel, fieldSel, speedSel, speedRacer])

  const clearFilters = () => {
    setSite(''); setHeroPos(''); setVpipPos(''); setFormat('')
    setTotalSel(''); setLeftSel(''); setFieldSel(''); setSpeedSel(''); setSpeedRacer(false)
  }
  const activeFilters = [site, heroPos, vpipPos, format, totalSel, leftSel, fieldSel, speedSel]
    .filter(Boolean).length + (speedRacer ? 1 : 0)

  // ── Seleção manual (release por hand_id) ──────────────────────────────────
  // `visible` = o que a tabela mostra: lista filtrada, ou (em "ver marcadas") só
  // as marcadas, ignorando os filtros. A seleção NUNCA deriva de `filtered`.
  const visible = showSelected ? hands.filter(h => selected.has(h.hand_id)) : filtered
  const toggleSel = handId => setSelected(s => {
    const n = new Set(s); n.has(handId) ? n.delete(handId) : n.add(handId); return n
  })
  const selectAllVisible = () => setSelected(s => {
    const n = new Set(s); visible.forEach(h => n.add(h.hand_id)); return n   // UNIÃO, não substitui
  })
  const clearSelected = () => { setSelected(new Set()); setShowSelected(false) }
  const allVisibleSelected = visible.length > 0 && visible.every(h => selected.has(h.hand_id))
  async function sendSelected() {
    if (selected.size === 0) return
    setSendBusy(true); setSendResult(null)
    try {
      const res = await queue.release([...selected])
      setSendResult(res)
      const rel = new Set(res.released || [])
      setSelected(s => new Set([...s].filter(id => !rel.has(id))))  // tira as enviadas
      await refresh()
    } catch (e) {
      setSendResult({ error: String(e.message || e) })
    } finally { setSendBusy(false) }
  }

  const scen = data?.scenario_counts || {}
  const fmtCounts = data?.format_counts || {}

  return (
    <div style={{ padding: 24, maxWidth: 1180, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>HRC Queue</h1>
        <button
          onClick={refresh}
          disabled={loading}
          style={{
            padding: '6px 14px', fontSize: 12, fontWeight: 600, borderRadius: 6,
            background: 'var(--accent)', border: 'none', color: '#fff',
            cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.5 : 1,
          }}
        >{loading ? 'A carregar…' : '↻ Refresh'}</button>
      </div>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 14 }}>
        Espelha os gates de <code>/api/queue/hrc</code> — é o que o adapter puxaria agora.
        {data && (
          <> {' · '}janela {data.filters.played_after} → {data.filters.played_before}
          {' · '}study_state={data.filters.study_state.join(',')}
          {' · '}basket {data.filters.tags.join(', ')}</>
        )}
      </div>

      {error && (
        <div style={{ padding: 12, borderRadius: 8, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#ef4444', fontSize: 13, marginBottom: 14 }}>
          Erro: {error}
        </div>
      )}

      {/* pt92 — Fila 100% MANUAL: sem 'abrir/fechar' nem disparo em lote. Só
          'Enviar ao HRC' (seleção) liberta mãos; o adapter só puxa as libertadas. */}
      {gate && (
        <div style={{
          marginBottom: 14, padding: 14, borderRadius: 8,
          border: '1px solid rgba(148,163,184,0.35)', background: 'rgba(148,163,184,0.06)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#94a3b8' }}>
              📋 FILA MANUAL
            </span>
            <span style={{ fontSize: 12, color: 'var(--muted)' }}>
              {gate.released_pending} em curso · {gate.not_released} disponíveis · {gate.eligible_total} elegíveis · {gate.done_of_released} já feitas
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
            <button onClick={doClearReleased} disabled={gateBusy || gate.released_total === 0}
              style={{ padding: '6px 14px', fontSize: 12, fontWeight: 600, borderRadius: 6, background: 'transparent', border: '1px solid rgba(239,68,68,0.5)', color: '#ef4444', cursor: gateBusy ? 'wait' : 'pointer', opacity: (gateBusy || gate.released_total === 0) ? 0.5 : 1 }}>
              Limpar fila ({gate.released_total})
            </button>
          </div>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 8 }}>
            O adapter só recebe mãos que <b>selecionares e enviares</b> ("Enviar ao HRC" abaixo). "Limpar fila" des-liberta tudo (pausa). As <b>postas de lado</b> não aparecem aqui.
          </div>
        </div>
      )}

      {/* pt41 Banner D1 — mãos bounty-format escondidas por falta de TS */}
      {pending && pending.total_hands > 0 && (
        <div style={{ marginBottom: 14, borderRadius: 8, border: '1px solid rgba(234,179,8,0.4)', background: 'rgba(234,179,8,0.08)' }}>
          <button
            onClick={() => setPendingOpen(o => !o)}
            style={{ width: '100%', textAlign: 'left', cursor: 'pointer', background: 'transparent', border: 'none', color: '#eab308', fontSize: 13, fontWeight: 600, padding: '10px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
          >
            <span>⚠ {pending.total_hands} mãos escondidas do /hrc por falta de Tournament Summary ({pending.count} torneios)</span>
            <span>{pendingOpen ? '▾' : '▸'}</span>
          </button>
          {pendingOpen && (
            <div style={{ padding: '0 12px 10px', overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: 'var(--muted)' }}>
                    {['torneio', 'tn', 'fmt', 'mãos', 'motivo'].map(h => (
                      <th key={h} style={{ padding: '4px 8px', fontWeight: 600 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {pending.groups.map(g => (
                    <tr key={g.tournament_number} style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                      <td style={{ padding: '4px 8px', maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{g.tournament_name || '—'}</td>
                      <td style={{ padding: '4px 8px', fontFamily: 'monospace' }}>{g.tournament_number}</td>
                      <td style={{ padding: '4px 8px' }}>{g.tournament_format || '—'}</td>
                      <td style={{ padding: '4px 8px' }}>{g.n_hands}</td>
                      <td style={{ padding: '4px 8px' }}>
                        <Chip color={g.reason === 'needs_ts_import' ? '#eab308' : '#f97316'}>
                          {g.reason === 'needs_ts_import' ? 'importar TS' : 'Mystery (não suportado)'}
                        </Chip>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {data && !error && (
        <>
          {/* Summary */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14 }}>
            <span style={{ fontSize: 15, fontWeight: 700 }}>{data.count} mãos elegíveis</span>
            <span style={{ color: 'var(--border)' }}>|</span>
            <Chip color={SRC_COLOR.real}>real {scen.real || 0}</Chip>
            <Chip color={SRC_COLOR.fallback_root}>fallback_root {scen.fallback_root || 0}</Chip>
            <Chip color={SRC_COLOR.fallback_unusable_position}>fallback_unusable {scen.fallback_unusable_position || 0}</Chip>
            <span style={{ color: 'var(--border)' }}>|</span>
            {Object.entries(fmtCounts).map(([k, v]) => <Chip key={k}>{k} {v}</Chip>)}
          </div>

          {/* Filtros client-side — 8 filtros combináveis (AND); "sem dado" aparece por defeito */}
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12, fontSize: 12, color: 'var(--muted)',
            padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 8 }}>
            <label style={SEL_LABEL}>Site:
              <select value={site} onChange={e => setSite(e.target.value)} style={SEL_STYLE}>
                <option value="">Todos</option>
                {sites.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label style={SEL_LABEL}>Hero pos:
              <select value={heroPos} onChange={e => setHeroPos(e.target.value)} style={SEL_STYLE}>
                <option value="">Todas</option>
                {heroPositions.map(p => <option key={p} value={p}>{p}</option>)}
                <option value="sd">— sem dado —</option>
              </select>
            </label>
            <label style={SEL_LABEL}>1º VPIP:
              <select value={vpipPos} onChange={e => setVpipPos(e.target.value)} style={SEL_STYLE}>
                <option value="">Todas</option>
                {vpipPositions.map(p => <option key={p} value={p}>{p}</option>)}
                <option value="sd">— sem dado —</option>
              </select>
            </label>
            <label style={SEL_LABEL}>Formato:
              <select value={format} onChange={e => setFormat(e.target.value)} style={SEL_STYLE}>
                <option value="">Todos</option>
                <option value="vanilla">Vanilla</option>
                <option value="pko">PKO/KO</option>
                <option value="sd">— sem dado —</option>
              </select>
            </label>
            <label style={SEL_LABEL}>Speed:
              <select value={speedSel} onChange={e => setSpeedSel(e.target.value)} style={SEL_STYLE}>
                <option value="">Todos</option>
                <option value="hyper">Hyper</option>
                <option value="turbo">Turbo</option>
                <option value="normal">Normal</option>
                <option value="sd">— sem dado —</option>
              </select>
            </label>
            <label style={SEL_LABEL}>Total jog.:
              <select value={totalSel} onChange={e => setTotalSel(e.target.value)} style={SEL_STYLE}>
                <option value="">Todos</option>
                <option value="<100">&lt;100</option>
                <option value="100-500">100–500</option>
                <option value="500-1000">500–1.000</option>
                <option value="1000+">1.000+</option>
                <option value="sd">— sem dado —</option>
              </select>
            </label>
            <label style={SEL_LABEL}>Restantes:
              <select value={leftSel} onChange={e => setLeftSel(e.target.value)} style={SEL_STYLE}>
                <option value="">Todos</option>
                <option value="1-50">1–50</option>
                <option value="51-200">51–200</option>
                <option value="201-1000">201–1.000</option>
                <option value="1000+">1.000+</option>
                <option value="sd">— sem dado —</option>
              </select>
            </label>
            <label style={SEL_LABEL}>% field:
              <select value={fieldSel} onChange={e => setFieldSel(e.target.value)} style={SEL_STYLE}>
                <option value="">Todos</option>
                <option value="FT">FT (mesa final)</option>
                <option value="<=10">≤10%</option>
                <option value="10-25">10–25%</option>
                <option value="25-50">25–50%</option>
                <option value=">50">&gt;50%</option>
                <option value="sd">— sem dado —</option>
              </select>
            </label>
            <label style={{ ...SEL_LABEL, cursor: 'pointer' }}>
              <input type="checkbox" checked={speedRacer} onChange={e => setSpeedRacer(e.target.checked)} />
              Só Speed Racer
            </label>
            <span style={{ opacity: 0.7, fontWeight: 600 }}>{filtered.length} de {hands.length}</span>
            {activeFilters > 0 && (
              <button onClick={clearFilters}
                style={{ ...SEL_STYLE, cursor: 'pointer', color: 'var(--accent)', fontWeight: 600 }}>
                limpar ({activeFilters})
              </button>
            )}
          </div>

          {/* Seleção manual → Enviar ao HRC (release por hand_id). Filtrar NUNCA envia. */}
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12,
            padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 8, background: 'rgba(59,130,246,0.05)' }}>
            <button onClick={selectAllVisible} style={{ ...SEL_STYLE, cursor: 'pointer' }}>
              Selecionar todas (visíveis: {visible.length})
            </button>
            <span style={{ fontWeight: 700, color: selected.size ? 'var(--accent)' : 'var(--muted)' }}>{selected.size} marcadas</span>
            {selected.size > 0 && (
              <>
                <label style={{ ...SEL_LABEL, cursor: 'pointer' }}>
                  <input type="checkbox" checked={showSelected} onChange={e => setShowSelected(e.target.checked)} />
                  ver só marcadas
                </label>
                <button onClick={clearSelected} style={{ ...SEL_STYLE, cursor: 'pointer' }}>limpar marcadas</button>
              </>
            )}
            <span style={{ flex: 1 }} />
            <button onClick={sendSelected} disabled={sendBusy || selected.size === 0}
              style={{ padding: '6px 16px', fontSize: 12, fontWeight: 700, borderRadius: 6, background: 'var(--accent)', border: 'none', color: '#fff',
                cursor: (sendBusy || selected.size === 0) ? 'not-allowed' : 'pointer', opacity: (sendBusy || selected.size === 0) ? 0.5 : 1 }}>
              {sendBusy ? 'A enviar…' : `Enviar marcadas (${selected.size})`}
            </button>
          </div>
          {sendResult && (
            <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 8, fontSize: 12, border: '1px solid var(--border)', background: 'var(--bg)' }}>
              {sendResult.error ? <span style={{ color: '#ef4444' }}>Erro: {sendResult.error}</span> : (
                <>
                  <span style={{ color: '#22c55e', fontWeight: 600 }}>✓ {(sendResult.released || []).length} enviadas ao HRC</span>
                  {(sendResult.missing_payouts || []).length > 0 && (
                    <span style={{ color: '#f97316', marginLeft: 12 }}>{sendResult.missing_payouts.length}× sem payout — não pode ir ao HRC (torneio sem estrutura de prémios)</span>
                  )}
                  {(sendResult.skipped || []).length > 0 && (
                    <span style={{ color: '#f59e0b', marginLeft: 12 }}>⚠ {sendResult.skipped.length} ignoradas</span>
                  )}
                  {(sendResult.skipped || []).length > 0 && (
                    <div style={{ marginTop: 6, color: 'var(--muted)' }}>
                      {sendResult.skipped.map(s => `${s.hand_id}: ${s.reason}`).join(' · ')}
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Tabela */}
          {visible.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
              {showSelected ? '0 mãos marcadas.' : (hands.length === 0 ? '0 mãos elegíveis agora.' : 'Nenhuma mão corresponde aos filtros.')}
            </div>
          ) : (
            <div style={{ overflowX: 'auto', border: '1px solid var(--border)', borderRadius: 8 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: 'var(--muted)', background: 'var(--bg)' }}>
                    <th style={{ padding: '8px 10px', borderBottom: '1px solid var(--border)', width: 30 }}>
                      <input type="checkbox" title="Marcar/desmarcar visíveis" checked={allVisibleSelected}
                        onChange={e => setSelected(s => {
                          const n = new Set(s)
                          visible.forEach(h => e.target.checked ? n.add(h.hand_id) : n.delete(h.hand_id))
                          return n
                        })} />
                    </th>
                    {['hand_id', 'played_at (UTC)', 'site', 'torneio', 'fmt', 'pos', '1ºVPIP', 'heroBB', 'restantes', 'total', '%field', 'speed', 'aggressor', 'tags', 'acções'].map(h => (
                      <th key={h} style={{
                        padding: '8px 10px', fontWeight: 600, whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)',
                        ...(h === 'acções' ? { position: 'sticky', right: 0, background: 'var(--bg)', zIndex: 2, borderLeft: '1px solid var(--border)' } : {}),
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visible.map(h => (
                    <tr key={h.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', ...(selected.has(h.hand_id) ? { background: 'rgba(59,130,246,0.08)' } : {}) }}>
                      <td style={{ padding: '7px 10px' }}>
                        <input type="checkbox" checked={selected.has(h.hand_id)} onChange={() => toggleSel(h.hand_id)} />
                      </td>
                      <td style={{ padding: '7px 10px', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>{h.hand_id}</td>
                      <td style={{ padding: '7px 10px', whiteSpace: 'nowrap', color: 'var(--muted)' }}>{fmtTs(h.played_at)}</td>
                      <td style={{ padding: '7px 10px' }}>{h.site}</td>
                      <td style={{ padding: '7px 10px', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {h.tournament_name}
                        <span style={{ color: 'var(--muted)', opacity: 0.7 }}> ({h.tournament_number})</span>
                      </td>
                      <td style={{ padding: '7px 10px' }}>{h.tournament_format || SD}</td>
                      <td style={{ padding: '7px 10px' }}>{normPos(h.position_hero) || SD}</td>
                      <td style={{ padding: '7px 10px' }}>{normPos(h.first_vpip_position) || SD}</td>
                      <td style={{ padding: '7px 10px' }}>{h.stack_hero_bb ?? SD}</td>
                      <td style={{ padding: '7px 10px' }} title={h.players_left_source || ''}>
                        {h.players_left != null ? h.players_left : SD}
                      </td>
                      <td style={{ padding: '7px 10px' }}>{h.total_players != null ? h.total_players : SD}</td>
                      <td style={{ padding: '7px 10px', whiteSpace: 'nowrap' }}>
                        {(() => {
                          const b = fieldBucket(h)
                          if (b === 'sd') return SD
                          if (b === 'FT') return <Chip color="#f59e0b">FT</Chip>
                          return `${Math.round(h.players_left / h.total_players * 100)}%`
                        })()}
                      </td>
                      <td style={{ padding: '7px 10px', whiteSpace: 'nowrap' }}>{h.tournament_speed || SD}</td>
                      <td style={{ padding: '7px 10px' }}>
                        <Chip color={SRC_COLOR[h.aggressor_source]}>{h.aggressor_source}</Chip>
                      </td>
                      <td style={{ padding: '7px 10px' }}>
                        <span style={{ display: 'inline-flex', gap: 4, flexWrap: 'wrap' }}>
                          {(h.hm3_tags || []).map(t => <Chip key={`h${t}`} color="#8b5cf6">{t}</Chip>)}
                          {(h.discord_tags || []).map(t => <Chip key={`d${t}`} color="#3b82f6">{t}</Chip>)}
                          {!(h.hm3_tags || []).length && !(h.discord_tags || []).length && '—'}
                        </span>
                      </td>
                      <td style={{ padding: '7px 10px', whiteSpace: 'nowrap', position: 'sticky', right: 0, background: 'var(--bg)', zIndex: 1, borderLeft: '1px solid var(--border)' }}>
                        {(() => {
                          const isRev = curState(h) === 'resolved'
                          const c = isRev ? '#22c55e' : '#3b82f6'
                          const busy = stBusy[h.id] === 'busy'
                          return (
                            <button
                              onClick={() => toggleState(h)}
                              disabled={busy}
                              title={isRev ? 'Marcar como Nova' : 'Marcar como Revista'}
                              style={{
                                fontSize: 11, fontWeight: 600, cursor: busy ? 'wait' : 'pointer',
                                color: c, background: `${c}1f`, border: `1px solid ${c}55`,
                                borderRadius: 4, padding: '2px 7px', marginRight: 8,
                                opacity: busy ? 0.5 : 1,
                              }}
                            >{busy ? '…' : (isRev ? 'Revista' : 'Nova')}</button>
                          )
                        })()}
                        {h.has_payout && (
                          <button
                            onClick={() => downloadPack(h.hand_id)}
                            disabled={dl[h.hand_id] === 'busy'}
                            title="Download do pack HRC (hh.txt + payouts.json)"
                            style={{
                              fontSize: 11, fontWeight: 600, cursor: 'pointer',
                              color: 'var(--accent2, #818cf8)', background: 'transparent',
                              border: '1px solid var(--border)', borderRadius: 4,
                              padding: '2px 7px', marginRight: 8,
                              opacity: dl[h.hand_id] === 'busy' ? 0.5 : 1,
                            }}
                          >{dl[h.hand_id] === 'busy' ? '…' : '⬇ HRC'}</button>
                        )}
                        <Link to={`/replayer/${h.id}`} style={{ color: 'var(--accent2, #818cf8)', textDecoration: 'none' }}>ver →</Link>
                        {dl[h.hand_id] === 'err' && (
                          <span style={{ color: '#ef4444', marginLeft: 6, fontSize: 11 }}>erro</span>
                        )}
                        {stBusy[h.id] === 'err' && (
                          <span style={{ color: '#ef4444', marginLeft: 6, fontSize: 11 }}>erro</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* pt83 — Enviadas: mãos libertadas + estado (resolvida / por resolver / cancelada) */}
      {sent && (
        <div style={{ marginTop: 30 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 4px' }}>Enviadas ao HRC</h2>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <span>{sent.total} no total</span>
            <span style={{ color: 'var(--border)' }}>|</span>
            <Chip color="#22c55e">resolvida {sent.sent.filter(s => curSentState(s) === 'resolvida').length}</Chip>
            <Chip color="#eab308">por resolver {sent.sent.filter(s => curSentState(s) === 'por_resolver').length}</Chip>
            <Chip color="#ef4444">cancelada {sent.sent.filter(s => curSentState(s) === 'cancelada').length}</Chip>
            {verify && verify.total > 0 && (
              <>
                <span style={{ color: 'var(--border)' }}>|</span>
                <span style={{ fontSize: 11 }}>verificação HH↔HRC:</span>
                <Chip color="#22c55e">✓ {verify.summary.ok || 0}</Chip>
                <Chip color="#eab308">⚠ {verify.summary.warn || 0}</Chip>
                <Chip color="#ef4444">✗ {verify.summary.fail || 0}</Chip>
              </>
            )}
          </div>
          {sent.sent.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
              Nenhuma mão enviada ainda.
            </div>
          ) : (
            <div style={{ overflowX: 'auto', border: '1px solid var(--border)', borderRadius: 8 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: 'var(--muted)', background: 'var(--bg)' }}>
                    {['hand_id', 'played_at (UTC)', 'site', 'torneio', 'estado', 'acções'].map(h => (
                      <th key={h} style={{ padding: '8px 10px', fontWeight: 600, whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sent.sent.map(s => {
                    const st = curSentState(s)
                    const meta = SENT_STATE[st] || { c: '#94a3b8', label: st }
                    const vEntry = verify?.byId?.[s.hand_id]   // só as resolvidas têm result_zip
                    const isOpen = vOpen === s.hand_id
                    return (
                    <Fragment key={s.hand_id}>
                      <tr style={{ borderBottom: isOpen ? 'none' : '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '7px 10px', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                            <VerifyBadge verdict={vEntry?.verdict} open={isOpen}
                              onClick={() => toggleVerify(s.hand_id)} />
                            {s.hand_id}
                          </span>
                        </td>
                        <td style={{ padding: '7px 10px', whiteSpace: 'nowrap', color: 'var(--muted)' }}>{fmtTs(s.played_at)}</td>
                        <td style={{ padding: '7px 10px' }}>{s.site}</td>
                        <td style={{ padding: '7px 10px', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.tournament_name || '—'}</td>
                        <td style={{ padding: '7px 10px', whiteSpace: 'nowrap' }}>
                          <Chip color={meta.c}>{meta.label}</Chip>
                          {st === 'por_resolver' && fmtAge(s.released_at) && (
                            <span style={{ color: 'var(--muted)', marginLeft: 6 }}>enviada {fmtAge(s.released_at)}</span>
                          )}
                          {st === 'cancelada' && s.error && (
                            <span style={{ color: 'var(--muted)', marginLeft: 6 }} title={s.error}>· {s.error}</span>
                          )}
                        </td>
                        <td style={{ padding: '7px 10px', whiteSpace: 'nowrap' }}>
                          {st === 'cancelada' && (
                            <button
                              onClick={() => doRequeue(s.hand_id)}
                              disabled={rqBusy[s.hand_id] === 'busy'}
                              title="Apaga o resultado falhado e re-põe a mão na fila (o adapter re-puxa)"
                              style={{
                                fontSize: 11, fontWeight: 600, cursor: rqBusy[s.hand_id] === 'busy' ? 'wait' : 'pointer',
                                color: '#eab308', background: '#eab3081f', border: '1px solid #eab30855',
                                borderRadius: 4, padding: '2px 7px', marginRight: 8,
                                opacity: rqBusy[s.hand_id] === 'busy' ? 0.5 : 1,
                              }}
                            >{rqBusy[s.hand_id] === 'busy' ? '…' : '↻ Re-pôr na fila'}</button>
                          )}
                          {s.id != null && (
                            <Link to={`/replayer/${s.id}`} style={{ color: 'var(--accent2, #818cf8)', textDecoration: 'none' }}>ver →</Link>
                          )}
                          {rqBusy[s.hand_id] === 'err' && (
                            <span style={{ color: '#ef4444', marginLeft: 6, fontSize: 11 }}>erro</span>
                          )}
                        </td>
                      </tr>
                      {isOpen && (
                        <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                          <td colSpan={6} style={{ padding: 0 }}>
                            <VerifyDetail res={vDetail[s.hand_id]} handDbId={s.id} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
