import { useCallback, useRef, useState } from 'react'
import { lobbys } from '../api/client'

// Estado por ficheiro nesta sessão de upload (pending → processing → terminal).
// Espelha a UX da janela "SS Mesa", adaptado à semântica do gate de lobby:
//   lobby     = backend confirmou lobby (is_lobby)
//   ignored   = não-lobby genuíno (json_invalid/site_undetected) — ignorado
//   transient = falha transitória da Vision (vision_failed) — volta a tentar
//   error     = erro de transporte / HTTP
const STATUS = {
  pending:    { label: 'em fila',           color: '#64748b' },
  processing: { label: 'a processar…',      color: '#3b82f6' },
  lobby:      { label: 'lobby',             color: '#22c55e' },
  ignored:    { label: 'não-lobby',         color: '#eab308' },
  transient:  { label: 'falha transitória', color: '#f97316' },
  error:      { label: 'erro',              color: '#ef4444' },
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

// Resposta do /api/lobbys/upload → status terminal do ficheiro.
// is_lobby true (inclui dedup) → lobby. Senão, vision_failed é transitório
// (≠ não-lobby genuíno) → retry; o resto é não-lobby ignorado.
function classify(j) {
  if (j?.is_lobby) return 'lobby'
  if (j?.result === 'vision_failed') return 'transient'
  return 'ignored'
}

// captured_at = File.lastModified em hora LOCAL do browser (Lisboa), formatada
// naive (sem offset/Z) — equivalente ao mtime que o appimport usa para lobbys.
// O nome do Windows "Captura de ecrã YYYY-MM-DD HHMMSS" NÃO traz o
// YYYYMMDDHHMMSS que a via table-SS lê do nome; por isso a hora vem do ficheiro.
// NÃO usar toISOString() (converte para UTC com 'Z' → o backend, convenção pt51,
// trataria a wall-clock UTC como Lisboa e deslocava a hora pelo offset).
function lastModifiedToLisbonNaiveISO(ms) {
  const d = new Date(ms)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}` +
         `T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

export default function LobbysPage() {
  const [items, setItems] = useState([])      // uploads desta sessão
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)
  const keyRef = useRef(0)

  const patch = (key, fields) =>
    setItems(prev => prev.map(it => (it.key === key ? { ...it, ...fields } : it)))

  const addFiles = useCallback(async (fileList) => {
    const picked = Array.from(fileList).filter(f => /\.(png|jpe?g)$/i.test(f.name))
    if (!picked.length) return
    const entries = picked.map(f => ({
      key: ++keyRef.current, name: f.name, file: f, status: 'pending', result: null,
    }))
    setItems(prev => [...entries, ...prev])
    // Sequencial — evita martelar a Vision em paralelo. O upload devolve o
    // veredicto final (gate síncrono), por isso o estado nunca fica preso.
    for (const e of entries) {
      patch(e.key, { status: 'processing' })
      try {
        const captured_at = lastModifiedToLisbonNaiveISO(e.file.lastModified)
        const r = await lobbys.upload(e.file, { captured_at })
        patch(e.key, { status: classify(r), result: r })
      } catch (err) {
        patch(e.key, { status: 'error', result: { reason_detail: String(err.message || err) } })
      }
    }
  }, [])

  const onDrop = useCallback((ev) => {
    ev.preventDefault(); setDragging(false)
    if (ev.dataTransfer.files.length) addFiles(ev.dataTransfer.files)
  }, [addFiles])
  const onDragOver = useCallback((ev) => { ev.preventDefault(); setDragging(true) }, [])
  const onDragLeave = useCallback(() => setDragging(false), [])

  return (
    <div style={{ padding: 24, maxWidth: 1180, margin: '0 auto' }}>
      {/* Header */}
      <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 4px' }}>Lobbys</h1>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
        Carrega SSs de <b>lobby de torneio</b> (2ª via, fora do Discord). A Vision lê o
        lobby e, se for mesmo um lobby, entra em <code>tournament_payouts</code> pela mesma
        pipeline do sync. Um print qualquer que não seja lobby é <b>ignorado</b> (nada gravado).
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
        Arrasta SSs de lobby aqui, ou <span style={{ color: 'var(--accent)' }}>clica para escolher</span>
        <div style={{ fontSize: 11, opacity: 0.7, marginTop: 4 }}>.png .jpg — a hora vem do ficheiro (data de modificação)</div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".png,.jpg,.jpeg"
          style={{ display: 'none' }}
          onChange={(e) => { if (e.target.files.length) addFiles(e.target.files); e.target.value = '' }}
        />
      </div>

      {/* Resultado por ficheiro (sessão actual) */}
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
                  {it.status === 'lobby' && (
                    <span style={{ color: 'var(--muted)' }}>
                      {r.site || '—'} · {r.tournament_name || '—'}
                      {r.tournament_number && (
                        <> {' → '}<b style={{ color: 'var(--text)' }}>tn {r.tournament_number}</b></>
                      )}
                      <span style={{ opacity: 0.7 }}> ({r.result}){r.dedup ? ' · dedup' : ''}</span>
                    </span>
                  )}
                  {it.status === 'ignored' && (
                    <span style={{ color: 'var(--muted)', opacity: 0.85 }}>
                      ignorado (não-lobby: {r.result || '—'})
                    </span>
                  )}
                  {it.status === 'transient' && (
                    <span style={{ color: 'var(--muted)', opacity: 0.85 }}>
                      Vision falhou (transitório) — volta a arrastar para tentar de novo
                    </span>
                  )}
                  {it.status === 'error' && (
                    <span style={{ color: 'var(--muted)', opacity: 0.85 }}>
                      {r.reason_detail || r.result || '—'}
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
