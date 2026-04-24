import { useState, useRef, useCallback } from 'react'
import { imports, hm3, mtt, screenshots } from '../api/client'

// ── File type detection ──────────────────────────────────────────────────────

function detectFileType(file) {
  const name = file.name.toLowerCase()
  const ext = name.split('.').pop()

  if (ext === 'csv') return 'hm3'
  if (ext === 'png' || ext === 'jpg' || ext === 'jpeg') return 'screenshot'
  if (ext === 'txt') return 'hh'
  if (ext === 'zip') {
    // ZIP could be HH bulk, HRC tree, or MTT
    // We can't peek inside in the browser without JSZip, so we use filename heuristics
    if (name.includes('hrc') || name.includes('gto') || name.includes('tree') || name.includes('node')) return 'gto'
    return 'hh_zip'
  }
  return 'unknown'
}

const TYPE_META = {
  hm3:        { label: 'HM3 CSV',       color: '#8b5cf6', endpoint: 'hm3' },
  hh:         { label: 'Hand History',   color: '#3b82f6', endpoint: 'import' },
  hh_zip:     { label: 'HH ZIP',        color: '#3b82f6', endpoint: 'import' },
  gto:        { label: 'HRC / GTO',     color: '#22c55e', endpoint: 'gto' },
  screenshot: { label: 'Screenshot',     color: '#f59e0b', endpoint: 'screenshot' },
  unknown:    { label: 'Desconhecido',   color: '#ef4444', endpoint: null },
}

// ── Upload logic ─────────────────────────────────────────────────────────────

async function uploadFile(file, type, options = {}) {
  const form = new FormData()
  form.append('file', file)

  const API = (import.meta.env.VITE_API_URL || '') + '/api'

  switch (type) {
    case 'hm3': {
      let qs = ''
      const params = []
      if (options.daysBack) params.push(`days_back=${options.daysBack}`)
      if (params.length) qs = '?' + params.join('&')
      const res = await fetch(`${API}/hm3/import${qs}`, { method: 'POST', credentials: 'include', body: form })
      return await res.json()
    }
    case 'hh':
    case 'hh_zip': {
      const res = await fetch(`${API}/import`, { method: 'POST', credentials: 'include', body: form })
      return await res.json()
    }
    case 'gto': {
      form.append('name', file.name.replace(/\.zip$/i, ''))
      const res = await fetch(`${API}/gto/trees/import`, { method: 'POST', credentials: 'include', body: form })
      return await res.json()
    }
    case 'screenshot': {
      const res = await fetch(`${API}/screenshots`, { method: 'POST', credentials: 'include', body: form })
      return await res.json()
    }
    default:
      throw new Error('Tipo de ficheiro não suportado')
  }
}

function formatResult(type, result) {
  if (!result) return 'Sem resposta'
  if (result.detail) return `Erro: ${result.detail}`

  switch (type) {
    case 'hm3':
      return [
        result.inserted && `${result.inserted} mãos inseridas`,
        result.skipped_duplicates && `${result.skipped_duplicates} duplicados`,
        result.skipped_date_filter && `${result.skipped_date_filter} fora do período`,
        result.villains_created && `${result.villains_created} vilões`,
        result.migrated_to_study > 0 && `${result.migrated_to_study} → Estudo`,
        result.rejected_pre_2026 > 0 && `${result.rejected_pre_2026} <2026 rejeitadas`,
        result.errors && `${result.errors} erros`,
      ].filter(Boolean).join(' · ') || 'Importado'

    case 'hh':
    case 'hh_zip':
      return [
        result.hands_inserted && `${result.hands_inserted} mãos inseridas`,
        result.hands_found && result.hands_inserted && result.hands_found > result.hands_inserted &&
          `${result.hands_found - result.hands_inserted} ignoradas`,
        result.rematched?.length && `${result.rematched.length} screenshots matched`,
        result.migrated_to_study > 0 && `${result.migrated_to_study} → Estudo`,
        result.hands_rejected_pre_2026 > 0 && `${result.hands_rejected_pre_2026} <2026 rejeitadas`,
      ].filter(Boolean).join(' · ') || 'Importado'

    case 'gto':
      return result.tree_id ? `Árvore #${result.tree_id} criada (${result.nodes_count || '?'} nós)` : 'Importado'

    case 'screenshot':
      return result.status === 'matched'
        ? `Match: mão #${result.hand_id} (${result.players_mapped || 0} jogadores)`
        : result.status === 'orphan'
          ? 'Sem match — ficou como órfã'
          : 'Processado'

    default:
      return JSON.stringify(result).slice(0, 100)
  }
}

// ── Component ────────────────────────────────────────────────────────────────

export default function ImportModal({ open, onClose }) {
  const [files, setFiles] = useState([])  // [{id, file, type, status, result, daysBack}]
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef()
  const idCounter = useRef(0)

  const addFiles = useCallback((fileList) => {
    const newFiles = Array.from(fileList).map(f => ({
      id: ++idCounter.current,
      file: f,
      type: detectFileType(f),
      status: 'pending', // pending | uploading | done | error
      result: null,
      daysBack: '',
    }))
    setFiles(prev => [...prev, ...newFiles])
  }, [])

  const removeFile = useCallback((id) => {
    setFiles(prev => prev.filter(f => f.id !== id))
  }, [])

  const updateFile = useCallback((id, updates) => {
    setFiles(prev => prev.map(f => f.id === id ? { ...f, ...updates } : f))
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files)
  }, [addFiles])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setDragging(true)
  }, [])

  const handleDragLeave = useCallback(() => setDragging(false), [])

  const importAll = useCallback(async () => {
    const pending = files.filter(f => f.status === 'pending')
    if (!pending.length) return

    // Upload all in parallel
    await Promise.all(pending.map(async (f) => {
      updateFile(f.id, { status: 'uploading' })
      try {
        const options = {}
        if (f.type === 'hm3' && f.daysBack) options.daysBack = parseInt(f.daysBack)
        const result = await uploadFile(f.file, f.type, options)
        updateFile(f.id, { status: 'done', result })
      } catch (err) {
        updateFile(f.id, { status: 'error', result: { detail: err.message } })
      }
    }))
  }, [files, updateFile])

  const clearDone = useCallback(() => {
    setFiles(prev => prev.filter(f => f.status !== 'done' && f.status !== 'error'))
  }, [])

  const pendingCount = files.filter(f => f.status === 'pending').length
  const hasHm3 = files.some(f => f.type === 'hm3' && f.status === 'pending')

  if (!open) return null

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10,
        width: 560, maxHeight: '80vh', display: 'flex', flexDirection: 'column',
        boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          <span style={{ fontSize: 15, fontWeight: 600 }}>Importar ficheiros</span>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: 'var(--muted)', fontSize: 18, cursor: 'pointer', padding: '0 4px', lineHeight: 1 }}
          >&times;</button>
        </div>

        {/* Drop zone */}
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          style={{
            margin: '16px 20px',
            padding: '28px 20px',
            border: `2px dashed ${dragging ? 'var(--accent)' : 'var(--border)'}`,
            borderRadius: 8,
            background: dragging ? 'rgba(99,102,241,0.06)' : 'transparent',
            textAlign: 'center',
            transition: 'all 0.15s',
            cursor: 'pointer',
          }}
          onClick={() => inputRef.current?.click()}
        >
          <div style={{ fontSize: 13, color: dragging ? 'var(--accent2)' : 'var(--muted)', marginBottom: 6 }}>
            Largar ficheiros aqui ou carregar para escolher
          </div>
          <div style={{ fontSize: 11, color: 'var(--muted)', opacity: 0.7 }}>
            HH .txt .zip &nbsp;·&nbsp; HM3 .csv &nbsp;·&nbsp; HRC .zip &nbsp;·&nbsp; Screenshots .png .jpg
          </div>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".txt,.csv,.zip,.png,.jpg,.jpeg"
            style={{ display: 'none' }}
            onChange={e => { if (e.target.files.length) addFiles(e.target.files); e.target.value = '' }}
          />
        </div>

        {/* HM3 options (shown only when there's a pending HM3 CSV) */}
        {hasHm3 && (
          <div style={{ margin: '0 20px 12px', padding: '10px 14px', background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.2)', borderRadius: 6, display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 12, color: '#a78bfa', fontWeight: 500 }}>HM3</span>
            <label style={{ fontSize: 12, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
              Últimos
              <input
                type="number"
                min="1"
                max="365"
                placeholder="todos"
                style={{
                  width: 60, padding: '3px 6px', fontSize: 12,
                  background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text)',
                }}
                onChange={e => {
                  const val = e.target.value
                  setFiles(prev => prev.map(f => f.type === 'hm3' ? { ...f, daysBack: val } : f))
                }}
              />
              dias
            </label>
            <span style={{ fontSize: 11, color: 'var(--muted)', opacity: 0.6 }}>vazio = importa tudo</span>
          </div>
        )}

        {/* File list */}
        {files.length > 0 && (
          <div style={{ flex: 1, overflowY: 'auto', padding: '0 20px', maxHeight: 280 }}>
            {files.map(f => {
              const meta = TYPE_META[f.type] || TYPE_META.unknown
              const statusIcon = f.status === 'pending' ? '○' : f.status === 'uploading' ? '◌' : f.status === 'done' ? '✓' : '✗'
              const statusColor = f.status === 'done' ? '#22c55e' : f.status === 'error' ? '#ef4444' : f.status === 'uploading' ? '#f59e0b' : 'var(--muted)'
              return (
                <div key={f.id} style={{
                  display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0',
                  borderBottom: '1px solid rgba(255,255,255,0.03)',
                }}>
                  <span style={{ fontSize: 14, color: statusColor, width: 18, textAlign: 'center', flexShrink: 0 }}>{statusIcon}</span>
                  <span style={{
                    fontSize: 10, fontWeight: 600, color: meta.color,
                    background: `${meta.color}18`, padding: '2px 7px', borderRadius: 3, flexShrink: 0,
                  }}>{meta.label}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {f.file.name}
                    </div>
                    {f.result && (
                      <div style={{ fontSize: 11, color: f.status === 'error' ? '#ef4444' : '#22c55e', marginTop: 2 }}>
                        {formatResult(f.type, f.result)}
                      </div>
                    )}
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--muted)', flexShrink: 0 }}>
                    {(f.file.size / 1024).toFixed(0)}KB
                  </span>
                  {f.status === 'pending' && (
                    <button
                      onClick={() => removeFile(f.id)}
                      style={{ background: 'transparent', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 14, padding: '0 4px' }}
                      onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
                      onMouseLeave={e => e.currentTarget.style.color = 'var(--muted)'}
                    >&times;</button>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {/* Footer */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 20px', borderTop: '1px solid var(--border)',
        }}>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>
            {files.length === 0
              ? ''
              : pendingCount > 0
                ? `${pendingCount} ficheiro${pendingCount > 1 ? 's' : ''} por importar`
                : 'Importação concluída'}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {files.some(f => f.status === 'done' || f.status === 'error') && (
              <button
                onClick={clearDone}
                style={{
                  padding: '6px 14px', fontSize: 12, borderRadius: 5,
                  background: 'transparent', border: '1px solid var(--border)',
                  color: 'var(--muted)', cursor: 'pointer',
                }}
              >Limpar</button>
            )}
            <button
              onClick={importAll}
              disabled={pendingCount === 0}
              style={{
                padding: '6px 16px', fontSize: 12, fontWeight: 600, borderRadius: 5,
                background: pendingCount > 0 ? 'var(--accent)' : 'var(--border)',
                border: 'none', color: '#fff', cursor: pendingCount > 0 ? 'pointer' : 'default',
                opacity: pendingCount > 0 ? 1 : 0.4,
              }}
            >Importar{pendingCount > 1 ? ` (${pendingCount})` : ''}</button>
          </div>
        </div>
      </div>
    </div>
  )
}
