import { useEffect, useState, useRef } from 'react'

const API = (import.meta.env.VITE_API_URL || '') + '/api/gto'

async function apiFetch(path, opts = {}) {
  const res = await fetch(API + path, { credentials: 'include', ...opts })
  if (res.status === 401) { window.location.href = '/login'; throw new Error('401') }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Erro ${res.status}`)
  }
  if (res.status === 204) return null
  return res.json()
}

const FORMATS = ['PKO', 'KO', 'vanilla', 'mystery']
const PHASES  = ['early', 'middle', 'bubble', 'itm', 'final_table']
const POSITIONS = ['UTG', 'UTG1', 'MP', 'MP1', 'HJ', 'CO', 'BTN', 'SB', 'BB']

function Badge({ label, color = '#444' }) {
  return (
    <span style={{
      background: color, color: '#fff', fontSize: 10, fontWeight: 700,
      padding: '2px 6px', borderRadius: 4, marginRight: 4,
    }}>{label}</span>
  )
}

function TreeRow({ tree, onDelete, onEdit }) {
  const stackRange = tree.hero_stack_bb_min != null
    ? `${tree.hero_stack_bb_min}–${tree.hero_stack_bb_max}bb`
    : '—'

  const coveringLabel = tree.covers_at_least_one && tree.covered_by_at_least_one
    ? 'Mixed'
    : tree.covers_at_least_one
    ? 'Cobre'
    : tree.covered_by_at_least_one
    ? 'Coberto'
    : '—'

  const coverColor = tree.covers_at_least_one && !tree.covered_by_at_least_one
    ? '#2a7'
    : tree.covered_by_at_least_one && !tree.covers_at_least_one
    ? '#c44'
    : '#666'

  return (
    <tr style={{ borderBottom: '1px solid #1e1e1e' }}>
      <td style={{ padding: '8px 12px', fontWeight: 600 }}>{tree.name}</td>
      <td style={{ padding: '8px 12px' }}>
        <Badge label={tree.format || '—'} color={tree.format === 'PKO' ? '#7c4' : tree.format === 'vanilla' ? '#47a' : '#a74'} />
      </td>
      <td style={{ padding: '8px 12px', color: 'var(--muted)' }}>{tree.num_players ? `${tree.num_players}-max` : '—'}</td>
      <td style={{ padding: '8px 12px' }}>
        <Badge label={tree.hero_position || '—'} color='#555' />
      </td>
      <td style={{ padding: '8px 12px', color: 'var(--muted)' }}>{stackRange}</td>
      <td style={{ padding: '8px 12px' }}>
        <Badge label={coveringLabel} color={coverColor} />
      </td>
      <td style={{ padding: '8px 12px', color: 'var(--muted)' }}>{tree.tournament_phase || '—'}</td>
      <td style={{ padding: '8px 12px', color: 'var(--muted)' }}>{tree.node_count?.toLocaleString()}</td>
      <td style={{ padding: '8px 12px', color: 'var(--muted)', fontSize: 11 }}>{tree.uploaded_by || '—'}</td>
      <td style={{ padding: '8px 12px' }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => onEdit(tree)}>✏️</button>
          <button className="btn btn-ghost btn-sm" style={{ color: '#c44' }} onClick={() => onDelete(tree.id)}>🗑</button>
        </div>
      </td>
    </tr>
  )
}

function ImportModal({ onClose, onSuccess }) {
  const [file, setFile] = useState(null)
  const [form, setForm] = useState({
    name: '', format: '', num_players: '', tournament_phase: '',
    hero_position: '', hero_stack_bb_min: '', hero_stack_bb_max: '',
    villain_stack_bb: '', uploaded_by: '', tags: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [preview, setPreview] = useState(null)

  function set(k, v) { setForm(f => ({ ...f, [k]: v })) }

  async function handleFileChange(e) {
    const f = e.target.files[0]
    if (!f) return
    setFile(f)
    // Auto-preencher nome com o nome do ficheiro (sem extensão)
    const stem = f.name.replace(/\.zip$/i, '')
    set('name', stem)
    // Preview rápido: parsear o ZIP no frontend para mostrar metadata
    try {
      const bytes = await f.arrayBuffer()
      // Não temos JSZip aqui — mostrar apenas o nome
      setPreview({ filename: f.name, size: (f.size / 1024).toFixed(0) + ' KB' })
    } catch {}
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!file) { setError('Selecciona um ficheiro ZIP'); return }
    if (!form.name.trim()) { setError('Nome obrigatório'); return }

    setLoading(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      Object.entries(form).forEach(([k, v]) => {
        if (v !== '' && v != null) fd.append(k, v)
      })
      const res = await fetch((import.meta.env.VITE_API_URL || '') + '/api/gto/import', {
        method: 'POST', credentials: 'include', body: fd,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Erro ${res.status}`)
      }
      const data = await res.json()
      onSuccess(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }}>
      <div style={{
        background: '#1a1a1a', border: '1px solid #333', borderRadius: 8,
        padding: 28, width: 560, maxHeight: '90vh', overflowY: 'auto',
      }}>
        <h3 style={{ marginTop: 0, marginBottom: 20 }}>Importar Tree HRC</h3>

        <form onSubmit={handleSubmit}>
          {/* Ficheiro */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 12, color: 'var(--muted)' }}>
              Ficheiro ZIP (HRC Complete Export)
            </label>
            <input type="file" accept=".zip" onChange={handleFileChange}
              style={{ width: '100%', padding: '6px 0', color: 'var(--text)' }} />
            {preview && (
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
                {preview.filename} — {preview.size}
              </div>
            )}
          </div>

          {/* Nome */}
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Nome *</label>
            <input className="input" value={form.name} onChange={e => set('name', e.target.value)}
              placeholder="ex: PKO_6max_UTG_12bb_middle_pushfold" style={{ width: '100%' }} />
          </div>

          {/* Linha: Formato + Nº Jogadores */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Formato</label>
              <select className="input" value={form.format} onChange={e => set('format', e.target.value)} style={{ width: '100%' }}>
                <option value="">Auto-detectado</option>
                {FORMATS.map(f => <option key={f} value={f}>{f}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Nº Jogadores</label>
              <select className="input" value={form.num_players} onChange={e => set('num_players', e.target.value)} style={{ width: '100%' }}>
                <option value="">Auto</option>
                {[2,3,4,5,6,7,8,9].map(n => <option key={n} value={n}>{n}-max</option>)}
              </select>
            </div>
          </div>

          {/* Linha: Posição + Fase */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Posição Hero</label>
              <select className="input" value={form.hero_position} onChange={e => set('hero_position', e.target.value)} style={{ width: '100%' }}>
                <option value="">—</option>
                {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Fase do Torneio</label>
              <select className="input" value={form.tournament_phase} onChange={e => set('tournament_phase', e.target.value)} style={{ width: '100%' }}>
                <option value="">—</option>
                {PHASES.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
          </div>

          {/* Stack range */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 12 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Stack Min (BB)</label>
              <input className="input" type="number" step="0.5" value={form.hero_stack_bb_min}
                onChange={e => set('hero_stack_bb_min', e.target.value)} placeholder="Auto" style={{ width: '100%' }} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Stack Max (BB)</label>
              <input className="input" type="number" step="0.5" value={form.hero_stack_bb_max}
                onChange={e => set('hero_stack_bb_max', e.target.value)} placeholder="Auto" style={{ width: '100%' }} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Stack Vilão (BB)</label>
              <input className="input" type="number" step="0.5" value={form.villain_stack_bb}
                onChange={e => set('villain_stack_bb', e.target.value)} placeholder="—" style={{ width: '100%' }} />
            </div>
          </div>

          {/* Tags + Uploaded by */}
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12, marginBottom: 20 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Tags (JSON: ["pko","push_fold"])</label>
              <input className="input" value={form.tags} onChange={e => set('tags', e.target.value)}
                placeholder='["push_fold","short_stack"]' style={{ width: '100%' }} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Contribuidor</label>
              <input className="input" value={form.uploaded_by} onChange={e => set('uploaded_by', e.target.value)}
                placeholder="Rui" style={{ width: '100%' }} />
            </div>
          </div>

          {error && (
            <div style={{ color: '#f66', fontSize: 12, marginBottom: 12, padding: '8px 12px', background: '#2a1111', borderRadius: 4 }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={loading}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'A importar…' : 'Importar Tree'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function EditModal({ tree, onClose, onSuccess }) {
  const [form, setForm] = useState({
    name: tree.name || '',
    format: tree.format || '',
    num_players: tree.num_players || '',
    tournament_phase: tree.tournament_phase || '',
    hero_position: tree.hero_position || '',
    hero_stack_bb_min: tree.hero_stack_bb_min || '',
    hero_stack_bb_max: tree.hero_stack_bb_max || '',
    villain_stack_bb: tree.villain_stack_bb || '',
    uploaded_by: tree.uploaded_by || '',
    tags: tree.tags ? JSON.stringify(tree.tags) : '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  function set(k, v) { setForm(f => ({ ...f, [k]: v })) }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const body = {}
      Object.entries(form).forEach(([k, v]) => {
        if (v !== '' && v != null) {
          if (k === 'tags') body[k] = JSON.parse(v)
          else if (['num_players'].includes(k)) body[k] = parseInt(v)
          else if (['hero_stack_bb_min','hero_stack_bb_max','villain_stack_bb'].includes(k)) body[k] = parseFloat(v)
          else body[k] = v
        }
      })
      await apiFetch(`/trees/${tree.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      onSuccess()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }}>
      <div style={{
        background: '#1a1a1a', border: '1px solid #333', borderRadius: 8,
        padding: 28, width: 520, maxHeight: '90vh', overflowY: 'auto',
      }}>
        <h3 style={{ marginTop: 0, marginBottom: 20 }}>Editar Tree</h3>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Nome</label>
            <input className="input" value={form.name} onChange={e => set('name', e.target.value)} style={{ width: '100%' }} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Formato</label>
              <select className="input" value={form.format} onChange={e => set('format', e.target.value)} style={{ width: '100%' }}>
                <option value="">—</option>
                {FORMATS.map(f => <option key={f} value={f}>{f}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Nº Jogadores</label>
              <select className="input" value={form.num_players} onChange={e => set('num_players', e.target.value)} style={{ width: '100%' }}>
                <option value="">—</option>
                {[2,3,4,5,6,7,8,9].map(n => <option key={n} value={n}>{n}-max</option>)}
              </select>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Posição Hero</label>
              <select className="input" value={form.hero_position} onChange={e => set('hero_position', e.target.value)} style={{ width: '100%' }}>
                <option value="">—</option>
                {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Fase</label>
              <select className="input" value={form.tournament_phase} onChange={e => set('tournament_phase', e.target.value)} style={{ width: '100%' }}>
                <option value="">—</option>
                {PHASES.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 12 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Stack Min (BB)</label>
              <input className="input" type="number" step="0.5" value={form.hero_stack_bb_min}
                onChange={e => set('hero_stack_bb_min', e.target.value)} style={{ width: '100%' }} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Stack Max (BB)</label>
              <input className="input" type="number" step="0.5" value={form.hero_stack_bb_max}
                onChange={e => set('hero_stack_bb_max', e.target.value)} style={{ width: '100%' }} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Vilão (BB)</label>
              <input className="input" type="number" step="0.5" value={form.villain_stack_bb}
                onChange={e => set('villain_stack_bb', e.target.value)} style={{ width: '100%' }} />
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12, marginBottom: 20 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Tags (JSON)</label>
              <input className="input" value={form.tags} onChange={e => set('tags', e.target.value)} style={{ width: '100%' }} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--muted)' }}>Contribuidor</label>
              <input className="input" value={form.uploaded_by} onChange={e => set('uploaded_by', e.target.value)} style={{ width: '100%' }} />
            </div>
          </div>
          {error && (
            <div style={{ color: '#f66', fontSize: 12, marginBottom: 12, padding: '8px 12px', background: '#2a1111', borderRadius: 4 }}>
              {error}
            </div>
          )}
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={loading}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'A guardar…' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function GTOBrainPage() {
  const [trees, setTrees] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showImport, setShowImport] = useState(false)
  const [editTree, setEditTree] = useState(null)
  const [filters, setFilters] = useState({ format: '', num_players: '', tournament_phase: '', hero_position: '' })
  const [deleteConfirm, setDeleteConfirm] = useState(null)

  async function loadTrees() {
    setLoading(true)
    setError(null)
    try {
      const qs = new URLSearchParams(
        Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ''))
      ).toString()
      const data = await apiFetch(`/trees${qs ? '?' + qs : ''}`)
      setTrees(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadTrees() }, [filters])

  async function handleDelete(id) {
    if (deleteConfirm !== id) { setDeleteConfirm(id); return }
    try {
      await apiFetch(`/trees/${id}`, { method: 'DELETE' })
      setDeleteConfirm(null)
      loadTrees()
    } catch (err) {
      alert(err.message)
    }
  }

  // Stats resumidas
  const totalNodes = trees.reduce((s, t) => s + (t.node_count || 0), 0)
  const byFormat = trees.reduce((acc, t) => {
    acc[t.format || '?'] = (acc[t.format || '?'] || 0) + 1
    return acc
  }, {})

  return (
    <div style={{ padding: '24px 28px', maxWidth: 1200 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20 }}>GTO Brain</h2>
          <p style={{ margin: '4px 0 0', color: 'var(--muted)', fontSize: 13 }}>
            {trees.length} trees · {totalNodes.toLocaleString()} nós
            {Object.entries(byFormat).map(([f, n]) => (
              <span key={f} style={{ marginLeft: 12 }}>
                <Badge label={`${f}: ${n}`} color={f === 'PKO' ? '#7c4' : f === 'vanilla' ? '#47a' : '#a74'} />
              </span>
            ))}
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowImport(true)}>
          + Importar Tree HRC
        </button>
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        <select className="input" value={filters.format} onChange={e => setFilters(f => ({ ...f, format: e.target.value }))}
          style={{ width: 120 }}>
          <option value="">Formato</option>
          {FORMATS.map(f => <option key={f} value={f}>{f}</option>)}
        </select>
        <select className="input" value={filters.num_players} onChange={e => setFilters(f => ({ ...f, num_players: e.target.value }))}
          style={{ width: 110 }}>
          <option value="">Jogadores</option>
          {[2,3,4,5,6,7,8,9].map(n => <option key={n} value={n}>{n}-max</option>)}
        </select>
        <select className="input" value={filters.hero_position} onChange={e => setFilters(f => ({ ...f, hero_position: e.target.value }))}
          style={{ width: 110 }}>
          <option value="">Posição</option>
          {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        <select className="input" value={filters.tournament_phase} onChange={e => setFilters(f => ({ ...f, tournament_phase: e.target.value }))}
          style={{ width: 120 }}>
          <option value="">Fase</option>
          {PHASES.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        {Object.values(filters).some(v => v !== '') && (
          <button className="btn btn-ghost btn-sm" onClick={() => setFilters({ format: '', num_players: '', tournament_phase: '', hero_position: '' })}>
            Limpar
          </button>
        )}
      </div>

      {/* Tabela */}
      {loading ? (
        <div style={{ color: 'var(--muted)', padding: 32 }}>A carregar…</div>
      ) : error ? (
        <div style={{ color: '#f66', padding: 16, background: '#2a1111', borderRadius: 6 }}>{error}</div>
      ) : trees.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: '60px 20px', color: 'var(--muted)',
          border: '2px dashed #333', borderRadius: 8,
        }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>🧠</div>
          <div style={{ fontSize: 15, marginBottom: 8 }}>Nenhuma tree importada ainda</div>
          <div style={{ fontSize: 13, marginBottom: 20 }}>
            Importa um ZIP do HRC Pro (Complete Export, PrettyPrint JSON)
          </div>
          <button className="btn btn-primary" onClick={() => setShowImport(true)}>
            + Importar primeira tree
          </button>
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #333', color: 'var(--muted)', fontSize: 11, textTransform: 'uppercase' }}>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>Nome</th>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>Formato</th>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>Mesa</th>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>Posição</th>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>Stack</th>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>Covering</th>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>Fase</th>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>Nós</th>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>Por</th>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}></th>
              </tr>
            </thead>
            <tbody>
              {trees.map(tree => (
                <TreeRow
                  key={tree.id}
                  tree={tree}
                  onDelete={handleDelete}
                  onEdit={setEditTree}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Confirm delete */}
      {deleteConfirm && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24,
          background: '#2a1111', border: '1px solid #c44', borderRadius: 8,
          padding: '14px 20px', zIndex: 999,
        }}>
          <div style={{ marginBottom: 10, fontSize: 13 }}>Apagar esta tree e todos os seus nós?</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => setDeleteConfirm(null)}>Cancelar</button>
            <button className="btn btn-sm" style={{ background: '#c44', color: '#fff' }}
              onClick={() => handleDelete(deleteConfirm)}>
              Confirmar apagar
            </button>
          </div>
        </div>
      )}

      {/* Modais */}
      {showImport && (
        <ImportModal
          onClose={() => setShowImport(false)}
          onSuccess={(data) => {
            setShowImport(false)
            loadTrees()
          }}
        />
      )}
      {editTree && (
        <EditModal
          tree={editTree}
          onClose={() => setEditTree(null)}
          onSuccess={() => { setEditTree(null); loadTrees() }}
        />
      )}
    </div>
  )
}
