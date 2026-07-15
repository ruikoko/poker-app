import { useState } from 'react'
import ZoomImg from './ZoomImg'
import { handImageUrl, entryImageUrl, absImageUrl } from '../api/client'

// FONTE ÚNICA de QUALQUER imagem num painel (lei do lightbox + fim da doença "imagem partida").
// Monta o src pelos helpers centrais → nenhum painel volta a construir `${API_ROOT}/...` à mão.
// Aceita UMA de: `handDbId` (o backend resolve o entry certo — preferido, evita o entry_id
// ambíguo), `entryId` (quando se sabe o entry), ou `url` (URL do backend relativo/absoluto).
// Zoom no clique (ZoomImg). Fallback "sem imagem" em vez de ícone partido.
// Uso: <HandImage handDbId={h.hand_db_id} style={{width:320}} caption="$125 (a rever)" />
export default function HandImage({ handDbId, entryId, url, alt = 'imagem da mão', style, caption }) {
  const [broken, setBroken] = useState(false)
  const src = handDbId != null ? handImageUrl(handDbId)
    : entryId != null ? entryImageUrl(entryId)
    : absImageUrl(url)
  if (!src || broken) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
        minHeight: 90, borderRadius: 7, border: '1px dashed rgba(255,255,255,0.15)',
        color: '#8b9691', fontSize: 11, padding: 8, ...style }}>
        sem imagem
      </div>
    )
  }
  const img = (
    <ZoomImg src={src} alt={alt} onError={() => setBroken(true)}
      style={{ width: 200, maxWidth: '100%', borderRadius: 7, objectFit: 'contain',
        border: '1px solid rgba(255,255,255,0.10)', background: '#000', ...style }} />
  )
  if (!caption) return img
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {img}
      <span style={{ fontSize: 10, color: '#8b9691', textAlign: 'center' }}>{caption} (clica p/ zoom)</span>
    </div>
  )
}
