import { useState, useEffect } from 'react'

// LEI UNIVERSAL DE UI (regista como lei da app): qualquer imagem num painel/card abre
// AMPLIADA ao clique (lightbox), fecha com ✕ / Esc / clique-fora. Usa-se em TODO o lado —
// miniatura sem zoom é painel inutilizável (o Rui trabalha com os olhos na imagem).
// Uso: <ZoomImg src={url} alt="..." style={{ width: 320, ... }} onError={...} />
export default function ZoomImg({ src, alt = '', style, ...rest }) {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!open) return
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])
  if (!src) return null
  return (
    <>
      <img src={src} alt={alt} loading="lazy" onClick={() => setOpen(true)}
        style={{ cursor: 'zoom-in', ...style }} {...rest} />
      {open && (
        <div onClick={() => setOpen(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.9)', zIndex: 3000,
            display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'zoom-out', padding: 20 }}>
          <button onClick={() => setOpen(false)} aria-label="Fechar"
            style={{ position: 'absolute', top: 14, right: 20, fontSize: 30, lineHeight: 1, color: '#fff',
              background: 'transparent', border: 'none', cursor: 'pointer' }}>✕</button>
          <img src={src} alt={alt} onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '96vw', maxHeight: '92vh', objectFit: 'contain', borderRadius: 8 }} />
        </div>
      )}
    </>
  )
}
