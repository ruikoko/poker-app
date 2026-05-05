import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { hands as handsApi, screenshots } from '../api/client'
import { HERO_NAMES_ALL } from '../heroNames'
import TagEditor from '../components/TagEditor'
import HandHistoryViewer from '../components/HandHistoryViewer'
import AttachedImagesSection from '../components/AttachedImagesSection'

const SUIT_COLORS = { h: '#ef4444', d: '#3b82f6', c: '#22c55e', s: '#e2e8f0' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }
const SUIT_BG = { h: '#7f1d1d', d: '#1e3a5f', c: '#14532d', s: '#1e293b' }
const SEAT_ORDER = ['SB','BB','UTG','UTG1','UTG+1','UTG2','UTG+2','MP','MP1','MP+1','HJ','CO','BTN']
const POS_COLORS = { BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa', SB: '#f59e0b', BB: '#ef4444', UTG: '#22c55e', 'UTG1': '#16a34a', 'UTG+1': '#16a34a', 'UTG2': '#15803d', 'UTG+2': '#15803d', MP: '#06b6d4', 'MP1': '#0891b2', 'MP+1': '#0891b2' }

function RCard({ card, size = 'md' }) {
  if (!card || card.length < 2) return <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 36, height: 50, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 5, fontSize: 14, color: '#4b5563' }}>?</span>
  const w = size === 'lg' ? 48 : 36, h = size === 'lg' ? 66 : 50, fs = size === 'lg' ? 19 : 15
  const rank = card.slice(0, -1).toUpperCase(), suit = card.slice(-1).toLowerCase()
  return <span style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', width: w, height: h, background: SUIT_BG[suit] || '#1e293b', border: `1.5px solid ${SUIT_COLORS[suit]}50`, borderRadius: 5, fontFamily: "'Fira Code',monospace", fontWeight: 700, fontSize: fs, color: '#fff', lineHeight: 1, userSelect: 'none', boxShadow: '0 2px 6px rgba(0,0,0,0.4)' }}><span>{rank}</span><span style={{ fontSize: fs * 0.8, color: SUIT_COLORS[suit] }}>{SUIT_SYMBOLS[suit]}</span></span>
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ color: '#4b5563' }}>—</span>
  const norm = pos.replace('+', '')
  const c = POS_COLORS[pos] || POS_COLORS[norm] || '#64748b'
  return <span style={{ display: 'inline-block', padding: '4px 12px', borderRadius: 5, fontSize: 14, fontWeight: 700, letterSpacing: 0.5, color: c, background: `${c}18`, border: `1px solid ${c}30`, minWidth: 38, textAlign: 'center' }}>{pos}</span>
}


export default function HandDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [hand, setHand] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  const refreshHand = () => {
    handsApi.get(id).then(h => setHand(h)).catch(e => setError(e.message))
  }

  useEffect(() => { setLoading(true); handsApi.get(id).then(h => { setHand(h); setLoading(false) }).catch(e => { setError(e.message); setLoading(false) }) }, [id])

  if (loading) return <div style={{ padding: 60, textAlign: 'center', color: '#64748b', fontSize: 16 }}>A carregar...</div>
  if (error) return <div style={{ padding: 60, textAlign: 'center', color: '#ef4444', fontSize: 16 }}>{error}</div>
  if (!hand) return null

  // Placeholder SS upload / Discord sem HH real: render dedicado com Vision dump.
  // Quando HH chegar, _insert_hand apaga o placeholder e a hand canonical toma o lugar.
  const isPlaceholder = (hand.player_names?.match_method || '').startsWith('discord_placeholder_')
  if (isPlaceholder) {
    return <PlaceholderView hand={hand} navigate={navigate} onUpdate={(patch) => setHand(h => ({ ...h, ...patch }))} />
  }

  const meta = hand.all_players_actions?._meta || {}
  const bb = meta.bb || 1
  const players = Object.entries(hand.all_players_actions || {})
    .filter(([k]) => k !== '_meta')
    .map(([name, info]) => ({ name, ...info }))
    .sort((a, b) => {
      const ai = SEAT_ORDER.indexOf(a.position) === -1 ? 99 : SEAT_ORDER.indexOf(a.position)
      const bi = SEAT_ORDER.indexOf(b.position) === -1 ? 99 : SEAT_ORDER.indexOf(b.position)
      return ai - bi
    })

  // Tech Debt #8: Mesa+Acções renderizado por HandHistoryViewer (componente canónico).
  // Este componente lida internamente com:
  //   - resolução de hashes GG (via raw_resolved fallback raw + apa.seat)
  //   - cálculo de pot/stacks/posições (via parseHH canónico)
  //   - bloco SHOWDOWN dedicado com cards lg
  const blindsLabel = meta.sb && meta.bb ? `${Math.round(meta.sb)}/${Math.round(meta.bb)}${meta.ante ? `(${Math.round(meta.ante)})` : ''}` : ''

  const tourneyName = hand.stakes || ''
  const playedDate = hand.played_at ? new Date(hand.played_at).toLocaleString('pt-PT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''
  const resultColor = hand.result > 0 ? '#22c55e' : hand.result < 0 ? '#ef4444' : '#64748b'

  return (
    <div style={{ maxWidth: 880, margin: '0 auto', padding: '28px 24px' }}>

      {/* ── HEADER ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, gap: 12 }}>
        <button onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', color: '#818cf8', cursor: 'pointer', fontSize: 16, fontWeight: 600, flexShrink: 0 }}>&larr; Voltar</button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <TagEditor hand={hand} onUpdate={(patch) => setHand(h => ({ ...h, ...patch }))} />
        </div>
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          {hand.raw && hand.all_players_actions && (
            <a href={`/replayer/${hand.id}`} style={{ padding: '8px 20px', borderRadius: 6, fontSize: 14, fontWeight: 700, background: '#6366f1', color: '#fff', textDecoration: 'none' }}>&#9654; Replayer</a>
          )}
          {hand.raw && (
            <button onClick={() => { navigator.clipboard.writeText(hand.raw); setCopied(true); setTimeout(() => setCopied(false), 2000) }} style={{ padding: '8px 20px', borderRadius: 6, fontSize: 14, fontWeight: 700, background: copied ? 'rgba(34,197,94,0.15)' : 'rgba(245,158,11,0.1)', color: copied ? '#22c55e' : '#f59e0b', border: `1px solid ${copied ? 'rgba(34,197,94,0.3)' : 'rgba(245,158,11,0.25)'}`, cursor: 'pointer' }}>{copied ? '✓ Copiado' : 'Copiar HH'}</button>
          )}
        </div>
      </div>

      {/* ── INFO GRID — FIRST THING ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 14 }}>
        {[
          { l: 'SALA', v: hand.site },
          { l: 'DATA', v: playedDate },
          { l: 'RESULTADO', v: hand.result != null ? `${hand.result > 0 ? '+' : ''}${Number(hand.result).toFixed(1)} BB` : '—', c: resultColor, big: true },
          { l: 'POSIÇÃO', v: null, badge: hand.position },
          { l: 'TORNEIO', v: tourneyName },
          { l: 'HAND ID', v: hand.hand_id },
          { l: 'DB ID', v: `#${hand.id}` },
          { l: 'BLINDS', v: blindsLabel || '—' },
          { l: 'LEVEL', v: meta.level != null ? `Lv ${meta.level}` : '—' },
          { l: 'JOGADORES', v: players.length },
        ].map(({ l, v, c, badge, big }) => (
          <div key={l} style={{ background: '#0f1117', borderRadius: 6, padding: '12px 16px' }}>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 700, letterSpacing: 0.5, marginBottom: 4 }}>{l}</div>
            {badge ? <PosBadge pos={badge} /> : <div style={{ fontSize: big ? 18 : 15, color: c || '#f1f5f9', fontWeight: 700, wordBreak: 'break-all' }}>{v || '—'}</div>}
          </div>
        ))}
      </div>

      {/* ── HERO CARDS + BOARD ── */}
      <div style={{ background: '#0f1117', borderRadius: 8, padding: '16px 20px', marginBottom: 14, display: 'flex', gap: 40, alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 13, color: '#94a3b8', fontWeight: 700, marginBottom: 8 }}>HERO &middot; <PosBadge pos={hand.position} /></div>
          <div style={{ display: 'flex', gap: 6 }}>
            {hand.hero_cards?.length > 0 ? hand.hero_cards.map((c, i) => <RCard key={i} card={c} size="lg" />) : <span style={{ color: '#4b5563' }}>—</span>}
          </div>
        </div>
        {hand.board?.length > 0 && (
          <div>
            <div style={{ fontSize: 13, color: '#94a3b8', fontWeight: 700, marginBottom: 8 }}>BOARD</div>
            <div style={{ display: 'flex', gap: 5 }}>{hand.board.map((c, i) => <RCard key={i} card={c} size="lg" />)}</div>
          </div>
        )}
      </div>

      {/* ── IMAGENS ANEXADAS (Tech Debt #B9 — galeria manual) ── */}
      <AttachedImagesSection hand={hand} onChange={refreshHand} />

      {/* ── MESA + ACÇÕES + SHOWDOWN (Tech Debt #8 — renderer canónico) ── */}
      <HandHistoryViewer hand={hand} />
    </div>
  )
}

// ── Placeholder View ────────────────────────────────────────────────────────
// Render dedicado para placeholders (match_method='discord_placeholder_*').
// Mostra dados Vision (hero, board, players, SB/BB) e SS grande. Esconde
// secções que exigem HH real: replayer, copy HH, acções por street, pot.

function PlaceholderView({ hand, navigate, onUpdate }) {
  const [ssFullscreen, setSsFullscreen] = useState(false)
  const pn = hand.player_names || {}
  const hero = pn.hero
  const board = pn.board || []
  const visionSb = pn.vision_sb
  const visionBb = pn.vision_bb
  const visionLevel = pn.vision_level
  const playersList = pn.players_list || []
  const playedDate = hand.played_at
    ? new Date(hand.played_at).toLocaleString('pt-PT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : '—'
  const imgUrl = hand.entry_id ? screenshots.imageUrl(hand.entry_id) : null

  return (
    <div style={{ maxWidth: 880, margin: '0 auto', padding: '28px 24px' }}>
      {/* Header — só voltar + tags (editáveis) */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, gap: 12 }}>
        <button onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', color: '#818cf8', cursor: 'pointer', fontSize: 16, fontWeight: 600, flexShrink: 0 }}>&larr; Voltar</button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <TagEditor hand={hand} onUpdate={onUpdate} />
        </div>
      </div>

      {/* Banner placeholder */}
      <div style={{
        background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.3)',
        borderRadius: 8, padding: '14px 18px', marginBottom: 16,
        color: '#a5b4fc', fontSize: 13, lineHeight: 1.5,
      }}>
        <strong style={{ color: '#c7d2fe' }}>Mão sem HH ainda.</strong>{' '}
        Dados extraídos via Vision da SS. Serão substituídos pelos dados canónicos quando a HH for importada (HM3 ou ZIP).
      </div>

      {/* Info grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 14 }}>
        {[
          { l: 'SALA', v: hand.site },
          { l: 'DATA', v: playedDate },
          { l: 'HAND ID', v: hand.hand_id },
          { l: 'DB ID', v: `#${hand.id}` },
          { l: 'HERO', v: hero || '—' },
          { l: 'LEVEL', v: visionLevel != null ? `Lv ${visionLevel}` : '—' },
          { l: 'JOGADORES', v: playersList.length || '—' },
        ].map(({ l, v }) => (
          <div key={l} style={{ background: '#0f1117', borderRadius: 6, padding: '12px 16px' }}>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 700, letterSpacing: 0.5, marginBottom: 4 }}>{l}</div>
            <div style={{ fontSize: 15, color: '#f1f5f9', fontWeight: 700, wordBreak: 'break-all' }}>{v || '—'}</div>
          </div>
        ))}
      </div>

      {/* Board (se existir) */}
      {board.length > 0 && (
        <div style={{ background: '#0f1117', borderRadius: 8, padding: '16px 20px', marginBottom: 14 }}>
          <div style={{ fontSize: 13, color: '#94a3b8', fontWeight: 700, marginBottom: 8 }}>BOARD</div>
          <div style={{ display: 'flex', gap: 5 }}>
            {board.map((c, i) => <RCard key={i} card={c} size="lg" />)}
          </div>
        </div>
      )}

      {/* Screenshot (prominent) */}
      {imgUrl && (
        <div style={{ background: '#0f1117', borderRadius: 8, padding: 16, marginBottom: 14 }}>
          <div style={{ fontSize: 13, color: '#94a3b8', fontWeight: 700, marginBottom: 10 }}>SCREENSHOT</div>
          <img
            src={imgUrl}
            alt="Screenshot"
            style={{ maxWidth: '100%', maxHeight: 500, borderRadius: 6, border: '1px solid #2a2d3a', display: 'block', cursor: 'pointer' }}
            onClick={() => setSsFullscreen(true)}
          />
        </div>
      )}

      {/* Mesa (players_list) */}
      {playersList.length > 0 && (
        <div style={{ background: '#0f1117', borderRadius: 8, padding: '16px 20px' }}>
          <div style={{ fontSize: 13, color: '#94a3b8', fontWeight: 700, marginBottom: 12 }}>MESA ({playersList.length} JOGADORES)</div>
          {playersList.map((p, i) => {
            const nameLower = (p.name || '').toLowerCase()
            const isHero = p.name === hero || HERO_NAMES_ALL.has(nameLower)
            const isSb = p.name === visionSb
            const isBb = p.name === visionBb
            const label = isSb ? 'SB' : isBb ? 'BB' : null
            const stackDisplay = p.stack_unit === 'bb'
              ? `${p.stack_raw ?? p.stack} BB`
              : (p.stack_chips || p.stack ? Math.round(p.stack_chips || p.stack).toLocaleString() : '—')
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 14, padding: '9px 14px',
                borderBottom: i < playersList.length - 1 ? '1px solid #14171f' : 'none',
                background: isHero ? 'rgba(99,102,241,0.05)' : 'transparent', borderRadius: 4,
              }}>
                {label ? <PosBadge pos={label} /> : <span style={{ minWidth: 48 }} />}
                <span style={{ fontSize: 16, fontWeight: isHero ? 700 : 500, color: isHero ? '#a5b4fc' : '#f1f5f9', minWidth: 160 }}>
                  {p.name || '—'}
                  {isHero && <span style={{ fontSize: 10, fontWeight: 700, color: '#818cf8', marginLeft: 6 }}>HERO</span>}
                </span>
                <span style={{ fontSize: 15, color: '#64748b', fontFamily: 'monospace', minWidth: 90, textAlign: 'right' }}>
                  {stackDisplay}
                </span>
                {p.bounty_pct != null && p.bounty_pct > 0 && (
                  <span style={{
                    fontSize: 14, color: '#7dd3fc', fontWeight: 700,
                    padding: '2px 8px', borderRadius: 4,
                    background: 'rgba(125,211,252,0.08)', border: '1px solid rgba(125,211,252,0.15)',
                  }}>{p.bounty_pct}%</span>
                )}
                {p.country && (
                  <span style={{ fontSize: 12, color: '#64748b', fontFamily: 'monospace' }}>{p.country}</span>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Screenshot fullscreen overlay (mesmo padrão de Hands/Villains) */}
      {ssFullscreen && imgUrl && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.92)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000,
            cursor: 'pointer',
          }}
          onClick={() => setSsFullscreen(false)}
        >
          <img
            src={imgUrl}
            alt="Screenshot"
            style={{ maxWidth: '95vw', maxHeight: '95vh', borderRadius: 8 }}
            onClick={e => e.stopPropagation()}
          />
          <button
            onClick={() => setSsFullscreen(false)}
            style={{
              position: 'absolute', top: 20, right: 20,
              background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff',
              fontSize: 24, cursor: 'pointer', borderRadius: 8, padding: '4px 12px',
            }}
          >✕</button>
        </div>
      )}
    </div>
  )
}
