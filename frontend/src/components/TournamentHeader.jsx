import { useState } from 'react'

// Halos radiais por sala — pintados atrás do wordmark, criam um foco de luz
// localizado em volta do mesmo. Posição/dimensão são iguais em todas as salas
// (right 160, 320×80); só muda a cor do radial-gradient.
const HALO_BASE = {
  position: 'absolute',
  right: 160,
  top: '50%',
  transform: 'translateY(-50%)',
  width: 320,
  height: 80,
  pointerEvents: 'none',
  zIndex: 0,
}

const SITE_HALO_BG = {
  WPN:        'radial-gradient(ellipse 45% 60% at center, rgba(146, 212, 0, 0.55) 0%, rgba(120, 175, 0, 0.30) 35%, rgba(70, 105, 0, 0.12) 65%, transparent 100%)',
  Winamax:    'radial-gradient(ellipse 45% 60% at center, rgba(168, 37, 45, 0.75) 0%, rgba(146, 32, 40, 0.50) 35%, rgba(100, 22, 28, 0.22) 65%, transparent 100%)',
  PokerStars: 'radial-gradient(ellipse 45% 60% at center, rgba(255, 255, 255, 0.18) 0%, rgba(220, 220, 220, 0.10) 40%, rgba(180, 180, 180, 0.04) 70%, transparent 100%)',
  GGPoker:    'radial-gradient(ellipse 45% 60% at center, rgba(27, 107, 126, 0.55) 0%, rgba(20, 80, 95, 0.32) 40%, rgba(15, 50, 60, 0.15) 70%, transparent 100%)',
}

function SiteHalo({ site }) {
  const bg = SITE_HALO_BG[site]
  if (!bg) return null
  return <div aria-hidden style={{ ...HALO_BASE, backgroundImage: bg }} />
}

// Wordmark container — igual em TODAS as salas. Conteúdo varia por sala.
const WORDMARK_CONTAINER = {
  position: 'absolute',
  right: 220,
  top: '50%',
  transform: 'translateY(-50%)',
  width: 200,
  height: 60,
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
      <div aria-hidden style={WORDMARK_CONTAINER}>
        <span style={{
          fontFamily: "Impact, 'Arial Black', sans-serif",
          fontStyle: 'italic',
          fontWeight: 900,
          fontSize: 32,
          color: '#FFFFFF',
          letterSpacing: -0.5,
          lineHeight: 1,
          opacity: 0.85,
        }}>YaPoker</span>
      </div>
    )
  }
  if (site === 'Winamax') {
    return (
      <div aria-hidden style={WORDMARK_CONTAINER}>
        <div style={{
          fontFamily: "'Oswald', sans-serif",
          fontSize: 34,
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
              left: -1,
              right: -1,
              height: 3.5,
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
      <div aria-hidden style={WORDMARK_CONTAINER}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <img
            src="/logos/ps_logo.png"
            alt="PokerStars"
            style={{
              height: 28,
              pointerEvents: 'none',
              userSelect: 'none',
            }}
          />
          <span style={{
            fontFamily: "'Cinzel', Georgia, serif",
            fontSize: 22,
            fontWeight: 700,
            color: '#FFFFFF',
            letterSpacing: 1,
            lineHeight: 1,
            opacity: 0.92,
          }}>POKERSTARS</span>
        </div>
      </div>
    )
  }
  if (site === 'GGPoker') {
    return (
      <div aria-hidden style={WORDMARK_CONTAINER}>
        <img
          src="/logos/gg1.png"
          alt="GGPoker"
          style={{
            height: 60,
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
      right: 160,
      top: '50%',
      transform: 'translateY(-50%)',
      width: 320,
      height: 80,
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
        background: '#0A0A0E',
        minHeight: 70,
        padding: `14px 20px 14px ${14 + indent}px`,
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        borderBottom: isLast ? 'none' : '1px solid #1A1A1F',
        cursor: onToggle ? 'pointer' : 'default',
        userSelect: 'none',
        filter: hoverable && hovered ? 'brightness(1.06)' : 'none',
        transition: 'filter 0.15s',
      }}
    >
      {/* Halo radial — atrás de tudo */}
      <SiteHalo site={site} />

      {/* Estrelas decorativas só para GG, dentro da zona do halo */}
      {isGG && <GGStarsLocal />}

      {/* Wordmark — sobre o halo */}
      <SiteWordmark site={site} />

      {/* Setinha play — z-index acima do halo/wordmark */}
      <span style={{
        color: '#6E91BC',
        fontSize: 14,
        marginRight: 12,
        flex: '0 0 auto',
        position: 'relative', zIndex: 2,
        transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
        transition: 'transform 0.15s',
      }}>▶</span>

      {/* Texto principal — max-width impede invasão da zona do wordmark+stats */}
      <div style={{
        flex: '0 1 auto',
        minWidth: 0,
        maxWidth: 'calc(100% - 480px)',
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

      {/* Slot extraRight — depois do texto, antes das stats absolute */}
      {extraRight && (
        <div
          style={{ position: 'relative', zIndex: 2, marginLeft: 12, flex: '0 0 auto' }}
          onClick={e => e.stopPropagation()}
        >
          {extraRight}
        </div>
      )}

      {/* Stats absolute right 16 — sempre fora do fluxo, zero sobreposição */}
      {hasStats && (
        <div style={{
          position: 'absolute',
          right: 16,
          top: '50%',
          transform: 'translateY(-50%)',
          display: 'flex',
          gap: 22,
          fontSize: 13,
          minWidth: 180,
          justifyContent: 'flex-end',
          zIndex: 2,
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
