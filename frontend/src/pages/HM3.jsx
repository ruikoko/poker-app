import { useEffect, useState, useCallback } from 'react'
import { hands, hm3 } from '../api/client'
import Replayer from '../components/Replayer'
import HandRow from '../components/HandRow'
import HandHistoryViewer from '../components/HandHistoryViewer'
import TournamentHeader from '../components/TournamentHeader'

// ── Constants ────────────────────────────────────────────────────────────────

const SUIT_BG = { h: '#dc2626', d: '#2563eb', c: '#16a34a', s: '#1e293b' }

const STATES = [
  { v: '',         l: 'Todos os estados' },
  { v: 'new',      l: 'Novas' },
  { v: 'resolved', l: 'Revistas' },
]

const STATE_META = {
  new:      { label: 'Nova',    color: '#3b82f6', bg: 'rgba(59,130,246,0.15)' },
  resolved: { label: 'Revista', color: '#22c55e', bg: 'rgba(34,197,94,0.15)' },
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function PokerCard({ card, size = 'sm' }) {
  if (!card || card.length < 2) return <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 24, height: 34, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 3, fontSize: 11, color: '#4b5563' }}>?</span>
  const rank = card.slice(0, -1).toUpperCase()
  const suit = card.slice(-1).toLowerCase()
  const bg = SUIT_BG[suit] || '#1e2130'
  const w = size === 'lg' ? 38 : size === 'md' ? 34 : 24
  const h = size === 'lg' ? 50 : size === 'md' ? 46 : 34
  const fsRank = size === 'lg' ? 20 : size === 'md' ? 16 : 14
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: w, height: h, background: bg, border: '1px solid rgba(255,255,255,0.2)', borderRadius: 3, fontFamily: "'Fira Code', monospace", fontSize: fsRank, fontWeight: 700, color: '#fff', lineHeight: 1, boxShadow: '0 1px 2px rgba(0,0,0,0.3)', userSelect: 'none' }}>{rank}</span>
  )
}

function StateBadge({ state }) {
  const meta = STATE_META[state] || { label: state, color: '#666', bg: 'rgba(100,100,100,0.15)' }
  return <span style={{ display: 'inline-block', padding: '2px 9px', borderRadius: 999, fontSize: 11, fontWeight: 600, letterSpacing: 0.3, color: meta.color, background: meta.bg }}>{meta.label}</span>
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ display: 'inline-block', width: 48, textAlign: 'center', color: '#4b5563' }}>&mdash;</span>
  const colors = { BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa', SB: '#f59e0b', BB: '#ef4444', UTG: '#22c55e', UTG1: '#16a34a', UTG2: '#15803d', MP: '#06b6d4', MP1: '#0891b2' }
  const c = colors[pos] || '#64748b'
  const isBlind = pos === 'SB' || pos === 'BB'
  return <span style={{ display: 'inline-block', padding: '2px 0', borderRadius: 4, width: 48, textAlign: 'center', fontSize: 11, fontWeight: 700, letterSpacing: 0.5, color: '#0a0c14', background: isBlind ? c : '#e2e8f0', border: `1px solid ${isBlind ? c : '#e2e8f0'}` }}>{pos}</span>
}

function ResultBadge({ result }) {
  if (result == null) return <span style={{ color: '#4b5563' }}>&mdash;</span>
  const val = Number(result)
  if (val > 0) return <span style={{ color: '#22c55e', fontWeight: 600, fontFamily: 'monospace' }}>+{val.toFixed(1)} BB</span>
  if (val < 0) return <span style={{ color: '#ef4444', fontWeight: 600, fontFamily: 'monospace' }}>{val.toFixed(1)} BB</span>
  return <span style={{ color: '#64748b', fontFamily: 'monospace' }}>0 BB</span>
}

function Tag({ t }) {
  const colors = { icm: '#6366f1', pko: '#f59e0b', ko: '#f59e0b', pos: '#22c55e', bvb: '#8b5cf6', ss: '#ef4444', ft: '#06b6d4', nota: '#64748b', 'nota++': '#818cf8', 'ICM PKO': '#f59e0b', 'PKO pos': '#22c55e', 'For Review': '#3b82f6', GTw: '#06b6d4', 'MW PKO': '#fb923c' }
  const c = colors[t] || '#64748b'
  return <span style={{ display: 'inline-block', padding: '1px 7px', borderRadius: 999, fontSize: 11, fontWeight: 600, marginRight: 3, color: c, background: `${c}18`, border: `1px solid ${c}30` }}>#{t}</span>
}

function extractLevel(raw) {
  if (!raw) return null
  const wn = raw.match(/level:\s*(\d+)/i)
  if (wn) return `Lv ${wn[1]}`
  const ps = raw.match(/Level\s+([IVXLCDM]+|\d+)/i)
  if (ps) {
    const v = ps[1]
    const roman = { I:1, V:5, X:10, L:50, C:100, D:500, M:1000 }
    if (/^[IVXLCDM]+$/i.test(v)) {
      let num = 0
      for (let i = 0; i < v.length; i++) {
        const cur = roman[v[i].toUpperCase()] || 0
        const next = roman[v[i+1]?.toUpperCase()] || 0
        num += cur < next ? -cur : cur
      }
      return `Lv ${num}`
    }
    return `Lv ${v}`
  }
  return null
}

// ── Detail Modal ─────────────────────────────────────────────────────────────

function HandDetailModal({ hand, onClose, onUpdate }) {
  const [notes, setNotes] = useState(hand.notes || '')
  const [tags, setTags] = useState((hand.tags || []).join(', '))
  const [saving, setSaving] = useState(false)
  const [copied, setCopied] = useState(false)

  const level = extractLevel(hand.raw)

  async function save() {
    setSaving(true)
    try {
      const tagList = tags.split(',').map(t => t.trim()).filter(Boolean)
      await hands.update(hand.id, { notes, tags: tagList })
      onUpdate()
    } catch (e) { alert(e.message) }
    finally { setSaving(false) }
  }

  async function changeState(newState) {
    try { await hands.update(hand.id, { study_state: newState }); onUpdate() }
    catch (e) { alert(e.message) }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, backdropFilter: 'blur(4px)' }} onClick={onClose}>
      <div style={{ width: '92%', maxWidth: 800, maxHeight: '90vh', overflow: 'auto', background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12, padding: 28 }} onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <span style={{ fontWeight: 700, fontSize: 17 }}>Mão #{hand.id}</span>
              <StateBadge state={hand.study_state} />
              {hand.result != null && <ResultBadge result={hand.result} />}
            </div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              {hand.stakes && <span style={{ fontSize: 12, color: '#64748b' }}>{hand.stakes}</span>}
              {(() => {
                const m = hand.all_players_actions?._meta
                if (m || level) {
                  return <span style={{ fontSize: 11, color: '#4b5563', fontFamily: 'monospace', fontWeight: 600 }}>
                    {level || ''}{m ? ` · ${Math.round(m.sb)}/${Math.round(m.bb)}${m.ante ? `(${Math.round(m.ante)})` : ''}` : ''}
                  </span>
                }
                return null
              })()}
              <span style={{ fontSize: 11, color: '#4b5563' }}>{hand.site} &middot; {hand.played_at ? hand.played_at.slice(0, 10) : ''}</span>
            </div>
          </div>
          <button style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 18, padding: 4 }} onClick={onClose}>&#10005;</button>
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          {hand.raw && (
            <button onClick={() => { navigator.clipboard.writeText(hand.raw); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
              style={{ padding: '5px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600, background: copied ? 'rgba(34,197,94,0.15)' : 'rgba(34,197,94,0.1)', color: '#22c55e', border: `1px solid ${copied ? 'rgba(34,197,94,0.3)' : 'rgba(34,197,94,0.2)'}`, cursor: 'pointer' }}
            >{copied ? '✓ Copiado' : 'Copiar HH'}</button>
          )}
          {hand.raw && hand.all_players_actions && (
            <a href={`/replayer/${hand.id}`} target="_blank" rel="noopener noreferrer"
              style={{ padding: '5px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600, background: 'rgba(99,102,241,0.1)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.2)', cursor: 'pointer', textDecoration: 'none' }}
            >&#9654; Replayer</a>
          )}
          <a href={`/hand/${hand.id}`} target="_blank" rel="noopener noreferrer"
            style={{ padding: '5px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600, background: 'rgba(245,158,11,0.1)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.2)', cursor: 'pointer', textDecoration: 'none' }}
          >Detalhe</a>
        </div>

        {/* Info Grid */}
        {(() => {
          const m = hand.all_players_actions?._meta || {}
          const blindsLabel = m.sb && m.bb ? `${Math.round(m.sb)}/${Math.round(m.bb)}${m.ante ? `(${Math.round(m.ante)})` : ''}` : ''
          const resultColor = hand.result > 0 ? '#22c55e' : hand.result < 0 ? '#ef4444' : '#64748b'
          return (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginBottom: 14 }}>
              {[
                { l: 'SALA', v: hand.site },
                { l: 'DATA', v: hand.played_at ? hand.played_at.slice(0, 10) : '—' },
                { l: 'RESULTADO', v: hand.result != null ? `${hand.result > 0 ? '+' : ''}${Number(hand.result).toFixed(1)} BB` : '—', c: resultColor },
                { l: 'POSIÇÃO', v: null, badge: hand.position },
                { l: 'TORNEIO', v: hand.stakes || '—' },
                { l: 'HAND ID', v: hand.hand_id || '—' },
                { l: 'BLINDS', v: blindsLabel || '—' },
                { l: 'LEVEL', v: level || (m.level != null ? `Lv ${m.level}` : '—') },
                { l: 'JOGADORES', v: Object.keys(hand.all_players_actions || {}).filter(k => k !== '_meta').length || '—' },
              ].map(({ l, v, c, badge }) => (
                <div key={l} style={{ background: '#0f1117', borderRadius: 6, padding: '8px 12px' }}>
                  <div style={{ fontSize: 10, color: '#64748b', fontWeight: 700, letterSpacing: 0.5, marginBottom: 3 }}>{l}</div>
                  {badge ? <PosBadge pos={badge} /> : <div style={{ fontSize: 13, color: c || '#f1f5f9', fontWeight: 700, wordBreak: 'break-all' }}>{v}</div>}
                </div>
              ))}
            </div>
          )
        })()}
        <div style={{ background: '#0f1117', borderRadius: 10, padding: '16px 20px', marginBottom: 20, display: 'flex', gap: 32, alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Hero &middot; <PosBadge pos={hand.position} /></div>
            <div style={{ display: 'flex', gap: 5 }}>
              {hand.hero_cards?.length > 0 ? hand.hero_cards.map((c, i) => <PokerCard key={i} card={c} size="lg" />) : <span style={{ color: '#4b5563', fontSize: 13 }}>Cartas não visíveis</span>}
            </div>
          </div>
          {hand.board?.length > 0 && (
            <div>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Board</div>
              <div style={{ display: 'flex', gap: 5 }}>{hand.board.slice(0, 5).map((c, i) => <PokerCard key={i} card={c} size="lg" />)}</div>
            </div>
          )}
        </div>

        {/* Tags */}
        {hand.tags?.length > 0 && (
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 16 }}>
            {hand.tags.map(t => <Tag key={t} t={t} />)}
          </div>
        )}

        {/* Tech Debt #8: HandHistoryViewer canónico (substitui parseRawHH local + bloco render). */}
        <HandHistoryViewer hand={hand} />

        {/* Replayer */}
        {hand.raw && hand.all_players_actions && (
          <>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 6 }}>
              <a href={`/replayer/${hand.id}`} target="_blank" rel="noopener noreferrer" style={{
                fontSize: 11, fontWeight: 600, color: '#818cf8', textDecoration: 'none',
                padding: '4px 12px', borderRadius: 5, background: 'rgba(99,102,241,0.1)',
                border: '1px solid rgba(99,102,241,0.25)', display: 'inline-flex', alignItems: 'center', gap: 4,
              }}>&#9654; Fullscreen</a>
            </div>
            <Replayer hand={hand} />
          </>
        )}

        {/* Notes */}
        <div style={{ marginBottom: 14 }}>
          <label style={{ fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 6, color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.5 }}>Notas de Estudo</label>
          <textarea rows={3} style={{ width: '100%', fontSize: 13, background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '8px 12px', fontFamily: 'inherit', resize: 'vertical' }} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Adicionar notas..." />
        </div>

        {/* Tags edit */}
        <div style={{ marginBottom: 20 }}>
          <label style={{ fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 6, color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.5 }}>Tags (separadas por vírgula)</label>
          <input type="text" style={{ width: '100%', fontSize: 13, background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '8px 12px' }} value={tags} onChange={e => setTags(e.target.value)} placeholder="ICM PKO, nota++..." />
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', borderTop: '1px solid #2a2d3a', paddingTop: 16 }}>
          <button style={{ padding: '7px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: '#6366f1', color: '#fff', border: 'none', cursor: 'pointer', opacity: saving ? 0.6 : 1 }} disabled={saving} onClick={save}>{saving ? 'A guardar...' : 'Guardar'}</button>
          {hand.study_state !== 'resolved' && <button style={{ padding: '7px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: 'rgba(34,197,94,0.12)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.3)', cursor: 'pointer' }} onClick={() => changeState('resolved')}>Revista &#10003;</button>}
        </div>
      </div>
    </div>
  )
}

// ── Day Group (collapsible) ───────────────────────────────────────────────────

// Normaliza tournament_format legacy (dual-accept) para display case-exact.
// Legacy 'KO' e' mapeado para 'PKO' conforme decidido no D3.
function normalizeFormat(fmt) {
  if (!fmt) return null
  const f = fmt.toString().trim().toLowerCase()
  if (f === 'super ko') return 'Super KO'
  if (f === 'mystery ko' || f === 'mystery') return 'Mystery KO'
  if (f === 'vanilla') return 'Vanilla'
  if (f === 'pko' || f === 'ko') return 'PKO'
  return fmt
}

// Compoe o titulo unificado a partir dos campos estruturados das maos do grupo.
// Segmentos em falta sao omitidos (separador ' · ' nao aparece entre vazios).
// H1/H2 vem de min/max de played_at do grupo.
// Cada campo faz fallback-through-all: procura a primeira mao do grupo que
// tenha o campo populado (defensivo contra primeira mao ter NULL isolado).
function composeTournamentTitle(hands) {
  if (!hands || hands.length === 0) return 'Sem torneio'

  const site = hands.find(h => h.site)?.site || ''
  const name = hands.find(h => h.tournament_name)?.tournament_name || ''
  const tid = hands.find(h => h.tournament_number)?.tournament_number || ''
  const rawFmt = hands.find(h => h.tournament_format)?.tournament_format
  const fmt = normalizeFormat(rawFmt) || ''
  const buyinHand = hands.find(h => h.buy_in != null)
  const buyinNum = buyinHand ? Number(buyinHand.buy_in) : null
  // Currency heuristic: WPN usa $; outras salas usam €.
  const currency = (site === 'WPN') ? '$' : '€'
  const buyinStr = (buyinNum != null && !isNaN(buyinNum)) ? `${buyinNum}${currency}` : ''

  const times = hands.map(h => h.played_at).filter(Boolean).sort()
  const h1 = times.length ? times[0].slice(11, 16) : ''
  const h2 = times.length ? times[times.length - 1].slice(11, 16) : ''
  const timeRange = (h1 && h2) ? `${h1} → ${h2}` : ''

  const segs = []
  if (site) segs.push(site)
  if (name) segs.push(name)
  // buyin + fmt combinados num segmento (ex: '250€ PKO'); omitidos se ambos vazios.
  // WPN: omitir fmt — a prize-pool-string (tournament_name) ja e' a categoria,
  // evita redundancia tipo "... · $30,000 GTD Tournament · Vanilla · #...".
  const buyinFmt = (site === 'WPN')
    ? buyinStr
    : [buyinStr, fmt].filter(Boolean).join(' ')
  if (buyinFmt) segs.push(buyinFmt)
  if (tid) segs.push(`#${tid}`)
  if (timeRange) segs.push(timeRange)
  return segs.join(' · ')
}

// Agrega tags unicas das maos do grupo, ordenadas por frequencia DESC,
// depois alfabeticamente como tie-breaker.
function aggregateTags(hands) {
  const counts = {}
  for (const h of hands) {
    for (const t of (h.hm3_tags || [])) {
      if (!t) continue
      counts[t] = (counts[t] || 0) + 1
    }
  }
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([t]) => t)
}

function TournamentSubGroup({ hands, onOpenDetail, onDeleteHand }) {
  const [open, setOpen] = useState(false)
  const wins = hands.filter(h => h.result != null && Number(h.result) > 0).length
  const losses = hands.filter(h => h.result != null && Number(h.result) < 0).length
  const totalBB = hands.reduce((a, h) => a + (Number(h.result) || 0), 0)

  // Inline da lógica de composeTournamentTitle — campos separados em vez da
  // string monolítica, para alimentar TournamentHeader.
  const site = hands.find(h => h.site)?.site
  const tournamentName = hands.find(h => h.tournament_name)?.tournament_name
  const tournamentNumber = hands.find(h => h.tournament_number)?.tournament_number
  const rawFmt = hands.find(h => h.tournament_format)?.tournament_format
  const fmt = normalizeFormat(rawFmt) || ''
  const buyinHand = hands.find(h => h.buy_in != null)
  const buyIn = buyinHand ? Number(buyinHand.buy_in) : null
  // WPN: omitir fmt — a prize-pool-string (tournament_name) já é a categoria.
  const tournamentFormat = (site === 'WPN') ? null : (fmt || null)

  const times = hands.map(h => h.played_at).filter(Boolean).sort()
  const timeStart = times.length ? times[0].slice(11, 16) : undefined
  const timeEnd = times.length ? times[times.length - 1].slice(11, 16) : undefined

  const tags = aggregateTags(hands)

  return (
    <div style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
      <TournamentHeader
        site={site}
        tournamentName={tournamentName}
        tournamentNumber={tournamentNumber}
        timeStart={timeStart}
        timeEnd={timeEnd}
        handCount={hands.length}
        wins={wins}
        losses={losses}
        bbResult={totalBB}
        buyIn={buyIn}
        tournamentFormat={tournamentFormat}
        tags={tags}
        expanded={open}
        onToggle={() => setOpen(!open)}
        indent={18}
        isLast
      />
      {open && hands.map((h, idx) => (
        <HandRow
          key={h.id}
          hand={h}
          idx={idx}
          onClick={() => onOpenDetail(h.id)}
          onDelete={onDeleteHand}
        />
      ))}
    </div>
  )
}

function DayGroup({ dateKey, dateLabel, hands, wins, losses, totalBB, onOpenDetail, onDeleteHand }) {
  const [open, setOpen] = useState(false)

  // Sub-group by tournament_number (fallback stakes for legacy rows).
  // Grupos ordenados por min(played_at) ASC dentro do dia (ordem de inicio).
  const byTourney = {}
  for (const h of hands) {
    const key = h.tournament_number || h.stakes || 'Sem torneio'
    if (!byTourney[key]) byTourney[key] = []
    byTourney[key].push(h)
  }
  const tourneyKeys = Object.keys(byTourney).sort((a, b) => {
    const ta = byTourney[a].reduce((m, h) => h.played_at && (m == null || h.played_at < m) ? h.played_at : m, null) || ''
    const tb = byTourney[b].reduce((m, h) => h.played_at && (m == null || h.played_at < m) ? h.played_at : m, null) || ''
    return ta.localeCompare(tb)
  })

  return (
    <div style={{ marginBottom: 6, border: `1px solid ${open ? 'rgba(139,92,246,0.3)' : '#2a2d3a'}`, borderRadius: 10, overflow: 'hidden', transition: 'border-color 0.2s' }}>
      <div onClick={() => setOpen(!open)} style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 16px', background: open ? 'rgba(139,92,246,0.06)' : '#1a1d27',
        cursor: 'pointer', userSelect: 'none',
      }}
        onMouseEnter={e => { if (!open) e.currentTarget.style.background = '#1e2130' }}
        onMouseLeave={e => { if (!open) e.currentTarget.style.background = '#1a1d27' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ display: 'inline-block', fontSize: 11, color: '#8b5cf6', transform: open ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>&#9654;</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0' }}>{dateLabel}</span>
          <span style={{ fontSize: 12, color: '#6366f1' }}>{tourneyKeys.length} torneio{tourneyKeys.length !== 1 ? 's' : ''}</span>
          <span style={{ fontSize: 12, color: '#64748b' }}>{hands.length} {hands.length === 1 ? 'mão' : 'mãos'}</span>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', fontSize: 11 }}>
          <span style={{ color: '#22c55e' }}>{wins}W</span>
          <span style={{ color: '#ef4444' }}>{losses}L</span>
          <span style={{ color: totalBB >= 0 ? '#22c55e' : '#ef4444', fontWeight: 600, fontFamily: 'monospace' }}>
            {totalBB >= 0 ? '+' : ''}{totalBB.toFixed(1)} BB
          </span>
        </div>
      </div>
      {open && (
        <div>
          {tourneyKeys.map(tk => (
            <TournamentSubGroup
              key={tk}
              hands={byTourney[tk]}
              onOpenDetail={onOpenDetail}
              onDeleteHand={onDeleteHand}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main Page ────────────────────────────────────────────────────────────────

// ── Import Panel with date/nota filter ───────────────────────────────────────

function HM3ImportPanel({ onImported }) {
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState(null)
  const [daysBack, setDaysBack] = useState('7')
  const [notaOnly, setNotaOnly] = useState(true)
  const [reparsing, setReparsing] = useState(false)
  const [reparseResult, setReparseResult] = useState(null)

  const handleImport = async (files) => {
    if (!files || files.length === 0) return
    setImporting(true)
    setImportResult(null)
    try {
      const results = []
      for (const file of files) {
        const r = await hm3.import(file, { daysBack: daysBack || null, notaOnly })
        results.push(r)
      }
      const total = results.reduce((a, r) => ({
        inserted: a.inserted + (r.inserted || 0),
        skipped: a.skipped + (r.skipped_duplicates || 0),
        skippedDate: a.skippedDate + (r.skipped_date_filter || 0),
        skippedNota: a.skippedNota + (r.skipped_nota_filter || 0),
        villains: a.villains + (r.villains_created || 0),
      }), { inserted: 0, skipped: 0, skippedDate: 0, skippedNota: 0, villains: 0 })
      setImportResult(total)
      if (total.inserted > 0) onImported?.()
    } catch (e) {
      setImportResult({ error: e.message })
    } finally {
      setImporting(false)
    }
  }

  return (
    <div style={{
      background: 'rgba(139,92,246,0.04)', border: '1px solid rgba(139,92,246,0.15)',
      borderRadius: 8, padding: '14px 20px', marginBottom: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: '#a78bfa' }}>Importar CSV</span>
        <select value={daysBack} onChange={e => setDaysBack(e.target.value)} style={{
          background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6,
          color: '#e2e8f0', padding: '5px 10px', fontSize: 12,
        }}>
          <option value="">Todas as datas</option>
          <option value="3">Últimos 3 dias</option>
          <option value="7">Últimos 7 dias</option>
          <option value="14">Últimos 14 dias</option>
          <option value="30">Últimos 30 dias</option>
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#94a3b8', cursor: 'pointer' }}>
          <input type="checkbox" checked={notaOnly} onChange={e => setNotaOnly(e.target.checked)}
            style={{ accentColor: '#8b5cf6' }} />
          Só com tag nota
        </label>
        <label style={{
          padding: '6px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600,
          background: importing ? 'rgba(139,92,246,0.1)' : 'rgba(139,92,246,0.15)',
          color: '#a78bfa', border: '1px solid rgba(139,92,246,0.3)', cursor: 'pointer',
        }}>
          {importing ? 'A importar...' : '📂 Escolher CSV'}
          <input type="file" accept=".csv" hidden onChange={e => handleImport(e.target.files)} />
        </label>
        <button onClick={async () => {
          setReparsing(true); setReparseResult(null)
          try { const r = await hm3.reParse(); setReparseResult(r); onImported?.() }
          catch (e) { setReparseResult({ error: e.message }) }
          finally { setReparsing(false) }
        }} style={{ padding: '6px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: 'rgba(245,158,11,0.1)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.25)', cursor: 'pointer' }}>
          {reparsing ? 'A re-parsear...' : '🔄 Re-parse'}
        </button>
      </div>
      {importResult && !importResult.error && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#94a3b8', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ color: '#22c55e' }}>{importResult.inserted} importadas</span>
          {importResult.skipped > 0 && <span style={{ color: '#f59e0b' }}>{importResult.skipped} duplicadas</span>}
          {importResult.skippedDate > 0 && <span style={{ color: '#64748b' }}>{importResult.skippedDate} fora do prazo</span>}
          {importResult.skippedNota > 0 && <span style={{ color: '#64748b' }}>{importResult.skippedNota} sem nota</span>}
          {importResult.villains > 0 && <span style={{ color: '#8b5cf6' }}>{importResult.villains} vilões</span>}
        </div>
      )}
      {importResult?.error && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#ef4444' }}>{importResult.error}</div>
      )}
      {reparseResult && !reparseResult.error && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#f59e0b' }}>Re-parse: {reparseResult.updated || 0} actualizadas de {reparseResult.processed || 0}</div>
      )}
      {reparseResult?.error && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#ef4444' }}>Re-parse erro: {reparseResult.error}</div>
      )}
    </div>
  )
}


export default function HM3Page() {
  const [data, setData] = useState({ data: [], total: 0, pages: 1 })
  const [weekOffset, setWeekOffset] = useState(0)
  const [totalWeeks, setTotalWeeks] = useState(1)
  const [filters, setFilters] = useState({ study_state: '', site: '', search: '', date_from: '', tag: '', result_min: '', result_max: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [stats, setStats] = useState(null)

  const HM3_SITES = ['Winamax', 'PokerStars', 'WPN']

  // Calculate Monday-Sunday range for a given week offset (0 = current week)
  const getWeekRange = (offset) => {
    const now = new Date()
    const day = now.getDay()
    const diffToMonday = day === 0 ? 6 : day - 1
    const monday = new Date(now)
    monday.setDate(now.getDate() - diffToMonday - (offset * 7))
    monday.setHours(0, 0, 0, 0)
    const sunday = new Date(monday)
    sunday.setDate(monday.getDate() + 6)
    sunday.setHours(23, 59, 59, 999)
    return {
      from: monday.toISOString().slice(0, 10),
      to: sunday.toISOString().slice(0, 10),
      label: `${monday.toLocaleDateString('pt-PT', { day: '2-digit', month: 'short' })} — ${sunday.toLocaleDateString('pt-PT', { day: '2-digit', month: 'short', year: 'numeric' })}`
    }
  }

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    const week = getWeekRange(weekOffset)
    const params = { ...filters, page: 1, page_size: 2000, date_from: week.from, date_to: week.to }
    if (!params.site) delete params.site
    if (!params.tag) delete params.tag
    if (!params.search) delete params.search
    if (!params.study_state) delete params.study_state
    if (!params.result_min) delete params.result_min
    if (!params.result_max) delete params.result_max
    hands.list(params)
      .then(d => {
        const filtered = (d.data || []).filter(h => HM3_SITES.includes(h.site))
        setData({ ...d, data: filtered })
        // Estimate total weeks from total hands
        const tw = Math.max(1, Math.ceil((d.total || 0) / Math.max(1, filtered.length || 50)))
        setTotalWeeks(Math.min(tw, 52))
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [weekOffset, filters])

  const loadStats = useCallback(() => {
    hm3.stats().then(setStats).catch(() => {})
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => { loadStats() }, [loadStats])

  function set(key, val) {
    setFilters(f => ({ ...f, [key]: val }))
    setWeekOffset(0)
  }

  async function openDetail(id) {
    try { setSelected(await hands.get(id)) }
    catch (e) { setError(e.message) }
  }

  async function deleteHand(id) {
    if (!confirm('Apagar esta mão?')) return
    try { await hands.delete(id); load(); loadStats() }
    catch (e) { setError(e.message) }
  }

  const rows = data.data || []
  const totalBysite = stats?.by_site || []

  return (
    <>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: -0.5 }}>HM3</div>
        <div style={{ color: '#64748b', fontSize: 13, marginTop: 3 }}>Mãos importadas do Holdem Manager 3</div>
      </div>

      {/* Stats — clickable to filter */}
      {totalBysite.length > 0 && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          {totalBysite.map(s => (
            <div key={s.site} onClick={() => set('site', filters.site === s.site ? '' : s.site)} style={{
              background: filters.site === s.site ? 'rgba(139,92,246,0.12)' : '#1a1d27',
              border: `1px solid ${filters.site === s.site ? 'rgba(139,92,246,0.4)' : '#2a2d3a'}`,
              borderRadius: 8, padding: '8px 16px', cursor: 'pointer', transition: 'all 0.15s',
            }}>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 4 }}>{s.site}</div>
              <div style={{ display: 'flex', gap: 12, fontSize: 12 }}>
                <span style={{ fontWeight: 700, color: '#e2e8f0' }}>{s.total}</span>
                <span style={{ color: '#3b82f6' }}>{s.new} novas</span>
                {s.review > 0 && <span style={{ color: '#f59e0b' }}>{s.review} rev</span>}
                {s.studying > 0 && <span style={{ color: '#8b5cf6' }}>{s.studying} est</span>}
                {s.resolved > 0 && <span style={{ color: '#22c55e' }}>{s.resolved} res</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Import with date/nota filter */}
      <HM3ImportPanel onImported={() => { load(); loadStats() }} />

      {/* Time filters */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
        {[
          { label: 'Todas', value: '' },
          { label: 'Hoje', value: (() => { const d = new Date(); d.setHours(0,0,0,0); return d.toISOString().slice(0,10) })() },
          { label: '3 dias', value: (() => { const d = new Date(); d.setDate(d.getDate()-3); return d.toISOString().slice(0,10) })() },
          { label: 'Semana', value: (() => { const d = new Date(); d.setDate(d.getDate()-7); return d.toISOString().slice(0,10) })() },
          { label: 'Mês', value: (() => { const d = new Date(); d.setDate(d.getDate()-30); return d.toISOString().slice(0,10) })() },
        ].map(({ label, value }) => (
          <button key={label} onClick={() => set('date_from', value)} style={{
            padding: '5px 14px', borderRadius: 20, fontSize: 12, fontWeight: 500, border: '1px solid',
            borderColor: filters.date_from === value ? '#8b5cf6' : '#2a2d3a',
            background: filters.date_from === value ? 'rgba(139,92,246,0.15)' : 'transparent',
            color: filters.date_from === value ? '#a78bfa' : '#64748b',
            cursor: 'pointer',
          }}>{label}</button>
        ))}
      </div>

      {/* Tag filter panels */}
      {(() => {
        // Compute tag counts from loaded data
        const tagCounts = {}
        for (const h of rows) {
          for (const t of (h.tags || [])) {
            tagCounts[t] = (tagCounts[t] || 0) + 1
          }
        }
        const topTags = Object.entries(tagCounts).sort((a, b) => b[1] - a[1]).slice(0, 12)
        if (topTags.length === 0) return null

        const tagColors = ['#8b5cf6', '#6366f1', '#f59e0b', '#22c55e', '#06b6d4', '#ec4899', '#f97316', '#ef4444', '#a78bfa', '#34d399', '#fb923c', '#64748b']

        return (
          <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
            {topTags.map(([tag, cnt], i) => {
              const active = filters.tag === tag
              const color = tagColors[i % tagColors.length]
              return (
                <button key={tag} onClick={() => set('tag', active ? '' : tag)} style={{
                  padding: '4px 12px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                  border: `1px solid ${active ? color : '#2a2d3a'}`,
                  background: active ? `${color}20` : '#1a1d27',
                  color: active ? color : '#64748b',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}>
                  #{tag} <span style={{ fontSize: 11, opacity: 0.7 }}>({cnt})</span>
                </button>
              )
            })}
          </div>
        )
      })()}

      {/* Filters */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20, background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 10, padding: '12px 16px' }}>
        <select value={filters.study_state} onChange={e => set('study_state', e.target.value)} style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 10px', fontSize: 12 }}>
          {STATES.map(s => <option key={s.v} value={s.v}>{s.l}</option>)}
        </select>
        <select value={filters.site} onChange={e => set('site', e.target.value)} style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 10px', fontSize: 12 }}>
          <option value="">Todas as salas</option>
          <option value="Winamax">Winamax</option>
          <option value="PokerStars">PokerStars</option>
          <option value="WPN">WPN</option>
        </select>
        <input type="text" placeholder="Pesquisar torneio, tag..." value={filters.search} onChange={e => set('search', e.target.value)} style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 12px', fontSize: 12, flex: 1, minWidth: 140 }} />
        <input type="number" placeholder="BB min" value={filters.result_min} onChange={e => set('result_min', e.target.value)} style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 8px', fontSize: 12, width: 65 }} />
        <input type="number" placeholder="BB max" value={filters.result_max} onChange={e => set('result_max', e.target.value)} style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 8px', fontSize: 12, width: 65 }} />
        {(filters.study_state || filters.site || filters.search || filters.date_from || filters.tag || filters.result_min || filters.result_max) && (
          <button onClick={() => { setFilters({ study_state: '', site: '', search: '', date_from: '', tag: '', result_min: '', result_max: '' }); setWeekOffset(0) }} style={{ padding: '6px 12px', borderRadius: 6, fontSize: 12, background: 'transparent', color: '#64748b', border: '1px solid #2a2d3a', cursor: 'pointer' }}>&#10005; Limpar</button>
        )}
      </div>

      {error && <div style={{ color: '#ef4444', fontSize: 13, marginBottom: 12, padding: '8px 12px', background: 'rgba(239,68,68,0.08)', borderRadius: 6, border: '1px solid rgba(239,68,68,0.2)' }}>{error}</div>}

      {loading && <div style={{ textAlign: 'center', padding: '48px 0', color: '#64748b' }}>A carregar...</div>}

      {!loading && rows.length === 0 && (
        <div style={{ textAlign: 'center', padding: '64px 0', color: '#64748b' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>&#128202;</div>
          <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 6 }}>Sem mãos HM3</div>
          <div style={{ fontSize: 13 }}>Importa mãos via "Importar HM3"</div>
        </div>
      )}

      {/* Hands grouped by day */}
      {!loading && rows.length > 0 && (() => {
        // Group by date
        const byDay = {}
        for (const h of rows) {
          const dk = h.played_at ? h.played_at.slice(0, 10) : 'sem-data'
          if (!byDay[dk]) byDay[dk] = []
          byDay[dk].push(h)
        }
        const sortedDays = Object.keys(byDay).sort((a, b) => b.localeCompare(a))
        const weekdays = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']

        return (
          <div style={{ marginBottom: 24 }}>
            {sortedDays.map(dk => {
              const dayHands = byDay[dk]
              const d = new Date(dk + 'T12:00:00')
              const label = dk === 'sem-data' ? 'Sem data' : `${weekdays[d.getDay()]}, ${d.toLocaleDateString('pt-PT', { day: '2-digit', month: 'long', year: 'numeric' })}`
              const wins = dayHands.filter(h => h.result != null && Number(h.result) > 0).length
              const losses = dayHands.filter(h => h.result != null && Number(h.result) < 0).length
              const totalBB = dayHands.reduce((a, h) => a + (Number(h.result) || 0), 0)

              return (
                <DayGroup
                  key={dk}
                  dateKey={dk}
                  dateLabel={label}
                  hands={dayHands}
                  wins={wins}
                  losses={losses}
                  totalBB={totalBB}
                  onOpenDetail={openDetail}
                  onDeleteHand={deleteHand}
                />
              )
            })}
          </div>
        )
      })()}

      {/* Pagination */}
      {data.pages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center', marginBottom: 24 }}>
          <button onClick={() => setWeekOffset(w => w + 1)} style={{ padding: '6px 14px', borderRadius: 6, fontSize: 12, background: '#1a1d27', color: '#e2e8f0', border: '1px solid #2a2d3a', cursor: 'pointer' }}>&#8592;</button>
          <span style={{ color: '#64748b', fontSize: 12 }}>{getWeekRange(weekOffset).label}</span>
          <button disabled={weekOffset <= 0} onClick={() => setWeekOffset(w => w - 1)} style={{ padding: '6px 14px', borderRadius: 6, fontSize: 12, background: weekOffset <= 0 ? 'transparent' : '#1a1d27', color: weekOffset <= 0 ? '#374151' : '#e2e8f0', border: '1px solid #2a2d3a', cursor: weekOffset <= 0 ? 'not-allowed' : 'pointer' }}>&#8594;</button>
        </div>
      )}

      {/* Detail Modal */}
      {selected && (
        <HandDetailModal
          hand={selected}
          onClose={() => setSelected(null)}
          onUpdate={() => { setSelected(null); load(); loadStats() }}
        />
      )}
    </>
  )
}
