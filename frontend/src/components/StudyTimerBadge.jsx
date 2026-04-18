import { useStudyTimer } from '../contexts/StudyTimerContext'

function fmt(s) {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const pad = (n) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`
}

const iconBtnStyle = (color, bg, border) => ({
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  width: 26, height: 26, padding: 0,
  background: bg, color, border: `1px solid ${border}`,
  borderRadius: 5, cursor: 'pointer',
})

export default function StudyTimerBadge() {
  const { active, paused, elapsed, pause, resume, stop, handId } = useStudyTimer()
  if (!active) return null

  const dotColor = paused ? '#f59e0b' : '#22c55e'
  const label = paused ? (handId ? `Pausado (mão #${handId})` : 'Pausado') :
                (handId ? `A estudar mão #${handId}` : 'Sessão de estudo activa')

  return (
    <div
      style={{
        position: 'fixed',
        right: 16,
        bottom: 16,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 10px 8px 12px',
        background: 'rgba(17, 24, 39, 0.92)',
        backdropFilter: 'blur(6px)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 8,
        boxShadow: '0 6px 20px rgba(0,0,0,0.45)',
        fontFamily: "'Fira Code', monospace",
        fontSize: 13,
        color: '#e5e7eb',
        userSelect: 'none',
      }}
      title={label}
    >
      <span
        style={{
          width: 8, height: 8, borderRadius: '50%',
          background: dotColor,
          boxShadow: `0 0 8px ${dotColor}`,
          animation: paused ? 'none' : 'pulse 1.6s ease-in-out infinite',
          opacity: paused ? 0.7 : 1,
        }}
      />
      <span style={{
        fontWeight: 600, letterSpacing: 0.5, minWidth: 52, textAlign: 'center',
        color: paused ? '#9ca3af' : '#e5e7eb',
      }}>{fmt(elapsed)}</span>

      {paused ? (
        <button
          onClick={resume}
          title="Retomar"
          style={iconBtnStyle('#86efac', 'rgba(34, 197, 94, 0.15)', 'rgba(34, 197, 94, 0.35)')}
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
            <path d="M2 1 L9 5 L2 9 Z" />
          </svg>
        </button>
      ) : (
        <button
          onClick={pause}
          title="Pausar"
          style={iconBtnStyle('#fcd34d', 'rgba(245, 158, 11, 0.15)', 'rgba(245, 158, 11, 0.35)')}
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
            <rect x="2" y="1" width="2.5" height="8" />
            <rect x="5.5" y="1" width="2.5" height="8" />
          </svg>
        </button>
      )}

      <button
        onClick={stop}
        title="Terminar sessão"
        style={{
          padding: '4px 10px',
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: 0.4,
          background: 'rgba(239, 68, 68, 0.15)',
          color: '#f87171',
          border: '1px solid rgba(239, 68, 68, 0.35)',
          borderRadius: 5,
          cursor: 'pointer',
        }}
      >STOP</button>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1;   transform: scale(1); }
          50%      { opacity: 0.5; transform: scale(0.85); }
        }
      `}</style>
    </div>
  )
}
