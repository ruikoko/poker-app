import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { hrc } from '../api/client'

// Cores por cenário do aggressor (espelha build_queue_zip / classify_aggressor_source).
const SRC_COLOR = {
  real: '#22c55e',
  fallback_root: '#eab308',
  fallback_unusable_position: '#f97316',
}

function fmtTs(iso) {
  if (!iso) return '—'
  // ISO UTC → "YYYY-MM-DD HH:MM" (UTC, consistente com played_at na BD)
  return iso.replace('T', ' ').slice(0, 16)
}

function Chip({ children, color }) {
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, color: color || 'var(--muted)',
      background: `${color || '#64748b'}1f`, padding: '2px 7px', borderRadius: 4,
      whiteSpace: 'nowrap',
    }}>{children}</span>
  )
}

export default function HRCQueuePage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [site, setSite] = useState('')
  const [format, setFormat] = useState('')

  async function refresh() {
    setLoading(true)
    setError(null)
    try {
      const out = await hrc.eligible()
      setData(out)
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  const hands = data?.hands || []
  const sites = useMemo(() => [...new Set(hands.map(h => h.site))].sort(), [hands])
  const formats = useMemo(() => [...new Set(hands.map(h => h.tournament_format).filter(Boolean))].sort(), [hands])

  const filtered = useMemo(() => hands.filter(h =>
    (!site || h.site === site) && (!format || h.tournament_format === format)
  ), [hands, site, format])

  const scen = data?.scenario_counts || {}
  const fmtCounts = data?.format_counts || {}

  return (
    <div style={{ padding: 24, maxWidth: 1180, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>HRC Queue</h1>
        <button
          onClick={refresh}
          disabled={loading}
          style={{
            padding: '6px 14px', fontSize: 12, fontWeight: 600, borderRadius: 6,
            background: 'var(--accent)', border: 'none', color: '#fff',
            cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.5 : 1,
          }}
        >{loading ? 'A carregar…' : '↻ Refresh'}</button>
      </div>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 14 }}>
        Espelha os gates de <code>/api/queue/hrc</code> — é o que o adapter puxaria agora.
        {data && (
          <> {' · '}janela {data.filters.played_after} → {data.filters.played_before}
          {' · '}study_state={data.filters.study_state.join(',')}
          {' · '}basket {data.filters.tags.join(', ')}</>
        )}
      </div>

      {error && (
        <div style={{ padding: 12, borderRadius: 8, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#ef4444', fontSize: 13, marginBottom: 14 }}>
          Erro: {error}
        </div>
      )}

      {data && !error && (
        <>
          {/* Summary */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14 }}>
            <span style={{ fontSize: 15, fontWeight: 700 }}>{data.count} mãos elegíveis</span>
            <span style={{ color: 'var(--border)' }}>|</span>
            <Chip color={SRC_COLOR.real}>real {scen.real || 0}</Chip>
            <Chip color={SRC_COLOR.fallback_root}>fallback_root {scen.fallback_root || 0}</Chip>
            <Chip color={SRC_COLOR.fallback_unusable_position}>fallback_unusable {scen.fallback_unusable_position || 0}</Chip>
            <span style={{ color: 'var(--border)' }}>|</span>
            {Object.entries(fmtCounts).map(([k, v]) => <Chip key={k}>{k} {v}</Chip>)}
          </div>

          {/* Filtros client-side */}
          <div style={{ display: 'flex', gap: 14, alignItems: 'center', marginBottom: 12, fontSize: 12, color: 'var(--muted)' }}>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              Site:
              <select value={site} onChange={e => setSite(e.target.value)}
                style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: 4, padding: '3px 6px', fontSize: 12 }}>
                <option value="">Todos</option>
                {sites.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              Formato:
              <select value={format} onChange={e => setFormat(e.target.value)}
                style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: 4, padding: '3px 6px', fontSize: 12 }}>
                <option value="">Todos</option>
                {formats.map(f => <option key={f} value={f}>{f}</option>)}
              </select>
            </label>
            <span style={{ opacity: 0.7 }}>{filtered.length} de {hands.length} visíveis</span>
          </div>

          {/* Tabela */}
          {filtered.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
              {hands.length === 0 ? '0 mãos elegíveis agora.' : 'Nenhuma mão corresponde aos filtros.'}
            </div>
          ) : (
            <div style={{ overflowX: 'auto', border: '1px solid var(--border)', borderRadius: 8 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: 'var(--muted)', background: 'var(--bg)' }}>
                    {['hand_id', 'played_at (UTC)', 'site', 'torneio', 'fmt', 'pos', 'heroBB', 'aggressor', 'tags', ''].map(h => (
                      <th key={h} style={{ padding: '8px 10px', fontWeight: 600, whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(h => (
                    <tr key={h.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={{ padding: '7px 10px', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>{h.hand_id}</td>
                      <td style={{ padding: '7px 10px', whiteSpace: 'nowrap', color: 'var(--muted)' }}>{fmtTs(h.played_at)}</td>
                      <td style={{ padding: '7px 10px' }}>{h.site}</td>
                      <td style={{ padding: '7px 10px', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {h.tournament_name}
                        <span style={{ color: 'var(--muted)', opacity: 0.7 }}> ({h.tournament_number})</span>
                      </td>
                      <td style={{ padding: '7px 10px' }}>{h.tournament_format || '—'}</td>
                      <td style={{ padding: '7px 10px' }}>{h.position_hero || '—'}</td>
                      <td style={{ padding: '7px 10px' }}>{h.stack_hero_bb ?? '—'}</td>
                      <td style={{ padding: '7px 10px' }}>
                        <Chip color={SRC_COLOR[h.aggressor_source]}>{h.aggressor_source}</Chip>
                      </td>
                      <td style={{ padding: '7px 10px' }}>
                        <span style={{ display: 'inline-flex', gap: 4, flexWrap: 'wrap' }}>
                          {(h.hm3_tags || []).map(t => <Chip key={`h${t}`} color="#8b5cf6">{t}</Chip>)}
                          {(h.discord_tags || []).map(t => <Chip key={`d${t}`} color="#3b82f6">{t}</Chip>)}
                          {!(h.hm3_tags || []).length && !(h.discord_tags || []).length && '—'}
                        </span>
                      </td>
                      <td style={{ padding: '7px 10px', whiteSpace: 'nowrap' }}>
                        <Link to={`/replayer/${h.id}`} style={{ color: 'var(--accent2, #818cf8)', textDecoration: 'none' }}>ver →</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
