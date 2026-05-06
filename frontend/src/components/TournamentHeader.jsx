import { useState } from 'react'

// Halos radiais por sala. Pintados atrás do wordmark, dentro do "wordmark area"
// flex item (480×120) — preenchem-no via absolute inset:0. Só varia a cor do
// radial-gradient por sala.
const HALO_BASE = {
  position: 'absolute',
  inset: 0,
  pointerEvents: 'none',
  zIndex: 0,
}

const SITE_HALO_BG = {
  WPN:        'radial-gradient(ellipse 45% 60% at center, rgba(146, 212, 0, 0.55) 0%, rgba(120, 175, 0, 0.30) 35%, rgba(70, 105, 0, 0.12) 65%, transparent 100%)',
  Winamax:    'radial-gradient(ellipse 45% 60% at center, rgba(168, 37, 45, 0.75) 0%, rgba(146, 32, 40, 0.50) 35%, rgba(100, 22, 28, 0.22) 65%, transparent 100%)',
  PokerStars: 'radial-gradient(ellipse 45% 60% at center, rgba(255, 255, 255, 0.18) 0%, rgba(220, 220, 220, 0.10) 40%, rgba(180, 180, 180, 0.04) 70%, transparent 100%)',
  GGPoker:    'radial-gradient(ellipse 45% 60% at center, rgba(27, 107, 126, 0.55) 0%, rgba(20, 80, 95, 0.32) 40%, rgba(15, 50, 60, 0.15) 70%, transparent 100%)',
}

// bareMode aplica este background ao CARD raiz (em vez de halo+wordmark). Só
// salas listadas têm gradient — restantes ficam fundo preto puro até spec.
const SITE_BARE_CARD_BG = {
  WPN: 'linear-gradient(180deg, #0A0A0E 0%, rgba(107,142,35,0.25) 50%, #0A0A0E 100%)',
}

function SiteHalo({ site }) {
  const bg = SITE_HALO_BG[site]
  if (!bg) return null
  return <div aria-hidden style={{ ...HALO_BASE, backgroundImage: bg }} />
}

// Wordmark inner — preenche o "wordmark area" flex item via absolute inset:0,
// flex-centra o conteúdo (texto/img). Conteúdo varia por sala.
const WORDMARK_INNER = {
  position: 'absolute',
  inset: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  pointerEvents: 'none',
  userSelect: 'none',
  zIndex: 1,
}

function SiteWordmark({ site }) {
  if (site === 'WPN') {
    return (
      <div aria-hidden style={WORDMARK_INNER}>
        <span style={{
          fontFamily: "Impact, 'Arial Black', sans-serif",
          fontStyle: 'italic',
          fontWeight: 900,
          fontSize: 64,
          color: '#FFFFFF',
          letterSpacing: -1,
          lineHeight: 1,
          opacity: 0.85,
        }}>YaPoker</span>
      </div>
    )
  }
  if (site === 'Winamax') {
    return (
      <div aria-hidden style={WORDMARK_INNER}>
        <div style={{
          fontFamily: "'Oswald', sans-serif",
          fontSize: 68,
          fontWeight: 600,
          color: '#FFFFFF',
          lineHeight: 1,
          letterSpacing: 0,
          display: 'inline-flex',
          alignItems: 'baseline',
        }}>
          <span style={{ position: 'relative', display: 'inline-block' }}>
            W
            <span style={{
              position: 'absolute',
              top: '50%',
              left: -2,
              right: -2,
              height: 7,
              background: '#FFFFFF',
              transform: 'translateY(-50%)',
              pointerEvents: 'none',
            }} />
          </span>
          <span>INAMAX</span>
        </div>
      </div>
    )
  }
  if (site === 'PokerStars') {
    return (
      <div aria-hidden style={WORDMARK_INNER}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <img
            src="/logos/ps_logo.png"
            alt="PokerStars"
            style={{
              height: 56,
              pointerEvents: 'none',
              userSelect: 'none',
            }}
          />
          <span style={{
            fontFamily: "'Cinzel', Georgia, serif",
            fontSize: 44,
            fontWeight: 700,
            color: '#FFFFFF',
            letterSpacing: 2,
            lineHeight: 1,
            opacity: 0.92,
          }}>POKERSTARS</span>
        </div>
      </div>
    )
  }
  if (site === 'GGPoker') {
    return (
      <div aria-hidden style={WORDMARK_INNER}>
        <img
          src="/logos/gg_horizontal.png"
          alt="GGPoker"
          style={{
            height: 90,
            pointerEvents: 'none',
            userSelect: 'none',
          }}
        />
      </div>
    )
  }
  return null
}

// Estrelas decorativas localizadas dentro da zona do halo do GG.
function GGStarsLocal() {
  return (
    <div aria-hidden style={{
      position: 'absolute',
      inset: 0,
      pointerEvents: 'none',
      opacity: 0.6,
      zIndex: 0,
    }}>
      <svg viewBox="0 0 320 80" preserveAspectRatio="none" width="100%" height="100%">
        <circle cx="60"  cy="20" r="0.7" fill="#FFFFFF" />
        <circle cx="100" cy="55" r="0.5" fill="#FFFFFF" />
        <circle cx="150" cy="30" r="0.9" fill="#FFFFFF" />
        <circle cx="240" cy="58" r="0.4" fill="#FFFFFF" />
        <circle cx="270" cy="18" r="0.6" fill="#FFFFFF" />
      </svg>
    </div>
  )
}

// WPN usa $; restantes €.
function fmtBuyIn(v, site) {
  if (v == null) return ''
  const n = Number(v)
  if (Number.isNaN(n)) return ''
  const c = site === 'WPN' ? '$' : '€'
  return n % 1 === 0 ? `${c}${n}` : `${c}${n.toFixed(2)}`
}

export default function TournamentHeader({
  site,
  tournamentName,
  tournamentNumber,
  timeStart,
  timeEnd,
  timeRangeOverride,
  handCount,
  wins,
  losses,
  bbResult,
  buyIn,
  blindsFirst,
  blindsLast,
  tournamentFormat,
  siHero,
  ssCount,
  villainCount,
  tags,
  expanded = false,
  onToggle,
  isLast = false,
  extraRight,
  onTmClick,
  indent = 0,
  hoverable = true,
  customTitle,
  bareMode = false,
}) {
  const [tmCopied, setTmCopied] = useState(false)
  const [hovered, setHovered] = useState(false)

  const isGG = site === 'GGPoker'

  const timeStr = timeRangeOverride
    ?? ((timeStart && timeEnd) ? `${timeStart} → ${timeEnd}` : (timeStart || timeEnd || ''))

  function handleTmClick(e) {
    e.stopPropagation()
    if (!onTmClick) return
    try {
      onTmClick(tournamentNumber)
      setTmCopied(true)
      setTimeout(() => setTmCopied(false), 600)
    } catch {
      // noop
    }
  }

  const titleParts = []
  if (tournamentName) {
    titleParts.push({ k: 'name', node: <span>{tournamentName}</span> })
  }
  if (tournamentNumber) {
    titleParts.push({
      k: 'tm',
      node: onTmClick ? (
        <span
          onClick={handleTmClick}
          title={tmCopied ? 'Copiado!' : 'Copiar TM'}
          style={{
            cursor: 'pointer',
            color: tmCopied ? '#97C459' : 'inherit',
            transition: 'color 0.15s',
          }}
        >{String(tournamentNumber)}</span>
      ) : <span>{String(tournamentNumber)}</span>,
    })
  }
  if (timeStr) {
    titleParts.push({ k: 'time', node: <span>{timeStr}</span> })
  }

  const tagsLine = (tags && tags.length > 0) ? tags.join(' · ') : ''

  const blindsLabel = blindsFirst && blindsLast
    ? (blindsFirst === blindsLast ? blindsFirst : `${blindsFirst} → ${blindsLast}`)
    : (blindsFirst || blindsLast || '')

  const hasStats = wins != null || losses != null || bbResult != null
  const bbColor = bbResult != null && bbResult >= 0 ? '#97C459' : '#F09595'
  const bbStr = bbResult != null
    ? ((bbResult >= 0 ? '+' : '') + Number(bbResult).toFixed(1) + ' BB')
    : ''

  return (
    <div
      onClick={onToggle}
      onMouseEnter={hoverable ? () => setHovered(true) : undefined}
      onMouseLeave={hoverable ? () => setHovered(false) : undefined}
      style={{
        position: 'relative',
        overflow: 'hidden',
        background: bareMode ? (SITE_BARE_CARD_BG[site] || '#0A0A0E') : '#0A0A0E',
        minHeight: 148,
        padding: `14px 16px 14px ${14 + indent}px`,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        borderBottom: isLast ? 'none' : '1px solid #1A1A1F',
        cursor: onToggle ? 'pointer' : 'default',
        userSelect: 'none',
        filter: hoverable && hovered ? 'brightness(1.06)' : 'none',
        transition: 'filter 0.15s',
      }}
    >
      {/* Setinha play */}
      <span style={{
        color: '#6E91BC',
        fontSize: 14,
        flex: '0 0 auto',
        position: 'relative', zIndex: 2,
        transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
        transition: 'transform 0.15s',
      }}>▶</span>

      {/* Texto principal — flex 1 1 auto. Custom title interno (em Hands.jsx)
          tem coluna 1fr antes do SI para empurrar SI até ao fim do slot. */}
      <div style={{
        flex: '1 1 auto',
        minWidth: 0,
        position: 'relative', zIndex: 2,
      }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: '#ECECEC', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {customTitle != null ? customTitle : (
            <>
              {titleParts.map((p, i) => (
                <span key={p.k}>{i > 0 && ' — '}{p.node}</span>
              ))}
              {handCount != null && (
                <span style={{ color: '#6E6E6A', fontWeight: 400, marginLeft: 8 }}>
                  {handCount} {handCount === 1 ? 'mão' : 'mãos'}
                </span>
              )}
              {buyIn != null && (
                <span style={{ color: '#F0B040', marginLeft: 10, fontSize: 12, fontWeight: 600 }}>
                  {fmtBuyIn(buyIn, site)}
                </span>
              )}
              {blindsLabel && (
                <span style={{ color: '#A0A0A0', marginLeft: 10, fontSize: 12, fontFamily: 'monospace' }}>
                  {blindsLabel}
                </span>
              )}
              {tournamentFormat && (
                <span style={{
                  marginLeft: 10, fontSize: 11, fontWeight: 700, padding: '1px 6px', borderRadius: 3,
                  color: /KO/i.test(tournamentFormat) ? '#F0B040' : '#A0A0A0',
                  background: /KO/i.test(tournamentFormat) ? 'rgba(240,176,64,0.12)' : 'rgba(160,160,160,0.10)',
                }}>{tournamentFormat}</span>
              )}
              {siHero != null && (
                <span style={{ color: '#FBBF24', marginLeft: 10, fontSize: 11, fontFamily: 'monospace', fontWeight: 700 }}>
                  SI {Number(siHero).toLocaleString('en-US')}
                </span>
              )}
              {ssCount != null && ssCount > 0 && (
                <span style={{ color: '#97C459', marginLeft: 10, fontSize: 11 }}>{ssCount} SS</span>
              )}
              {villainCount != null && villainCount > 0 && (
                <span style={{ color: '#A78BFA', marginLeft: 10, fontSize: 11 }}>{villainCount} V</span>
              )}
            </>
          )}
        </div>
        {tagsLine && (
          <div style={{ fontSize: 12, color: '#8A8A85', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {tagsLine}
          </div>
        )}
      </div>

      {/* Slot extraRight — entre texto e wordmark area */}
      {extraRight && (
        <div
          style={{ position: 'relative', zIndex: 2, flex: '0 0 auto' }}
          onClick={e => e.stopPropagation()}
        >
          {extraRight}
        </div>
      )}

      {/* Wordmark area — só em modo normal. Em bareMode, o gradient (se houver
          para esta sala) está aplicado ao background do card raiz e este bloco
          desaparece — layout vira [play] [customTitle] [stats]. */}
      {!bareMode && (
        <div aria-hidden style={{
          flex: '0 0 480px',
          height: 120,
          position: 'relative',
          pointerEvents: 'none',
        }}>
          <SiteHalo site={site} />
          {isGG && <GGStarsLocal />}
          <SiteWordmark site={site} />
        </div>
      )}

      {/* Stats — flex item, justifica para o fim. Sem position absolute. */}
      {hasStats && (
        <div style={{
          flex: '0 0 180px',
          display: 'flex',
          alignItems: 'center',
          gap: 22,
          fontSize: 13,
          justifyContent: 'flex-end',
          position: 'relative', zIndex: 2,
        }}>
          {wins != null && <span style={{ color: '#97C459' }}>{wins}W</span>}
          {losses != null && <span style={{ color: '#F09595' }}>{losses}L</span>}
          {bbResult != null && (
            <span style={{ color: bbColor, minWidth: 70, textAlign: 'right', fontWeight: 600, fontFamily: 'monospace' }}>
              {bbStr}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
