import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { tableSs, hands } from '../api/client'

// Estado por ficheiro nesta sessão de upload (pending → processing → terminal).
const STATUS = {
  pending:    { label: 'em fila',      color: '#64748b' },
  processing: { label: 'a processar…', color: '#3b82f6' },
  done:       { label: 'ligada',       color: '#22c55e' },
  no_match:   { label: 'sem match',    color: '#eab308' },
  error:      { label: 'erro',         color: '#ef4444' },
}

// Cor do chip de `result` na tabela "Últimas processadas" (valores do backend).
const RESULT_COLOR = {
  success: '#22c55e',
  no_match_to_hand: '#eab308',
  tm_ambiguous: '#f97316',
  vision_failed: '#ef4444',
  json_invalid: '#ef4444',
  site_undetected: '#ef4444',
}

function fmtTs(iso) {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 16)  // ISO UTC → "YYYY-MM-DD HH:MM"
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

// result do backend → status terminal do ficheiro.
function resultToStatus(result) {
  if (result === 'success') return 'done'
  if (result === 'no_match_to_hand' || result === 'tm_ambiguous') return 'no_match'
  return 'error'
}

export default function TableSSPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState([])          // uploads desta sessão
  const [dragging, setDragging] = useState(false)
  const [recent, setRecent] = useState([])
  const [loadingRecent, setLoadingRecent] = useState(true)
  const [recentError, setRecentError] = useState(null)
  const inputRef = useRef(null)
  const keyRef = useRef(0)

  // silent=true: actualiza a tabela sem mexer no spinner (refresh ao vivo após
  // cada upload — #23, fecha o "ainda a processar" preso mostrando já o
  // resultado reconciliado pelo R).
  async function refreshRecent(silent = false) {
    if (!silent) setLoadingRecent(true)
    setRecentError(null)
    try {
      const out = await tableSs.recent()
      setRecent(out?.items || [])
    } catch (e) {
      if (!silent) setRecentError(String(e.message || e))
    } finally {
      if (!silent) setLoadingRecent(false)
    }
  }

  useEffect(() => { refreshRecent() }, [])

  const patch = (key, fields) =>
    setItems(prev => prev.map(it => (it.key === key ? { ...it, ...fields } : it)))

  const addFiles = useCallback(async (fileList) => {
    const picked = Array.from(fileList).filter(f => /\.(png|jpe?g)$/i.test(f.name))
    if (!picked.length) return
    const entries = picked.map(f => ({
      key: ++keyRef.current, name: f.name, file: f, status: 'pending', result: null,
    }))
    setItems(prev => [...entries, ...prev])
    // Sequencial — evita martelar a Vision em paralelo. O upload já devolve o
    // match final (R corre síncrono), por isso o estado por ficheiro nunca fica
    // preso em "a processar"; refrescamos a tabela ao vivo a cada ficheiro.
    for (const e of entries) {
      patch(e.key, { status: 'processing' })
      try {
        const r = await tableSs.upload(e.file, { filename: e.file.name })
        patch(e.key, { status: resultToStatus(r.result), result: r })
      } catch (err) {
        patch(e.key, { status: 'error', result: { reason_detail: String(err.message || err) } })
      }
      refreshRecent(true)   // refresh ao vivo, sem flicker do spinner
    }
    refreshRecent()
  }, [])

  const onDrop = useCallback((ev) => {
    ev.preventDefault(); setDragging(false)
    if (ev.dataTransfer.files.length) addFiles(ev.dataTransfer.files)
  }, [addFiles])
  const onDragOver = useCallback((ev) => { ev.preventDefault(); setDragging(true) }, [])
  const onDragLeave = useCallback(() => setDragging(false), [])

  // matched_hand_id é o hand_id TEXT (ex. WN-10); o /replayer usa o id numérico.
  // Resolve no clique via search + match exacto (recent não expõe o db id).
  async function openHand(handIdText) {
    if (!handIdText) return
    try {
      const out = await hands.list({ search: handIdText })
      const row = (out?.data || []).find(r => r.hand_id === handIdText)
      if (row) navigate(`/replayer/${row.id}`)
    } catch { /* no-op */ }
  }

  return (
    <div style={{ padding: 24, maxWidth: 1180, margin: '0 auto' }}>
      {/* Header */}
      <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 4px' }}>SS Mesa</h1>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
        Carrega SSs de mesa (Intuitive Tables) para dar ao HRC um <code>players_left</code>{' '}
        fidedigno por mão. A Vision lê o painel da mesa e a SS é ligada à mão jogada
        em ±5 min do instante de captura.
      </div>

      {/* Drop zone */}
      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => inputRef.current?.click()}
        style={{
          border: `2px dashed ${dragging ? 'var(--accent)' : 'var(--border)'}`,
          borderRadius: 10, padding: '28px 16px', textAlign: 'center',
          cursor: 'pointer', background: dragging ? 'rgba(99,102,241,0.06)' : 'transparent',
          color: 'var(--muted)', fontSize: 13, marginBottom: 18,
        }}
      >
        <div style={{ fontSize: 22, marginBottom: 6 }}>⬆</div>
        Arrasta SSs de mesa aqui, ou <span style={{ color: 'var(--accent)' }}>clica para escolher</span>
        <div style={{ fontSize: 11, opacity: 0.7, marginTop: 4 }}>.png .jpg — nome com timestamp (YYYYMMDDHHMMSS)</div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".png,.jpg,.jpeg"
          style={{ display: 'none' }}
          onChange={(e) => { if (e.target.files.length) addFiles(e.target.files); e.target.value = '' }}
        />
      </div>

      {/* Em processamento (sessão actual) */}
      {items.length > 0 && (
        <div style={{ marginBottom: 22 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Nesta sessão</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {items.map(it => {
              const st = STATUS[it.status] || STATUS.pending
              const r = it.result || {}
              return (
                <div key={it.key} style={{
                  display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
                  padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 8,
                  fontSize: 12,
                }}>
                  <span style={{ fontFamily: 'monospace', flex: '0 0 auto' }}>{it.name}</span>
                  <Chip color={st.color}>{st.label}</Chip>
                  {it.status === 'done' && (
                    <span style={{ color: 'var(--muted)' }}>
                      {r.site} · {r.tournament_name} · <b style={{ color: 'var(--text)' }}>left {r.players_left ?? '—'}</b>
                      {r.hand_matched && (
                        <> {' · '}
                          <a onClick={() => openHand(r.hand_matched)}
                             style={{ color: 'var(--accent2, #818cf8)', cursor: 'pointer' }}>
                            {r.hand_matched} ver →
                          </a>
                        </>
                      )}
                    </span>
                  )}
                  {(it.status === 'no_match' || it.status === 'error') && (
                    <span style={{ color: 'var(--muted)', opacity: 0.85 }}>
                      {r.players_left != null && <>left {r.players_left} · </>}
                      {r.reason_detail || r.result || '—'}
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Últimas processadas */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Últimas processadas</div>
        <button
          onClick={refreshRecent}
          disabled={loadingRecent}
          style={{
            padding: '5px 12px', fontSize: 11, fontWeight: 600, borderRadius: 6,
            background: 'var(--accent)', border: 'none', color: '#fff',
            cursor: loadingRecent ? 'wait' : 'pointer', opacity: loadingRecent ? 0.5 : 1,
          }}
        >{loadingRecent ? 'A carregar…' : '↻ Refresh'}</button>
      </div>

      {recentError && (
        <div style={{ padding: 12, borderRadius: 8, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#ef4444', fontSize: 13, marginBottom: 14 }}>
          Erro: {recentError}
        </div>
      )}

      {!recentError && (
        recent.length === 0 ? (
          <div style={{ padding: 28, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
            {loadingRecent ? 'A carregar…' : 'Ainda não há SSs de mesa processadas.'}
          </div>
        ) : (
          <div style={{ overflowX: 'auto', border: '1px solid var(--border)', borderRadius: 8 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ textAlign: 'left', color: 'var(--muted)', background: 'var(--bg)' }}>
                  {['captura (UTC)', 'site', 'torneio', 'left', 'entries', 'mão', 'resultado', 'tent.'].map(h => (
                    <th key={h} style={{ padding: '8px 10px', fontWeight: 600, whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recent.map(row => (
                  <tr key={row.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <td style={{ padding: '7px 10px', whiteSpace: 'nowrap', color: 'var(--muted)' }}>{fmtTs(row.captured_at)}</td>
                    <td style={{ padding: '7px 10px' }}>{row.site || '—'}</td>
                    <td style={{ padding: '7px 10px', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {row.tournament_name || '—'}
                      {row.tournament_number && (
                        <span style={{ color: 'var(--muted)', opacity: 0.7 }}> ({row.tournament_number})</span>
                      )}
                    </td>
                    <td style={{ padding: '7px 10px', fontWeight: 600 }}>{row.players_left ?? '—'}</td>
                    <td style={{ padding: '7px 10px', color: 'var(--muted)' }}>{row.total_entries ?? '—'}</td>
                    <td style={{ padding: '7px 10px', whiteSpace: 'nowrap', fontFamily: 'monospace' }}>
                      {row.matched_hand_id ? (
                        <a onClick={() => openHand(row.matched_hand_id)}
                           style={{ color: 'var(--accent2, #818cf8)', cursor: 'pointer', textDecoration: 'none' }}>
                          {row.matched_hand_id} →
                        </a>
                      ) : '—'}
                    </td>
                    <td style={{ padding: '7px 10px' }} title={row.reason_detail || ''}>
                      <Chip color={RESULT_COLOR[row.result]}>{row.result}</Chip>
                    </td>
                    <td style={{ padding: '7px 10px', color: 'var(--muted)' }}>{row.attempt_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  )
}
