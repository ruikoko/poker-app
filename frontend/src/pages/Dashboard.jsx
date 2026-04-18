import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { hands, study, screenshots } from '../api/client'

// ── Constants ────────────────────────────────────────────────────────────────

const SUIT_BG = { h: '#dc2626', d: '#2563eb', c: '#16a34a', s: '#1e293b' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }

const STATE_META = {
  new:      { label: 'Nova',      color: '#3b82f6', bg: 'rgba(59,130,246,0.15)' },
  review:   { label: 'Revisão',   color: '#f59e0b', bg: 'rgba(245,158,11,0.15)' },
  studying: { label: 'A Estudar', color: '#8b5cf6', bg: 'rgba(139,92,246,0.15)' },
  resolved: { label: 'Resolvida', color: '#22c55e', bg: 'rgba(34,197,94,0.15)'  },
}

const POS_COLORS = {
  BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa',
  SB: '#f59e0b', BB: '#ef4444',
  UTG: '#22c55e', UTG1: '#16a34a', UTG2: '#15803d',
  MP: '#06b6d4', MP1: '#0891b2',
}

const SITE_COLORS = {
  PokerStars: '#ef4444', Winamax: '#22c55e', GGPoker: '#f59e0b',
  WPN: '#06b6d4', '888poker': '#8b5cf6',
}

const SITE_SHORT = {
  PokerStars: 'PS', Winamax: 'WN', GGPoker: 'GG',
  WPN: 'WPN', '888poker': '888',
}

// ── Mini-components ──────────────────────────────────────────────────────────

function PokerCard({ card }) {
  if (!card || card.length < 2) return null
  const rank = card.slice(0, -1).toUpperCase()
  const suit = card.slice(-1).toLowerCase()
  return (
    <span style={{
      display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      width: 24, height: 33, background: SUIT_BG[suit] || '#1e293b',
      border: '1px solid rgba(255,255,255,0.2)', borderRadius: 3,
      fontFamily: "'Fira Code',monospace", fontSize: 10, fontWeight: 700, color: '#fff',
      lineHeight: 1, gap: 0, userSelect: 'none',
    }}>
      <span>{rank}</span>
      <span style={{ fontSize: 8 }}>{SUIT_SYMBOLS[suit] || suit}</span>
    </span>
  )
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ color: '#4b5563' }}>&mdash;</span>
  const c = POS_COLORS[pos] || '#64748b'
  const isBlind = pos === 'SB' || pos === 'BB'
  return (
    <span style={{
      display: 'inline-block', padding: '2px 0', borderRadius: 4, width: 40, textAlign: 'center',
      fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
      color: '#0a0c14', background: isBlind ? c : '#e2e8f0',
    }}>{pos}</span>
  )
}

function StateBadge({ state }) {
  const m = STATE_META[state] || { label: state || '—', color: '#666', bg: 'rgba(100,100,100,0.15)' }
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 999,
      fontSize: 10, fontWeight: 600, color: m.color, background: m.bg,
    }}>{m.label}</span>
  )
}

function ResultBB({ result }) {
  if (result == null) return <span style={{ color: '#4b5563' }}>&mdash;</span>
  const v = Number(result)
  const color = v > 0 ? '#22c55e' : v < 0 ? '#ef4444' : '#64748b'
  return <span style={{ color, fontWeight: 600, fontFamily: 'monospace', fontSize: 12 }}>{v > 0 ? '+' : ''}{v.toFixed(1)}</span>
}

function SiteBadge({ site }) {
  const short = SITE_SHORT[site] || site || '—'
  const c = SITE_COLORS[site] || '#64748b'
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, color: c,
      background: `${c}15`, padding: '2px 6px', borderRadius: 3,
    }}>{short}</span>
  )
}

function formatStudyTime(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600)
  const m = Math.floor((totalSeconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${min}`
}

// ── Dashboard ────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [studyWeek, setStudyWeek] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    hands.stats().then(setStats).catch(e => setError(e.message))
    study.week().then(setStudyWeek).catch(() => {})
  }, [])

  const recent = stats?.recent || []
  const weekDays = studyWeek?.days || []
  const maxDaySeconds = Math.max(1, ...weekDays.map(d => d.seconds))

  const dayLabels = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
  const today = new Date().getDay() // 0=Dom, 1=Seg, ..., 6=Sáb
  const todayIdx = today === 0 ? 6 : today - 1

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 600 }}>Dashboard</div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
            {new Date().toLocaleDateString('pt-PT', { weekday: 'long', day: 'numeric', month: 'long' })}
          </div>
        </div>
      </div>

      {error && <div style={{ padding: '10px 16px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 6, color: '#ef4444', fontSize: 13, marginBottom: 16 }}>{error}</div>}

      {/* ── 3 Painéis ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>

        {/* Total de mãos */}
        <div
          onClick={() => navigate('/hands')}
          style={{
            background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            padding: '20px', cursor: 'pointer', transition: 'border-color 0.15s',
          }}
          onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
          onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
        >
          <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>Total de mãos</div>
          <div style={{ fontSize: 28, fontWeight: 600, lineHeight: 1 }}>
            {stats ? Number(stats.total).toLocaleString('pt-PT') : '—'}
          </div>
          {stats?.new_this_week != null && (
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8 }}>+{stats.new_this_week} esta semana</div>
          )}
        </div>

        {/* Mãos por estudar */}
        <div
          onClick={() => navigate('/hands?study_state=new')}
          style={{
            background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            padding: '20px', cursor: 'pointer', transition: 'border-color 0.15s',
          }}
          onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
          onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
        >
          <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>Mãos por estudar</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <span style={{ fontSize: 28, fontWeight: 600, lineHeight: 1 }}>
              {stats ? Number(stats.new).toLocaleString('pt-PT') : '—'}
            </span>
            <span style={{ fontSize: 12, color: 'var(--muted)' }}>novas</span>
          </div>
          {stats && (
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8, display: 'flex', gap: 10 }}>
              <span>{stats.review || 0} revisão</span>
              <span style={{ color: 'var(--border)' }}>·</span>
              <span>{stats.studying || 0} a estudar</span>
            </div>
          )}
        </div>

        {/* Tempo de estudo */}
        <div
          style={{
            background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            padding: '20px',
          }}
        >
          <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>Tempo de estudo</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <span style={{ fontSize: 28, fontWeight: 600, lineHeight: 1 }}>
              {studyWeek ? formatStudyTime(studyWeek.total_seconds) : '—'}
            </span>
            <span style={{ fontSize: 12, color: 'var(--muted)' }}>esta semana</span>
          </div>
          {/* Sparkline semanal */}
          <div style={{ display: 'flex', gap: 3, height: 32, alignItems: 'flex-end', marginTop: 12 }}>
            {weekDays.map((d, i) => {
              const pct = d.seconds > 0 ? Math.max(8, (d.seconds / maxDaySeconds) * 100) : 0
              const isFuture = i > todayIdx
              return (
                <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <div style={{
                    width: '100%', height: `${pct}%`, minHeight: pct > 0 ? 4 : 0,
                    background: isFuture ? 'var(--border)' : 'var(--accent)', borderRadius: 2,
                    opacity: isFuture ? 0.3 : d.seconds > 0 ? 1 : 0.15,
                  }} />
                </div>
              )
            })}
          </div>
          <div style={{ display: 'flex', gap: 3, marginTop: 4 }}>
            {dayLabels.map((l, i) => (
              <div key={i} style={{ flex: 1, textAlign: 'center', fontSize: 9, color: i === todayIdx ? 'var(--text)' : 'var(--muted)', fontWeight: i === todayIdx ? 600 : 400 }}>{l}</div>
            ))}
          </div>
        </div>

      </div>

      {/* ── Últimas 5 mãos importadas ── */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>Últimas mãos importadas</span>
          <button
            onClick={() => navigate('/hands')}
            style={{
              fontSize: 12, padding: '4px 12px', borderRadius: 4,
              background: 'transparent', border: '1px solid var(--border)', color: 'var(--muted)',
              cursor: 'pointer',
            }}
            onMouseEnter={e => e.currentTarget.style.color = 'var(--text)'}
            onMouseLeave={e => e.currentTarget.style.color = 'var(--muted)'}
          >Ver todas →</button>
        </div>

        {recent.length === 0 && !error && (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
            {stats === null ? 'A carregar…' : 'Sem mãos importadas'}
          </div>
        )}

        {recent.map((h, idx) => {
          const isLast = idx === recent.length - 1
          const stakes = h.stakes || ''
          // Extract blinds from stakes like "€45+€45+€10 EUR" or from level info
          const blindsMatch = stakes.match(/([\d,]+)\/([\d,]+)/)
          const blindsStr = blindsMatch ? `${blindsMatch[1]}/${blindsMatch[2]}` : ''

          return (
            <div
              key={h.id}
              onClick={() => navigate(`/hand/${h.id}`)}
              style={{
                display: 'grid',
                gridTemplateColumns: '64px 56px 44px 64px 1fr 44px 90px 72px',
                gap: 10, alignItems: 'center',
                padding: '10px 16px',
                borderBottom: isLast ? 'none' : '1px solid rgba(255,255,255,0.03)',
                cursor: 'pointer', transition: 'background 0.1s',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.06)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <div><StateBadge state={h.study_state} /></div>
              <div style={{ display: 'flex', gap: 3 }}>
                {h.hero_cards?.length > 0
                  ? h.hero_cards.map((c, i) => <PokerCard key={i} card={c} />)
                  : <span style={{ color: '#4b5563', fontSize: 11 }}>&mdash;</span>}
              </div>
              <div><PosBadge pos={h.position} /></div>
              <div><ResultBB result={h.result} /></div>
              <div style={{ fontSize: 12, color: '#94a3b8', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0 }}>
                {stakes}
              </div>
              <div style={{ textAlign: 'center' }}><SiteBadge site={h.site} /></div>
              <div style={{ fontSize: 11, color: '#4b5563', fontFamily: 'monospace', textAlign: 'right' }}>
                {blindsStr}
              </div>
              <div style={{ fontSize: 11, color: '#4b5563', fontFamily: 'monospace', textAlign: 'right' }}>
                {formatDate(h.played_at || h.created_at)}
              </div>
            </div>
          )
        })}
      </div>

      {/* ── Screenshots ── */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', marginTop: 24 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', borderBottom: '1px solid var(--border)' }}>
          <div style={{ padding: '16px 20px' }}>
            <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>Screenshots na BD</div>
            <div style={{ fontSize: 24, fontWeight: 600 }}>
              {stats?.total_screenshots != null ? Number(stats.total_screenshots).toLocaleString('pt-PT') : '—'}
            </div>
          </div>
          <div style={{ padding: '16px 20px', borderLeft: '1px solid var(--border)' }}>
            <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>Sem match</div>
            <div style={{ fontSize: 24, fontWeight: 600, color: stats?.orphan_screenshots > 0 ? '#f59e0b' : 'var(--text)' }}>
              {stats?.orphan_screenshots != null ? Number(stats.orphan_screenshots).toLocaleString('pt-PT') : '—'}
            </div>
          </div>
        </div>
        {stats?.orphan_screenshots > 0 && <OrphanList />}
      </div>
    </>
  )
}

// ── Orphan Screenshots List ──────────────────────────────────────────────────

function OrphanList() {
  const [orphans, setOrphans] = useState([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState({})

  useEffect(() => {
    screenshots.orphans().then(data => {
      setOrphans(Array.isArray(data) ? data : data?.data || [])
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  async function handleRematch(entryId) {
    setActionLoading(prev => ({ ...prev, [entryId]: 'rematch' }))
    try {
      const result = await screenshots.rematch(entryId)
      if (result?.status === 'matched') {
        setOrphans(prev => prev.filter(o => o.id !== entryId))
      }
    } catch (e) {
      console.error('Rematch error:', e)
    } finally {
      setActionLoading(prev => ({ ...prev, [entryId]: null }))
    }
  }

  async function handleDismiss(entryId) {
    setActionLoading(prev => ({ ...prev, [entryId]: 'dismiss' }))
    try {
      await screenshots.dismiss(entryId)
      setOrphans(prev => prev.filter(o => o.id !== entryId))
    } catch (e) {
      console.error('Dismiss error:', e)
    } finally {
      setActionLoading(prev => ({ ...prev, [entryId]: null }))
    }
  }

  if (loading) return <div style={{ padding: 16, fontSize: 12, color: 'var(--muted)', textAlign: 'center' }}>A carregar órfãos...</div>
  if (orphans.length === 0) return null

  return (
    <div style={{ maxHeight: 300, overflowY: 'auto' }}>
      {orphans.map((o, idx) => {
        const raw = o.raw_json || {}
        const tm = raw.tm || raw.tournament_number || '—'
        const date = o.discord_posted_at || o.created_at || ''
        const dateStr = date ? new Date(date).toLocaleString('pt-PT', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'
        const isActing = actionLoading[o.id]

        return (
          <div key={o.id} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '10px 20px',
            borderTop: idx > 0 ? '1px solid rgba(255,255,255,0.03)' : 'none',
            fontSize: 12,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
              <span style={{ color: '#f59e0b', fontSize: 11, fontWeight: 600, flexShrink: 0 }}>TM {tm}</span>
              <span style={{ color: 'var(--muted)', fontSize: 11 }}>{dateStr}</span>
              {o.file_name && <span style={{ color: '#4b5563', fontSize: 10, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 200 }}>{o.file_name}</span>}
            </div>
            <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
              <button
                onClick={() => handleRematch(o.id)}
                disabled={!!isActing}
                style={{
                  fontSize: 10, padding: '3px 10px', borderRadius: 4,
                  background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.25)',
                  color: '#22c55e', cursor: isActing ? 'wait' : 'pointer', fontWeight: 600,
                  opacity: isActing ? 0.5 : 1,
                }}
              >{isActing === 'rematch' ? '...' : 'Rematch'}</button>
              <button
                onClick={() => handleDismiss(o.id)}
                disabled={!!isActing}
                style={{
                  fontSize: 10, padding: '3px 10px', borderRadius: 4,
                  background: 'transparent', border: '1px solid var(--border)',
                  color: 'var(--muted)', cursor: isActing ? 'wait' : 'pointer',
                  opacity: isActing ? 0.5 : 1,
                }}
              >{isActing === 'dismiss' ? '...' : 'Ignorar'}</button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
