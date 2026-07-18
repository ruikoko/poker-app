import { useState } from 'react'
import { tagDecisions } from '../api/client'

// SELO DA TAG na página da mão — mostra as tags de estudo (discord_tags: pos-pko, nota,
// icm…, as que vêm da PASTA da captura) com um × para TIRAR. A remoção fica SELADA
// (tag_decisions) e sobrevive a todo o reprocessamento — não volta. A mão sem tag segue o
// caminho normal (vai para Torneios). NÃO toca as tags HM3 (essas vivem no TagEditor).
export default function DiscordTagSeal({ hand, onUpdate }) {
  const [busy, setBusy] = useState(null)
  const [err, setErr] = useState('')
  const tags = hand?.discord_tags || []
  if (!hand?.hand_id) return null

  async function remove(tag) {
    if (!window.confirm(`Tirar a tag "${tag}" desta mão? Fica selado — não volta no reprocessamento.`)) return
    setBusy(tag); setErr('')
    try {
      await tagDecisions.remove(hand.hand_id, tag)
      onUpdate?.({ discord_tags: tags.filter(t => t !== tag) })   // remoção otimista (LEI 1)
    } catch (e) {
      setErr(e.message || String(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
      <span style={{ fontSize: 10, color: '#64748b', fontWeight: 700, letterSpacing: 0.4 }}>TAGS DE ESTUDO</span>
      {tags.length === 0 && <span style={{ fontSize: 11, color: '#64748b', fontStyle: 'italic' }}>sem tags de captura</span>}
      {tags.map(t => (
        <button key={t} onClick={() => remove(t)} disabled={busy === t}
          title="Tirar esta tag (fica selado — não volta)"
          style={{
            fontSize: 11, padding: '3px 8px', borderRadius: 4,
            background: 'rgba(56,189,248,0.14)', border: '1px solid rgba(56,189,248,0.35)',
            color: '#7dd3fc', cursor: 'pointer', fontWeight: 600,
            display: 'inline-flex', alignItems: 'center', gap: 4, opacity: busy === t ? 0.5 : 1,
          }}>
          {t} <span style={{ opacity: 0.6, fontSize: 10 }}>×</span>
        </button>
      ))}
      {err && <span style={{ fontSize: 11, color: '#ef4444' }}>Erro: {err}</span>}
    </div>
  )
}
