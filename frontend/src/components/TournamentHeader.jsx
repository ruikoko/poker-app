import { useState } from 'react'

// Logo banner esbatido. mixBlendMode aplicado quando o ficheiro fonte tem fundo
// opaco (gg2.jpg é JPEG sem alpha → screen faz pixels escuros desaparecerem;
// PS sem blend até confirmarmos visualmente se aparece rectângulo branco).
const SITE_LOGOS = {
  WPN:        { src: '/logos/ya.webp',   opacity: 0.35 },
  Winamax:    { src: '/logos/wina2.png', opacity: 0.35 },
  PokerStars: { src: '/logos/ps.png',    opacity: 0.40 },
  GGPoker:    { src: '/logos/gg2.jpg',   opacity: 0.35, mixBlendMode: 'screen' },
}

const SITE_GRADIENTS = {
  WPN:        'linear-gradient(to right, #0A0A0C 0%, #0A0A0C 25%, #1F1F22 65%, #2D2D32 100%)',
  Winamax:    'linear-gradient(to right, #0A0A0C 0%, #0A0A0C 25%, #3D1416 65%, #5C1E20 100%)',
  PokerStars: 'linear-gradient(to right, #0A0A0C 0%, #0A0A0C 25%, #5A5A56 65%, #8A8A85 100%)',
  GGPoker:    'linear-gradient(to right, #0A0A0C 0%, #0A0A0C 25%, #0F4C5C 65%, #1B6B7E 100%)',
}

// Estrelas determinísticas para o card GG (não tremem entre renders).
const GG_STARS = [
  { cx: 462, cy: 18, r: 0.6 }, { cx: 488, cy: 42, r: 0.4 },
  { cx: 515, cy: 12, r: 0.7 }, { cx: 541, cy: 28, r: 0.5 },
  { cx: 568, cy: 45, r: 0.4 }, { cx: 594, cy: 22, r: 0.8 },
  { cx: 621, cy: 38, r: 0.5 }, { cx: 648, cy: 14, r: 0.6 },
  { cx: 674, cy: 30, r: 0.7 }, { cx: 701, cy: 50, r: 0.4 },
  { cx: 728, cy: 24, r: 0.9 }, { cx: 754, cy: 40, r: 0.5 },
  { cx: 781, cy: 16, r: 0.6 }, { cx: 808, cy: 32, r: 0.4 },
  { cx: 836, cy: 48, r: 0.7 }, { cx: 870, cy: 26, r: 0.5 },
]

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
}) {
  const [tmCopied, setTmCopied] = useState(false)
  const [hovered, setHovered] = useState(false)

  const logo = SITE_LOGOS[site]
  const gradient = SITE_GRADIENTS[site] || SITE_GRADIENTS.WPN
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
        background: gradient,
        minHeight: 64,
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
      {isGG && (
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.6 }}>
          <svg viewBox="0 0 1000 64" preserveAspectRatio="none" width="100%" height="100%">
            {GG_STARS.map((s, i) => (
              <circle key={i} cx={s.cx} cy={s.cy} r={s.r} fill="#FFFFFF" />
            ))}
          </svg>
        </div>
      )}

      {logo && (
        <img
          src={logo.src}
          alt=""
          aria-hidden
          style={{
            position: 'absolute',
            right: 200,
            top: '50%',
            transform: 'translateY(-50%)',
            height: 80,
            opacity: logo.opacity,
            mixBlendMode: logo.mixBlendMode || 'normal',
            pointerEvents: 'none',
            userSelect: 'none',
          }}
        />
      )}

      <span style={{
        color: '#6E91BC',
        fontSize: 14,
        marginRight: 12,
        flex: '0 0 auto',
        position: 'relative', zIndex: 1,
        transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
        transition: 'transform 0.15s',
      }}>▶</span>

      <div style={{ flex: '1 1 auto', minWidth: 0, position: 'relative', zIndex: 1 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: '#ECECEC', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
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
        </div>
        {tagsLine && (
          <div style={{ fontSize: 12, color: '#8A8A85', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {tagsLine}
          </div>
        )}
      </div>

      {hasStats && (
        <div style={{
          display: 'flex', gap: 22, fontSize: 13,
          minWidth: 180, justifyContent: 'flex-end',
          position: 'relative', zIndex: 1, flex: '0 0 auto',
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

      {extraRight && (
        <div
          style={{ position: 'relative', zIndex: 1, marginLeft: 12, flex: '0 0 auto' }}
          onClick={e => e.stopPropagation()}
        >
          {extraRight}
        </div>
      )}
    </div>
  )
}
