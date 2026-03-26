import { useEffect, useState, useCallback } from 'react'
import { tournaments } from '../api/client'

// ── Constantes ───────────────────────────────────────────────────────────────

const SITES  = ['Winamax', 'GGPoker', 'PokerStars', 'WPN']
const TYPES  = [{ v: '', l: 'Tipo' }, { v: 'ko', l: 'KO' }, { v: 'nonko', l: 'Non-KO' }]
const SPEEDS = [{ v: '', l: 'Speed' }, { v: 'normal', l: 'Normal' }, { v: 'turbo', l: 'Turbo' }, { v: 'hyper', l: 'Hyper' }]
const RESULT = [{ v: '', l: 'Resultado' }, { v: 'cashed', l: 'Cashed' }, { v: 'no_cash', l: 'Bust' }]

const SUIT_COLORS  = { h: '#ef4444', d: '#f97316', c: '#22c55e', s: '#e2e8f0' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }

const STREET_LABELS = { preflop: 'Pre-Flop', flop: 'Flop', turn: 'Turn', river: 'River' }
const STREET_COLORS = { preflop: '#6366f1', flop: '#22c55e', turn: '#f59e0b', river: '#ef4444' }

const ACTION_COLORS = {
  fold:  { color: '#64748b', bg: 'rgba(100,116,139,0.10)' },
  check: { color: '#94a3b8', bg: 'rgba(148,163,184,0.10)' },
  call:  { color: '#22c55e', bg: 'rgba(34,197,94,0.10)'   },
  bet:   { color: '#f59e0b', bg: 'rgba(245,158,11,0.10)'  },
  raise: { color: '#f97316', bg: 'rgba(249,115,22,0.10)'  },
  allin: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)'   },
}

// ── Helpers de UI ─────────────────────────────────────────────────────────────

function PokerCard({ card, size = 'md' }) {
  if (!card || card.length < 2) {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: size === 'sm' ? 26 : size === 'lg' ? 38 : 34,
        height: size === 'sm' ? 36 : size === 'lg' ? 50 : 46,
        background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 4, fontSize: size === 'sm' ? 10 : 12, color: '#4b5563',
      }}>?</span>
    )
  }
  const rank   = card.slice(0, -1).toUpperCase()
  const suit   = card.slice(-1).toLowerCase()
  const color  = SUIT_COLORS[suit] || '#e2e8f0'
  const symbol = SUIT_SYMBOLS[suit] || suit
  return (
    <span style={{
      display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      width: size === 'sm' ? 26 : size === 'lg' ? 38 : 34,
      height: size === 'sm' ? 36 : size === 'lg' ? 50 : 46,
      background: '#1e2130', border: '1px solid rgba(255,255,255,0.12)',
      borderRadius: 4, fontFamily: "'Fira Code', monospace",
      fontSize: size === 'sm' ? 10 : size === 'lg' ? 14 : 12,
      fontWeight: 700, color, lineHeight: 1, gap: 1, userSelect: 'none',
      boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
    }}>
      <span>{rank}</span>
      <span style={{ fontSize: size === 'sm' ? 9 : size === 'lg' ? 13 : 11 }}>{symbol}</span>
    </span>
  )
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ color: '#4b5563' }}>—</span>
  const colors = {
    BTN: '#6366f1', CO: '#8b5cf6', HJ: '#a78bfa',
    SB: '#f59e0b', BB: '#ef4444',
    UTG: '#22c55e', UTG1: '#16a34a', UTG2: '#15803d',
    MP: '#06b6d4', MP1: '#0891b2',
  }
  const c = colors[pos] || '#64748b'
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 4,
      fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
      color: c, background: `${c}20`, border: `1px solid ${c}40`,
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

function actionStyle(text) {
  const t = (text || '').toLowerCase()
  if (t.includes('all-in') || t.includes('allin') || t.includes('all in')) return ACTION_COLORS.allin
  if (t.startsWith('raise') || t.startsWith('re-raise')) return ACTION_COLORS.raise
  if (t.startsWith('bet')) return ACTION_COLORS.bet
  if (t.startsWith('call')) return ACTION_COLORS.call
  if (t.startsWith('check')) return ACTION_COLORS.check
  if (t.startsWith('fold')) return ACTION_COLORS.fold
  return { color: '#94a3b8', bg: 'rgba(148,163,184,0.08)' }
}

function ActionBadge({ text }) {
  const s = actionStyle(text)
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 4,
      fontSize: 10, fontWeight: 600, fontFamily: 'monospace',
      color: s.color, background: s.bg, border: `1px solid ${s.color}25`,
      whiteSpace: 'nowrap',
    }}>{text}</span>
  )
}

// ── Normalise all_players_actions ─────────────────────────────────────────────

function normaliseActions(raw) {
  if (!raw) return null
  if (Array.isArray(raw.players)) {
    return raw.players.map(p => ({
      name: p.name || 'Player',
      position: p.position,
      isHero: p.name === raw.hero_name,
      cards: p.cards || null,
      stackBB: p.stack_bb ?? null,
      actions: Object.fromEntries(
        Object.entries(p.actions || {}).map(([street, val]) => [
          street,
          Array.isArray(val) ? val : (val && val !== '-' && val !== 'None') ? [val] : [],
        ])
      ),
    }))
  }
  const SEAT_ORDER = ['SB', 'BB', 'UTG', 'UTG1', 'UTG2', 'MP', 'MP1', 'HJ', 'CO', 'BTN']
  return Object.entries(raw)
    .map(([name, info]) => ({
      name,
      position: info.position || '',
      isHero: !!info.is_hero,
      cards: info.cards || null,
      stackBB: info.stack_bb ?? null,
      actions: Object.fromEntries(
        Object.entries(info.actions || {}).map(([street, val]) => [
          street,
          Array.isArray(val) ? val : (val && val !== '-' && val !== 'None') ? [val] : [],
        ])
      ),
    }))
    .sort((a, b) => {
      const ia = SEAT_ORDER.indexOf(a.position)
      const ib = SEAT_ORDER.indexOf(b.position)
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
    })
}

// ── Acções por Street ─────────────────────────────────────────────────────────

function AllPlayersActions({ actions }) {
  const players = normaliseActions(actions)
  if (!players || players.length === 0) return null
  const streets = ['preflop', 'flop', 'turn', 'river']
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 10, textTransform: 'uppercase' }}>
        Acções por Street
      </div>
      {streets.map(street => {
        const hasActions = players.some(p => p.actions?.[street]?.length > 0)
        if (!hasActions) return null
        return (
          <div key={street} style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
                color: STREET_COLORS[street], textTransform: 'uppercase',
                padding: '2px 8px', borderRadius: 4,
                background: `${STREET_COLORS[street]}15`,
                border: `1px solid ${STREET_COLORS[street]}30`,
              }}>{STREET_LABELS[street]}</span>
            </div>
            <div style={{
              display: 'flex', flexDirection: 'column', gap: 0,
              background: '#0f1117', borderRadius: 8, padding: '6px 12px',
              border: '1px solid #1e2130',
            }}>
              {players.map((player, i) => {
                const acts = player.actions?.[street] || []
                if (acts.length === 0) return null
                return (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '5px 0', borderBottom: '1px solid #1a1d27',
                  }}>
                    <PosBadge pos={player.position} />
                    <span style={{
                      fontSize: 11,
                      color: player.isHero ? '#818cf8' : '#94a3b8',
                      fontWeight: player.isHero ? 600 : 400,
                      minWidth: 80,
                    }}>
                      {player.name}
                      {player.isHero && <span style={{ fontSize: 9, color: '#6366f1', marginLeft: 4 }}>(HERO)</span>}
                    </span>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {acts.map((a, j) => <ActionBadge key={j} text={a} />)}
                    </div>
                    {player.stackBB != null && (
                      <span style={{ fontSize: 9, color: '#4b5563', marginLeft: 'auto', fontFamily: 'monospace' }}>
                        {player.stackBB.toFixed(1)} BB
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Modal de Detalhe da Mão ───────────────────────────────────────────────────

function HandDetailModal({ hand, onClose }) {
  const isGG = (hand.raw || '').includes('gg.gl') || (hand.hand_id || '').startsWith('GG-')
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
      backdropFilter: 'blur(4px)',
    }} onClick={onClose}>
      <div
        style={{
          width: '92%', maxWidth: 800, maxHeight: '90vh', overflow: 'auto',
          background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12,
          padding: 28,
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <span style={{ fontWeight: 700, fontSize: 17 }}>Mão #{hand.id}</span>
              {hand.result != null && <ResultBadge result={hand.result} />}
            </div>
            {hand.stakes && <div style={{ fontSize: 12, color: '#64748b' }}>{hand.stakes}</div>}
          </div>
          <button
            style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 18, padding: 4 }}
            onClick={onClose}
          >&#10005;</button>
        </div>

        {/* Cartas + Board */}
        <div style={{
          background: '#0f1117', borderRadius: 10, padding: '16px 20px',
          marginBottom: 20, display: 'flex', gap: 32, alignItems: 'center', flexWrap: 'wrap',
        }}>
          <div>
            <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>
              Hero · <PosBadge pos={hand.position} />
            </div>
            <div style={{ display: 'flex', gap: 5 }}>
              {hand.hero_cards?.length > 0
                ? hand.hero_cards.map((c, i) => <PokerCard key={i} card={c} size="lg" />)
                : <span style={{ color: '#4b5563', fontSize: 13 }}>Cartas não visíveis</span>
              }
            </div>
          </div>
          {hand.board?.length > 0 && (
            <div>
              <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Board</div>
              <div style={{ display: 'flex', gap: 5 }}>
                {hand.board.slice(0, 5).map((c, i) => <PokerCard key={i} card={c} size="lg" />)}
              </div>
            </div>
          )}
        </div>

        {/* Info grid */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px 20px',
          marginBottom: 20, fontSize: 13,
        }}>
          {[
            { l: 'Sala',      v: hand.site },
            { l: 'Data',      v: hand.played_at ? hand.played_at.slice(0, 10) : null },
            { l: 'Resultado', v: <ResultBadge result={hand.result} /> },
            { l: 'Posição',   v: <PosBadge pos={hand.position} /> },
            { l: 'Torneio',   v: hand.stakes },
            { l: 'Hand ID',   v: hand.hand_id ? <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{hand.hand_id.slice(-12)}</span> : null },
          ].map(({ l, v }) => (
            <div key={l} style={{ background: '#0f1117', borderRadius: 6, padding: '8px 12px' }}>
              <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, letterSpacing: 0.4, marginBottom: 3, textTransform: 'uppercase' }}>{l}</div>
              <div>{v || <span style={{ color: '#4b5563' }}>—</span>}</div>
            </div>
          ))}
        </div>

        {/* Acções por street */}
        {hand.all_players_actions && <AllPlayersActions actions={hand.all_players_actions} />}

        {/* Screenshot */}
        {hand.screenshot_url && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>Screenshot</div>
            <img
              src={hand.screenshot_url}
              alt="Screenshot da mão"
              style={{ maxWidth: '100%', borderRadius: 8, border: '1px solid #2a2d3a', cursor: 'pointer' }}
              onClick={() => window.open(hand.screenshot_url, '_blank')}
            />
          </div>
        )}

        {/* Replayer GG */}
        {isGG && hand.raw && (hand.raw.startsWith('http') || hand.raw.includes('gg.gl')) && (
          <div style={{ marginBottom: 16 }}>
            <a href={hand.raw} target="_blank" rel="noopener noreferrer" style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 500,
              background: 'rgba(99,102,241,0.12)', color: '#818cf8',
              border: '1px solid rgba(99,102,241,0.25)', textDecoration: 'none',
            }}>
              &#9654; Abrir Replayer GG
            </a>
          </div>
        )}

        {/* Tags */}
        {hand.tags && hand.tags.length > 0 && (
          <div style={{ marginTop: 8 }}>
            {hand.tags.map(t => (
              <span key={t} style={{
                display: 'inline-block', padding: '2px 9px', borderRadius: 999,
                fontSize: 11, fontWeight: 600, marginRight: 4,
                color: '#818cf8', background: 'rgba(99,102,241,0.12)',
                border: '1px solid rgba(99,102,241,0.25)',
              }}>#{t}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Painel de Mãos do Torneio ─────────────────────────────────────────────────

function TournamentHandsPanel({ tournament, onClose }) {
  const [handsData, setHandsData] = useState({ data: [], total: 0 })
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')
  const [selected, setSelected]   = useState(null)
  const [page, setPage]           = useState(1)

  const PAGE_SIZE = 200

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    tournaments.hands(tournament.id, { page, page_size: PAGE_SIZE })
      .then(res => setHandsData({ data: res.data || [], total: res.total || 0, pages: res.pages || 1 }))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [tournament.id, page])

  useEffect(() => { load() }, [load])

  const cur = tournament.currency || '$'
  const res = Number(tournament.result || 0)

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 900,
      backdropFilter: 'blur(4px)',
    }} onClick={onClose}>
      <div
        style={{
          width: '96%', maxWidth: 1100, maxHeight: '92vh', overflow: 'auto',
          background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12,
          padding: 28,
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>{tournament.name}</div>
            <div style={{ display: 'flex', gap: 16, fontSize: 13, color: '#64748b', flexWrap: 'wrap' }}>
              <span>{tournament.date}</span>
              <span>{tournament.site}</span>
              <span>{cur}{Number(tournament.buyin || 0).toFixed(2)} buy-in</span>
              {tournament.cashout > 0 && <span style={{ color: '#22c55e' }}>Cashed: {cur}{Number(tournament.cashout).toFixed(2)}</span>}
              <span style={{ color: res >= 0 ? '#22c55e' : '#ef4444', fontWeight: 600 }}>
                {res >= 0 ? '+' : ''}{cur}{Math.abs(res).toFixed(2)}
              </span>
              {tournament.position && <span>Pos: {tournament.position}</span>}
              {tournament.players && <span>{tournament.players} jogadores</span>}
            </div>
          </div>
          <button
            style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 18, padding: 4 }}
            onClick={onClose}
          >&#10005;</button>
        </div>

        {/* Contagem */}
        <div style={{ fontSize: 13, color: '#64748b', marginBottom: 16 }}>
          {loading ? 'A carregar…' : `${handsData.total} mãos neste torneio`}
        </div>

        {error && (
          <div style={{ color: '#ef4444', fontSize: 13, marginBottom: 12, padding: '8px 12px', background: 'rgba(239,68,68,0.08)', borderRadius: 6 }}>
            {error}
          </div>
        )}

        {/* Tabela de mãos */}
        {!loading && handsData.data.length === 0 && (
          <div style={{ textAlign: 'center', padding: 32, color: '#4b5563', fontSize: 14 }}>
            Sem mãos importadas para este torneio.
            <div style={{ fontSize: 12, marginTop: 8, color: '#374151' }}>
              As mãos são associadas automaticamente ao importar ficheiros HH após importar os summaries.
            </div>
          </div>
        )}

        {!loading && handsData.data.length > 0 && (
          <div style={{ border: '1px solid #2a2d3a', borderRadius: 8, overflow: 'hidden' }}>
            {/* Cabeçalho */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '50px 60px 90px 150px 80px 80px 1fr',
              gap: 8, padding: '8px 16px',
              background: '#0f1117', borderBottom: '1px solid #2a2d3a',
              fontSize: 10, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.5,
            }}>
              <span>#</span>
              <span>Pos.</span>
              <span>Cartas</span>
              <span>Board</span>
              <span>Resultado</span>
              <span>Tags</span>
              <span>Data/Hora</span>
            </div>

            {handsData.data.map((hand, idx) => {
              const hRes = Number(hand.result || 0)
              return (
                <div
                  key={hand.id}
                  onClick={() => setSelected(hand)}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '50px 60px 90px 150px 80px 80px 1fr',
                    gap: 8, padding: '8px 16px',
                    background: idx % 2 === 0 ? '#1a1d27' : '#1e2130',
                    borderBottom: '1px solid #1e2130',
                    cursor: 'pointer', alignItems: 'center',
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.06)'}
                  onMouseLeave={e => e.currentTarget.style.background = idx % 2 === 0 ? '#1a1d27' : '#1e2130'}
                >
                  {/* Número sequencial */}
                  <span style={{ fontSize: 11, color: '#4b5563', fontFamily: 'monospace' }}>#{idx + 1 + (page - 1) * PAGE_SIZE}</span>

                  {/* Posição */}
                  <PosBadge pos={hand.position} />

                  {/* Cartas do hero */}
                  <div style={{ display: 'flex', gap: 2 }}>
                    {hand.hero_cards?.length > 0
                      ? hand.hero_cards.map((c, i) => <PokerCard key={i} card={c} size="sm" />)
                      : <span style={{ color: '#374151', fontSize: 11 }}>—</span>
                    }
                  </div>

                  {/* Board */}
                  <div style={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                    {hand.board?.length > 0
                      ? hand.board.slice(0, 5).map((c, i) => <PokerCard key={i} card={c} size="sm" />)
                      : <span style={{ color: '#374151', fontSize: 11 }}>—</span>
                    }
                  </div>

                  {/* Resultado */}
                  <ResultBadge result={hand.result} />

                  {/* Tags + badge de estudo */}
                  <div style={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
                    {hand.screenshot_url && (
                      <span title="Tem screenshot" style={{
                        fontSize: 9, padding: '1px 5px', borderRadius: 999,
                        color: '#22c55e', background: 'rgba(34,197,94,0.12)',
                        border: '1px solid rgba(34,197,94,0.25)',
                      }}>★</span>
                    )}
                    {hand.study_state && hand.study_state !== 'mtt_archive' && (
                      <span title={`Estudo: ${hand.study_state}`} style={{
                        fontSize: 9, padding: '1px 5px', borderRadius: 999,
                        color: '#818cf8', background: 'rgba(99,102,241,0.12)',
                        border: '1px solid rgba(99,102,241,0.25)',
                      }}>{hand.study_state}</span>
                    )}
                    {(hand.tags || []).filter(t => t !== 'mtt').map(t => (
                      <span key={t} style={{
                        fontSize: 9, padding: '1px 5px', borderRadius: 999,
                        color: '#818cf8', background: 'rgba(99,102,241,0.12)',
                        border: '1px solid rgba(99,102,241,0.2)',
                      }}>#{t}</span>
                    ))}
                  </div>

                  {/* Data/hora */}
                  <span style={{ fontSize: 11, color: '#4b5563' }}>
                    {hand.played_at ? hand.played_at.slice(0, 16).replace('T', ' ') : '—'}
                  </span>
                </div>
              )
            })}
          </div>
        )}

        {/* Paginação */}
        {handsData.pages > 1 && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'center', marginTop: 16 }}>
            <button
              style={{ padding: '6px 14px', borderRadius: 6, fontSize: 12, background: '#1e2130', border: '1px solid #2a2d3a', color: '#94a3b8', cursor: 'pointer' }}
              disabled={page <= 1} onClick={() => setPage(p => p - 1)}
            >← Anterior</button>
            <span style={{ fontSize: 12, color: '#64748b' }}>Pág. {page} / {handsData.pages}</span>
            <button
              style={{ padding: '6px 14px', borderRadius: 6, fontSize: 12, background: '#1e2130', border: '1px solid #2a2d3a', color: '#94a3b8', cursor: 'pointer' }}
              disabled={page >= handsData.pages} onClick={() => setPage(p => p + 1)}
            >Próxima →</button>
          </div>
        )}
      </div>

      {/* Modal de detalhe da mão (sobre o painel) */}
      {selected && <HandDetailModal hand={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

// ── Página Principal: Torneios ────────────────────────────────────────────────

export default function TournamentsPage() {
  const [filters, setFilters] = useState({ site: '', type: '', speed: '', result: '', page: 1 })
  const [data, setData]       = useState({ data: [], total: 0, pages: 1 })
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')
  const [selected, setSelected] = useState(null)   // torneio seleccionado para drill-down

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    tournaments.list({ ...filters, page_size: 50 })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [filters])

  useEffect(() => { load() }, [load])

  function set(key, val) {
    setFilters(f => ({ ...f, [key]: val, page: key !== 'page' ? 1 : f.page }))
  }

  const rows = data.data || []

  // Totais da página actual
  const pageTotalBuyin   = rows.reduce((s, t) => s + Number(t.buyin || 0), 0)
  const pageTotalCashout = rows.reduce((s, t) => s + Number(t.cashout || 0), 0)
  const pageTotalResult  = rows.reduce((s, t) => s + Number(t.result || 0), 0)

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">MTT</div>
          <div className="page-subtitle">{data.total} torneios arquivados · clique para ver mãos</div>
        </div>
      </div>

      {/* Filtros */}
      <div className="filters">
        <select value={filters.site} onChange={e => set('site', e.target.value)}>
          <option value="">Todas as salas</option>
          {SITES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filters.type} onChange={e => set('type', e.target.value)}>
          {TYPES.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
        </select>
        <select value={filters.speed} onChange={e => set('speed', e.target.value)}>
          {SPEEDS.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
        </select>
        <select value={filters.result} onChange={e => set('result', e.target.value)}>
          {RESULT.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
        </select>
        <button className="btn btn-ghost btn-sm" onClick={() => setFilters({ site: '', type: '', speed: '', result: '', page: 1 })}>
          Limpar
        </button>
      </div>

      {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Data</th>
                <th>Sala</th>
                <th>Torneio</th>
                <th>Tipo</th>
                <th>Buy-in</th>
                <th>Cashout</th>
                <th>Pos.</th>
                <th>Mãos</th>
                <th>Resultado</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={9} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>A carregar…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={9}><div className="empty-state">Sem resultados.</div></td></tr>
              )}
              {!loading && rows.map(t => {
                const res = Number(t.result)
                const cur = t.currency || '$'
                return (
                  <tr
                    key={t.id}
                    style={{ cursor: 'pointer' }}
                    onClick={() => setSelected(t)}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.06)'}
                    onMouseLeave={e => e.currentTarget.style.background = ''}
                  >
                    <td className="muted">{t.date}</td>
                    <td>{t.site}</td>
                    <td style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={t.name}>
                      {t.name}
                    </td>
                    <td>
                      <span style={{ display: 'inline-flex', gap: 4 }}>
                        <span className={`badge badge-${t.type}`}>{t.type}</span>
                        {t.speed !== 'normal' && <span className={`badge badge-${t.speed}`}>{t.speed}</span>}
                      </span>
                    </td>
                    <td>{cur}{Number(t.buyin).toFixed(2)}</td>
                    <td>{t.cashout > 0 ? `${cur}${Number(t.cashout).toFixed(2)}` : '—'}</td>
                    <td className="muted">{t.position ?? '—'}</td>
                    <td className="muted" style={{ fontFamily: 'monospace', fontSize: 11 }}>
                      {t.hand_count != null ? t.hand_count : '—'}
                    </td>
                    <td className={res >= 0 ? 'green' : 'red'}>
                      {res >= 0 ? '+' : ''}{cur}{Math.abs(res).toFixed(2)}
                    </td>
                  </tr>
                )
              })}

              {/* Totais da página */}
              {!loading && rows.length > 0 && (
                <tr style={{ borderTop: '2px solid #2a2d3a', fontWeight: 700, background: '#0f1117' }}>
                  <td colSpan={4} style={{ color: '#64748b', fontSize: 11 }}>Total ({rows.length} torneios)</td>
                  <td>${pageTotalBuyin.toFixed(2)}</td>
                  <td>${pageTotalCashout.toFixed(2)}</td>
                  <td></td>
                  <td></td>
                  <td className={pageTotalResult >= 0 ? 'green' : 'red'}>
                    {pageTotalResult >= 0 ? '+' : ''}${Math.abs(pageTotalResult).toFixed(2)}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {data.pages > 1 && (
          <div className="pagination">
            <button className="btn btn-ghost btn-sm" disabled={filters.page <= 1} onClick={() => set('page', filters.page - 1)}>← Anterior</button>
            <span className="muted">Pág. {filters.page} / {data.pages}</span>
            <button className="btn btn-ghost btn-sm" disabled={filters.page >= data.pages} onClick={() => set('page', filters.page + 1)}>Próxima →</button>
          </div>
        )}
      </div>

      {/* Painel de drill-down */}
      {selected && (
        <TournamentHandsPanel
          tournament={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  )
}
