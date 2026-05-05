import TagEditor from './TagEditor'
import { SITE_COLORS, SITE_COLOR_DEFAULT } from '../lib/siteColors'

// ── Constantes (cópia de Hands.jsx para auto-conteúdo) ──────────────────────

const SUIT_BG      = { h: '#dc2626', d: '#2563eb', c: '#16a34a', s: '#1e293b' }
const SUIT_SYMBOLS = { h: '♥', d: '♦', c: '♣', s: '♠' }

const STATE_META = {
  new:      { label: 'Nova',    color: '#3b82f6', bg: 'rgba(59,130,246,0.15)' },
  resolved: { label: 'Revista', color: '#22c55e', bg: 'rgba(34,197,94,0.15)'  },
}

const POS_COLORS = {
  BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa',
  SB: '#f59e0b', BB: '#ef4444',
  UTG: '#22c55e', UTG1: '#16a34a', UTG2: '#15803d',
  MP: '#06b6d4', MP1: '#0891b2',
}

// ── Primitives internos (size="sm", cópia das de Hands.jsx) ─────────────────

function PokerCard({ card, size = 'sm' }) {
  if (!card || card.length < 2) {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: size === 'sm' ? 26 : 34, height: size === 'sm' ? 36 : 46,
        background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 4, fontSize: size === 'sm' ? 10 : 12, color: '#4b5563',
      }}>?</span>
    )
  }
  const rank = card.slice(0, -1).toUpperCase()
  const suit = card.slice(-1).toLowerCase()
  const bg = SUIT_BG[suit] || '#1e2130'
  return (
    <span style={{
      display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      width: size === 'sm' ? 26 : 34, height: size === 'sm' ? 36 : 46,
      background: bg, border: '1px solid rgba(255,255,255,0.2)',
      borderRadius: 4, fontFamily: "'Fira Code', monospace",
      fontSize: size === 'sm' ? 10 : 12, fontWeight: 700, color: '#fff',
      lineHeight: 1, gap: 1, userSelect: 'none',
      boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
    }}>
      <span>{rank}</span>
      <span style={{ fontSize: size === 'sm' ? 9 : 11 }}>{SUIT_SYMBOLS[suit] || suit}</span>
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
      display: 'inline-block', padding: '2px 0', borderRadius: 4, width: 48, textAlign: 'center',
      fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
      color: '#0a0c14', background: isBlind ? c : '#e2e8f0',
      border: `1px solid ${isBlind ? c : '#e2e8f0'}`,
    }}>{pos}</span>
  )
}

function ResultBadge({ result }) {
  if (result == null) return <span style={{ color: '#4b5563' }}>—</span>
  const val = Number(result)
  if (val > 0) return <span style={{ color: '#22c55e', fontWeight: 600, fontFamily: 'monospace' }}>+{val.toFixed(1)} BB</span>
  if (val < 0) return <span style={{ color: '#ef4444', fontWeight: 600, fontFamily: 'monospace' }}>{val.toFixed(1)} BB</span>
  return <span style={{ color: '#64748b', fontFamily: 'monospace' }}>0 BB</span>
}

// ── HandRow ──────────────────────────────────────────────────────────────────

export default function HandRow({ hand, onClick, onDelete, onTagsUpdate, idx = 0, extraEnd }) {
  const pos = hand.position ?? hand.hero_position
  const result = hand.result ?? hand.hero_result
  const meta = hand.all_players_actions?._meta
  const level = meta?.level ? `Lv ${meta.level}` : null
  const blindsLabel = meta ? `${Math.round(meta.sb)}/${Math.round(meta.bb)}` : null
  const lvBlinds = [level, blindsLabel].filter(Boolean).join(' ')

  const zebra = idx % 2 === 0 ? '#1a1d27' : '#1e2130'

  // Site short + cor
  const siteShort =
    hand.site === 'Winamax'    ? 'WN'
    : hand.site === 'PokerStars' ? 'PS'
    : hand.site === 'WPN'        ? 'WPN'
    : hand.site === 'GGPoker'    ? 'GG'
    : '?'
  const siteColor = SITE_COLORS[hand.site] || SITE_COLOR_DEFAULT

  // Buy-in: soma componentes do stakes (ex: €45+€45+€10 → €100)
  const stakesStr = hand.stakes || ''
  let buyin = ''
  const bm1 = stakesStr.match(/(\d+(?:\.\d+)?)\s*[€$]\s*\+\s*(\d+(?:\.\d+)?)\s*[€$](?:\s*\+\s*(\d+(?:\.\d+)?)\s*[€$])?/)
  const bm2 = stakesStr.match(/[€$](\d+(?:\.\d+)?)\s*\+\s*[€$](\d+(?:\.\d+)?)(?:\s*\+\s*[€$](\d+(?:\.\d+)?))?/)
  const bm3 = stakesStr.match(/(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)(?:\s*\+\s*(\d+(?:\.\d+)?))?/)
  const bmatch = bm1 || bm2 || bm3
  if (bmatch) {
    const total = [bmatch[1], bmatch[2], bmatch[3]].filter(Boolean).map(Number).reduce((a, b) => a + b, 0)
    buyin = `${stakesStr.includes('$') ? '$' : '€'}${total}`
  }

  // Tournament name: limpar buy-in/moeda/parênteses
  const tourneyName = stakesStr
    .replace(/\(.*?\)/g, '')
    .replace(/[\d€$.,]+\s*\+\s*[\d€$.,]+(?:\s*\+\s*[\d€$.,]+)?/g, '')
    .replace(/EUR|USD/gi, '')
    .trim() || stakesStr

  // DD/MM + HH:MM em TZ local. Antes slicava a string ISO (UTC), agora
  // converte via Date para bater com as horas a que o utilizador jogou.
  const playedDt = hand.played_at ? new Date(hand.played_at) : null
  const dateStr = playedDt
    ? `${String(playedDt.getDate()).padStart(2, '0')}/${String(playedDt.getMonth() + 1).padStart(2, '0')}`
    : ''
  const timeStr = playedDt
    ? `${String(playedDt.getHours()).padStart(2, '0')}:${String(playedDt.getMinutes()).padStart(2, '0')}`
    : ''

  // KO/NKO
  const fmt = hand.tournament_format
  // Dual-accept: legacy 'vanilla' e novo canonical 'Vanilla' (D3).
  const isKO = fmt && fmt.toLowerCase() !== 'vanilla'
  const showFmt = !!fmt

  // GG.gl link (se existir em raw ou notes)
  const ggMatch = (hand.raw || '').match(/https?:\/\/gg\.gl\/\S+/) || (hand.notes || '').match(/https?:\/\/gg\.gl\/\S+/)

  return (
    <div
      onClick={onClick}
      style={{
        display: 'grid',
        gridTemplateColumns:
          '5.6% 5.6% 5.6% 5.6% 8.6% 3.9% 23.3% 3.6% 3.4% 7.9% 8.3% 1fr',
        alignItems: 'center',
        padding: '7px 8px',
        background: zebra,
        borderBottom: '1px solid rgba(255,255,255,0.03)',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'background 0.1s',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.06)' }}
      onMouseLeave={e => { e.currentTarget.style.background = zebra }}
    >
      {/* 1. Estado */}
      <div><StateBadge state={hand.study_state} /></div>

      {/* 2. Hero cards */}
      <div style={{ display: 'flex', gap: 2 }}>
        {hand.hero_cards?.length > 0
          ? hand.hero_cards.map((c, i) => <PokerCard key={i} card={c} size="sm" />)
          : <span style={{ color: '#4b5563', fontSize: 11 }}>—</span>}
      </div>

      {/* 3. Posição */}
      <div><PosBadge pos={pos} /></div>

      {/* 4. Resultado BB */}
      <div><ResultBadge result={result} /></div>

      {/* 5. Nome do torneio */}
      <div style={{
        fontSize: 11, color: '#94a3b8',
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        minWidth: 0, paddingRight: 10,
      }}>
        {tourneyName}
      </div>

      {/* 6. Buy-in */}
      <div style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
        {buyin}
      </div>

      {/* 7. Board */}
      <div style={{ display: 'flex', gap: 4, minWidth: 0 }}>
        {hand.board?.length > 0
          ? hand.board.slice(0, 5).map((c, i) => (
            <span key={i} style={{ display: 'inline-flex', marginLeft: (i === 3 || i === 4) ? 12 : 0 }}>
              <PokerCard card={c} size="sm" />
            </span>
          ))
          : <span style={{ color: '#4b5563', fontSize: 10 }}>—</span>}
      </div>

      {/* 8. Sala */}
      <div style={{ textAlign: 'center' }}>
        <span style={{
          fontSize: 10, fontWeight: 700,
          color: siteColor, background: `${siteColor}15`,
          padding: '2px 5px', borderRadius: 3,
        }}>{siteShort}</span>
      </div>

      {/* 9. KO / NKO (novo) */}
      <div style={{ textAlign: 'center' }}>
        {showFmt && (
          <span style={{
            fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
            fontFamily: 'monospace', padding: '2px 5px', borderRadius: 3,
            background: isKO ? '#064e3b' : '#1e293b',
            color: isKO ? '#6ee7b7' : '#64748b',
          }}>{isKO ? 'KO' : 'NKO'}</span>
        )}
      </div>

      {/* 10. Level / Blinds */}
      <div style={{
        fontSize: 10, color: '#4b5563', fontFamily: 'monospace',
        fontWeight: 600, textAlign: 'right', whiteSpace: 'nowrap',
      }}>
        {lvBlinds}
      </div>

      {/* 11. Data + Hora + #B34 ID */}
      <div style={{
        fontSize: 10, color: '#64748b', fontFamily: 'monospace',
        textAlign: 'right', whiteSpace: 'nowrap', lineHeight: 1.3,
      }}>
        <div>{dateStr} <span style={{ color: '#94a3b8' }}>{timeStr}</span></div>
        {hand.id != null && (
          <div style={{ fontSize: 9, color: '#374151', fontStyle: 'italic' }}>
            #{hand.id}
          </div>
        )}
      </div>

      {/* 12. Botões */}
      <div style={{
        display: 'flex', gap: 4, alignItems: 'center', justifyContent: 'flex-end',
      }}>
        {/* Anexos imagem (Bucket 1) — discreto, só aparece se >0 */}
        {hand.attachment_count > 0 && (
          <span
            onClick={e => e.stopPropagation()}
            title={`${hand.attachment_count} ${hand.attachment_count === 1 ? 'imagem anexada' : 'imagens anexadas'}`}
            style={{
              fontSize: 10, color: '#64748b', fontFamily: 'monospace',
              padding: '2px 5px', borderRadius: 3, fontWeight: 600,
              background: 'rgba(100,116,139,0.08)',
              whiteSpace: 'nowrap',
            }}
          >📎 {hand.attachment_count}</span>
        )}
        {hand.all_players_actions && (
          <a
            href={`/replayer/${hand.id}`}
            target="_blank" rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            style={{
              fontSize: 10, color: '#818cf8', textDecoration: 'none',
              padding: '2px 6px', borderRadius: 4,
              background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)',
              fontWeight: 600,
            }}
          >▶</a>
        )}
        {ggMatch && (
          <a
            href={ggMatch[0]}
            target="_blank" rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            style={{
              fontSize: 10, color: '#f59e0b', textDecoration: 'none',
              padding: '2px 6px', borderRadius: 4,
              background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)',
              fontWeight: 600,
            }}
          >GG</a>
        )}
        {hand.discord_tags?.length > 0 && (
          <div
            style={{ display: 'inline-flex', gap: 3, alignItems: 'center' }}
            onClick={e => e.stopPropagation()}
            title={`Canais Discord (readonly): ${hand.discord_tags.join(', ')}`}
          >
            {hand.discord_tags.slice(0, 2).map((ch, i) => (
              <span
                key={i}
                style={{
                  fontSize: 10, padding: '2px 6px', borderRadius: 3,
                  background: 'rgba(88,101,242,0.18)',
                  border: '1px solid rgba(88,101,242,0.45)',
                  color: '#5865F2',
                  fontWeight: 700, fontFamily: 'monospace',
                  whiteSpace: 'nowrap',
                }}
              >#{ch}</span>
            ))}
            {hand.discord_tags.length > 2 && (
              <span
                style={{
                  fontSize: 10, padding: '2px 5px', borderRadius: 3,
                  background: 'rgba(88,101,242,0.1)',
                  color: '#5865F2', fontWeight: 700,
                  fontFamily: 'monospace',
                }}
              >+{hand.discord_tags.length - 2}</span>
            )}
          </div>
        )}
        <div onClick={e => e.stopPropagation()}>
          <TagEditor
            hand={hand}
            variant="inline"
            onUpdate={patch => {
              hand.hm3_tags = patch.hm3_tags
              onTagsUpdate?.(hand.id, patch)
            }}
          />
        </div>
        {extraEnd}
        <button
          style={{
            background: 'transparent', border: 'none', color: '#4b5563',
            cursor: 'pointer', fontSize: 12, padding: '0 4px',
          }}
          onClick={e => { e.stopPropagation(); onDelete?.(hand.id) }}
          onMouseEnter={e => { e.currentTarget.style.color = '#ef4444' }}
          onMouseLeave={e => { e.currentTarget.style.color = '#4b5563' }}
        >✕</button>
      </div>
    </div>
  )
}
