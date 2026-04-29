import { useEffect, useState, useCallback } from 'react'
import { images as imagesApi } from '../api/client'

/**
 * Popup galeria de imagens (~600px largura).
 *
 * Tech Debt #B9 fix: anexação manual em vez de match temporal automático.
 * Utilizador escolhe explicitamente que imagem anexa a que mão.
 *
 * Props:
 *   - onClose():       fecha popup sem anexar
 *   - onPick(entryId): callback quando user click "Anexar" numa imagem
 *   - alreadyAttached: lista de entry_ids já anexadas a esta mão (filtra)
 *
 * UI:
 *   - Header: título + filtros (canal dropdown, data input)
 *   - Grid 3 colunas de thumbnails
 *   - Click thumbnail → preview maior dentro do popup
 *   - Botão "Anexar" quando preview seleccionado
 *   - Filtro "esconder já anexadas" (default ON)
 */

const DISCORD_COLOR = '#5865F2'

export default function ImageGalleryPopup({ onClose, onPick, alreadyAttached = [] }) {
  const [items, setItems] = useState([])
  const [channels, setChannels] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [filterChannel, setFilterChannel] = useState('')
  const [filterDate, setFilterDate] = useState('')
  const [hideAttached, setHideAttached] = useState(true)
  const [selected, setSelected] = useState(null)

  const loadGallery = useCallback(() => {
    setLoading(true)
    setError('')
    const params = { page_size: 200 }
    if (filterChannel) params.channel = filterChannel
    if (filterDate) params.date = filterDate
    imagesApi.gallery(params)
      .then(r => setItems(r.items || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [filterChannel, filterDate])

  useEffect(() => {
    imagesApi.channels().then(r => setChannels(r.channels || [])).catch(() => {})
  }, [])

  useEffect(() => {
    loadGallery()
  }, [loadGallery])

  const attachedSet = new Set(alreadyAttached)
  const visibleItems = hideAttached
    ? items.filter(it => !attachedSet.has(it.entry_id))
    : items

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1500, backdropFilter: 'blur(4px)',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: '92%', maxWidth: 600, maxHeight: '85vh',
          background: '#1a1d27', border: '1px solid #2a2d3a',
          borderRadius: 10, display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{ padding: '14px 18px', borderBottom: '1px solid #2a2d3a', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9' }}>
            Galeria de imagens Discord
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 18, padding: 4 }}
          >&#10005;</button>
        </div>

        {/* Filtros */}
        <div style={{ padding: '10px 18px', borderBottom: '1px solid #2a2d3a', display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <select
            value={filterChannel}
            onChange={e => setFilterChannel(e.target.value)}
            style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '5px 10px', fontSize: 12 }}
          >
            <option value="">Todos os canais</option>
            {channels.map(c => (
              <option key={c.channel_id} value={c.channel_name}>
                #{c.channel_name} ({c.n_images})
              </option>
            ))}
          </select>
          <input
            type="date"
            value={filterDate}
            onChange={e => setFilterDate(e.target.value)}
            style={{ background: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 6, color: '#e2e8f0', padding: '4px 8px', fontSize: 12 }}
          />
          {filterDate && (
            <button
              onClick={() => setFilterDate('')}
              style={{ padding: '4px 10px', borderRadius: 6, fontSize: 11, background: 'transparent', color: '#64748b', border: '1px solid #2a2d3a', cursor: 'pointer' }}
            >limpar</button>
          )}
          <label style={{ fontSize: 11, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={hideAttached}
              onChange={e => setHideAttached(e.target.checked)}
            />
            Esconder anexadas
          </label>
        </div>

        {/* Conteúdo */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '12px 18px' }}>
          {loading && (
            <div style={{ textAlign: 'center', padding: '32px 0', color: '#64748b' }}>A carregar...</div>
          )}
          {error && (
            <div style={{ color: '#ef4444', fontSize: 12, padding: '8px 12px', background: 'rgba(239,68,68,0.08)', borderRadius: 6, marginBottom: 8 }}>{error}</div>
          )}

          {!loading && visibleItems.length === 0 && (
            <div style={{ textAlign: 'center', padding: '32px 0', color: '#64748b', fontSize: 13 }}>
              Sem imagens nesta filtragem.
            </div>
          )}

          {!loading && selected && (
            <div style={{ marginBottom: 14, padding: 12, background: '#0f1117', borderRadius: 8, border: '1px solid #2a2d3a' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#f1f5f9', marginBottom: 4 }}>
                    Pré-visualização
                  </div>
                  <div style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>
                    {selected.channel_name && <span style={{ color: DISCORD_COLOR, marginRight: 8 }}>#{selected.channel_name}</span>}
                    {selected.posted_at && new Date(selected.posted_at).toLocaleString('pt-PT')}
                  </div>
                </div>
                <button
                  onClick={() => onPick(selected.entry_id)}
                  style={{ padding: '7px 16px', borderRadius: 6, fontSize: 13, fontWeight: 600, background: '#22c55e', color: '#fff', border: 'none', cursor: 'pointer' }}
                >Anexar</button>
              </div>
              <a href={selected.image_url} target="_blank" rel="noopener noreferrer">
                <img
                  src={imagesApi.rawUrl(selected.entry_id)}
                  alt="preview"
                  style={{ maxWidth: '100%', maxHeight: 300, borderRadius: 6, border: '1px solid rgba(255,255,255,0.08)', display: 'block', margin: '0 auto' }}
                />
              </a>
            </div>
          )}

          {!loading && visibleItems.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              {visibleItems.map(it => {
                const isSelected = selected?.entry_id === it.entry_id
                const isAttached = attachedSet.has(it.entry_id)
                return (
                  <div
                    key={it.entry_id}
                    onClick={() => setSelected(it)}
                    style={{
                      position: 'relative', cursor: 'pointer',
                      borderRadius: 6, overflow: 'hidden',
                      border: isSelected
                        ? '2px solid #818cf8'
                        : '1px solid rgba(255,255,255,0.08)',
                      background: '#0f1117',
                      opacity: isAttached ? 0.4 : 1,
                    }}
                  >
                    <img
                      src={imagesApi.rawUrl(it.entry_id)}
                      alt=""
                      style={{ width: '100%', height: 100, objectFit: 'cover', display: 'block' }}
                      onError={e => { e.target.style.display = 'none' }}
                    />
                    <div style={{ padding: '4px 6px', fontSize: 10, color: '#64748b', fontFamily: 'monospace', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                      {it.channel_name && <span style={{ color: DISCORD_COLOR }}>#{it.channel_name}</span>}
                      {isAttached && <span style={{ marginLeft: 4, color: '#22c55e' }}>✓</span>}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '10px 18px', borderTop: '1px solid #2a2d3a', fontSize: 11, color: '#64748b', display: 'flex', justifyContent: 'space-between' }}>
          <span>{visibleItems.length} {visibleItems.length === 1 ? 'imagem' : 'imagens'}</span>
          <span>Click thumbnail → pré-visualizar → "Anexar"</span>
        </div>
      </div>
    </div>
  )
}
