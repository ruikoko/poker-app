import TagEditor from './TagEditor'

// ── Internal primitives (cópia de HM3.jsx; extrair para partilhado num PR futuro) ──

const SUIT_BG = { h: '#dc2626', d: '#2563eb', c: '#16a34a', s: '#1e293b' }
const SUIT_SYMBOLS = { h: '♥', d: '♦', c: '♣', s: '♠' }

const STATE_META = {
  new:      { label: 'Nova',      color: '#3b82f6', bg: 'rgba(59,130,246,0.15)' },
  review:   { label: 'Revisão',   color: '#f59e0b', bg: 'rgba(245,158,11,0.15)' },
  studying: { label: 'A Estudar', color: '#8b5cf6', bg: 'rgba(139,92,246,0.15)' },
  resolved: { label: 'Resolvida', color: '#22c55e', bg: 'rgba(34,197,94,0.15)' },
}

const POS_COLORS = {
  BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa',
  SB: '#f59e0b', BB: '#ef4444',
  UTG: '#22c55e', UTG1: '#16a34a', UTG2: '#15803d',
  MP: '#06b6d4', MP1: '#0891b2',
}

const SITE_SHORT = {
  Winamax: 'WN', PokerStars: 'PS', WPN: 'WPN', GGPoker: 'GG',
}

function PokerCard({ card }) {
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
      display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      width: 24, height: 34,
      background: bg, border: '1px solid rgba(255,255,255,0.2)',
      borderRadius: 3, fontFamily: "'Fira Code', monospace",
      fontSize: 10, fontWeight: 700, color: '#fff', lineHeight: 1,
      boxShadow: '0 1px 2px rgba(0,0,0,0.3)', userSelect: 'none',
    }}>
      <span>{rank}</span>
      <span style={{ fontSize: 9 }}>{SUIT_SYMBOLS[suit] || suit}</span>
    </span>
  )
}

function StateBadge({ state }) {
  const meta = STATE_META[state] || { label: state || '—', color: '#666', bg: 'rgba(100,100,100,0.15)' }
  return (
    <span style={{
      display: 'inline-block', padding: '2px 9px', borderRadius: 999,
      fontSize: 11, fontWeight: 600, letterSpacing: 0.3,
      color: meta.color, background: meta.bg,
    }}>{meta.label}</span>
  )
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ display: 'inline-block', width: 48, textAlign: 'center', color: '#4b5563' }}>—</span>
  const c = POS_COLORS[pos] || '#64748b'
  const isBlind = pos === 'SB' || pos === 'BB'
  return (
    <span style={{
      display: 'inline-block', padding: '2px 0', borderRadius: 4,
      width: 48, textAlign: 'center',
      fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
      color: '#0a0c14', background: isBlind ? c : '#e2e8f0',
      border: `1px solid ${isBlind ? c : '#e2e8f0'}`,
    }}>{pos}</span>
  )
}

function ResultBadge({ result }) {
  if (result == null) return <span style={{ color: '#4b5563' }}>—</span>
  const val = Number(result)
  if (val > 0) return <span style={{ color: '#22c55e', fontWeight: 600, fontFamily: 'monospace', fontSize: 12 }}>+{val.toFixed(1)} BB</span>
  if (val < 0) return <span style={{ color: '#ef4444', fontWeight: 600, fontFamily: 'monospace', fontSize: 12 }}>{val.toFixed(1)} BB</span>
  return <span style={{ color: '#64748b', fontFamily: 'monospace', fontSize: 12 }}>0 BB</span>
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtBuyIn(v) {
  if (v == null) return ''
  return v % 1 === 0 ? `$${v}` : `$${v.toFixed(2)}`
}

function fmtDateTime(iso) {
  if (!iso) return ''
  // MM-DD HH:MM
  return `${iso.slice(5, 10)} ${iso.slice(11, 16)}`
}

function deriveBlindsLabel(hand) {
  if (hand.blinds) return hand.blinds
  const meta = hand.all_players_actions?._meta
  if (!meta) return ''
  const base = `${Math.round(meta.sb)}/${Math.round(meta.bb)}`
  return meta.ante ? `${base}(${Math.round(meta.ante)})` : base
}

// ── HandRow ──────────────────────────────────────────────────────────────────

export default function HandRow({ hand, idx = 0, onClick, onDelete, onTagsUpdate, extraEnd }) {
  const pos = hand.position ?? hand.hero_position
  const result = hand.result ?? hand.hero_result
  const meta = hand.all_players_actions?._meta
  const level = meta?.level
  const blindsLabel = deriveBlindsLabel(hand)
  const siteShort = SITE_SHORT[hand.site] || hand.site || ''
  const zebra = idx % 2 === 0 ? '#1a1d27' : '#1e2130'

  const fmt = hand.tournament_format
  const isKO = fmt && fmt !== 'vanilla'
  const showFmt = !!fmt

  const canReplay = !!hand.all_players_actions

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px',
        background: zebra, borderBottom: '1px solid rgba(255,255,255,0.03)',
        cursor: onClick ? 'pointer' : 'default', transition: 'background 0.1s',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.06)' }}
      onMouseLeave={e => { e.currentTarget.style.background = zebra }}
    >
      {/* 1. StateBadge */}
      <div style={{ minWidth: 64, flexShrink: 0 }}><StateBadge state={hand.study_state} /></div>

      {/* 2. hero cards */}
      <div style={{ display: 'flex', gap: 3, minWidth: 58, flexShrink: 0 }}>
        {hand.hero_cards?.length > 0
          ? hand.hero_cards.map((c, i) => <PokerCard key={i} card={c} />)
          : <span style={{ color: '#4b5563', fontSize: 12 }}>—</span>}
      </div>

      {/* 3. Position */}
      <div style={{ minWidth: 48, flexShrink: 0 }}><PosBadge pos={pos} /></div>

      {/* 4. ±BB */}
      <div style={{ minWidth: 84, flexShrink: 0 }}><ResultBadge result={result} /></div>

      {/* 5. Buy-in */}
      <div style={{
        minWidth: 52, flexShrink: 0, fontSize: 11,
        fontFamily: 'monospace', color: '#f59e0b', fontWeight: 600,
      }}>{fmtBuyIn(hand.buy_in)}</div>

      {/* 6. board */}
      <div style={{ display: 'flex', gap: 3, minWidth: 130, width: 130, flexShrink: 0 }}>
        {hand.board?.length > 0
          ? hand.board.slice(0, 5).map((c, i) => <PokerCard key={i} card={c} />)
          : <span style={{ color: '#4b5563', fontSize: 11 }}>—</span>}
      </div>

      {/* 7. Site */}
      <div style={{
        minWidth: 32, flexShrink: 0, fontSize: 11,
        color: '#64748b', fontWeight: 600, fontFamily: 'monospace',
      }}>{siteShort}</div>

      {/* 8. KO / NKO */}
      <div style={{ minWidth: 36, flexShrink: 0 }}>
        {showFmt && (
          <span style={{
            fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
            fontFamily: 'monospace', padding: '3px 6px', borderRadius: 3,
            background: isKO ? '#064e3b' : '#1e293b',
            color: isKO ? '#6ee7b7' : '#64748b',
          }}>{isKO ? 'KO' : 'NKO'}</span>
        )}
      </div>

      {/* 9. Blinds (+ Lv se existir) */}
      <div style={{
        minWidth: 100, flexShrink: 0, fontSize: 11,
        color: '#4b5563', fontFamily: 'monospace', fontWeight: 600,
      }}>
        {level != null && <span style={{ marginRight: 6 }}>Lv{level}</span>}
        {blindsLabel}
      </div>

      {/* 10. Data/Hora MM-DD HH:MM */}
      <div style={{
        minWidth: 78, flexShrink: 0, fontSize: 11,
        color: '#4b5563', fontFamily: 'monospace',
      }}>{fmtDateTime(hand.played_at)}</div>

      {/* 11. Replayer ▶ */}
      <div style={{ minWidth: 24, flexShrink: 0 }}>
        {canReplay && (
          <a
            href={`/replayer/${hand.id}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            style={{
              fontSize: 10, color: '#22c55e', textDecoration: 'none',
              padding: '2px 6px', borderRadius: 4,
              background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.2)',
              fontWeight: 600,
            }}
          >▶</a>
        )}
      </div>

      {/* 12. Tags editáveis (hm3_tags) */}
      <div style={{ flexShrink: 0 }} onClick={e => e.stopPropagation()}>
        <TagEditor
          hand={hand}
          variant="inline"
          onUpdate={patch => onTagsUpdate?.(hand.id, patch)}
        />
      </div>

      {/* Extra end slot (ex: villain_count / SS indicators em Torneios) */}
      {extraEnd && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          {extraEnd}
        </div>
      )}

      {/* Delete ✕ */}
      <button
        onClick={e => { e.stopPropagation(); onDelete?.(hand.id) }}
        style={{
          background: 'transparent', border: 'none', color: '#4b5563',
          cursor: 'pointer', fontSize: 12, padding: '0 4px', flexShrink: 0,
          marginLeft: 'auto',
        }}
        onMouseEnter={e => { e.currentTarget.style.color = '#ef4444' }}
        onMouseLeave={e => { e.currentTarget.style.color = '#4b5563' }}
      >✕</button>
    </div>
  )
}
