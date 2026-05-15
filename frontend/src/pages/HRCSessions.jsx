import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { hrc } from '../api/client'

export default function HRCSessionsPage() {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadInfo, setUploadInfo] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(null)  // {id, name} ou null
  const [deleting, setDeleting] = useState(false)
  const inputRef = useRef(null)

  async function refresh() {
    setLoading(true)
    setError(null)
    try {
      const rows = await hrc.sessions()
      setSessions(rows)
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  async function handleFiles(files) {
    if (!files || !files.length) return
    const file = files[0]
    if (!file.name.toLowerCase().endsWith('.zip')) {
      setError('Apenas zips são aceites.')
      return
    }
    setUploading(true)
    setError(null)
    setUploadInfo(null)
    const t0 = performance.now()
    try {
      const out = await hrc.upload(file, { source: 'manual' })
      const dt = ((performance.now() - t0) / 1000).toFixed(1)
      setUploadInfo({
        session_id: out.session_id,
        total_nodes: out.total_nodes,
        seconds: dt,
        filename: file.name,
      })
      await refresh()
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setUploading(false)
    }
  }

  async function handleDelete() {
    if (!confirmDelete) return
    setDeleting(true)
    setError(null)
    try {
      await hrc.delete(confirmDelete.id)
      setSessions((prev) => prev.filter((s) => s.id !== confirmDelete.id))
      setConfirmDelete(null)
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div className="page-title">HRC Sessions</div>
        <div className="page-subtitle">
          Importa um zip Complete Export do HRC e explora as estratégias.
        </div>
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          handleFiles(e.dataTransfer.files)
        }}
        onClick={() => inputRef.current?.click()}
        style={{
          border: `2px dashed ${dragOver ? 'var(--accent)' : 'var(--border)'}`,
          background: dragOver ? 'rgba(99,102,241,0.08)' : 'var(--surface)',
          borderRadius: 'var(--radius)',
          padding: 32,
          textAlign: 'center',
          cursor: uploading ? 'wait' : 'pointer',
          marginBottom: 24,
          opacity: uploading ? 0.7 : 1,
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".zip,application/zip"
          style={{ display: 'none' }}
          onChange={(e) => handleFiles(e.target.files)}
          disabled={uploading}
        />
        {uploading ? (
          <div style={{ color: 'var(--muted)' }}>A enviar e a processar — isto pode demorar até ~60s para zips grandes…</div>
        ) : (
          <>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
              Arrastar zip Complete Export para aqui
            </div>
            <div style={{ color: 'var(--muted)', fontSize: 13 }}>
              ou clica para escolher um ficheiro
            </div>
          </>
        )}
      </div>

      {error && (
        <div style={{
          background: 'rgba(239,68,68,0.1)',
          border: '1px solid var(--red)',
          color: '#fca5a5',
          padding: '12px 16px',
          borderRadius: 'var(--radius)',
          marginBottom: 16,
          fontSize: 13,
        }}>
          {error}
        </div>
      )}

      {uploadInfo && (
        <div style={{
          background: 'rgba(34,197,94,0.08)',
          border: '1px solid var(--green)',
          color: '#86efac',
          padding: '12px 16px',
          borderRadius: 'var(--radius)',
          marginBottom: 16,
          fontSize: 13,
        }}>
          Sessão <strong>#{uploadInfo.session_id}</strong> ({uploadInfo.filename}):{' '}
          {uploadInfo.total_nodes.toLocaleString()} nodes em {uploadInfo.seconds}s.{' '}
          <Link to={`/hrc-sessions/${uploadInfo.session_id}`} style={{ color: 'var(--accent2)' }}>
            Abrir →
          </Link>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid var(--border)' }}>
              <th style={th}>#</th>
              <th style={th}>Nome</th>
              <th style={{ ...th, textAlign: 'right' }}>Nodes</th>
              <th style={th}>Source</th>
              <th style={th}>Importado</th>
              <th style={th}>Hand</th>
              <th style={{ ...th, width: 160 }}>Acções</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={7} style={{ padding: 24, color: 'var(--muted)', textAlign: 'center' }}>A carregar…</td></tr>
            )}
            {!loading && sessions.length === 0 && (
              <tr><td colSpan={7} style={{ padding: 24, color: 'var(--muted)', textAlign: 'center' }}>
                Sem sessões importadas. Arrasta um zip acima.
              </td></tr>
            )}
            {sessions.map((s) => (
              <tr key={s.id} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={td}>{s.id}</td>
                <td style={{ ...td, fontWeight: 600 }}>{s.name}</td>
                <td style={{ ...td, textAlign: 'right', fontFamily: "'Fira Code', monospace" }}>
                  {Number(s.total_nodes).toLocaleString()}
                </td>
                <td style={td}>
                  <span style={{
                    fontSize: 11, padding: '2px 6px',
                    background: s.source === 'watcher' ? 'rgba(99,102,241,0.2)' : 'rgba(100,116,139,0.2)',
                    color: s.source === 'watcher' ? '#a5b4fc' : '#cbd5e1',
                    borderRadius: 3,
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                  }}>{s.source}</span>
                </td>
                <td style={{ ...td, color: 'var(--muted)' }}>
                  {new Date(s.uploaded_at).toLocaleString('pt-PT', {
                    year: 'numeric', month: '2-digit', day: '2-digit',
                    hour: '2-digit', minute: '2-digit',
                  })}
                </td>
                <td style={{ ...td, color: 'var(--muted)' }}>
                  {s.related_hand_id ?? '—'}
                </td>
                <td style={td}>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <Link to={`/hrc-sessions/${s.id}`} className="btn btn-ghost btn-sm">Abrir</Link>
                    <button
                      className="btn btn-ghost btn-sm"
                      style={{ color: '#f87171' }}
                      onClick={() => setConfirmDelete({ id: s.id, name: s.name })}
                      title="Apagar sessão"
                    >Apagar</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {confirmDelete && (
        <div
          onClick={() => !deleting && setConfirmDelete(null)}
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(0,0,0,0.6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              padding: 24,
              maxWidth: 460,
              width: '90%',
            }}
          >
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
              Apagar sessão {confirmDelete.name}?
            </div>
            <div style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 20 }}>
              Esta acção não pode ser desfeita. Todos os nodes da sessão também são apagados.
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setConfirmDelete(null)}
                disabled={deleting}
              >Cancelar</button>
              <button
                className="btn btn-sm"
                onClick={handleDelete}
                disabled={deleting}
                style={{
                  background: 'var(--red)',
                  color: '#fff',
                  border: 'none',
                  padding: '6px 14px',
                  borderRadius: 'var(--radius)',
                  cursor: deleting ? 'wait' : 'pointer',
                  opacity: deleting ? 0.6 : 1,
                }}
              >{deleting ? 'A apagar…' : 'Apagar'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const th = { padding: '10px 12px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5 }
const td = { padding: '10px 12px', fontSize: 13 }
