import { useState, useRef, useEffect } from 'react'
import { hands as handsApi } from '../api/client'

// ── Lista das 53 tags HM3 com mãos (scan de 18/04/2026) ─────────────────────
// Ordenadas por nº de mãos descendente no topo; se criares tag nova no HM3,
// podes adicionar aqui OU usar o campo livre (qualquer nome funciona).
export const HM3_TAGS = [
  'nota++', 'ICM PKO', 'PKO pos', 'For Review', 'ICM', 'GTw', 'MW PKO',
  'PKO SS', 'Timetell', 'SQZ PKO', 'MW', 'bvb pos', 'nota', 'nando',
  '3b pos flop mono', 'Turn cbet IP', 'nota ex', 'RFI PKO-', 'Turn Cbet IP',
  'perceived range river forte', 'Stats', 'cc/3b IP PKO +', 'MW OP',
  'Bvb pos', 'RFI FT', 'SB vs Steal PKO', 'SQZ', 'bvB PKO PRE', 'bvB pre',
  'cc/3b IP PKO-', 'chat', 'spots do pisso river q devia r',
  'PKO pos 3bet', 'cbet OP', 'cbet OP PKO+', 'prbe PKO', 'stats',
  'BB SS vs CBET PKO', 'CC vs SQZ PKO', 'IP vs 3bet PKO',
  'IP vs mcbet Flop PKO', 'MW IP', 'OP vs 3bet', 'OP vs 3bet PKO',
  'OP vs cbet Flop PKO -', 'RFI PKO LS', 'RFI PKO+', 'SB SS vs open',
  'analise field', 'bet vs mcbet', 'bvB PKO pos', 'probe MW',
  'vs Turn cbet OP', 'GG Hands',
]

/**
 * Editor de tags HM3 para uma mão.
 *
 * Props:
 *   hand: objecto mão (tem id e hm3_tags)
 *   onUpdate: callback chamado depois de gravar ({hm3_tags})
 *   variant: 'full' (dropdown + tags visíveis) | 'inline' (só botão +)
 */
export default function TagEditor({ hand, onUpdate, variant = 'full' }) {
  const [open, setOpen] = useState(false)
  const [filter, setFilter] = useState('')
  const [saving, setSaving] = useState(false)
  const popoverRef = useRef(null)
  const buttonRef = useRef(null)

  const currentTags = hand?.hm3_tags || []

  // Fechar ao clicar fora
  useEffect(() => {
    if (!open) return
    function handler(e) {
      if (popoverRef.current && !popoverRef.current.contains(e.target) &&
          buttonRef.current && !buttonRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  async function applyChange(newTags) {
    setSaving(true)
    try {
      // Regra: se adicionaste uma tag manual que não seja "GG Hands",
      // e a mão ainda tem "GG Hands", remover "GG Hands" automaticamente.
      const hasManualHM3 = newTags.some(t => t !== 'GG Hands')
      const finalTags = hasManualHM3
        ? newTags.filter(t => t !== 'GG Hands')
        : newTags

      await handsApi.update(hand.id, { hm3_tags: finalTags })
      onUpdate?.({ hm3_tags: finalTags })
    } catch (e) {
      console.error('TagEditor save error:', e)
      alert('Erro ao gravar tag: ' + (e.message || e))
    } finally {
      setSaving(false)
    }
  }

  function toggleTag(tag) {
    const next = currentTags.includes(tag)
      ? currentTags.filter(t => t !== tag)
      : [...currentTags, tag]
    applyChange(next)
  }

  function addCustom(text) {
    const clean = text.trim()
    if (!clean || currentTags.includes(clean)) return
    applyChange([...currentTags, clean])
    setFilter('')
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && filter.trim()) {
      e.preventDefault()
      addCustom(filter)
    }
  }

  const filteredOptions = filter
    ? HM3_TAGS.filter(t => t.toLowerCase().includes(filter.toLowerCase()))
    : HM3_TAGS

  // ── VARIANT: INLINE ──────────────────────────────────────────────────────
  // Um só botão "+" sem mostrar as tags. Útil para a lista.
  if (variant === 'inline') {
    return (
      <div style={{ position: 'relative', display: 'inline-block' }} onClick={e => e.stopPropagation()}>
        <button
          ref={buttonRef}
          onClick={e => { e.stopPropagation(); setOpen(o => !o) }}
          title="Editar tags"
          style={{
            fontSize: 10, padding: '2px 6px', borderRadius: 3,
            background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.25)',
            color: '#818cf8', cursor: 'pointer', fontWeight: 600,
          }}
        >
          {currentTags.length > 0 ? `🏷️ ${currentTags.length}` : '🏷️ +'}
        </button>
        {open && renderPopover(popoverRef, currentTags, filter, setFilter, filteredOptions, toggleTag, handleKeyDown, saving)}
      </div>
    )
  }

  // ── VARIANT: FULL ────────────────────────────────────────────────────────
  return (
    <div style={{ position: 'relative' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
        {currentTags.length === 0 && (
          <span style={{ fontSize: 11, color: '#64748b', fontStyle: 'italic' }}>sem tags</span>
        )}
        {currentTags.map(t => (
          <button
            key={t}
            onClick={() => toggleTag(t)}
            disabled={saving}
            title="Clique para remover"
            style={{
              fontSize: 11, padding: '3px 8px', borderRadius: 4,
              background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)',
              color: '#a5b4fc', cursor: 'pointer', fontWeight: 600,
              display: 'inline-flex', alignItems: 'center', gap: 4,
            }}
          >
            {t} <span style={{ opacity: 0.5, fontSize: 10 }}>×</span>
          </button>
        ))}
        <button
          ref={buttonRef}
          onClick={() => setOpen(o => !o)}
          style={{
            fontSize: 11, padding: '3px 10px', borderRadius: 4,
            background: 'transparent', border: '1px dashed rgba(129,140,248,0.4)',
            color: '#818cf8', cursor: 'pointer', fontWeight: 600,
          }}
        >
          + tag
        </button>
      </div>
      {open && renderPopover(popoverRef, currentTags, filter, setFilter, filteredOptions, toggleTag, handleKeyDown, saving)}
    </div>
  )
}

// ── Popover reutilizado entre variants ──────────────────────────────────────
function renderPopover(ref, currentTags, filter, setFilter, filteredOptions, toggleTag, handleKeyDown, saving) {
  return (
    <div
      ref={ref}
      style={{
        position: 'absolute', top: 'calc(100% + 4px)', left: 0, zIndex: 9999,
        width: 280, maxHeight: 380, display: 'flex', flexDirection: 'column',
        background: '#0f172a', border: '1px solid rgba(255,255,255,0.12)',
        borderRadius: 6, boxShadow: '0 12px 32px rgba(0,0,0,0.6)',
      }}
    >
      <div style={{ padding: 8, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <input
          autoFocus
          type="text"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Procurar ou escrever tag nova..."
          style={{
            width: '100%', boxSizing: 'border-box',
            fontSize: 12, padding: '6px 8px', borderRadius: 4,
            background: '#1e293b', border: '1px solid rgba(255,255,255,0.08)',
            color: '#e2e8f0', outline: 'none',
          }}
        />
        {filter.trim() && !filteredOptions.some(o => o.toLowerCase() === filter.trim().toLowerCase()) && (
          <div style={{ fontSize: 10, color: '#818cf8', marginTop: 4 }}>
            Enter para adicionar "<b>{filter.trim()}</b>" como tag nova
          </div>
        )}
      </div>
      <div style={{ overflowY: 'auto', flex: 1 }}>
        {filteredOptions.length === 0 && (
          <div style={{ padding: 12, fontSize: 11, color: '#64748b', textAlign: 'center' }}>
            Sem resultados. Enter para criar.
          </div>
        )}
        {filteredOptions.map(tag => {
          const active = currentTags.includes(tag)
          return (
            <button
              key={tag}
              onClick={() => toggleTag(tag)}
              disabled={saving}
              style={{
                width: '100%', textAlign: 'left',
                padding: '6px 10px', fontSize: 12,
                background: active ? 'rgba(99,102,241,0.15)' : 'transparent',
                border: 'none', borderBottom: '1px solid rgba(255,255,255,0.03)',
                color: active ? '#a5b4fc' : '#cbd5e1',
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
                fontWeight: active ? 600 : 400,
              }}
              onMouseEnter={e => e.currentTarget.style.background = active ? 'rgba(99,102,241,0.22)' : 'rgba(255,255,255,0.04)'}
              onMouseLeave={e => e.currentTarget.style.background = active ? 'rgba(99,102,241,0.15)' : 'transparent'}
            >
              <span style={{ width: 12, display: 'inline-flex', justifyContent: 'center' }}>{active ? '✓' : ''}</span>
              <span>{tag}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
