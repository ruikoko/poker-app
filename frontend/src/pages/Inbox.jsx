import { useEffect, useState, useCallback, useRef } from 'react'
import { hands, imports, screenshots } from '../api/client'

const STATE_COLORS = {
  new:       '#3b82f6',
  review:    '#f59e0b',
  studying:  '#8b5cf6',
  resolved:  '#22c55e',
}

const SUIT_COLORS = { h: '#ef4444', d: '#f97316', c: '#22c55e', s: '#e2e8f0' }
const SUIT_BG     = { h: '#dc2626', d: '#2563eb', c: '#16a34a', s: '#1e293b' }
const SUIT_SYMBOLS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' }

function MiniCard({ card }) {
  if (!card || card.length < 2) return <span style={{ color: '#4b5563' }}>?</span>
  const rank = card.slice(0, -1).toUpperCase()
  const suit = card.slice(-1).toLowerCase()
  const bg = SUIT_BG[suit] || '#1e2130'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 24, height: 32, background: bg, border: '1px solid rgba(255,255,255,0.2)',
      borderRadius: 3, fontFamily: "'Fira Code', monospace", fontSize: 10,
      fontWeight: 700, color: '#fff', lineHeight: 1, gap: 0,
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

// ── Orphan Screenshot Row (componente separado para usar useState) ───────────
function OrphanScreenshotRow({ o, onRematch, onDismiss }) {
  const [showImg, setShowImg] = useState(false)
  const meta = (o.raw_json && o.raw_json.file_meta) || {}
  const players = (o.raw_json && o.raw_json.players_by_position) || {}
  const playersList = (o.raw_json && o.raw_json.players_list) || []
  const visionDone = o.raw_json && o.raw_json.vision_done
  const imgB64 = o.raw_json && o.raw_json.img_b64
  const mimeType = (o.raw_json && o.raw_json.mime_type) || 'image/png'
  const heroName = o.raw_json && o.raw_json.hero
  const visionSb = o.raw_json && o.raw_json.vision_sb
  const visionBb = o.raw_json && o.raw_json.vision_bb
  const playersCount = playersList.length || Object.keys(players).length

  return (
    <div style={{
      padding: '7px 16px 7px 36px', fontSize: 11,
      borderBottom: '1px solid rgba(30,33,48,0.6)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ color: visionDone ? '#22c55e' : '#f59e0b', fontSize: 10 }}>{visionDone ? '●' : '○'}</span>
        <div
          style={{ flex: 1, minWidth: 0, cursor: imgB64 ? 'pointer' : 'default' }}
          onClick={() => imgB64 && setShowImg(v => !v)}
        >
          <span style={{ color: '#94a3b8', fontFamily: 'monospace' }}>
            {meta.time || '—'}
          </span>
          <span style={{ color: '#4b5563', marginLeft: 8 }}>
            blinds {meta.blinds || '—'}
          </span>
          {visionDone && playersCount > 0 && (
            <span style={{ color: '#22c55e', marginLeft: 8 }}>
              {playersCount} jogadores
            </span>
          )}
          {heroName && (
            <span style={{ color: '#818cf8', marginLeft: 8, fontSize: 10 }}>Hero: {heroName}</span>
          )}
          {visionSb && (
            <span style={{ color: '#f59e0b', marginLeft: 8, fontSize: 10 }}>SB: {visionSb}</span>
          )}
          {!visionDone && (
            <span style={{ color: '#f59e0b', marginLeft: 8, fontSize: 10 }}>Vision a processar...</span>
          )}
          {imgB64 && (
            <span style={{ color: '#6366f1', marginLeft: 8, fontSize: 10 }}>{showImg ? '▼ fechar' : '▶ ver SS'}</span>
          )}
        </div>
        <button
          onClick={() => onRematch(o.id)}
          style={{
            padding: '3px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
            background: 'rgba(99,102,241,0.1)', color: '#818cf8',
            border: '1px solid rgba(99,102,241,0.25)', cursor: 'pointer',
          }}
        >Rematch</button>
        <button
          onClick={() => onDismiss(o.id)}
          style={{
            padding: '3px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
            background: 'transparent', color: '#374151',
            border: '1px solid #1e2130', cursor: 'pointer',
          }}
        >&#10005;</button>
      </div>
      {showImg && imgB64 && (
        <div style={{ marginTop: 8, marginBottom: 4 }}>
          <img
            src={`data:${mimeType};base64,${imgB64}`}
            alt="Screenshot"
            style={{ maxWidth: '100%', maxHeight: 500, borderRadius: 6, border: '1px solid #2a2d3a' }}
          />
        </div>
      )}
    </div>
  )
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

  // Orphan screenshots state
  const [orphans, setOrphans] = useState([])
  const [orphansLoading, setOrphansLoading] = useState(false)
  const [orphansExpanded, setOrphansExpanded] = useState(false)
  const [expandedTMs, setExpandedTMs] = useState({})

  const loadOrphans = useCallback(() => {
    setOrphansLoading(true)
    screenshots.orphans()
      .then(d => setOrphans(d.data || []))
      .catch(() => setOrphans([]))
      .finally(() => setOrphansLoading(false))
  }, [])

  useEffect(() => { loadOrphans() }, [loadOrphans])

  async function handleRematch(entryId) {
    try {
      const res = await screenshots.rematch(entryId)
      if (res.status === 'matched') {
        loadOrphans()
        load()
      } else {
        alert(res.message)
      }
    } catch (e) {
      alert(e.message)
    }
  }

  async function handleDismiss(entryId) {
    try {
      await screenshots.dismiss(entryId)
      loadOrphans()
    } catch (e) {
      alert(e.message)
    }
  }

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
    loadOrphans() // Refresh orphan screenshots
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
                        ? `${item.result.hands_inserted} mãos arquivadas em MTT${item.result.rematched_screenshots > 0 ? ` · ${item.result.rematched_screenshots} screenshot(s) matched` : ''}`
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

      {/* ── Orphan Screenshots ── */}
      {(orphansLoading || orphans.length > 0) && (() => {
        // Agrupar órfãos por TM number
        const byTM = {}
        orphans.forEach(o => {
          const tm = (o.raw_json && o.raw_json.tm) || 'sem-tm'
          if (!byTM[tm]) byTM[tm] = []
          byTM[tm].push(o)
        })
        const tmGroups = Object.entries(byTM)

        return (
          <div style={{
            background: '#1a1d27', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 10,
            overflow: 'hidden', marginBottom: 20,
          }}>
            {/* Cabeçalho colapsável */}
            <div
              onClick={() => setOrphansExpanded(v => !v)}
              style={{
                padding: '10px 16px',
                borderBottom: orphansExpanded ? '1px solid rgba(245,158,11,0.15)' : 'none',
                display: 'flex', alignItems: 'center', gap: 8,
                cursor: 'pointer', userSelect: 'none',
              }}
            >
              <span style={{ color: '#f59e0b', fontSize: 13 }}>&#9888;</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#f59e0b' }}>
                Screenshots sem HH
              </span>
              <span style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                minWidth: 20, height: 18, padding: '0 6px', borderRadius: 9,
                background: 'rgba(245,158,11,0.15)', color: '#f59e0b',
                fontSize: 10, fontWeight: 700,
              }}>{orphans.length}</span>
              <span style={{ fontSize: 11, color: '#4b5563', marginLeft: 2 }}>
                {tmGroups.length} torneio{tmGroups.length !== 1 ? 's' : ''}
              </span>
              <span style={{ marginLeft: 'auto', color: '#4b5563', fontSize: 12, transition: 'transform 0.2s', display: 'inline-block', transform: orphansExpanded ? 'rotate(180deg)' : 'none' }}>&#9660;</span>
            </div>

            {/* Conteúdo expansível */}
            {orphansLoading ? (
              <div style={{ padding: '16px', color: '#4b5563', fontSize: 12 }}>A carregar...</div>
            ) : orphansExpanded && (
              <div>
                {tmGroups.map(([tm, entries]) => {
                  const isOpen = expandedTMs[tm] !== false // aberto por defeito se só 1 entry
                  const firstMeta = (entries[0].raw_json && entries[0].raw_json.file_meta) || {}
                  return (
                    <div key={tm} style={{ borderBottom: '1px solid #1e2130' }}>
                      {/* Cabeçalho do grupo TM */}
                      <div
                        onClick={() => setExpandedTMs(prev => ({ ...prev, [tm]: !isOpen }))}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 10,
                          padding: '8px 16px', cursor: 'pointer',
                          background: 'rgba(245,158,11,0.04)',
                          borderBottom: isOpen ? '1px solid rgba(245,158,11,0.08)' : 'none',
                        }}
                      >
                        <span style={{ color: '#f59e0b', fontSize: 10, transition: 'transform 0.15s', display: 'inline-block', transform: isOpen ? 'rotate(90deg)' : 'none' }}>&#9654;</span>
                        <span style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', fontFamily: 'monospace' }}>{tm}</span>
                        <span style={{ fontSize: 11, color: '#64748b' }}>{firstMeta.date || ''}</span>
                        <span style={{
                          marginLeft: 4,
                          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                          minWidth: 18, height: 16, padding: '0 5px', borderRadius: 8,
                          background: 'rgba(99,102,241,0.15)', color: '#818cf8',
                          fontSize: 10, fontWeight: 700,
                        }}>{entries.length}</span>
                        <span style={{ fontSize: 11, color: '#4b5563' }}>mão{entries.length !== 1 ? 's' : ''}</span>
                        {/* Rematch all */}
                        <button
                          onClick={e => { e.stopPropagation(); entries.forEach(o => handleRematch(o.id)) }}
                          style={{
                            marginLeft: 'auto', padding: '3px 9px', borderRadius: 5, fontSize: 10, fontWeight: 600,
                            background: 'rgba(99,102,241,0.12)', color: '#818cf8',
                            border: '1px solid rgba(99,102,241,0.3)', cursor: 'pointer',
                          }}
                        >Rematch todos</button>
                      </div>

                      {/* Linhas individuais */}
                      {isOpen && entries.map(o => (
                        <OrphanScreenshotRow
                          key={o.id}
                          o={o}
                          onRematch={handleRematch}
                          onDismiss={handleDismiss}
                        />
                      ))}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )
      })()}

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
