import { useEffect, useState, useCallback, useRef } from 'react'
import { hands, imports, screenshots } from '../api/client'

const STATE_COLORS = {
  new:       '#3b82f6',
  review:    '#f59e0b',
  studying:  '#8b5cf6',
  resolved:  '#22c55e',
}

const SUIT_COLORS = { h: '#ef4444', d: '#f97316', c: '#22c55e', s: '#e2e8f0' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }

function MiniCard({ card }) {
  if (!card || card.length < 2) return <span style={{ color: '#4b5563' }}>?</span>
  const rank = card.slice(0, -1).toUpperCase()
  const suit = card.slice(-1).toLowerCase()
  const color = SUIT_COLORS[suit] || '#e2e8f0'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 24, height: 32, background: '#1e2130', border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 3, fontFamily: "'Fira Code', monospace", fontSize: 10,
      fontWeight: 700, color, lineHeight: 1, gap: 0,
    }}>
      <span>{rank}</span>
      <span style={{ fontSize: 8 }}>{SUIT_SYMBOLS[suit]}</span>
    </span>
  )
}

function PosBadge({ pos }) {
  if (!pos) return <span style={{ color: '#4b5563' }}>&mdash;</span>
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
      fontSize: 10, fontWeight: 700, letterSpacing: 0.4,
      color: c, background: `${c}18`, border: `1px solid ${c}30`,
    }}>{pos}</span>
  )
}

function StateBadge({ state }) {
  const meta = {
    new:      { label: 'Nova',      color: '#3b82f6', bg: 'rgba(59,130,246,0.12)' },
    review:   { label: 'Revisão',   color: '#f59e0b', bg: 'rgba(245,158,11,0.12)' },
    studying: { label: 'A Estudar', color: '#8b5cf6', bg: 'rgba(139,92,246,0.12)' },
    resolved: { label: 'Resolvida', color: '#22c55e', bg: 'rgba(34,197,94,0.12)' },
  }
  const m = meta[state] || { label: state, color: '#666', bg: 'rgba(100,100,100,0.12)' }
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 999,
      fontSize: 10, fontWeight: 600, color: m.color, background: m.bg,
    }}>{m.label}</span>
  )
}

function ResultBadge({ result }) {
  if (result == null) return <span style={{ color: '#4b5563' }}>&mdash;</span>
  const val = Number(result)
  if (val > 0) return <span style={{ color: '#22c55e', fontWeight: 600, fontFamily: 'monospace', fontSize: 11 }}>+{val.toFixed(1)}</span>
  if (val < 0) return <span style={{ color: '#ef4444', fontWeight: 600, fontFamily: 'monospace', fontSize: 11 }}>{val.toFixed(1)}</span>
  return <span style={{ color: '#64748b', fontFamily: 'monospace', fontSize: 11 }}>0</span>
}

// ── File type icons ──
function FileIcon({ type }) {
  const icons = {
    hh: { icon: '\u2660', color: '#6366f1', label: 'Hand History' },
    summary: { icon: '\u2211', color: '#f59e0b', label: 'Tournament Summary' },
    screenshot: { icon: '\u25A3', color: '#22c55e', label: 'Screenshot' },
    unknown: { icon: '?', color: '#64748b', label: 'Desconhecido' },
  }
  const m = icons[type] || icons.unknown
  return (
    <span title={m.label} style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 28, height: 28, borderRadius: 6,
      background: `${m.color}15`, border: `1px solid ${m.color}30`,
      color: m.color, fontSize: 14, fontWeight: 700,
    }}>{m.icon}</span>
  )
}

function classifyFile(file) {
  const name = file.name.toLowerCase()
  const isImage = file.type.startsWith('image/') || /\.(png|jpg|jpeg|gif|webp)$/.test(name)
  if (isImage) return 'screenshot'
  if (name.includes('summary') || name.includes('ts_')) return 'summary'
  if (name.startsWith('gg') || name.includes('hand') || name.includes('hh')) return 'hh'
  if (name.endsWith('.zip') || name.endsWith('.txt')) return 'hh' // default for text/zip
  return 'unknown'
}

export default function InboxPage() {
  const [data, setData]       = useState({ data: [], total: 0, pages: 1 })
  const [page, setPage]       = useState(1)
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)

  // Upload state
  const [dragOver, setDragOver] = useState(false)
  const [uploadQueue, setUploadQueue] = useState([]) // { file, type, status, result }
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef(null)

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    hands.list({ study_state: 'new', page, page_size: 50 })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [page])

  useEffect(() => { load() }, [load])

  // ── Drag & Drop handlers ──
  function handleDragOver(e) {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(true)
  }
  function handleDragLeave(e) {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(false)
  }
  function handleDrop(e) {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(false)
    const files = Array.from(e.dataTransfer.files)
    addFiles(files)
  }
  function handleFileSelect(e) {
    const files = Array.from(e.target.files)
    addFiles(files)
    e.target.value = ''
  }

  function addFiles(files) {
    const newItems = files.map(f => ({
      file: f,
      type: classifyFile(f),
      status: 'pending', // pending | uploading | done | error
      result: null,
    }))
    setUploadQueue(prev => [...prev, ...newItems])
  }

  function removeFromQueue(idx) {
    setUploadQueue(prev => prev.filter((_, i) => i !== idx))
  }

  function changeType(idx, newType) {
    setUploadQueue(prev => prev.map((item, i) => i === idx ? { ...item, type: newType } : item))
  }

  async function processQueue() {
    setUploading(true)
    const queue = [...uploadQueue]

    for (let i = 0; i < queue.length; i++) {
      if (queue[i].status !== 'pending') continue

      // Update status to uploading
      setUploadQueue(prev => prev.map((item, j) => j === i ? { ...item, status: 'uploading' } : item))

      try {
        // For screenshots, use the Vision endpoint
        if (queue[i].type === 'screenshot') {
          const res = await screenshots.upload(queue[i].file)
          setUploadQueue(prev => prev.map((item, j) => j === i ? {
            ...item, status: 'done', result: { import_type: 'screenshot', ...res }
          } : item))
          continue
        }

        // For HH and summaries, use the existing import endpoint
        const res = await imports.upload(queue[i].file)
        setUploadQueue(prev => prev.map((item, j) => j === i ? { ...item, status: 'done', result: res } : item))
      } catch (err) {
        setUploadQueue(prev => prev.map((item, j) => j === i ? { ...item, status: 'error', result: { error: err.message } } : item))
      }
    }

    setUploading(false)
    load() // Refresh the inbox
  }

  function clearCompleted() {
    setUploadQueue(prev => prev.filter(item => item.status === 'pending'))
  }

  async function quickAction(id, newState) {
    try {
      await hands.update(id, { study_state: newState })
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  const rows = data.data || []
  const pendingCount = uploadQueue.filter(i => i.status === 'pending').length
  const doneCount = uploadQueue.filter(i => i.status === 'done').length

  return (
    <>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <div>
            <div className="page-title">Inbox</div>
            <div className="page-subtitle">{data.total} mãos novas por processar</div>
          </div>
        </div>
      </div>

      {/* ── Upload Zone ── */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        style={{
          border: `2px dashed ${dragOver ? '#6366f1' : '#2a2d3a'}`,
          borderRadius: 12,
          padding: uploadQueue.length > 0 ? '16px 20px' : '32px 20px',
          marginBottom: 20,
          textAlign: 'center',
          cursor: 'pointer',
          background: dragOver ? 'rgba(99,102,241,0.06)' : '#1a1d27',
          transition: 'all 0.2s',
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".txt,.zip,.png,.jpg,.jpeg,.webp"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />

        {uploadQueue.length === 0 ? (
          <>
            <div style={{ fontSize: 28, marginBottom: 8, color: dragOver ? '#6366f1' : '#4b5563' }}>
              {dragOver ? '\u2B07' : '\u2191'}
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, color: dragOver ? '#818cf8' : '#94a3b8', marginBottom: 4 }}>
              {dragOver ? 'Largar ficheiros aqui' : 'Arrastar ficheiros ou clicar para seleccionar'}
            </div>
            <div style={{ fontSize: 12, color: '#4b5563' }}>
              Screenshots (.png/.jpg) → Mãos de estudo &middot; HH &amp; Summaries (.zip/.txt) → Arquivo MTT
            </div>
          </>
        ) : (
          <div onClick={e => e.stopPropagation()}>
            {/* File queue */}
            <div style={{ textAlign: 'left' }}>
              {uploadQueue.map((item, idx) => (
                <div key={idx} style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '8px 0',
                  borderBottom: idx < uploadQueue.length - 1 ? '1px solid #1e2130' : 'none',
                  opacity: item.status === 'done' ? 0.6 : 1,
                }}>
                  <FileIcon type={item.type} />

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 500, color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.file.name}
                    </div>
                    <div style={{ fontSize: 10, color: '#4b5563' }}>
                      {(item.file.size / 1024).toFixed(0)} KB
                    </div>
                  </div>

                  {/* Type selector (only for pending) */}
                  {item.status === 'pending' && (
                    <select
                      value={item.type}
                      onChange={e => changeType(idx, e.target.value)}
                      onClick={e => e.stopPropagation()}
                      style={{
                        background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 4,
                        color: '#94a3b8', padding: '3px 6px', fontSize: 10,
                      }}
                    >
                      <option value="hh">Hand History</option>
                      <option value="summary">Tournament Summary</option>
                      <option value="screenshot">Screenshot</option>
                    </select>
                  )}

                  {/* Status */}
                  {item.status === 'uploading' && (
                    <span style={{ fontSize: 11, color: '#6366f1', fontWeight: 500 }}>A processar...</span>
                  )}
                  {item.status === 'done' && item.result && !item.result.error && (
                    <span style={{ fontSize: 11, fontWeight: 500, color:
                      item.result.import_type === 'screenshot'
                        ? (item.result.status === 'matched' ? '#22c55e' : '#f59e0b')
                        : '#22c55e'
                    }}>
                      {item.result.import_type === 'hands'
                        ? `${item.result.hands_inserted} mãos arquivadas em MTT`
                        : item.result.import_type === 'tournaments'
                          ? `${item.result.inserted} torneios → MTT`
                          : item.result.status === 'matched'
                            ? `✓ Match: mão #${item.result.hand_id}`
                            : item.result.tm_number
                              ? `TM ${item.result.tm_number} — sem HH`
                              : 'Sem TM detectado'
                      }
                    </span>
                  )}
                  {item.status === 'error' && (
                    <span style={{ fontSize: 11, color: '#ef4444', fontWeight: 500 }}>
                      {item.result?.error || 'Erro'}
                    </span>
                  )}

                  {/* Remove button (only for pending) */}
                  {item.status === 'pending' && (
                    <button
                      onClick={e => { e.stopPropagation(); removeFromQueue(idx) }}
                      style={{ background: 'transparent', border: 'none', color: '#4b5563', cursor: 'pointer', fontSize: 14, padding: '0 4px' }}
                      onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
                      onMouseLeave={e => e.currentTarget.style.color = '#4b5563'}
                    >&#10005;</button>
                  )}
                </div>
              ))}
            </div>

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: 8, marginTop: 12, justifyContent: 'flex-end' }}>
              {doneCount > 0 && (
                <button
                  onClick={e => { e.stopPropagation(); clearCompleted() }}
                  style={{
                    padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 500,
                    background: 'transparent', color: '#64748b', border: '1px solid #2a2d3a', cursor: 'pointer',
                  }}
                >Limpar concluídos</button>
              )}
              {pendingCount > 0 && (
                <>
                  <button
                    onClick={e => { e.stopPropagation(); fileInputRef.current?.click() }}
                    style={{
                      padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 500,
                      background: 'transparent', color: '#94a3b8', border: '1px solid #2a2d3a', cursor: 'pointer',
                    }}
                  >+ Adicionar</button>
                  <button
                    onClick={e => { e.stopPropagation(); processQueue() }}
                    disabled={uploading}
                    style={{
                      padding: '6px 18px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                      background: uploading ? '#4b5563' : '#6366f1', color: '#fff',
                      border: 'none', cursor: uploading ? 'not-allowed' : 'pointer',
                    }}
                  >{uploading ? 'A processar...' : `Importar ${pendingCount} ficheiro${pendingCount > 1 ? 's' : ''}`}</button>
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}

      {/* ── Hands table ── */}
      <div style={{
        background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 10,
        overflow: 'hidden',
      }}>
        <div style={{
          padding: '12px 16px', borderBottom: '1px solid #2a2d3a',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#94a3b8' }}>
            Mãos novas ({data.total})
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1e2130' }}>
                {['Data', 'Torneio', 'Pos', 'Cartas', 'Board', 'Resultado', 'Acções'].map(h => (
                  <th key={h} style={{
                    padding: '8px 12px', textAlign: 'left', color: '#4b5563',
                    fontWeight: 600, fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.4,
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: 32, color: '#4b5563' }}>A carregar...</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: 48, color: '#4b5563' }}>
                  <div style={{ fontSize: 28, marginBottom: 8 }}>&#127183;</div>
                  Inbox vazia. Importa ficheiros HH acima.
                </td></tr>
              )}
              {!loading && rows.map(h => (
                <tr key={h.id} style={{ borderBottom: '1px solid #1e2130' }}>
                  <td style={{ padding: '8px 12px', color: '#64748b', whiteSpace: 'nowrap', fontSize: 11 }}>
                    {h.played_at ? h.played_at.slice(5, 10) : '—'}
                  </td>
                  <td style={{ padding: '8px 12px', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#94a3b8', fontSize: 11 }}>
                    {h.stakes || '—'}
                  </td>
                  <td style={{ padding: '8px 12px' }}><PosBadge pos={h.position} /></td>
                  <td style={{ padding: '8px 12px' }}>
                    <div style={{ display: 'flex', gap: 2 }}>
                      {h.hero_cards?.length > 0 ? h.hero_cards.map((c, i) => <MiniCard key={i} card={c} />) : <span style={{ color: '#374151' }}>&mdash;</span>}
                    </div>
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    <div style={{ display: 'flex', gap: 2 }}>
                      {h.board?.length > 0 ? h.board.slice(0, 5).map((c, i) => <MiniCard key={i} card={c} />) : <span style={{ color: '#374151' }}>&mdash;</span>}
                    </div>
                  </td>
                  <td style={{ padding: '8px 12px' }}><ResultBadge result={h.result} /></td>
                  <td style={{ padding: '8px 12px' }}>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button
                        style={{
                          padding: '3px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                          background: 'rgba(245,158,11,0.1)', color: '#f59e0b',
                          border: '1px solid rgba(245,158,11,0.25)', cursor: 'pointer',
                        }}
                        onClick={() => quickAction(h.id, 'review')}
                      >Revisão</button>
                      <button
                        style={{
                          padding: '3px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                          background: 'rgba(139,92,246,0.1)', color: '#8b5cf6',
                          border: '1px solid rgba(139,92,246,0.25)', cursor: 'pointer',
                        }}
                        onClick={() => quickAction(h.id, 'studying')}
                      >Estudar</button>
                      <button
                        style={{
                          padding: '3px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                          background: 'rgba(34,197,94,0.1)', color: '#22c55e',
                          border: '1px solid rgba(34,197,94,0.25)', cursor: 'pointer',
                        }}
                        onClick={() => quickAction(h.id, 'resolved')}
                      >&#10003;</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {data.pages > 1 && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center',
            padding: '12px 0', borderTop: '1px solid #1e2130',
          }}>
            <button
              disabled={page <= 1}
              onClick={() => setPage(p => p - 1)}
              style={{
                padding: '5px 12px', borderRadius: 6, fontSize: 11, fontWeight: 500,
                background: page <= 1 ? 'transparent' : '#0f1117',
                color: page <= 1 ? '#374151' : '#94a3b8',
                border: '1px solid #2a2d3a', cursor: page <= 1 ? 'not-allowed' : 'pointer',
              }}
            >&#8592;</button>
            <span style={{ color: '#4b5563', fontSize: 11 }}>
              {page} / {data.pages}
            </span>
            <button
              disabled={page >= data.pages}
              onClick={() => setPage(p => p + 1)}
              style={{
                padding: '5px 12px', borderRadius: 6, fontSize: 11, fontWeight: 500,
                background: page >= data.pages ? 'transparent' : '#0f1117',
                color: page >= data.pages ? '#374151' : '#94a3b8',
                border: '1px solid #2a2d3a', cursor: page >= data.pages ? 'not-allowed' : 'pointer',
              }}
            >&#8594;</button>
          </div>
        )}
      </div>
    </>
  )
}
