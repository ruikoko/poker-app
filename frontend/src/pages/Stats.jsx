import { useEffect, useState, useCallback } from 'react'
import { stats } from '../api/client'

// ── Category definitions matching the spreadsheet ─────────────────────────────

const PREFLOP_CATEGORIES = {
  'RFI': ['Early RFI', 'Middle RFI', 'CO Steal', 'BTN Steal'],
  'BvB': ['SB UO VPIP', 'BB fold to SB steal', 'BB raise vs SB limp UOP', 'SB Steal'],
  'CC/3Bet IP': ['EP 3bet', 'EP Cold Call', 'EP VPIP', 'MP 3bet', 'MP Cold Call', 'MP VPIP', 'CO 3bet', 'CO Cold Call', 'CO VPIP', 'BTN 3bet', 'BTN Cold Call', 'BTN VPIP'],
  'Vs 3Bet IP/OOP': ['BTN fold to CO steal', 'BTN VPIP', 'Fold to 3bet IP', 'Fold to 3bet OOP'],
  'Squeeze': ['Squeeze', 'Squeeze vs BTN Raiser'],
  'Defesa BB': ['BB fold vs CO steal', 'BB fold vs BTN steal', 'BB fold vs SB steal', 'BB resteal vs BTN steal'],
  'Defesa SB': ['SB fold to CO Steal', 'SB fold to BTN Steal', 'SB resteal vs BTN'],
}

const POSTFLOP_CATEGORIES = {
  'Flop Cbet': ['Flop CBet IP %', 'Flop CBet 3BetPot IP', 'Flop Cbet OOP%'],
  'Vs Cbet': ['Flop fold vs Cbet IP', 'Flop raise Cbet IP', 'Flop raise Cbet OOP', 'Fold vs Check Raise'],
  'Skipped Cbet': ['Flop bet vs missed Cbet SRP'],
  'Turn Play': ['Turn CBet IP%', 'Turn Cbet OOP%', 'Turn donk bet', 'Turn donk bet SRP vs PFR', 'Bet turn vs Missed Flop'],
  'Turn Fold': ['Turn Fold vs Cbet OOP'],
  'River play': ['WTSD%', 'W$SD%', 'W$WSF Rating', 'River Agg %', 'W$SD% B River'],
}

const RADAR_LABELS_PREFLOP = ['RFI', 'BvB', '3b & CC', 'vs 3b IP/OOP', 'Squeeze', 'Defesa BB', 'Defesa SB']
const RADAR_LABELS_POSTFLOP = ['Cbet', 'Vs Cbet', 'vs Skipped Cbet', 'Turn play', 'River play']

// ── Helpers ──────────────────────────────────────────────────────────────────

function scoreColor(score) {
  if (score == null) return '#4b5563'
  if (score >= 80) return '#22c55e'
  if (score >= 60) return '#84cc16'
  if (score >= 40) return '#f59e0b'
  if (score >= 20) return '#f97316'
  return '#ef4444'
}

function scoreBg(score) {
  if (score == null) return 'rgba(75,85,99,0.1)'
  if (score >= 80) return 'rgba(34,197,94,0.12)'
  if (score >= 60) return 'rgba(132,204,22,0.12)'
  if (score >= 40) return 'rgba(245,158,11,0.12)'
  if (score >= 20) return 'rgba(249,115,22,0.12)'
  return 'rgba(239,68,68,0.12)'
}

// ── Radar Chart (SVG) ────────────────────────────────────────────────────────

function RadarChart({ labels, values, size = 200, color = '#6366f1', title = '' }) {
  const cx = size / 2
  const cy = size / 2
  const r = size * 0.38
  const n = labels.length
  if (n < 3) return null

  const angleStep = (2 * Math.PI) / n
  const startAngle = -Math.PI / 2

  // Grid circles
  const gridLevels = [25, 50, 75, 100]

  // Points for each value
  const points = values.map((v, i) => {
    const angle = startAngle + i * angleStep
    const pct = Math.min(100, Math.max(0, v || 0)) / 100
    return {
      x: cx + r * pct * Math.cos(angle),
      y: cy + r * pct * Math.sin(angle),
    }
  })

  const polygon = points.map(p => `${p.x},${p.y}`).join(' ')

  return (
    <div style={{ textAlign: 'center' }}>
      {title && <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>{title}</div>}
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Grid */}
        {gridLevels.map(level => {
          const gr = r * level / 100
          const gpoints = Array.from({ length: n }, (_, i) => {
            const angle = startAngle + i * angleStep
            return `${cx + gr * Math.cos(angle)},${cy + gr * Math.sin(angle)}`
          }).join(' ')
          return <polygon key={level} points={gpoints} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={0.5} />
        })}

        {/* Axis lines */}
        {labels.map((_, i) => {
          const angle = startAngle + i * angleStep
          return <line key={i} x1={cx} y1={cy} x2={cx + r * Math.cos(angle)} y2={cy + r * Math.sin(angle)} stroke="rgba(255,255,255,0.08)" strokeWidth={0.5} />
        })}

        {/* Data polygon */}
        <polygon points={polygon} fill={`${color}20`} stroke={color} strokeWidth={2} />

        {/* Data points */}
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={3} fill={color} stroke="#1a1d27" strokeWidth={1.5} />
        ))}

        {/* Labels */}
        {labels.map((label, i) => {
          const angle = startAngle + i * angleStep
          const lx = cx + (r + 18) * Math.cos(angle)
          const ly = cy + (r + 18) * Math.sin(angle)
          const anchor = Math.abs(Math.cos(angle)) < 0.1 ? 'middle' : Math.cos(angle) > 0 ? 'start' : 'end'
          return (
            <text key={i} x={lx} y={ly} textAnchor={anchor} dominantBaseline="middle" fill="#64748b" fontSize={8} fontWeight={600}>
              {label}
            </text>
          )
        })}

        {/* Center score */}
        {values.length > 0 && (() => {
          const avg = Math.round(values.reduce((a, b) => a + (b || 0), 0) / values.length)
          return (
            <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle" fill={scoreColor(avg)} fontSize={20} fontWeight={700}>
              {avg}
            </text>
          )
        })()}
      </svg>
    </div>
  )
}

// ── Score Bar ─────────────────────────────────────────────────────────────────

function ScoreBar({ label, score, small = false }) {
  const c = scoreColor(score)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: small ? 3 : 5 }}>
      <span style={{ fontSize: small ? 10 : 11, color: '#94a3b8', minWidth: small ? 100 : 120 }}>{label}</span>
      <div style={{ flex: 1, height: small ? 6 : 8, background: 'rgba(255,255,255,0.04)', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${Math.min(100, score || 0)}%`, height: '100%', background: c, borderRadius: 4, transition: 'width 0.3s' }} />
      </div>
      <span style={{ fontSize: small ? 10 : 12, fontWeight: 700, color: c, minWidth: 28, textAlign: 'right', fontFamily: 'monospace' }}>{score != null ? Math.round(score) : '—'}</span>
    </div>
  )
}

// ── Score Card ────────────────────────────────────────────────────────────────

function ScoreCard({ title, score, color }) {
  const c = color || scoreColor(score)
  return (
    <div style={{
      background: scoreBg(score), border: `1px solid ${c}30`,
      borderRadius: 10, padding: '12px 16px', textAlign: 'center', minWidth: 90,
    }}>
      <div style={{ fontSize: 24, fontWeight: 800, color: c, fontFamily: 'monospace' }}>{score != null ? Math.round(score) : '—'}</div>
      <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, marginTop: 4, textTransform: 'uppercase', letterSpacing: 0.4 }}>{title}</div>
    </div>
  )
}

// ── Input Table for monthly data ──────────────────────────────────────────────

function MonthlyInputTable({ format, categories, monthData, ideals, onSave }) {
  const [values, setValues] = useState({})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const init = {}
    for (const [cat, statNames] of Object.entries(categories)) {
      for (const sn of statNames) {
        const key = `${cat}|${sn}`
        init[key] = monthData?.[cat]?.[sn] ?? ''
      }
    }
    setValues(init)
  }, [monthData, format])

  function handleChange(key, val) {
    setValues(v => ({ ...v, [key]: val }))
  }

  async function save() {
    setSaving(true)
    try {
      const entries = Object.entries(values)
        .filter(([, v]) => v !== '' && v != null)
        .map(([key, v]) => {
          const [cat, statName] = key.split('|')
          return { month: monthData?._month || '', format, category: cat, stat_name: statName, value: parseFloat(v) }
        })
      await onSave(entries)
    } catch (e) { alert(e.message) }
    finally { setSaving(false) }
  }

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: '#e2e8f0' }}>{format}</span>
        <button onClick={save} disabled={saving} style={{
          padding: '5px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600,
          background: saving ? '#4b5563' : '#6366f1', color: '#fff', border: 'none', cursor: saving ? 'not-allowed' : 'pointer',
        }}>{saving ? 'A guardar...' : 'Guardar'}</button>
      </div>
      {Object.entries(categories).map(([cat, statNames]) => (
        <div key={cat} style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: '#8b5cf6', fontWeight: 600, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.4 }}>{cat}</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 6 }}>
            {statNames.map(sn => {
              const key = `${cat}|${sn}`
              const ideal = ideals?.[cat]?.[sn]
              const val = values[key]
              const numVal = parseFloat(val)
              const deviation = ideal && !isNaN(numVal) ? Math.abs(numVal - ideal) / ideal * 100 : null
              const score = deviation != null ? Math.max(0, 100 - deviation) : null
              const borderColor = score != null ? `${scoreColor(score)}40` : '#2a2d3a'
              return (
                <div key={sn} style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  background: '#0f1117', borderRadius: 6, padding: '4px 8px',
                  border: `1px solid ${borderColor}`,
                }}>
                  <span style={{ fontSize: 10, color: '#64748b', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={sn}>{sn}</span>
                  <input
                    type="number"
                    step="0.1"
                    value={val}
                    onChange={e => handleChange(key, e.target.value)}
                    style={{
                      width: 52, fontSize: 12, background: 'transparent', border: 'none',
                      color: score != null ? scoreColor(score) : '#e2e8f0',
                      fontWeight: 700, fontFamily: 'monospace', textAlign: 'right',
                    }}
                    placeholder={ideal != null ? String(ideal) : '—'}
                  />
                  {ideal != null && (
                    <span style={{ fontSize: 8, color: '#4b5563', fontFamily: 'monospace', minWidth: 20, textAlign: 'right' }}>{ideal}</span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function StatsPage() {
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedMonth, setSelectedMonth] = useState('')
  const [editMonth, setEditMonth] = useState('')
  const [tab, setTab] = useState('dashboard') // 'dashboard' | 'input'
  const [error, setError] = useState('')

  const loadDashboard = useCallback(() => {
    setLoading(true)
    stats.dashboard(selectedMonth || null)
      .then(setDashboard)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [selectedMonth])

  useEffect(() => { loadDashboard() }, [loadDashboard])

  // Init schema + defaults on first visit
  useEffect(() => {
    stats.initSchema().catch(() => {})
    stats.initDefaults().catch(() => {})
  }, [])

  async function handleSave(entries) {
    await stats.save(entries)
    loadDashboard()
  }

  const d = dashboard || {}
  const sc = d.scores || {}
  const st = d.stats || {}
  const ideals = d.ideals || {}
  const months = d.available_months || []

  // Compute preflop radar values from scores
  const preflopScores = sc['9-max'] || {}
  const radarPreflop = RADAR_LABELS_PREFLOP.map(l => {
    const catMap = { 'RFI': 'RFI', 'BvB': 'BvB', '3b & CC': 'CC/3Bet IP', 'vs 3b IP/OOP': 'Vs 3Bet IP/OOP', 'Squeeze': 'Squeeze', 'Defesa BB': 'Defesa BB', 'Defesa SB': 'Defesa SB' }
    return preflopScores[catMap[l]] || 0
  })

  const postflopScores = sc['Post-flop'] || {}
  const radarPostflop = RADAR_LABELS_POSTFLOP.map(l => {
    const catMap = { 'Cbet': 'Flop Cbet', 'Vs Cbet': 'Vs Cbet', 'vs Skipped Cbet': 'Skipped Cbet', 'Turn play': 'Turn Play', 'River play': 'River play' }
    return postflopScores[catMap[l]] || 0
  })

  const pkoScores = sc['PKO'] || {}

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: -0.5 }}>Stats</div>
          <div style={{ color: '#64748b', fontSize: 13, marginTop: 3 }}>Folha de Rail &middot; {d.month || 'sem dados'}</div>
        </div>
        <div style={{ display: 'flex', gap: 4, background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 8, padding: 3 }}>
          {[
            { mode: 'dashboard', label: 'Dashboard' },
            { mode: 'input', label: 'Editar' },
          ].map(({ mode, label }) => (
            <button key={mode} onClick={() => setTab(mode)} style={{
              padding: '5px 14px', borderRadius: 6, fontSize: 12, fontWeight: 500, border: 'none', cursor: 'pointer',
              background: tab === mode ? '#6366f1' : 'transparent',
              color: tab === mode ? '#fff' : '#64748b',
            }}>{label}</button>
          ))}
        </div>
      </div>

      {/* Month selector */}
      {months.length > 0 && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
          {months.slice(0, 12).map(m => (
            <button key={m} onClick={() => setSelectedMonth(m)} style={{
              padding: '4px 12px', borderRadius: 20, fontSize: 11, fontWeight: 500,
              border: `1px solid ${(selectedMonth || d.month) === m ? '#6366f1' : '#2a2d3a'}`,
              background: (selectedMonth || d.month) === m ? 'rgba(99,102,241,0.15)' : 'transparent',
              color: (selectedMonth || d.month) === m ? '#818cf8' : '#64748b',
              cursor: 'pointer',
            }}>{m}</button>
          ))}
        </div>
      )}

      {error && <div style={{ color: '#ef4444', fontSize: 13, marginBottom: 12, padding: '8px 12px', background: 'rgba(239,68,68,0.08)', borderRadius: 6 }}>{error}</div>}
      {loading && <div style={{ textAlign: 'center', padding: '48px 0', color: '#64748b' }}>A carregar...</div>}

      {/* ── Dashboard Tab ── */}
      {!loading && tab === 'dashboard' && (
        <div>
          {/* Top score cards */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
            <ScoreCard title="Average" score={(() => { const all = Object.values(sc).map(f => f._average).filter(v => v != null); return all.length > 0 ? all.reduce((a, b) => a + b, 0) / all.length : null })() } />
            <ScoreCard title="Pre-flop 9-max" score={preflopScores._average} />
            <ScoreCard title="PKO" score={pkoScores._average} />
            <ScoreCard title="Post-flop" score={postflopScores._average} />
          </div>

          {/* Radar charts row */}
          <div style={{ display: 'flex', gap: 24, marginBottom: 24, flexWrap: 'wrap', justifyContent: 'center' }}>
            <div style={{ background: '#1a1d27', borderRadius: 12, padding: 16, border: '1px solid #2a2d3a' }}>
              <RadarChart labels={RADAR_LABELS_PREFLOP} values={radarPreflop} size={220} color="#6366f1" title="Pre-flop" />
            </div>
            <div style={{ background: '#1a1d27', borderRadius: 12, padding: 16, border: '1px solid #2a2d3a' }}>
              <RadarChart labels={RADAR_LABELS_PREFLOP} values={RADAR_LABELS_PREFLOP.map(l => {
                const catMap = { 'RFI': 'RFI', 'BvB': 'BvB', '3b & CC': 'CC/3Bet IP', 'vs 3b IP/OOP': 'Vs 3Bet IP/OOP', 'Squeeze': 'Squeeze', 'Defesa BB': 'Defesa BB', 'Defesa SB': 'Defesa SB' }
                return pkoScores[catMap[l]] || 0
              })} size={220} color="#f59e0b" title="PKO" />
            </div>
            <div style={{ background: '#1a1d27', borderRadius: 12, padding: 16, border: '1px solid #2a2d3a' }}>
              <RadarChart labels={RADAR_LABELS_POSTFLOP} values={radarPostflop} size={220} color="#22c55e" title="Pós-flop" />
            </div>
          </div>

          {/* Score breakdown */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
            {/* Pre-flop 9-max */}
            <div style={{ background: '#1a1d27', borderRadius: 10, padding: 16, border: '1px solid #2a2d3a' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 12 }}>Pre-flop 9-max</div>
              {Object.entries(PREFLOP_CATEGORIES).map(([cat]) => (
                <ScoreBar key={cat} label={cat} score={preflopScores[cat]} />
              ))}
            </div>

            {/* PKO */}
            <div style={{ background: '#1a1d27', borderRadius: 10, padding: 16, border: '1px solid #2a2d3a' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 12 }}>PKO</div>
              {Object.entries(PREFLOP_CATEGORIES).map(([cat]) => (
                <ScoreBar key={cat} label={cat} score={pkoScores[cat]} />
              ))}
            </div>

            {/* Post-flop */}
            <div style={{ background: '#1a1d27', borderRadius: 10, padding: 16, border: '1px solid #2a2d3a' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 12 }}>Pós-flop</div>
              {Object.entries(POSTFLOP_CATEGORIES).map(([cat]) => (
                <ScoreBar key={cat} label={cat} score={postflopScores[cat]} />
              ))}
            </div>

            {/* 6-max */}
            <div style={{ background: '#1a1d27', borderRadius: 10, padding: 16, border: '1px solid #2a2d3a' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 12 }}>6-max</div>
              {Object.entries(PREFLOP_CATEGORIES).map(([cat]) => {
                const sixScores = sc['6-max'] || {}
                return <ScoreBar key={cat} label={cat} score={sixScores[cat]} />
              })}
            </div>
          </div>

          {/* No data message */}
          {!d.month && (
            <div style={{ textAlign: 'center', padding: '48px 0', color: '#64748b' }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>&#128202;</div>
              <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 6 }}>Sem dados de stats</div>
              <div style={{ fontSize: 13 }}>Vai à aba "Editar" para introduzir os teus números mensais</div>
            </div>
          )}
        </div>
      )}

      {/* ── Input Tab ── */}
      {!loading && tab === 'input' && (
        <div>
          {/* Month input */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 20 }}>
            <span style={{ fontSize: 12, color: '#64748b' }}>Mês:</span>
            <input
              type="month"
              value={editMonth || (d.month || '')}
              onChange={e => setEditMonth(e.target.value)}
              style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '6px 12px', fontSize: 12 }}
            />
          </div>

          <MonthlyInputTable
            format="9-max"
            categories={PREFLOP_CATEGORIES}
            monthData={{ ...(st['9-max'] || {}), _month: editMonth || d.month || '' }}
            ideals={ideals['9-max'] || {}}
            onSave={handleSave}
          />

          <MonthlyInputTable
            format="PKO"
            categories={PREFLOP_CATEGORIES}
            monthData={{ ...(st['PKO'] || {}), _month: editMonth || d.month || '' }}
            ideals={ideals['PKO'] || {}}
            onSave={handleSave}
          />

          <MonthlyInputTable
            format="6-max"
            categories={PREFLOP_CATEGORIES}
            monthData={{ ...(st['6-max'] || {}), _month: editMonth || d.month || '' }}
            ideals={ideals['6-max'] || {}}
            onSave={handleSave}
          />

          <MonthlyInputTable
            format="Post-flop"
            categories={POSTFLOP_CATEGORIES}
            monthData={{ ...(st['Post-flop'] || {}), _month: editMonth || d.month || '' }}
            ideals={ideals['Post-flop'] || {}}
            onSave={handleSave}
          />
        </div>
      )}
    </>
  )
}
