import { useEffect, useState } from 'react'

/**
 * ZoomableImage — abre a imagem (captura) num lightbox ao clicar.
 * Clica no gatilho → overlay fullscreen com a imagem em grande.
 * Clica fora / Esc → fecha. Reutilizável onde a imagem da captura aparece
 * (triagem, Dashboard, Estudo, detalhe da mão) por consistência.
 *
 * Gatilho:
 *  - por defeito = uma MINIATURA <img src> (estilo via thumbStyle).
 *  - se passares `children`, eles são o gatilho clicável (ex.: o nome/ID da
 *    mão como texto), estilizável via triggerStyle. Sem `src`, os children
 *    renderizam tal-e-qual SEM serem clicáveis (mão sem captura).
 *
 * Props: src, alt, thumbStyle (miniatura), children + triggerStyle (texto), onError.
 */
export default function ZoomableImage({ src, alt = '', thumbStyle = {}, onError, children, triggerStyle = {} }) {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', onKey)
    // bloqueia scroll do body enquanto aberto
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [open])

  // Sem captura: como wrapper de texto mostra os children não-clicáveis;
  // como miniatura não renderiza nada (comportamento de sempre).
  if (!src) return children ? children : null

  const trigger = children ? (
    <span
      onClick={() => setOpen(true)}
      title="Clica para ver a captura"
      style={{ cursor: 'zoom-in', ...triggerStyle }}
    >{children}</span>
  ) : (
    <img
      src={src}
      alt={alt}
      onClick={() => setOpen(true)}
      onError={onError}
      title="Clica para ampliar"
      style={{ cursor: 'zoom-in', ...thumbStyle }}
    />
  )

  return (
    <>
      {trigger}
      {open && (
        <div
          onClick={() => setOpen(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            background: 'rgba(0,0,0,0.85)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 24, cursor: 'zoom-out',
          }}
        >
          <img
            src={src}
            alt={alt}
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '96vw', maxHeight: '94vh', objectFit: 'contain',
              borderRadius: 8, boxShadow: '0 8px 40px rgba(0,0,0,0.6)', cursor: 'default' }}
          />
          <button
            onClick={() => setOpen(false)}
            aria-label="Fechar"
            style={{ position: 'fixed', top: 16, right: 20, fontSize: 22, lineHeight: 1,
              width: 40, height: 40, borderRadius: 20, cursor: 'pointer',
              background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.25)',
              color: '#fff' }}
          >×</button>
        </div>
      )}
    </>
  )
}
