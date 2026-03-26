import { useEffect, useState, useCallback } from 'react'
import { discord, hands as handsApi } from '../api/client'

// ── Constantes ──────────────────────────────────────────────────────────────

const DATE_FILTERS = [
  { label: 'Todas', value: '' },
  { label: 'Hoje', fn: () => { const d = new Date(); d.setHours(0,0,0,0); return d.toISOString().slice(0,10) } },
  { label: '3 dias', fn: () => { const d = new Date(); d.setDate(d.getDate()-3); return d.toISOString().slice(0,10) } },
  { label: 'Semana', fn: () => { const d = new Date(); d.setDate(d.getDate()-7); return d.toISOString().slice(0,10) } },
  { label: 'Mês', fn: () => { const d = new Date(); d.setDate(d.getDate()-30); return d.toISOString().slice(0,10) } },
]

const SORT_OPTIONS = [
  { value: 'imported_desc', label: 'Importação (recente)' },
  { value: 'imported_asc',  label: 'Importação (antiga)' },
  { value: 'discord_desc',  label: 'Discord (recente)' },
  { value: 'discord_asc',   label: 'Discord (antiga)' },
  { value: 'count_desc',    label: 'Mais mãos primeiro' },
  { value: 'count_asc',     label: 'Menos mãos primeiro' },
]

const STATE_META = {
  new:      { label: 'Nova',      color: '#3b82f6', bg: 'rgba(59,130,246,0.15)' },
  review:   { label: 'Revisão',   color: '#f59e0b', bg: 'rgba(245,158,11,0.15)' },
  studying: { label: 'A Estudar', color: '#8b5cf6', bg: 'rgba(139,92,246,0.15)' },
  resolved: { label: 'Resolvida', color: '#22c55e', bg: 'rgba(34,197,94,0.15)'  },
}

const SUIT_COLORS = { h: '#ef4444', d: '#f97316', c: '#22c55e', s: '#e2e8f0' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }

const TAG_COLORS = {
  icm: '#6366f1', pko: '#f59e0b', ko: '#f59e0b', pos: '#22c55e',
  bvb: '#8b5cf6', ss: '#ef4444', ft: '#06b6d4', nota: '#64748b',
  cbet: '#a78bfa', ip: '#34d399', mw: '#fb923c',
  speed: '#ec4899', racer: '#ec4899',
}

// ── Mini Componentes ────────────────────────────────────────────────────────

function PokerCard({ card, size = 'sm' }) {
  if (!card || card.length < 2) return <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 26, height: 36, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 4, fontSize: 10, color: '#4b5563' }}>?</span>
  const rank = card.slice(0, -1).toUpperCase()
  const suit = card.slice(-1).toLowerCase()
  const color = SUIT_COLORS[suit] || '#e2e8f0'
  const symbol = SUIT_SYMBOLS[suit] || suit
  return (
    <span style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', width: size === 'sm' ? 26 : 34, height: size === 'sm' ? 36 : 46, background: '#1e2130', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 4, fontFamily: "'Fira Code', monospace", fontSize: size === 'sm' ? 10 : 12, fontWeight: 700, color, lineHeight: 1, gap: 1, userSelect: 'none', boxShadow: '0 1px 3px rgba(0,0,0,0.4)' }}>
      <span>{rank}</span>
      <span style={{ fontSize: size === 'sm' ? 9 : 11 }}>{symbol}</span>
    </span>
  )
}

function StateBadge({ state }) {
  const meta = STATE_META[state] || { label: state, color: '#666', bg: 'rgba(100,100,100,0.15)' }
  return <span style={{ display: 'inline-block', padding: '2px 9px', borderRadius: 999, fontSize: 10, fontWeight: 600, letterSpacing: 0.3, color: meta.color, background: meta.bg }}>{meta.label}</span>
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ color: '#4b5563' }}>&mdash;</span>
  const colors = { BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa', SB: '#f59e0b', BB: '#ef4444', UTG: '#22c55e', UTG1: '#16a34a', UTG2: '#15803d', MP: '#06b6d4', MP1: '#0891b2' }
  const c = colors[pos] || '#64748b'
  return <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700, letterSpacing: 0.5, color: c, background: `${c}20`, border: `1px solid ${c}40` }}>{pos}</span>
}

function ResultBadge({ result }) {
  if (result == null) return <span style={{ color: '#4b5563' }}>&mdash;</span>
  const val = Number(result)
  if (val > 0) return <span style={{ color: '#22c55e', fontWeight: 600, fontFamily: 'monospace' }}>+{val.toFixed(1)} BB</span>
  if (val < 0) return <span style={{ color: '#ef4444', fontWeight: 600, fontFamily: 'monospace' }}>{val.toFixed(1)} BB</span>
  return <span style={{ color: '#64748b', fontFamily: 'monospace' }}>0 BB</span>
}

function TagBadge({ t }) {
  const c = TAG_COLORS[t] || '#64748b'
  return <span style={{ display: 'inline-block', padding: '1px 7px', borderRadius: 999, fontSize: 10, fontWeight: 600, marginRight: 3, color: c, background: `${c}18`, border: `1px solid ${c}30` }}>#{t}</span>
}

// ── Hand Row (dentro de tag group) ──────────────────────────────────────────

function HandRow({ hand, onClick }) {
  return (
    <div onClick={onClick} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px', background: '#1a1d27', borderBottom: '1px solid #1e2130', cursor: 'pointer', transition: 'background 0.1s' }}
      onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.04)'}
      onMouseLeave={e => e.currentTarget.style.background = '#1a1d27'}>
      <div style={{ minWidth: 60 }}><StateBadge state={hand.study_state} /></div>
      <div style={{ minWidth: 50 }}><PosBadge pos={hand.position} /></div>
      <div style={{ display: 'flex', gap: 3, minWidth: 60 }}>
        {hand.hero_cards?.length > 0
          ? hand.hero_cards.map((c, i) => <PokerCard key={i} card={c} />)
          : <span style={{ color: '#374151', fontSize: 11 }}>&mdash;</span>}
      </div>
      <div style={{ display: 'flex', gap: 3, minWidth: 140 }}>
        {hand.board?.length > 0
          ? hand.board.slice(0, 5).map((c, i) => <PokerCard key={i} card={c} />)
          : <span style={{ color: '#374151', fontSize: 11 }}>&mdash;</span>}
      </div>
      <div style={{ minWidth: 80 }}><ResultBadge result={hand.result} /></div>
      <div style={{ flex: 1, fontSize: 11, color: '#64748b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{hand.stakes || ''}</div>
      <div style={{ fontSize: 10, color: '#4b5563', minWidth: 60, textAlign: 'right' }}>
        {hand.discord_posted_at ? new Date(hand.discord_posted_at).toLocaleDateString('pt-PT') : ''}
      </div>
      <div style={{ fontSize: 10, color: '#374151', minWidth: 60, textAlign: 'right' }}>
        {hand.created_at ? new Date(hand.created_at).toLocaleDateString('pt-PT') : ''}
      </div>
    </div>
  )
}

// ── Tag Group (colapsável) ──────────────────────────────────────────────────

function TagGroup({ tagKey, tagHands, onOpenDetail, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)

  const wins = tagHands.filter(h => h.result != null && Number(h.result) > 0).length
  const losses = tagHands.filter(h => h.result != null && Number(h.result) < 0).length
  const totalBB = tagHands.reduce((sum, h) => sum + (Number(h.result) || 0), 0)

  // Determinar a cor pela primeira tag individual
  const firstTag = tagKey.split('+')[0]
  const tagColor = TAG_COLORS[firstTag] || '#64748b'

  return (
    <div style={{ marginBottom: 8, border: `1px solid ${open ? `${tagColor}40` : '#2a2d3a'}`, borderRadius: 10, overflow: 'hidden', transition: 'border-color 0.2s' }}>
      <div onClick={() => setOpen(!open)} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', background: open ? `${tagColor}08` : '#1a1d27', cursor: 'pointer', transition: 'background 0.15s', userSelect: 'none' }}
        onMouseEnter={e => { if (!open) e.currentTarget.style.background = '#1e2130' }}
        onMouseLeave={e => { if (!open) e.currentTarget.style.background = '#1a1d27' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ display: 'inline-block', fontSize: 10, color: tagColor, transform: open ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>&#9654;</span>
          <div style={{ display: 'flex', gap: 4 }}>
            {tagKey.split('+').map(t => <TagBadge key={t} t={t} />)}
          </div>
          <span style={{ fontSize: 12, color: '#64748b' }}>{tagHands.length} {tagHands.length === 1 ? 'mão' : 'mãos'}</span>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', fontSize: 11 }}>
          <span style={{ color: '#22c55e' }}>{wins}W</span>
          <span style={{ color: '#ef4444' }}>{losses}L</span>
          <span style={{ color: totalBB >= 0 ? '#22c55e' : '#ef4444', fontWeight: 600, fontFamily: 'monospace' }}>{totalBB >= 0 ? '+' : ''}{totalBB.toFixed(1)} BB</span>
        </div>
      </div>
      {open && (
        <div>
          {/* Header das colunas */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '6px 16px', borderBottom: '1px solid #1e2130', fontSize: 9, color: '#4b5563', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            <div style={{ minWidth: 60 }}>Estado</div>
            <div style={{ minWidth: 50 }}>Pos</div>
            <div style={{ minWidth: 60 }}>Cartas</div>
            <div style={{ minWidth: 140 }}>Board</div>
            <div style={{ minWidth: 80 }}>Resultado</div>
            <div style={{ flex: 1 }}>Torneio</div>
            <div style={{ minWidth: 60, textAlign: 'right' }}>Discord</div>
            <div style={{ minWidth: 60, textAlign: 'right' }}>Import.</div>
          </div>
          {tagHands.map(h => (
            <HandRow key={h.id} hand={h} onClick={() => onOpenDetail(h.id)} />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Hand Detail Modal ───────────────────────────────────────────────────────

function HandDetailModal({ hand, onClose }) {
  const isGG = (hand.raw || '').includes('gg.gl')

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, backdropFilter: 'blur(4px)' }} onClick={onClose}>
      <div style={{ width: '92%', maxWidth: 700, maxHeight: '90vh', overflow: 'auto', background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12, padding: 28 }} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <span style={{ fontWeight: 700, fontSize: 17 }}>Mão #{hand.id}</span>
              <StateBadge state={hand.study_state} />
              {hand.result != null && <ResultBadge result={hand.result} />}
            </div>
            {hand.stakes && <div style={{ fontSize: 12, color: '#64748b' }}>{hand.stakes}</div>}
          </div>
          <button style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 18, padding: 4 }} onClick={onClose}>&#10005;</button>
        </div>

        {/* Cartas + Board */}
        <div style={{ background: '#0f1117', borderRadius: 10, padding: '16px 20px', marginBottom: 20, display: 'flex', gap: 32, alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Hero &middot; <PosBadge pos={hand.position} /></div>
            <div style={{ display: 'flex', gap: 5 }}>
              {hand.hero_cards?.length > 0
                ? hand.hero_cards.map((c, i) => <PokerCard key={i} card={c} size="md" />)
                : <span style={{ color: '#4b5563', fontSize: 13 }}>Cartas não visíveis</span>}
            </div>
          </div>
          {hand.board?.length > 0 && (
            <div>
              <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Board</div>
              <div style={{ display: 'flex', gap: 5 }}>{hand.board.slice(0, 5).map((c, i) => <PokerCard key={i} card={c} size="md" />)}</div>
            </div>
          )}
        </div>

        {/* Info grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px 20px', marginBottom: 20, fontSize: 13 }}>
          {[
            { l: 'Sala', v: hand.site },
            { l: 'Data da Mão', v: hand.played_at ? hand.played_at.slice(0, 10) : null },
            { l: 'Resultado', v: <ResultBadge result={hand.result} /> },
            { l: 'Posição', v: <PosBadge pos={hand.position} /> },
            { l: 'Torneio', v: hand.stakes },
            { l: 'Postado no Discord', v: hand.discord_posted_at ? new Date(hand.discord_posted_at).toLocaleString('pt-PT') : null },
            { l: 'Importado', v: hand.created_at ? new Date(hand.created_at).toLocaleString('pt-PT') : null },
            { l: 'Canal Discord', v: hand.discord_channel_name ? `#${hand.discord_channel_name}` : null },
            { l: 'Tags', v: hand.tags?.length > 0 ? <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>{hand.tags.map(t => <TagBadge key={t} t={t} />)}</div> : null },
          ].map(({ l, v }) => (
            <div key={l} style={{ background: '#0f1117', borderRadius: 6, padding: '8px 12px' }}>
              <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, letterSpacing: 0.4, marginBottom: 3, textTransform: 'uppercase' }}>{l}</div>
              <div>{v || <span style={{ color: '#4b5563' }}>&mdash;</span>}</div>
            </div>
          ))}
        </div>

        {/* Replayer link */}
        {isGG && (
          <div style={{ marginBottom: 16 }}>
            <a href={hand.raw} target="_blank" rel="noopener noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 500, background: 'rgba(99,102,241,0.12)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.25)', textDecoration: 'none' }}>
              &#9654; Abrir Replayer GG
            </a>
          </div>
        )}

        {/* Notas */}
        {hand.notes && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>Notas</div>
            <div style={{ background: '#0f1117', borderRadius: 6, padding: '8px 12px', fontSize: 12, color: '#94a3b8', whiteSpace: 'pre-wrap', maxHeight: 120, overflow: 'auto' }}>{hand.notes}</div>
          </div>
        )}

        {/* Link para editar na página Mãos */}
        <div style={{ borderTop: '1px solid #2a2d3a', paddingTop: 16, display: 'flex', gap: 8 }}>
          <a href={`/hands`} style={{ padding: '7px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: '#6366f1', color: '#fff', textDecoration: 'none' }}>
            Abrir na página Mãos
          </a>
        </div>
      </div>
    </div>
  )
}

// ── Página Principal ─────────────────────────────────────────────────────────

export default function DiscordPage() {
  const [status, setStatus] = useState(null)
  const [stats, setStats] = useState(null)
  const [syncState, setSyncState] = useState([])
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [sortBy, setSortBy] = useState('imported_desc')
  const [handsList, setHandsList] = useState([])
  const [loadingHands, setLoadingHands] = useState(false)
  const [selected, setSelected] = useState(null)
  const [tab, setTab] = useState('hands') // 'hands' | 'bot'

  const loadStatus = useCallback(() => {
    discord.status().then(setStatus).catch(e => setError(e.message))
    const params = dateFrom ? { date_from: dateFrom } : {}
    discord.stats(params).then(setStats).catch(() => {})
    discord.syncState().then(setSyncState).catch(() => {})
  }, [dateFrom])

  const loadHands = useCallback(() => {
    setLoadingHands(true)
    const params = { page_size: 200 }
    if (dateFrom) params.date_from = dateFrom
    handsApi.list(params)
      .then(r => setHandsList(r.data || []))
      .catch(e => setError(e.message))
      .finally(() => setLoadingHands(false))
  }, [dateFrom])

  useEffect(() => { loadStatus(); loadHands() }, [loadStatus, loadHands])

  const triggerSync = async () => {
    setSyncing(true); setMsg('')
    try {
      const r = await discord.sync()
      setMsg(`Sync iniciado em ${r.servers} servidor(es). Actualiza em 30s.`)
      setTimeout(() => { loadStatus(); loadHands() }, 30000)
    } catch (e) { setError(e.message) }
    finally { setSyncing(false) }
  }

  async function openDetail(id) {
    try { const h = await handsApi.get(id); setSelected(h) }
    catch (e) { setError(e.message) }
  }

  // Agrupar por tags
  const tagGroups = {}
  const noTagHands = []
  handsList.forEach(h => {
    if (h.tags && h.tags.length > 0) {
      const tagKey = [...h.tags].sort().join('+')
      if (!tagGroups[tagKey]) tagGroups[tagKey] = { tags: h.tags, hands: [] }
      tagGroups[tagKey].hands.push(h)
    } else {
      noTagHands.push(h)
    }
  })

  // Ordenar grupos
  let sortedGroups = Object.entries(tagGroups)
  if (sortBy === 'count_desc') sortedGroups.sort((a, b) => b[1].hands.length - a[1].hands.length)
  else if (sortBy === 'count_asc') sortedGroups.sort((a, b) => a[1].hands.length - b[1].hands.length)
  else if (sortBy === 'imported_desc') sortedGroups.sort((a, b) => {
    const aMax = Math.max(...a[1].hands.map(h => h.created_at ? new Date(h.created_at).getTime() : 0))
    const bMax = Math.max(...b[1].hands.map(h => h.created_at ? new Date(h.created_at).getTime() : 0))
    return bMax - aMax
  })
  else if (sortBy === 'imported_asc') sortedGroups.sort((a, b) => {
    const aMin = Math.min(...a[1].hands.filter(h => h.created_at).map(h => new Date(h.created_at).getTime()))
    const bMin = Math.min(...b[1].hands.filter(h => h.created_at).map(h => new Date(h.created_at).getTime()))
    return aMin - bMin
  })
  else if (sortBy === 'discord_desc') sortedGroups.sort((a, b) => {
    const aMax = Math.max(...a[1].hands.map(h => h.discord_posted_at ? new Date(h.discord_posted_at).getTime() : 0))
    const bMax = Math.max(...b[1].hands.map(h => h.discord_posted_at ? new Date(h.discord_posted_at).getTime() : 0))
    return bMax - aMax
  })
  else if (sortBy === 'discord_asc') sortedGroups.sort((a, b) => {
    const aMin = Math.min(...a[1].hands.filter(h => h.discord_posted_at).map(h => new Date(h.discord_posted_at).getTime()))
    const bMin = Math.min(...b[1].hands.filter(h => h.discord_posted_at).map(h => new Date(h.discord_posted_at).getTime()))
    return aMin - bMin
  })

  const fmtDate = (d) => d ? new Date(d).toLocaleString('pt-PT') : '—'

  return (
    <>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: -0.5 }}>Discord</div>
          <div style={{ color: '#64748b', fontSize: 13, marginTop: 3 }}>
            {handsList.length} mãos importadas &middot; {Object.keys(tagGroups).length} tags
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={{ padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 500, background: 'transparent', color: '#64748b', border: '1px solid #2a2d3a', cursor: 'pointer' }} onClick={() => { loadStatus(); loadHands() }}>Actualizar</button>
          <button style={{ padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: '#6366f1', color: '#fff', border: 'none', cursor: 'pointer', opacity: syncing || !status?.online ? 0.5 : 1 }} onClick={triggerSync} disabled={syncing || !status?.online}>
            {syncing ? 'A sincronizar...' : 'Sincronizar Agora'}
          </button>
        </div>
      </div>

      {error && <div style={{ color: '#ef4444', fontSize: 13, marginBottom: 12, padding: '8px 12px', background: 'rgba(239,68,68,0.08)', borderRadius: 6, border: '1px solid rgba(239,68,68,0.2)' }}>{error}</div>}
      {msg && <div style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.25)', borderRadius: 8, padding: '10px 16px', marginBottom: 16, color: '#818cf8', fontSize: 13 }}>{msg}</div>}

      {/* Tabs: Mãos | Bot */}
      <div style={{ display: 'flex', gap: 4, background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 8, padding: 3, marginBottom: 16, width: 'fit-content' }}>
        {[
          { id: 'hands', label: 'Mãos Importadas' },
          { id: 'bot', label: 'Estado do Bot' },
        ].map(({ id, label }) => (
          <button key={id} onClick={() => setTab(id)} style={{ padding: '5px 14px', borderRadius: 6, fontSize: 12, fontWeight: 500, border: 'none', cursor: 'pointer', background: tab === id ? '#6366f1' : 'transparent', color: tab === id ? '#fff' : '#64748b', transition: 'all 0.15s' }}>{label}</button>
        ))}
      </div>

      {/* ═══════ TAB: Mãos Importadas ═══════ */}
      {tab === 'hands' && (
        <>
          {/* Filtros temporais */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
            {DATE_FILTERS.map(({ label, value, fn }) => {
              const filterValue = fn ? fn() : (value ?? '')
              const isActive = dateFrom === filterValue
              return (
                <button key={label} onClick={() => setDateFrom(filterValue)} style={{ padding: '5px 14px', borderRadius: 20, fontSize: 12, fontWeight: 500, border: '1px solid', borderColor: isActive ? '#6366f1' : '#2a2d3a', background: isActive ? 'rgba(99,102,241,0.15)' : 'transparent', color: isActive ? '#818cf8' : '#64748b', cursor: 'pointer', transition: 'all 0.15s' }}>{label}</button>
              )
            })}
          </div>

          {/* Ordenação */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 10, padding: '10px 16px' }}>
            <span style={{ fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>Ordenar por:</span>
            <select value={sortBy} onChange={e => setSortBy(e.target.value)} style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '5px 10px', fontSize: 12 }}>
              {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            {/* Stats rápidas */}
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 16, fontSize: 12 }}>
              <span style={{ color: '#64748b' }}>Entries: <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{stats?.entries?.total_entries ?? '—'}</span></span>
              <span style={{ color: '#64748b' }}>Pendentes: <span style={{ color: '#f59e0b', fontWeight: 600 }}>{stats?.entries?.pending ?? '—'}</span></span>
              <span style={{ color: '#64748b' }}>Bot: <span style={{ color: status?.online ? '#22c55e' : '#ef4444', fontWeight: 600 }}>{status?.online ? 'Online' : 'Offline'}</span></span>
            </div>
          </div>

          {/* Loading */}
          {loadingHands && (
            <div style={{ textAlign: 'center', padding: '48px 0', color: '#64748b' }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>&#10227;</div>A carregar...
            </div>
          )}

          {/* Empty */}
          {!loadingHands && handsList.length === 0 && (
            <div style={{ textAlign: 'center', padding: '64px 0', color: '#64748b' }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>&#127183;</div>
              <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 6 }}>Sem mãos neste período</div>
              <div style={{ fontSize: 13 }}>Sincroniza o Discord ou altera o filtro temporal.</div>
            </div>
          )}

          {/* Tag groups colapsáveis */}
          {!loadingHands && handsList.length > 0 && (
            <div>
              {sortedGroups.map(([tagKey, group]) => (
                <TagGroup key={tagKey} tagKey={tagKey} tagHands={group.hands} onOpenDetail={openDetail} />
              ))}
              {noTagHands.length > 0 && (
                <TagGroup tagKey="sem-tag" tagHands={noTagHands} onOpenDetail={openDetail} />
              )}
            </div>
          )}
        </>
      )}

      {/* ═══════ TAB: Estado do Bot ═══════ */}
      {tab === 'bot' && (
        <>
          {/* Estado do Bot */}
          <div className="stat-grid" style={{ marginBottom: 24 }}>
            <div className="stat-card">
              <div className="stat-label">Estado</div>
              <div className="stat-value" style={{ color: status?.online ? '#22c55e' : '#ef4444', fontSize: 18 }}>{status?.online ? 'Online' : 'Offline'}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Bot</div>
              <div className="stat-value" style={{ fontSize: 14 }}>{status?.user || '—'}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Entries Extraídas</div>
              <div className="stat-value">{stats?.entries?.total_entries ?? '—'}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Pendentes</div>
              <div className="stat-value" style={{ color: 'var(--accent)' }}>{stats?.entries?.pending ?? '—'}</div>
            </div>
          </div>

          {/* Servidores e Canais */}
          {status?.online && status.servers?.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ marginBottom: 12 }}>Servidores Monitorizados</h3>
              {status.servers.map(srv => (
                <div key={srv.id} style={{ background: 'var(--surface)', borderRadius: 8, padding: 16, marginBottom: 12 }}>
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>{srv.name}</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {srv.channels.map(ch => (
                      <span key={ch.id} style={{ padding: '4px 10px', borderRadius: 4, fontSize: 12, background: ch.monitored ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.05)', color: ch.monitored ? 'var(--accent)' : 'var(--muted)', border: ch.monitored ? '1px solid var(--accent)' : '1px solid transparent' }}>#{ch.name}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Por Tipo */}
          {stats?.by_type?.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ marginBottom: 12 }}>Por Tipo de Conteúdo</h3>
              <table className="data-table">
                <thead><tr><th>Tipo</th><th style={{ textAlign: 'right' }}>Quantidade</th></tr></thead>
                <tbody>{stats.by_type.map(r => <tr key={r.entry_type}><td>{r.entry_type}</td><td style={{ textAlign: 'right' }}>{r.count}</td></tr>)}</tbody>
              </table>
            </div>
          )}

          {/* Por Canal */}
          {stats?.by_channel?.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ marginBottom: 12 }}>Por Canal</h3>
              <table className="data-table">
                <thead><tr><th>Canal</th><th style={{ textAlign: 'right' }}>Entries</th></tr></thead>
                <tbody>{stats.by_channel.map(r => <tr key={r.channel}><td>#{r.channel}</td><td style={{ textAlign: 'right' }}>{r.count}</td></tr>)}</tbody>
              </table>
            </div>
          )}

          {/* Histórico de Sync */}
          {syncState.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ marginBottom: 12 }}>Histórico de Sincronização</h3>
              <table className="data-table">
                <thead><tr><th>Canal</th><th style={{ textAlign: 'right' }}>Mensagens</th><th style={{ textAlign: 'right' }}>Último Sync</th></tr></thead>
                <tbody>{syncState.map(r => <tr key={r.channel_id}><td>#{r.channel_name}</td><td style={{ textAlign: 'right' }}>{r.messages_synced}</td><td style={{ textAlign: 'right' }}>{fmtDate(r.last_sync_at)}</td></tr>)}</tbody>
              </table>
            </div>
          )}

          {/* Offline */}
          {status && !status.online && (
            <div style={{ background: 'var(--surface)', borderRadius: 8, padding: 24, textAlign: 'center', color: 'var(--muted)' }}>
              <p style={{ marginBottom: 12 }}>O bot Discord não está online.</p>
              <p style={{ fontSize: 13 }}>Verifica que as variáveis <code>DISCORD_BOT_TOKEN</code> e <code>DISCORD_SERVER_IDS</code> estão configuradas no Railway.</p>
            </div>
          )}
        </>
      )}

      {/* Modal */}
      {selected && <HandDetailModal hand={selected} onClose={() => setSelected(null)} />}
    </>
  )
}
