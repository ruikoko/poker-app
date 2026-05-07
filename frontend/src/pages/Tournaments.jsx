import { useState, useEffect, useCallback } from 'react'
import { mtt } from '../api/client'
import HandRow from '../components/HandRow'
import TournamentHeader from '../components/TournamentHeader'

// ── Constantes ───────────────────────────────────────────────────────────────

const SUIT_COLORS  = { h: '#ef4444', d: '#f97316', c: '#22c55e', s: '#e2e8f0' }
const SUIT_BG      = { h: '#dc2626', d: '#2563eb', c: '#16a34a', s: '#1e293b' }

const POS_COLORS = {
  BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa',
  SB: '#f59e0b', BB: '#ef4444',
  UTG: '#22c55e', UTG1: '#16a34a', UTG2: '#15803d',
  MP: '#06b6d4', MP1: '#0891b2',
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function PokerCard({ card, size = 'sm' }) {
  if (!card || card.length < 2) {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: 24, height: 34,
        background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 3, fontSize: 11, color: '#4b5563',
      }}>?</span>
    )
  }
  const rank = card.slice(0, -1).toUpperCase()
  const suit = card.slice(-1).toLowerCase()
  const bg = SUIT_BG[suit] || '#1e2130'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 24, height: 34,
      background: bg, border: '1px solid rgba(255,255,255,0.2)',
      borderRadius: 3, fontFamily: "'Fira Code', monospace",
      fontSize: 14, fontWeight: 700, color: '#fff', lineHeight: 1,
      boxShadow: '0 1px 2px rgba(0,0,0,0.3)', userSelect: 'none',
    }}>{rank}</span>
  )
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ display: 'inline-block', width: 48, textAlign: 'center', color: '#4b5563' }}>—</span>
  const c = POS_COLORS[pos] || '#64748b'
  const isBlind = pos === 'SB' || pos === 'BB'
  return (
    <span style={{
      display: 'inline-block', padding: '1px 0', borderRadius: 3, width: 48, textAlign: 'center',
      fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
      color: '#0a0c14', background: isBlind ? c : '#e2e8f0', border: `1px solid ${isBlind ? c : '#e2e8f0'}`,
    }}>{pos}</span>
  )
}

function ResultBadge({ result }) {
  if (result == null) return <span style={{ color: '#4b5563' }}>—</span>
  const val = Number(result)
  if (val > 0) return <span style={{ color: '#22c55e', fontWeight: 600, fontFamily: 'monospace', fontSize: 12 }}>+{val.toFixed(1)}</span>
  if (val < 0) return <span style={{ color: '#ef4444', fontWeight: 600, fontFamily: 'monospace', fontSize: 12 }}>{val.toFixed(1)}</span>
  return <span style={{ color: '#64748b', fontFamily: 'monospace', fontSize: 12 }}>0</span>
}

function formatDateLabel(iso) {
  if (!iso) return 'Sem data'
  const d = new Date(iso)
  const weekdays = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']
  return `${weekdays[d.getDay()]}, ${d.toLocaleDateString('pt-PT', { day: '2-digit', month: 'long', year: 'numeric' })}`
}

// Todas as funções de data/hora usam TZ local do browser (Portugal). Coerente
// com o que o utilizador espera ver — a hora a que realmente jogou.
function formatDateKey(iso) {
  if (!iso) return 'unknown'
  const d = new Date(iso)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function formatDayMonth(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function formatDayTimeRange(firstIso, lastIso) {
  if (!firstIso) return ''
  const fDay = formatDayMonth(firstIso)
  const fTime = formatTime(firstIso)
  if (!lastIso || firstIso === lastIso) return `${fDay} ${fTime}`
  const lDay = formatDayMonth(lastIso)
  const lTime = formatTime(lastIso)
  return fDay === lDay
    ? `${fDay} ${fTime} → ${lTime}`
    : `${fDay} ${fTime} → ${lDay} ${lTime}`
}

// Remove buy-in monetário ($N, $N.M, $N,M) do nome do torneio. Preserva
// sufixos tipo "$1M GTD" — o "M" a seguir ao número falha o lookahead.
function cleanTournamentName(name) {
  if (!name) return name
  return name
    .replace(/(?<=^|\s)\$\d+(?:[.,]\d+)?(?=\s|$)/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

// Strip ".0"/".00" de números inteiros no string de blinds. Preserva 2.5, 100.50.
function cleanBlinds(s) {
  if (!s) return s
  return s.replace(/(\d+)\.0+(?=\D|$)/g, '$1')
}

// ── Import Panel ─────────────────────────────────────────────────────────────

function ImportPanel({ onImported }) {
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  const handleFiles = async (files) => {
    if (!files || files.length === 0) return
    setImporting(true)
    setResult(null)
    try {
      const results = []
      for (const file of files) {
        const r = await mtt.import(file)
        results.push(r)
      }
      const total = results.reduce((a, r) => ({
        inserted: a.inserted + (r.inserted || 0),
        skipped: a.skipped + (r.skipped || 0),
        matched: a.matched + (r.matched_with_screenshots || 0),
        villains: a.villains + (r.villains_created || 0),
        errors: a.errors + (r.errors || 0),
      }), { inserted: 0, skipped: 0, matched: 0, villains: 0, errors: 0 })
      setResult(total)
      if (total.inserted > 0) onImported?.()
    } catch (e) {
      setResult({ error: e.message })
    } finally {
      setImporting(false)
    }
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}
      style={{
        border: `2px dashed ${dragOver ? '#6366f1' : 'rgba(255,255,255,0.1)'}`,
        borderRadius: 8, padding: '16px 24px', marginBottom: 16,
        background: dragOver ? 'rgba(99,102,241,0.05)' : 'rgba(255,255,255,0.02)',
        textAlign: 'center', transition: 'all 0.2s',
      }}
    >
      {importing ? (
        <div style={{ color: '#f59e0b' }}>A importar HH de MTT...</div>
      ) : (
        <>
          <div style={{ color: '#94a3b8', fontSize: 13 }}>
            Arrastar ficheiros HH (.txt / .zip) ou{' '}
            <label style={{ color: '#6366f1', cursor: 'pointer', textDecoration: 'underline' }}>
              clicar
              <input type="file" accept=".txt,.zip" multiple hidden
                onChange={(e) => handleFiles(e.target.files)} />
            </label>
          </div>
        </>
      )}
      {result && !result.error && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#94a3b8', display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
          <span style={{ color: '#22c55e' }}>{result.inserted} mãos</span>
          {result.skipped > 0 && <span style={{ color: '#f59e0b' }}>{result.skipped} dup</span>}
          <span style={{ color: '#6366f1' }}>{result.matched} com SS</span>
          <span style={{ color: '#8b5cf6' }}>{result.villains} villains</span>
        </div>
      )}
      {result?.error && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#ef4444' }}>{result.error}</div>
      )}
    </div>
  )
}

// ── Stats Bar ────────────────────────────────────────────────────────────────

function StatsBar({ stats }) {
  if (!stats) return null
  return (
    <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
      {[
        { label: 'Mãos', value: stats.total_hands, color: '#e2e8f0' },
        { label: 'Com SS', value: stats.hands_with_screenshot, color: '#22c55e' },
        { label: 'Torneios', value: stats.tournaments, color: '#6366f1' },
        { label: 'Villains', value: stats.unique_villains, color: '#f59e0b' },
      ].map(({ label, value, color }) => (
        <div key={label} style={{
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 6, padding: '6px 14px',
        }}>
          <span style={{ fontSize: 16, fontWeight: 700, color, fontFamily: 'monospace' }}>{value}</span>
          <span style={{ fontSize: 11, color: '#4b5563', marginLeft: 6 }}>{label}</span>
        </div>
      ))}
    </div>
  )
}

// ── Villain Row (inside hand detail) ─────────────────────────────────────────

function VillainRow({ v }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      background: 'rgba(255,255,255,0.02)', borderRadius: 4, padding: '4px 8px',
      border: '1px solid rgba(255,255,255,0.04)',
    }}>
      <PosBadge pos={v.position} />
      <span style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', minWidth: 100 }}>
        {v.player_name}
      </span>
      {v.stack && (
        <span style={{ fontSize: 11, color: '#64748b' }}>
          {Number(v.stack).toLocaleString()}
        </span>
      )}
      {v.bounty_pct && (
        <span style={{ fontSize: 11, color: '#f59e0b' }}>{v.bounty_pct}</span>
      )}
      {v.country && (
        <span style={{ fontSize: 11, color: '#64748b' }}>{v.country}</span>
      )}
      <span style={{
        fontSize: 11, fontWeight: 600, padding: '1px 5px', borderRadius: 3,
        color: v.vpip_action === 'call' ? '#22c55e' : v.vpip_action === 'raise' ? '#f97316' : '#ef4444',
        background: v.vpip_action === 'call' ? 'rgba(34,197,94,0.1)' : v.vpip_action === 'raise' ? 'rgba(249,115,22,0.1)' : 'rgba(239,68,68,0.1)',
      }}>{v.vpip_action}</span>
    </div>
  )
}

// ── Hand Row (inside tournament group) ───────────────────────────────────────

// Expansion abaixo da HandRow: villains (VPIP) + mesa (screenshot players) + acções.
function TournamentDetail({ hand, onDeleteHand, onDeleteScreenshot }) {
  const hasVillains = hand.villains && hand.villains.length > 0
  const hasSsPlayers = hand.screenshot_players && Object.keys(hand.screenshot_players).length > 0

  return (
    <div style={{ padding: '8px 12px 12px 52px', background: 'rgba(255,255,255,0.01)' }}>
      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
        {hand.raw && (
          <button onClick={() => navigator.clipboard.writeText(hand.raw)}
            style={{ padding: '4px 12px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: 'rgba(34,197,94,0.1)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.2)', cursor: 'pointer' }}
          >Copiar HH</button>
        )}
        <a href={`/replayer/${hand.id}`} target="_blank" rel="noopener noreferrer"
          style={{ padding: '4px 12px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: 'rgba(99,102,241,0.1)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.2)', textDecoration: 'none' }}
        >&#9654; Replayer</a>
        <a href={`/hand/${hand.id}`} target="_blank" rel="noopener noreferrer"
          style={{ padding: '4px 12px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: 'rgba(245,158,11,0.1)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.2)', textDecoration: 'none' }}
        >Detalhe</a>
      </div>

      {/* Villains */}
      {hasVillains && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4, fontWeight: 600 }}>
            Villains (VPIP)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {hand.villains.map((v, i) => <VillainRow key={i} v={v} />)}
          </div>
        </div>
      )}

      {/* Screenshot players */}
      {hasSsPlayers && (
        <div>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4, fontWeight: 600 }}>
            Mesa (Screenshot)
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {Object.entries(hand.screenshot_players).map(([pos, data]) => {
              const name = typeof data === 'string' ? data : data?.name || '?'
              const bounty = typeof data === 'object' ? (data?.bounty_pct || data?.bounty) : null
              const country = typeof data === 'object' ? (data?.country_flag || data?.country) : null
              return (
                <div key={pos} style={{
                  display: 'flex', alignItems: 'center', gap: 4,
                  background: 'rgba(255,255,255,0.02)', borderRadius: 3, padding: '2px 6px',
                  border: '1px solid rgba(255,255,255,0.04)', fontSize: 11,
                }}>
                  <PosBadge pos={pos} />
                  <span style={{ color: '#94a3b8' }}>{name}</span>
                  {bounty ? <span style={{ color: '#f59e0b', fontSize: 9 }}>{bounty}</span> : null}
                  {country ? <span style={{ fontSize: 9 }}>{country}</span> : null}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {!hasVillains && !hasSsPlayers && (
        <div style={{ fontSize: 11, color: '#4b5563', fontStyle: 'italic' }}>
          Sem dados adicionais
        </div>
      )}

      {/* Delete SS (apagar mão já está no HandRow) */}
      {hand.has_screenshot && hand.screenshot_entry_id && (
        <div style={{ display: 'flex', gap: 8, marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          <button
            onClick={() => onDeleteScreenshot(hand.screenshot_entry_id)}
            style={{
              padding: '3px 10px', borderRadius: 4, fontSize: 11, fontWeight: 600,
              background: 'rgba(239,68,68,0.08)', color: '#ef4444',
              border: '1px solid rgba(239,68,68,0.2)', cursor: 'pointer',
            }}
          >Apagar Screenshot</button>
        </div>
      )}
    </div>
  )
}

// ── Tournament Group ─────────────────────────────────────────────────────────

function TournamentGroup({
  tmNumber, tournamentName, hands, tmSummary, onLoadHands, defaultSite,
  expandedHands, toggleHand, onDeleteHand, onDeleteScreenshot,
}) {
  const [open, setOpen] = useState(false)
  const [loadingHands, setLoadingHands] = useState(false)
  const isLazy = hands === undefined
  const loadedHands = hands || []

  // Quando é lazy e o grupo abre pela primeira vez, dispara o fetch.
  useEffect(() => {
    if (open && isLazy && !loadingHands && onLoadHands) {
      setLoadingHands(true)
      Promise.resolve(onLoadHands(tmNumber)).finally(() => setLoadingHands(false))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // Header stats — preferir tmSummary (vem do endpoint /dates, sempre presente em lazy).
  const ssCount = loadedHands.filter(h => h.has_screenshot).length
  const totalVillains = tmSummary?.villain_count
    ?? loadedHands.reduce((a, h) => a + (h.villain_count || 0), 0)
  const handCount = tmSummary?.hand_count ?? loadedHands.length

  const buyIn = tmSummary?.buy_in ?? loadedHands.find(h => h.buy_in != null)?.buy_in
  const fmtBuyIn = v => (v % 1 === 0 ? `$${v}` : `$${v.toFixed(2)}`)

  // Sumário pode vir do servidor (lazy) ou derivar-se das hands (eager).
  const newest = loadedHands[0]
  const oldest = loadedHands[loadedHands.length - 1]
  const blindsFirstRaw = tmSummary?.blinds_first ?? oldest?.blinds
  const blindsLastRaw  = tmSummary?.blinds_last  ?? newest?.blinds
  const blindsFirst = blindsFirstRaw ? cleanBlinds(blindsFirstRaw) : null
  const blindsLast  = blindsLastRaw  ? cleanBlinds(blindsLastRaw)  : null
  const firstTs = tmSummary?.first_played_at ?? oldest?.played_at
  const lastTs  = tmSummary?.last_played_at  ?? newest?.played_at
  const timeRange = formatDayTimeRange(firstTs, lastTs)
  const formatBadge = tmSummary?.tournament_format
    ?? loadedHands.find(h => h.tournament_format)?.tournament_format

  const displayName = cleanTournamentName(tournamentName)

  // Site para gradient/logo + W/L/BB derivados de loadedHands. Em modo lazy
  // (loadedHands vazio até abrir), wins/losses/bb passam null e o header
  // oculta a secção stats — evita "0W 0L +0.0 BB" enganador.
  const hasHands = loadedHands.length > 0
  const site = loadedHands.find(h => h.site)?.site || defaultSite
  const wins = hasHands ? loadedHands.filter(h => Number(h.result) > 0).length : null
  const losses = hasHands ? loadedHands.filter(h => Number(h.result) < 0).length : null
  const bbResult = hasHands ? loadedHands.reduce((a, h) => a + (Number(h.result) || 0), 0) : null

  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.05)',
      borderRadius: 12, marginBottom: 4, overflow: 'hidden',
    }}>
      <TournamentHeader
        site={site}
        tournamentName={displayName}
        tournamentNumber={tmNumber}
        timeRangeOverride={timeRange}
        handCount={handCount}
        wins={wins}
        losses={losses}
        bbResult={bbResult}
        buyIn={buyIn}
        blindsFirst={blindsFirst}
        blindsLast={blindsLast}
        tournamentFormat={formatBadge}
        ssCount={isLazy ? null : ssCount}
        villainCount={totalVillains}
        expanded={open}
        onToggle={() => setOpen(!open)}
        isLast
      />

      {/* Hands list */}
      {open && (
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          {loadingHands && loadedHands.length === 0 && (
            <div style={{ padding: '10px 12px', fontSize: 11, color: '#f59e0b' }}>
              A carregar mãos...
            </div>
          )}
          {loadedHands.map((h, idx) => (
            <div key={h.id}>
              <HandRow
                hand={h}
                idx={idx}
                onClick={() => toggleHand(h.id)}
                onDelete={onDeleteHand}
              />
              {expandedHands.has(h.id) && (
                <TournamentDetail
                  hand={h}
                  onDeleteHand={onDeleteHand}
                  onDeleteScreenshot={onDeleteScreenshot}
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Date Group ───────────────────────────────────────────────────────────────

function DateGroup({
  dateKey, dateLabel, tournaments, dateSummary, onLoadTournamentHands, handsByTm,
  expandedHands, toggleHand, onDeleteHand, onDeleteScreenshot, defaultSite,
}) {
  const [open, setOpen] = useState(false)

  // `tournaments` pode vir em 2 formatos:
  //  - Array (lazy, /mtt/dates): [{tm, name, hand_count, ...}]
  //  - Objecto (eager, aba Com SS): { TM123: {name, hands: [...]} }
  const isLazy = Array.isArray(tournaments)

  const tmList = isLazy
    ? tournaments
    : Object.entries(tournaments).map(([tm, v]) => ({ tm, name: v.name, hands: v.hands }))

  const totalHands = isLazy
    ? (dateSummary?.hand_count ?? tmList.reduce((a, t) => a + (t.hand_count || 0), 0))
    : tmList.reduce((a, t) => a + t.hands.length, 0)
  const totalSS = isLazy
    ? null  // desconhecido sem fetch de mãos; na aba "Sem SS" é sempre 0 por definição
    : tmList.reduce((a, t) => a + t.hands.filter(h => h.has_screenshot).length, 0)

  return (
    <div style={{ marginBottom: 8 }}>
      {/* Date header */}
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px',
          cursor: 'pointer', background: 'rgba(255,255,255,0.03)',
          borderRadius: 6, border: '1px solid rgba(255,255,255,0.06)',
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
        onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
      >
        <span style={{ color: '#f59e0b', fontSize: 13 }}>{open ? '▼' : '▶'}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0' }}>{dateLabel}</span>
        <span style={{ fontSize: 11, color: '#6366f1' }}>
          {tmList.length} torneio{tmList.length !== 1 ? 's' : ''}
        </span>
        {totalSS !== null && (
          <span style={{ fontSize: 11, color: '#22c55e' }}>
            {totalSS} SS
          </span>
        )}
        <span style={{ fontSize: 11, color: '#94a3b8' }}>
          {totalHands} mãos
        </span>
      </div>

      {/* Tournaments */}
      {open && (
        <div style={{ paddingLeft: 16, paddingTop: 4 }}>
          {tmList.map(t => (
            <TournamentGroup
              key={t.tm}
              tmNumber={t.tm}
              tournamentName={t.name}
              hands={isLazy ? handsByTm?.[t.tm] : t.hands}
              tmSummary={isLazy ? t : undefined}
              defaultSite={defaultSite}
              onLoadHands={isLazy ? onLoadTournamentHands : undefined}
              expandedHands={expandedHands}
              toggleHand={toggleHand}
              onDeleteHand={onDeleteHand}
              onDeleteScreenshot={onDeleteScreenshot}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function TournamentsPage() {
  const [tab, setTab] = useState('gg') // 'gg' or 'hm3'
  const [hands, setHands] = useState([])
  const [stats, setStats] = useState(null)
  const [notaStats, setNotaStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState({ ss_filter: 'with' })
  const [expandedHands, setExpandedHands] = useState(new Set())

  // ── Estado lazy (aba Sem SS) ─────────────────────────────────────────────
  const [dateIndex, setDateIndex] = useState({ dates: [], total_dates: 0, total_hands: 0, has_more: false })
  const [dateOffset, setDateOffset] = useState(0)
  const [dateRange, setDateRange] = useState(null)     // null | '1d' | '3d' | '7d' | '15d' | '30d'
  const [formatFilter, setFormatFilter] = useState(null) // null | 'PKO' | 'NPKO'
  const [handsByTm, setHandsByTm] = useState({})         // { TM123: [hands...] } cache por expansão
  const [loadingMore, setLoadingMore] = useState(false)

  // GG (Com SS e Sem SS) passa a usar o fluxo lazy /mtt/dates. HM3 continua eager.
  const isLazyTab = tab === 'gg'
  // Pills de range/formato só fazem sentido em "Sem SS" (46k+ mãos).
  const showRangeAndFormatPills = tab === 'gg' && filter.ss_filter === 'without'

  const loadHands = useCallback(async () => {
    setLoading(true)
    try {
      if (tab === 'gg') {
        const params = {
          ss_filter: filter.ss_filter || 'without',
          limit_dates: 8,
          offset_dates: 0,
        }
        if (showRangeAndFormatPills && dateRange) params.date_range = dateRange
        if (showRangeAndFormatPills && formatFilter) params.format = formatFilter
        if (filter.tm_search) params.tm_search = filter.tm_search
        const data = await mtt.dates(params)
        setDateIndex(data)
        setDateOffset(0)
        setHandsByTm({})
        setHands([])
      } else {
        const { hm3 } = await import('../api/client')
        const data = await hm3.notaHands({ page: 1, page_size: 200 })
        setHands(data.hands || [])
      }
    } catch (e) {
      console.error('Erro a carregar mãos:', e)
    } finally {
      setLoading(false)
    }
  }, [filter, tab, dateRange, formatFilter, showRangeAndFormatPills])

  const loadMoreDates = useCallback(async () => {
    if (!isLazyTab || !dateIndex.has_more || loadingMore) return
    setLoadingMore(true)
    try {
      const nextOffset = dateOffset + 8
      const params = {
        ss_filter: filter.ss_filter || 'without',
        limit_dates: 8,
        offset_dates: nextOffset,
      }
      if (showRangeAndFormatPills && dateRange) params.date_range = dateRange
      if (showRangeAndFormatPills && formatFilter) params.format = formatFilter
      if (filter.tm_search) params.tm_search = filter.tm_search
      const data = await mtt.dates(params)
      setDateIndex(prev => ({
        ...data,
        dates: [...prev.dates, ...data.dates],
      }))
      setDateOffset(nextOffset)
    } catch (e) {
      console.error('Erro a carregar mais datas:', e)
    } finally {
      setLoadingMore(false)
    }
  }, [isLazyTab, dateIndex.has_more, dateOffset, dateRange, formatFilter,
      filter.ss_filter, filter.tm_search, loadingMore, showRangeAndFormatPills])

  const loadTournamentHands = useCallback(async (tmNumber) => {
    // tmNumber vem como "TM1234..." — usar como tm_search no endpoint existente.
    try {
      const tmDigits = tmNumber.startsWith('TM') ? tmNumber.slice(2) : tmNumber
      const data = await mtt.hands({
        ss_filter: filter.ss_filter || 'without',
        tm_search: tmDigits,
        page: 1,
        page_size: 200,
      })
      setHandsByTm(prev => ({ ...prev, [tmNumber]: data.hands || [] }))
    } catch (e) {
      console.error(`Erro a carregar mãos do torneio ${tmNumber}:`, e)
      setHandsByTm(prev => ({ ...prev, [tmNumber]: [] }))
    }
  }, [filter.ss_filter])

  const loadStats = useCallback(async () => {
    try {
      const data = await mtt.stats()
      setStats(data)
      const { hm3 } = await import('../api/client')
      const ns = await hm3.notaStats()
      setNotaStats(ns)
    } catch (e) {
      console.error('Erro a carregar stats:', e)
    }
  }, [])

  useEffect(() => { loadHands() }, [loadHands])
  useEffect(() => { loadStats() }, [loadStats])

  const toggleHand = useCallback((id) => {
    setExpandedHands(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const handleDeleteHand = async (handId) => {
    if (!confirm('Apagar esta mão e vilões associados?')) return
    try {
      await mtt.deleteHand(handId)
      loadHands()
      loadStats()
    } catch (e) {
      alert('Erro ao apagar: ' + e.message)
    }
  }

  const handleDeleteScreenshot = async (entryId) => {
    if (!confirm('Apagar screenshot e reverter match?')) return
    try {
      await mtt.deleteScreenshot(entryId)
      loadHands()
      loadStats()
    } catch (e) {
      alert('Erro ao apagar screenshot: ' + e.message)
    }
  }

  // Agrupar por data > torneio — só HM3 (GG passou a lazy via /mtt/dates).
  // Chave = TM number sempre que possível.
  const grouped = {}
  if (tab === 'hm3') {
    for (const h of hands) {
      const dateKey = formatDateKey(h.played_at)
      if (!grouped[dateKey]) grouped[dateKey] = {}
      const tmLabel =
        h.tm_number
        || (h.tournament_number ? `TM${h.tournament_number}` : null)
      const tourneyKey = tmLabel || h.tournament_name || h.stakes || 'unknown'
      if (!grouped[dateKey][tourneyKey]) {
        grouped[dateKey][tourneyKey] = { name: h.tournament_name || h.stakes, hands: [] }
      }
      grouped[dateKey][tourneyKey].hands.push(h)
    }
  }
  const sortedDates = Object.keys(grouped).sort((a, b) => b.localeCompare(a))

  const tabStyle = (active) => ({
    padding: '8px 24px', borderRadius: '6px 6px 0 0', fontSize: 14, fontWeight: 700,
    cursor: 'pointer', border: 'none', transition: 'all 0.2s',
    background: active ? '#1e2130' : 'transparent',
    color: active ? '#e2e8f0' : '#64748b',
    borderBottom: active ? '2px solid #6366f1' : '2px solid transparent',
  })

  return (
    <div style={{ padding: '24px 32px' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0', marginBottom: 4 }}>MTT</h1>
      <p style={{ fontSize: 13, color: '#64748b', marginBottom: 16 }}>
        Mãos de torneios para estudo
      </p>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <button style={tabStyle(tab === 'gg')} onClick={() => { setTab('gg'); setFilter({ ss_filter: 'with' }) }}>
          GG
          {stats && <span style={{ fontSize: 11, color: '#22c55e', marginLeft: 8 }}>{stats.hands_with_screenshot || 0}</span>}
        </button>
        <button style={tabStyle(tab === 'hm3')} onClick={() => { setTab('hm3'); setFilter({}) }}>
          HM3 com Nota
          {notaStats && <span style={{ fontSize: 11, color: '#f59e0b', marginLeft: 8 }}>{notaStats.total_hands || 0}</span>}
        </button>
      </div>

      {/* Stats bar */}
      {tab === 'gg' && <StatsBar stats={stats} />}
      {tab === 'hm3' && notaStats && (
        <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
          {[
            { label: 'Mãos', value: notaStats.total_hands, color: '#e2e8f0' },
            { label: 'Com Showdown', value: notaStats.with_showdown, color: '#8b5cf6' },
            { label: 'Torneios', value: notaStats.tournaments, color: '#6366f1' },
            { label: 'Salas', value: notaStats.sites, color: '#f59e0b' },
          ].map(({ label, value, color }) => (
            <div key={label} style={{
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 6, padding: '6px 14px',
            }}>
              <span style={{ fontSize: 16, fontWeight: 700, color, fontFamily: 'monospace' }}>{value}</span>
              <span style={{ fontSize: 11, color: '#4b5563', marginLeft: 6 }}>{label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Sub-navegação GG: Com SS / Sem SS */}
      {tab === 'gg' && (
        <div style={{
          display: 'inline-flex', gap: 4, marginBottom: 12, padding: 3,
          background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 8,
        }}>
          {[
            { value: 'with',    label: 'Com SS', color: '#22c55e' },
            { value: 'without', label: 'Sem SS', color: '#94a3b8' },
          ].map(({ value, label, color }) => {
            const active = filter.ss_filter === value
            return (
              <button
                key={value}
                onClick={() => setFilter(f => ({ ...f, ss_filter: value }))}
                style={{
                  padding: '6px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                  border: 'none', cursor: 'pointer',
                  background: active ? color : 'transparent',
                  color: active ? '#0a0c14' : color,
                  transition: 'all 0.15s',
                }}
              >{label}</button>
            )
          })}
        </div>
      )}

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        {tab === 'gg' && (
          <input
            type="text"
            placeholder="Pesquisar TM..."
            value={filter.tm_search || ''}
            onChange={(e) => setFilter(f => ({ ...f, tm_search: e.target.value }))}
            style={{
              background: '#1e2130', color: '#e2e8f0', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 4, padding: '4px 8px', fontSize: 12, width: 160,
            }}
          />
        )}

        {/* Pills de janela temporal + filtro formato — só aba Sem SS. */}
        {showRangeAndFormatPills && (
          <>
            <div style={{
              display: 'inline-flex', gap: 2, padding: 2,
              background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 6,
            }}>
              {[
                { value: null,  label: 'Default' },
                { value: '1d',  label: '1d' },
                { value: '3d',  label: '3d' },
                { value: '7d',  label: '7d' },
                { value: '15d', label: '15d' },
                { value: '30d', label: '30d' },
              ].map(({ value, label }) => {
                const active = dateRange === value
                return (
                  <button
                    key={label}
                    onClick={() => setDateRange(value)}
                    style={{
                      padding: '4px 10px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                      border: 'none', cursor: 'pointer',
                      background: active ? '#6366f1' : 'transparent',
                      color: active ? '#0a0c14' : '#94a3b8',
                    }}
                  >{label}</button>
                )
              })}
            </div>

            <div style={{
              display: 'inline-flex', gap: 2, padding: 2,
              background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 6,
            }}>
              {[
                { value: null,      label: 'Todos',   color: '#94a3b8' },
                { value: 'PKO',     label: 'PKO',     color: '#f59e0b' },
                { value: 'Vanilla', label: 'Vanilla', color: '#64748b' },
              ].map(({ value, label, color }) => {
                const active = formatFilter === value
                return (
                  <button
                    key={label}
                    onClick={() => setFormatFilter(value)}
                    style={{
                      padding: '4px 10px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                      border: 'none', cursor: 'pointer',
                      background: active ? color : 'transparent',
                      color: active ? '#0a0c14' : color,
                    }}
                  >{label}</button>
                )
              })}
            </div>
          </>
        )}
      </div>

      {/* Render eager — só HM3 agora. */}
      {tab === 'hm3' && (
        loading ? (
          <div style={{ color: '#f59e0b', padding: 20 }}>A carregar...</div>
        ) : sortedDates.length === 0 ? (
          <div style={{ color: '#4b5563', padding: 20, textAlign: 'center' }}>
            Nenhuma mão HM3 com tag nota encontrada.
          </div>
        ) : (
          <div>
            {sortedDates.map(dateKey => (
              <DateGroup
                key={dateKey}
                dateKey={dateKey}
                dateLabel={formatDateLabel(dateKey + 'T12:00:00')}
                tournaments={grouped[dateKey]}
                expandedHands={expandedHands}
                toggleHand={toggleHand}
                onDeleteHand={handleDeleteHand}
                onDeleteScreenshot={handleDeleteScreenshot}
              />
            ))}
          </div>
        )
      )}

      {/* Render lazy — toda a aba GG (Com SS e Sem SS). */}
      {tab === 'gg' && (
        loading ? (
          <div style={{ color: '#f59e0b', padding: 20 }}>A carregar...</div>
        ) : dateIndex.dates.length === 0 ? (
          <div style={{ color: '#4b5563', padding: 20, textAlign: 'center' }}>
            {filter.ss_filter === 'without'
              ? 'Nenhuma mão GG sem SS encontrada.'
              : 'Nenhuma mão GG com SS encontrada.'}
          </div>
        ) : (
          <div>
            <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8 }}>
              {dateIndex.total_hands.toLocaleString()} mãos em {dateIndex.total_dates} dia{dateIndex.total_dates !== 1 ? 's' : ''}
              {dateIndex.dates.length < dateIndex.total_dates && ` · ${dateIndex.dates.length} visíveis`}
            </div>
            {dateIndex.dates.map(d => (
              <DateGroup
                key={d.date_key}
                dateKey={d.date_key}
                dateLabel={formatDateLabel(d.date_key + 'T12:00:00')}
                tournaments={d.tournaments}
                dateSummary={d}
                defaultSite="GGPoker"
                handsByTm={handsByTm}
                onLoadTournamentHands={async (tm) => {
                  if (handsByTm[tm] !== undefined) return
                  await loadTournamentHands(tm)
                }}
                expandedHands={expandedHands}
                toggleHand={toggleHand}
                onDeleteHand={handleDeleteHand}
                onDeleteScreenshot={handleDeleteScreenshot}
              />
            ))}
            {dateIndex.has_more && !dateRange && (
              <div style={{ textAlign: 'center', marginTop: 12 }}>
                <button
                  onClick={loadMoreDates}
                  disabled={loadingMore}
                  style={{
                    padding: '8px 20px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                    background: 'rgba(99,102,241,0.1)', color: '#818cf8',
                    border: '1px solid rgba(99,102,241,0.2)', cursor: loadingMore ? 'wait' : 'pointer',
                  }}
                >{loadingMore ? 'A carregar...' : 'Ver mais 8 dias'}</button>
              </div>
            )}
          </div>
        )
      )}
    </div>
  )
}
