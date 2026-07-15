import { useState } from 'react'
import ZoomImg from './ZoomImg'
import { handImageUrl } from '../api/client'

// FONTE ÚNICA da imagem de uma mão (lei do lightbox + fim da doença "imagem partida").
// Recebe `handDbId` e monta o src pelo helper central (`handImageUrl`) → o backend resolve
// o entry certo (o `h.entry_id` aponta muitas vezes ao HH sem imagem). Nenhum painel volta
// a construir `${API_ROOT}/api/screenshots/image/${entry_id}` à mão. Zoom no clique (ZoomImg).
// Uso: <HandImage handDbId={h.hand_db_id} alt="..." style={{width:320}} caption="$125 (a rever)" />
export default function HandImage({ handDbId, alt = 'imagem da mão', style, caption }) {
  const [broken, setBroken] = useState(false)
  const src = handImageUrl(handDbId)
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
