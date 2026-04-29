import { useState } from 'react'
import { images as imagesApi } from '../api/client'
import ImageGalleryPopup from './ImageGalleryPopup'

/**
 * Secção "IMAGENS ANEXADAS (N)" + botão "+ Adicionar imagem" + popup galeria.
 *
 * Componente partilhado entre:
 *   - pages/HandDetailPage.jsx (rota /hand/:id)
 *   - pages/Hands.jsx HandDetailModal (modal Estudo → Por Torneio)
 *
 * Tech Debt #B9 fix: anexação manual em vez de match temporal automático.
 *
 * Props:
 *   - hand:     objecto hand com `id`, `attachments?: [{id, image_url, ...}]`
 *   - onChange: callback chamado após attach/detach com sucesso. Caller
 *               deve refetch hand para actualizar `hand.attachments`.
 *   - dense:    bool — versão compacta (thumbnail 120px em vez de 200px,
 *               padding menor). Default false.
 */
export default function AttachedImagesSection({ hand, onChange, dense = false }) {
  const [galleryOpen, setGalleryOpen] = useState(false)
  const [error, setError] = useState('')
  const handDbId = hand?.id

  const attachments = hand?.attachments || []
  const alreadyAttached = attachments.map(a => a.entry_id).filter(Boolean)
  const thumbWidth = dense ? 120 : 200
  const sectionPadding = dense ? '12px 14px' : '16px 20px'
  const sectionMargin = dense ? 10 : 14

  const handleAttach = async (entryId) => {
    try {
      await imagesApi.attach(handDbId, entryId)
      setGalleryOpen(false)
      setError('')
      onChange?.()
    } catch (e) {
      setError(`Anexar falhou: ${e.message}`)
    }
  }

  const handleDetach = async (haId) => {
    if (!confirm('Remover esta imagem da mão?')) return
    try {
      await imagesApi.detach(handDbId, haId)
      setError('')
      onChange?.()
    } catch (e) {
      setError(`Remover falhou: ${e.message}`)
    }
  }

  return (
    <>
      <div style={{ background: '#0f1117', borderRadius: 8, padding: sectionPadding, marginBottom: sectionMargin }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ fontSize: dense ? 12 : 13, color: '#94a3b8', fontWeight: 700 }}>
            IMAGENS ANEXADAS ({attachments.length})
          </div>
          <button
            onClick={() => setGalleryOpen(true)}
            style={{ padding: dense ? '5px 12px' : '6px 14px', borderRadius: 6, fontSize: dense ? 11 : 12, fontWeight: 600, background: 'rgba(99,102,241,0.15)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.3)', cursor: 'pointer' }}
          >
            + Adicionar imagem
          </button>
        </div>

        {error && (
          <div style={{ fontSize: 11, color: '#ef4444', marginBottom: 8, padding: '6px 10px', background: 'rgba(239,68,68,0.08)', borderRadius: 5, border: '1px solid rgba(239,68,68,0.2)' }}>{error}</div>
        )}

        {attachments.length > 0 ? (
          <div style={{ display: 'flex', gap: dense ? 10 : 14, flexWrap: 'wrap', alignItems: 'flex-start' }}>
            {attachments.map(att => {
              const src = att.entry_id
                ? imagesApi.rawUrl(att.entry_id)
                : (att.img_b64 ? `data:${att.mime_type || 'image/png'};base64,${att.img_b64}` : att.image_url)
              const dt = att.posted_at ? new Date(att.posted_at) : null
              const timeStr = dt
                ? `${String(dt.getHours()).padStart(2, '0')}:${String(dt.getMinutes()).padStart(2, '0')}`
                : ''
              const channelLabel = att.channel_name || ''
              const methodLabel = att.match_method === 'manual' ? 'manual' : (att.match_method || '')
              const metaLine = [timeStr, channelLabel, methodLabel].filter(Boolean).join(' · ')
              return (
                <div key={att.id} style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <button
                    onClick={() => handleDetach(att.id)}
                    title="Remover anexação"
                    style={{ position: 'absolute', top: 4, right: 4, width: 22, height: 22, borderRadius: '50%', background: 'rgba(0,0,0,0.7)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.5)', cursor: 'pointer', fontSize: 13, fontWeight: 700, zIndex: 2, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  >×</button>
                  <a
                    href={att.image_url || src}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Abrir imagem em nova aba"
                    style={{ cursor: 'zoom-in', display: 'inline-block' }}
                  >
                    <img
                      src={src}
                      alt={metaLine || 'anexo'}
                      style={{
                        width: thumbWidth, height: 'auto', display: 'block',
                        borderRadius: 6, border: '1px solid rgba(255,255,255,0.08)',
                      }}
                    />
                  </a>
                  <div style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace', maxWidth: thumbWidth }}>
                    {metaLine}
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div style={{ fontSize: 12, color: '#64748b', fontStyle: 'italic' }}>
            Sem imagens anexadas. Click "+ Adicionar imagem" para escolher da galeria.
          </div>
        )}
      </div>

      {galleryOpen && (
        <ImageGalleryPopup
          onClose={() => setGalleryOpen(false)}
          onPick={handleAttach}
          alreadyAttached={alreadyAttached}
        />
      )}
    </>
  )
}
