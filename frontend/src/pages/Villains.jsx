import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { villains, hands as handsApi, mtt, hm3 } from '../api/client'
import { SITE_COLORS, SITE_COLOR_DEFAULT } from '../lib/siteColors'
import { compactStreetActions } from '../lib/handParser'

// ── Mini helpers ─────────────────────────────────────────────────────────────

const SUIT_COLORS  = { h: '#ef4444', d: '#f97316', c: '#22c55e', s: '#e2e8f0' }
const SUIT_BG      = { h: '#dc2626', d: '#2563eb', c: '#16a34a', s: '#1e293b' }
const SUIT_SYMBOLS = { h: '♥', d: '♦', c: '♣', s: '♠' }

function MiniCard({ card, hidden = false }) {
  // Tech Debt #UX1 (pt7): prop `hidden` renderiza "—" cinza para villains
  // que não mostraram cards no showdown (foldaram ou mucked). Substitui o
  // hack antigo de mostrar cards do Hero como cards do villain.
  if (hidden) {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: 22, height: 30, background: '#0f1117',
        border: '1px solid #2a2d3a', borderRadius: 3,
        fontFamily: "'Fira Code', monospace", fontSize: 16,
        fontWeight: 700, color: '#4b5563', lineHeight: 1,
      }}>—</span>
    )
  }
  if (!card || card.length < 2) return <span style={{ color: '#4b5563' }}>?</span>
  const rank = card.slice(0, -1).toUpperCase()
  const suit = card.slice(-1).toLowerCase()
  const bg = SUIT_BG[suit] || '#1e2130'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 22, height: 30, background: bg, border: '1px solid rgba(255,255,255,0.2)',
      borderRadius: 3, fontFamily: "'Fira Code', monospace", fontSize: 11,
      fontWeight: 700, color: '#fff', lineHeight: 1, flexDirection: 'column', gap: 0,
    }}>
      <span>{rank}</span>
      <span style={{ fontSize: 7 }}>{SUIT_SYMBOLS[suit]}</span>
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
      display: 'inline-block', padding: '1px 6px', borderRadius: 3,
      fontSize: 11, fontWeight: 700, letterSpacing: 0.4,
      color: c, background: `${c}18`, border: `1px solid ${c}30`,
    }}>{pos}</span>
  )
}

function ResultBadge({ result }) {
  if (result == null) return <span style={{ color: '#4b5563' }}>—</span>
  const val = Number(result)
  if (val > 0) return <span style={{ color: '#22c55e', fontWeight: 600, fontFamily: 'monospace', fontSize: 11 }}>+{val.toFixed(1)}</span>
  if (val < 0) return <span style={{ color: '#ef4444', fontWeight: 600, fontFamily: 'monospace', fontSize: 11 }}>{val.toFixed(1)}</span>
  return <span style={{ color: '#64748b', fontFamily: 'monospace', fontSize: 11 }}>0</span>
}

// ── Tech Debt #12 + #UX1 (pt7): grid partilhado modal villain ──────────────
//
// Linha colapsada (10 cols): ▶ Data Pos+Nome Stack/Cards pf F T R Resultado Tournament
// Tabela expandida (6 cols mapeados): cols 3-8 da colapsada (Pos→Pos, Stack→Stack,
//   pf→pf, F→F, T→T, R→R). Cols 1-2 e 9-10 NÃO existem na expandida.
//
// gridTemplateColumns idêntico em ambas componentes garante alinhamento
// vertical: click ▶ expande sem mover horizontalmente o nome.
const GRID_COLS_FULL    = '14px 56px 130px 90px 80px 80px 80px 80px 60px 1fr'
const GRID_COLS_EXPANDED = 'subgrid'  // CSS subgrid herda do parent
// Fallback se subgrid não suportado: replica cols 3-8 (sem padding ▶/data nem cols R/T)
const GRID_COLS_EXPANDED_FALLBACK = '130px 90px 80px 80px 80px 80px'
// Wrapper expandido começa após cols ▶+Data (largura 14+56+gap=78px); usa
// margem-left ou nested grid. Solução simples: nested grid com mesmas cols
// 3-8 do template full, com margin-left para visual alinhamento.

const SEAT_ORDER = ['UTG', 'UTG1', 'UTG2', 'MP', 'MP1', 'HJ', 'CO', 'BTN', 'SB', 'BB']

function CompactHandRow({ hand, villainNick, expanded, onToggle }) {
  const apa = hand.all_players_actions || {}
  const villainInfo = apa[villainNick] || {}
  const villainPos = villainInfo.position || '?'
  const villainCards = villainInfo.cards
  const showVillainCards = Array.isArray(villainCards) && villainCards.length === 2

  const board = hand.board || []
  const flop = board.slice(0, 3)
  const turn = board.slice(3, 4)
  const river = board.slice(4, 5)

  const dateStr = hand.played_at ? hand.played_at.slice(5, 10) : '—'
  const tourneyName = hand.tournament_name || hand.stakes || ''
  const result = hand.villain_result ?? hand.result

  return (
    <div
      onClick={onToggle}
      style={{
        display: 'grid',
        gridTemplateColumns: GRID_COLS_FULL,
        alignItems: 'center', gap: 6,
        padding: '8px 10px',
        cursor: 'pointer',
        fontSize: 11,
      }}
      onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.04)'}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      <span style={{ color: '#4b5563', fontSize: 10 }}>{expanded ? '▼' : '▶'}</span>
      <span style={{ color: '#4b5563', fontFamily: 'monospace' }}>{dateStr}</span>
      <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
        <PosBadge pos={villainPos} />
        <span style={{ color: '#f59e0b', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{villainNick}</span>
      </span>
      <span style={{ display: 'flex', gap: 2 }}>
        {showVillainCards
          ? villainCards.map((c, j) => <MiniCard key={j} card={c} />)
          : [<MiniCard key="x1" hidden />, <MiniCard key="x2" hidden />]
        }
      </span>
      <span></span>{/* pf vazio na colapsada */}
      <span style={{ display: 'flex', gap: 2 }}>{flop.map((c, j) => <MiniCard key={j} card={c} />)}</span>
      <span style={{ display: 'flex', gap: 2 }}>{turn.map((c, j) => <MiniCard key={j} card={c} />)}</span>
      <span style={{ display: 'flex', gap: 2 }}>{river.map((c, j) => <MiniCard key={j} card={c} />)}</span>
      <span><ResultBadge result={result} /></span>
      <span style={{ color: '#4b5563', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {tourneyName}
      </span>
    </div>
  )
}

function ExpandedHandTable({ hand, villainNick }) {
  // Tabela 6 cols: Pos+Nome+Cards | Stack | pf | F | T | R
  // Alinha com cols 3-8 da CompactHandRow (Pos→Pos, Stack→Stack/Cards,
  // pf/F/T/R correspondentes). Margem-left de 14+56+gap=76px alinha com
  // col "Pos" da linha colapsada (skip cols ▶ + Data).
  const apa = hand.all_players_actions || {}
  const players = Object.entries(apa)
    .filter(([k]) => k !== '_meta')
    .map(([name, info]) => ({ name, ...info }))
    .sort((a, b) => {
      const ia = SEAT_ORDER.indexOf(a.position)
      const ib = SEAT_ORDER.indexOf(b.position)
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
    })

  // Para cada street, computar raiseCount cumulativo (todos os players).
  // Iteramos players por SEAT_ORDER mas a contagem importa só para o output
  // visual de cada player — raiseCount real é cross-player.
  // Estratégia: pré-computar para cada street o output compacto de cada
  // player por ordem de SEAT_ORDER (ordem aproximada de actuação).
  const STREETS = ['preflop', 'flop', 'turn', 'river']
  const compactByPlayerStreet = {}
  for (const st of STREETS) {
    let raiseCount = 0
    for (const p of players) {
      const acts = p.actions?.[st]
      if (!acts || acts.length === 0) {
        if (!compactByPlayerStreet[p.name]) compactByPlayerStreet[p.name] = {}
        compactByPlayerStreet[p.name][st] = ''
        continue
      }
      const { compact, raiseCountEnd } = compactStreetActions(acts, raiseCount)
      raiseCount = raiseCountEnd
      if (!compactByPlayerStreet[p.name]) compactByPlayerStreet[p.name] = {}
      compactByPlayerStreet[p.name][st] = compact
    }
  }

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '130px 90px 80px 80px 80px 80px',
      gap: 6,
      marginLeft: 76,  // 14 (chevron) + 56 (data) + 6*2 gaps = 76px
      padding: '8px 10px 12px',
      background: 'rgba(255,255,255,0.01)',
      fontSize: 11,
    }}>
      {/* Header row */}
      <div style={{ fontSize: 10, color: '#4b5563', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>Pos / Nome / Cards</div>
      <div style={{ fontSize: 10, color: '#4b5563', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>Stack</div>
      <div style={{ fontSize: 10, color: '#4b5563', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>pf</div>
      <div style={{ fontSize: 10, color: '#4b5563', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>F</div>
      <div style={{ fontSize: 10, color: '#4b5563', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>T</div>
      <div style={{ fontSize: 10, color: '#4b5563', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>R</div>

      {/* Player rows */}
      {players.map(p => {
        const isHero = !!p.is_hero
        const isVillain = p.name === villainNick
        const cards = p.cards
        // Hero sempre real cards; villain cards se mostrou no SD; outros: hidden ou real se mostraram
        const hasRealCards = Array.isArray(cards) && cards.length === 2
        const showCards = isHero ? hasRealCards : hasRealCards
        const stackStr = p.stack_bb != null ? `${p.stack_bb.toFixed(1)} BB` : '—'
        const cs = compactByPlayerStreet[p.name] || {}
        const nameColor = isHero ? '#818cf8' : isVillain ? '#f59e0b' : '#94a3b8'

        return (
          <RowRender
            key={p.name}
            isHero={isHero}
            isVillain={isVillain}
            pos={p.position}
            name={p.name}
            nameColor={nameColor}
            cards={cards}
            showCards={showCards}
            stackStr={stackStr}
            cs={cs}
          />
        )
      })}
    </div>
  )
}

function RowRender({ isHero, isVillain, pos, name, nameColor, cards, showCards, stackStr, cs }) {
  // Wrapper React.Fragment para emitir 6 cells directamente filhos do grid.
  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, overflow: 'hidden' }}>
        <PosBadge pos={pos} />
        <span style={{ color: nameColor, fontWeight: isHero || isVillain ? 600 : 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>
          {name}
          {isHero && <span style={{ fontSize: 8, color: '#6366f1', marginLeft: 3 }}>HERO</span>}
          {isVillain && <span style={{ fontSize: 8, color: '#f59e0b', marginLeft: 3 }}>★</span>}
        </span>
        <span style={{ display: 'flex', gap: 2 }}>
          {showCards
            ? cards.map((c, j) => <MiniCard key={j} card={c} />)
            : [<MiniCard key="x1" hidden />, <MiniCard key="x2" hidden />]
          }
        </span>
      </div>
      <div style={{ color: '#4b5563', fontFamily: 'monospace', fontSize: 11 }}>{stackStr}</div>
      <div style={{ color: '#94a3b8', fontFamily: 'monospace', fontSize: 10 }}>{cs.preflop || ''}</div>
      <div style={{ color: '#94a3b8', fontFamily: 'monospace', fontSize: 10 }}>{cs.flop || ''}</div>
      <div style={{ color: '#94a3b8', fontFamily: 'monospace', fontSize: 10 }}>{cs.turn || ''}</div>
      <div style={{ color: '#94a3b8', fontFamily: 'monospace', fontSize: 10 }}>{cs.river || ''}</div>
    </>
  )
}

// ── Villain Profile Panel ────────────────────────────────────────────────────

function VillainProfile({ villain, onClose, onSave }) {
  // Tech Debt #12 + #UX1 (pt7): refactor para 1 coluna 100% width.
  // PARTE 1 spec: removido painel esquerdo (Notas + Tags + Guardar);
  // "Mãos em Comum" expande para 100% width usando CompactHandRow + ExpandedHandTable.
  const [hands, setHands] = useState([])
  const [handsTotal, setHandsTotal] = useState(0)
  const [handsLoading, setHandsLoading] = useState(false)
  const [handsPage, setHandsPage] = useState(1)
  const [expandedHand, setExpandedHand] = useState(null)

  useEffect(() => {
    loadHands(1)
  }, [villain.nick])

  function loadHands(p) {
    setHandsLoading(true)
    setHandsPage(p)
    villains.searchHands(villain.nick, { page: p, page_size: 10 })
      .then(res => {
        setHands(res.data || [])
        setHandsTotal(res.total || 0)
      })
      .catch(() => {})
      .finally(() => setHandsLoading(false))
  }

  const handsPages = Math.ceil(handsTotal / 10)

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
      backdropFilter: 'blur(4px)',
    }} onClick={onClose}>
      <div
        style={{
          width: '95%', maxWidth: 1100, maxHeight: '92vh', overflow: 'auto',
          background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12,
          padding: 24,
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>{villain.nick}</div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              {villain.site && (
                <span style={{ fontSize: 12, color: '#64748b', background: '#0f1117', padding: '2px 8px', borderRadius: 4, border: '1px solid #2a2d3a' }}>
                  {villain.site}
                </span>
              )}
              {(villain.tags || []).map(t => (
                <span key={t} style={{ fontSize: 11, color: '#818cf8', background: 'rgba(99,102,241,0.12)', padding: '2px 8px', borderRadius: 999, border: '1px solid rgba(99,102,241,0.25)' }}>
                  #{t}
                </span>
              ))}
              <span style={{ fontSize: 12, color: '#4b5563' }}>{handsTotal} mãos em comum</span>
            </div>
          </div>
          <button
            style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 18, padding: 4 }}
            onClick={onClose}
          >✕</button>
        </div>

        {/* Mãos em Comum — 100% width */}
        <div>
          <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: 0.5, marginBottom: 8, textTransform: 'uppercase' }}>
            Mãos em Comum ({handsTotal})
          </div>

          {handsLoading && (
            <div style={{ textAlign: 'center', padding: '24px 0', color: '#4b5563', fontSize: 13 }}>A carregar...</div>
          )}

          {!handsLoading && hands.length === 0 && (
            <div style={{
              textAlign: 'center', padding: '32px 16px', color: '#4b5563', fontSize: 13,
              background: '#0f1117', borderRadius: 8, border: '1px solid #1e2130',
            }}>
              Sem mãos em comum na BD.<br />
              <span style={{ fontSize: 11, color: '#4b5563' }}>Importa HH ou faz match de screenshots.</span>
            </div>
          )}

          {!handsLoading && hands.length > 0 && (
            <div style={{ background: '#0f1117', borderRadius: 8, border: '1px solid #1e2130', overflow: 'hidden' }}>
              {hands.map((h, i) => {
                const isExpanded = expandedHand === h.id
                const toggle = () => setExpandedHand(isExpanded ? null : h.id)
                return (
                  <div key={h.id} style={{ borderBottom: i < hands.length - 1 ? '1px solid #1a1d27' : 'none' }}>
                    <CompactHandRow
                      hand={h}
                      villainNick={villain.nick}
                      expanded={isExpanded}
                      onToggle={toggle}
                    />
                    {isExpanded && (
                      <div>
                        <ExpandedHandTable hand={h} villainNick={villain.nick} />
                        {/* 3 acessos à mão */}
                        <div style={{ display: 'flex', gap: 6, padding: '4px 14px 12px 76px', flexWrap: 'wrap' }}>
                          {h.raw && h.all_players_actions && (
                            <a href={`/replayer/${h.id}`} target="_blank" rel="noopener noreferrer" style={{
                              fontSize: 11, color: '#818cf8', textDecoration: 'none', padding: '4px 10px',
                              borderRadius: 4, background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)',
                              fontWeight: 600,
                            }}>&#9654; Replayer</a>
                          )}
                          <a href={`/hand/${h.id}`} style={{
                            fontSize: 11, color: '#22c55e', textDecoration: 'none', padding: '4px 10px',
                            borderRadius: 4, background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.2)',
                            fontWeight: 600,
                          }}>HH Formatada</a>
                          {h.raw && (
                            <button onClick={() => { navigator.clipboard.writeText(h.raw); alert('HH copiada!') }} style={{
                              fontSize: 11, color: '#f59e0b', padding: '4px 10px',
                              borderRadius: 4, background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)',
                              fontWeight: 600, cursor: 'pointer',
                            }}>Copiar HH</button>
                          )}
                          {h.player_names?.gg_link && (
                            <a href={h.player_names.gg_link} target="_blank" rel="noopener noreferrer" style={{
                              fontSize: 11, color: '#fbbf24', textDecoration: 'none', padding: '4px 10px',
                              borderRadius: 4, background: 'rgba(251,191,36,0.1)', border: '1px solid rgba(251,191,36,0.2)',
                              fontWeight: 600,
                            }}>GG Replayer</a>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* Paginação */}
          {handsPages > 1 && (
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 10 }}>
              <button
                disabled={handsPage <= 1}
                onClick={() => loadHands(handsPage - 1)}
                style={{
                  padding: '4px 12px', borderRadius: 6, fontSize: 11,
                  background: 'transparent', color: handsPage <= 1 ? '#374151' : '#94a3b8',
                  border: '1px solid #2a2d3a', cursor: handsPage <= 1 ? 'not-allowed' : 'pointer',
                }}
              >←</button>
              <span style={{ color: '#4b5563', fontSize: 11, alignSelf: 'center' }}>
                {handsPage} / {handsPages}
              </span>
              <button
                disabled={handsPage >= handsPages}
                onClick={() => loadHands(handsPage + 1)}
                style={{
                  padding: '4px 12px', borderRadius: 6, fontSize: 11,
                  background: 'transparent', color: handsPage >= handsPages ? '#374151' : '#94a3b8',
                  border: '1px solid #2a2d3a', cursor: handsPage >= handsPages ? 'not-allowed' : 'pointer',
                }}
              >→</button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Página Principal ─────────────────────────────────────────────────────────

// ── Helpers Tech Debt #4 Parte D ─────────────────────────────────────────────

function SiteBadge({ site }) {
  const c = SITE_COLORS[site] || '#64748b'
  return (
    <span style={{
      display: 'inline-block', padding: '1px 7px', borderRadius: 3,
      fontSize: 10, fontWeight: 700, letterSpacing: 0.3,
      color: c, background: `${c}18`, border: `1px solid ${c}40`,
    }}>{site}</span>
  )
}

function relativeDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now - d
  const diffH = Math.floor(diffMs / 3600000)
  if (diffH < 1) return 'há minutos'
  if (diffH < 24) return `há ${diffH}h`
  const diffD = Math.floor(diffH / 24)
  if (diffD < 7) return `há ${diffD}d`
  return d.toLocaleDateString('pt-PT', { day: '2-digit', month: 'short' })
}

function datesLabel(arr) {
  if (!arr || arr.length === 0) return '—'
  if (arr.length === 1) return new Date(arr[0]).toLocaleDateString('pt-PT', { day: '2-digit', month: 'short' })
  if (arr.length === 2) {
    const fmt = (s) => new Date(s).toLocaleDateString('pt-PT', { day: '2-digit', month: 'short' })
    // arr vem ORDER BY date DESC; fim → início
    return `${fmt(arr[arr.length - 1])} → ${fmt(arr[0])}`
  }
  return `${arr.length} dias`
}

function CategoryBadge({ label, count, color }) {
  if (count == null) return null
  const dim = count === 0
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 4,
      fontSize: 11, fontWeight: 700, fontFamily: 'monospace',
      color: dim ? '#4b5563' : color,
      background: dim ? 'transparent' : `${color}15`,
      border: `1px solid ${dim ? '#2a2d3a' : color + '30'}`,
      marginRight: 4,
    }}>{label}: {count}</span>
  )
}

const TAB_DEFS = [
  { key: 'all',    label: 'Todos' },
  { key: 'sd',     label: 'Mãos com SD' },
  { key: 'nota',   label: 'Notas' },
  { key: 'friend', label: 'Amigos' },
]


// Tech Debt #13b — filtros sala persistidos em localStorage.
// Default: 4 salas activas. 0 salas → página vazia (respeita escolha user).
const SITES_ALL = ['Winamax', 'WPN', 'GGPoker', 'PokerStars']
const LS_KEY_SITE_FILTERS = 'villains_site_filters'

function loadInitialSiteFilters() {
  try {
    const raw = localStorage.getItem(LS_KEY_SITE_FILTERS)
    if (!raw) return new Set(SITES_ALL)
    const arr = JSON.parse(raw)
    if (!Array.isArray(arr)) return new Set(SITES_ALL)
    // Filtrar apenas salas conhecidas (ignora valores corrompidos)
    return new Set(arr.filter(s => SITES_ALL.includes(s)))
  } catch {
    return new Set(SITES_ALL)
  }
}

export default function VillainsPage() {
  const [data, setData]       = useState({ data: [], total: 0, pages: 1 })
  const [page, setPage]       = useState(1)
  const [search, setSearch]   = useState('')
  const [siteFilters, setSiteFilters] = useState(loadInitialSiteFilters)
  const [category, setCategory]     = useState('all')  // Tech Debt #13b: default Todos
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)

  // Create form
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ site: '', nick: '', note: '', tags: '' })
  const [creating, setCreating]     = useState(false)

  // Profile panel
  const [selected, setSelected] = useState(null)

  // Auto-abrir perfil se vier ?nick=... na URL (ex: vindo do Dashboard)
  const [searchParams, setSearchParams] = useSearchParams()
  useEffect(() => {
    const nickParam = searchParams.get('nick')
    if (!nickParam) return
    villains.list({ search: nickParam, page_size: 10 })
      .then(res => {
        const items = res?.data || []
        const match = items.find(v => v.nick === nickParam) || items[0]
        if (match) setSelected(match)
      })
      .catch(() => {})
      .finally(() => {
        searchParams.delete('nick')
        setSearchParams(searchParams, { replace: true })
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Tech Debt #13b — persistir filtros sala em localStorage
  useEffect(() => {
    try {
      localStorage.setItem(LS_KEY_SITE_FILTERS, JSON.stringify(Array.from(siteFilters)))
    } catch {
      // ignore quota/private mode errors
    }
  }, [siteFilters])

  function load(p = page, s = search) {
    // Tech Debt #13b: 0 salas seleccionadas → não chamar API, mostrar vazio.
    if (siteFilters.size === 0) {
      setData({ data: [], total: 0, pages: 0 })
      setLoading(false)
      return
    }
    // 4/4 salas → sem filtro (equivalente a all). <4/4 → CSV.
    const siteParam = siteFilters.size === SITES_ALL.length
      ? undefined
      : Array.from(siteFilters).join(',')
    setLoading(true)
    villains.listCategorized({
      category,
      site: siteParam,
      search: s || undefined,
      page: p,
      page_size: 50,
    })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  function toggleSiteFilter(site) {
    setSiteFilters(prev => {
      const next = new Set(prev)
      if (next.has(site)) next.delete(site)
      else next.add(site)
      return next
    })
    setPage(1)
  }

  useEffect(() => { load() }, [page, siteFilters, category])

  function handleSearch(e) {
    e.preventDefault()
    setPage(1)
    load(1, search)
  }

  // Adapter: lista nova devolve só nick. Modal VillainProfile precisa de id
  // (de villain_notes) para update da nota. Faz fetch ao endpoint legacy
  // e abre o modal com a row obtida. _create_villains_for_hand garante UPSERT
  // em villain_notes para todos os nicks criados pós-Parte A.
  async function openModal(nick) {
    try {
      const res = await villains.list({ search: nick, page_size: 5 })
      const match = (res.data || []).find(v => v.nick === nick)
      if (match) setSelected(match)
      else setError(`Sem entry em villain_notes para "${nick}". Tenta "Recalcular".`)
    } catch (e) {
      setError(e.message)
    }
  }

  async function handleCreate(e) {
    e.preventDefault()
    setCreating(true)
    try {
      await villains.create({
        ...form,
        tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : []
      })
      setForm({ site: '', nick: '', note: '', tags: '' })
      setShowCreate(false)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setCreating(false)
    }
  }

  async function deleteVillain(id) {
    if (!confirm('Apagar este vilão?')) return
    try {
      await villains.delete(id)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  const rows = data.data || []

  return (
    <>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <div>
            <div className="page-title">Vilões</div>
            <div className="page-subtitle">
              {data.total} {data.total === 1 ? 'vilão' : 'vilões'}
              {category !== 'all' && (
                <> · categoria <strong style={{ color: '#a5b4fc' }}>{TAB_DEFS.find(t => t.key === category)?.label}</strong></>
              )}
              {siteFilters.size > 0 && siteFilters.size < SITES_ALL.length && (
                <> · {Array.from(siteFilters).map(s => <SiteBadge key={s} site={s} />)}</>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <button
              onClick={async () => {
                if (!confirm('Recalcular hands_seen de todos os vilões (só VPIP)?')) return
                try {
                  const res = await villains.recalculate()
                  alert(`Recalculado: ${res.updated || 0} vilões actualizados`)
                  load()
                } catch (err) { alert('Erro: ' + err.message) }
              }}
              style={{ padding: '4px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: 'rgba(99,102,241,0.12)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.25)', cursor: 'pointer' }}
            >&#x1F504; Recalcular</button>
            <button
              onClick={async () => {
                if (!confirm('Re-enrich: re-processar todos os screenshots e criar villains VPIP?')) return
                try {
                  const res = await mtt.reEnrich()
                  alert(`Re-enrich: ${res.processed || 0} mãos, ${res.villains_created || 0} villains`)
                  load()
                } catch (err) { alert('Erro: ' + err.message) }
              }}
              style={{ padding: '4px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: 'rgba(245,158,11,0.12)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.25)', cursor: 'pointer' }}
            >&#x1F9E0; Re-enrich</button>
            <button
              onClick={async () => {
                if (!confirm('Re-parse: extrair acções de todas as mãos na BD? Pode demorar.')) return
                try {
                  const res = await hm3.reParse()
                  alert(`Re-parse concluído!\n\n${res.processed || 0} mãos processadas\n${res.updated || 0} actualizadas\n${res.errors || 0} erros`)
                  load()
                } catch (err) { alert('Erro: ' + err.message) }
              }}
              style={{ padding: '4px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: 'rgba(34,197,94,0.12)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.25)', cursor: 'pointer' }}
            >&#x1F4BE; Re-parse DB</button>
            <button
              onClick={async () => {
                if (!confirm('Migrar mtt_hands → hands? Copia mãos que faltam para a tabela principal.')) return
                try {
                  const res = await mtt.migrate()
                  alert(`Migração concluída!\n\n${res.migrated || 0} mãos migradas\n${res.skipped || 0} já existiam\n${res.errors || 0} erros`)
                  load()
                } catch (err) { alert('Erro: ' + err.message) }
              }}
              style={{ padding: '4px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: 'rgba(139,92,246,0.12)', color: '#8b5cf6', border: '1px solid rgba(139,92,246,0.25)', cursor: 'pointer' }}
            >&#x1F4E6; Migrar BD</button>
            <button className="btn btn-primary btn-sm" onClick={() => setShowCreate(s => !s)}>
              {showCreate ? 'Cancelar' : '+ Novo'}
            </button>
          </div>
        </div>
      </div>

      {showCreate && (
        <div className="card" style={{ marginBottom: 16 }}>
          <form onSubmit={handleCreate} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="form-group">
              <label>Nick *</label>
              <input required value={form.nick} onChange={e => setForm(f => ({ ...f, nick: e.target.value }))} />
            </div>
            <div className="form-group">
              <label>Sala</label>
              <input value={form.site} onChange={e => setForm(f => ({ ...f, site: e.target.value }))} placeholder="GGPoker, Winamax…" />
            </div>
            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
              <label>Nota</label>
              <textarea rows={3} value={form.note} onChange={e => setForm(f => ({ ...f, note: e.target.value }))} />
            </div>
            <div className="form-group">
              <label>Tags (separadas por vírgula)</label>
              <input value={form.tags} onChange={e => setForm(f => ({ ...f, tags: e.target.value }))} placeholder="fish, aggro, nitty" />
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button className="btn btn-primary" type="submit" disabled={creating}>
                {creating ? 'A guardar…' : 'Guardar'}
              </button>
            </div>
          </form>
        </div>
      )}

      {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}

      {/* TabBar — 4 tabs: Todos / Mãos com SD / Notas / Amigos */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 12, background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 8, padding: 3, width: 'fit-content' }}>
        {TAB_DEFS.map(t => (
          <button
            key={t.key}
            onClick={() => { setCategory(t.key); setPage(1) }}
            style={{
              padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
              border: 'none', cursor: 'pointer',
              background: category === t.key ? '#6366f1' : 'transparent',
              color: category === t.key ? '#fff' : '#94a3b8',
              transition: 'all 0.15s',
            }}
          >{t.label}</button>
        ))}
      </div>

      <div style={{ marginBottom: 12 }}>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Buscar por nick…"
            style={{ width: 220 }}
          />
          <button type="submit" className="btn btn-ghost btn-sm">Buscar</button>
          {search && <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setSearch(''); load(1, '') }}>✕</button>}
          {/* Tech Debt #13b — filtros sala multi-select com pills coloridas */}
          <div style={{ display: 'flex', gap: 6, marginLeft: 4 }}>
            {SITES_ALL.map(s => {
              const active = siteFilters.has(s)
              const c = SITE_COLORS[s] || SITE_COLOR_DEFAULT
              return (
                <button
                  key={s}
                  type="button"
                  onClick={() => toggleSiteFilter(s)}
                  style={{
                    padding: '5px 12px', borderRadius: 999,
                    fontSize: 12, fontWeight: 700, letterSpacing: 0.3,
                    border: `1px solid ${c}`,
                    background: active ? c : 'transparent',
                    color: active ? '#fff' : c,
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                    opacity: active ? 1 : 0.65,
                  }}
                >{s}</button>
              )
            })}
          </div>
        </form>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {loading && (
          <div style={{ textAlign: 'center', padding: 24, color: '#64748b' }}>A carregar…</div>
        )}
        {!loading && rows.length === 0 && (
          <div className="empty-state" style={{ padding: 32 }}>
            {siteFilters.size === 0
              ? 'Nenhuma sala seleccionada — todos os vilões filtrados. Activa pelo menos uma sala acima.'
              : category === 'friend'
              ? 'Sem amigos a aparecer. Quando jogares com Karluz/flightrisk vão entrar aqui automaticamente.'
              : 'Sem vilões nesta categoria.'}
          </div>
        )}
        {!loading && rows.map(v => (
          <div
            key={v.nick}
            onClick={() => openModal(v.nick)}
            style={{
              padding: '12px 16px', borderBottom: '1px solid #1a1d27',
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 16,
              flexWrap: 'wrap',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.05)'}
            onMouseLeave={e => e.currentTarget.style.background = ''}
          >
            <div style={{ minWidth: 180, flexShrink: 0 }}>
              <strong style={{ color: '#e2e8f0', fontSize: 14 }}>{v.nick}</strong>
            </div>

            <div style={{ display: 'flex', gap: 0, flexWrap: 'nowrap', minWidth: 280 }}>
              <CategoryBadge label="SD"      count={v.sd_count}     color="#a78bfa" />
              <CategoryBadge label="Notas"   count={v.nota_count}   color="#f59e0b" />
              <CategoryBadge label="Friends" count={v.friend_count} color="#06b6d4" />
            </div>

            <div style={{ minWidth: 70, fontSize: 13, fontFamily: 'monospace', color: '#fbbf24', fontWeight: 700 }}>
              {v.total_count} mãos
            </div>

            <div style={{ minWidth: 90, fontSize: 12, color: '#94a3b8' }}>
              {relativeDate(v.last_seen)}
            </div>

            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {(v.sites || []).map(s => <SiteBadge key={s} site={s} />)}
            </div>

            <div style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace', marginLeft: 'auto' }}>
              {datesLabel(v.dates)}
            </div>
          </div>
        ))}

        {data.pages > 1 && (
          <div className="pagination" style={{ padding: 12 }}>
            <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Anterior</button>
            <span className="muted">Pág. {page} / {data.pages}</span>
            <button className="btn btn-ghost btn-sm" disabled={page >= data.pages} onClick={() => setPage(p => p + 1)}>Próxima →</button>
          </div>
        )}
      </div>

      {/* Profile panel */}
      {selected && (
        <VillainProfile
          villain={selected}
          onClose={() => setSelected(null)}
          onSave={() => { load(); setSelected(null) }}
        />
      )}
    </>
  )
}
