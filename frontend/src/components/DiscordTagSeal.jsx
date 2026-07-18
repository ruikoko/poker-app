import { useState } from 'react'
import { tagDecisions } from '../api/client'

// SELO DA TAG na página da mão — mostra as tags de estudo (discord_tags: pos-pko, nota,
// icm…, as que vêm da PASTA da captura) com um × para TIRAR, e um "+ tag" para PÔR. As duas
// decisões ficam SELADAS (tag_decisions) e sobrevivem a todo o reprocessamento. A mão sem tag
// segue o caminho normal (vai para Torneios). NÃO toca as tags HM3 (essas vivem no TagEditor).

// Sugestões de tags de estudo canónicas (o Rui pode escrever qualquer uma à mão).
const SUGGESTIONS = ['nota', 'pos-pko', 'pos-nko', 'icm', 'icm-pko', 'speed-racer',
  'nota-ft', 'pos-pko-ft', 'pos-nko-ft', 'icm-ft', 'icm-pko-ft', 'speed-racer-ft']

export default function DiscordTagSeal({ hand, onUpdate }) {
  const [busy, setBusy] = useState(null)
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const [adding, setAdding] = useState(false)
  const [newTag, setNewTag] = useState('')
  const tags = hand?.discord_tags || []
  if (!hand?.hand_id) return null

  async function remove(tag) {
    if (!window.confirm(`Tirar a tag "${tag}" desta mão? Fica selado — não volta no reprocessamento.`)) return
    setBusy(tag); setErr(''); setMsg('')
    try {
      await tagDecisions.remove(hand.hand_id, tag)
      onUpdate?.({ discord_tags: tags.filter(t => t !== tag) })   // remoção otimista (LEI 1)
    } catch (e) {
      setErr(e.message || String(e))
    } finally {
      setBusy(null)
    }
  }

  async function add() {
    const tag = newTag.trim()
    if (!tag) return
    if (tags.includes(tag)) { setMsg(`"${tag}" já está nesta mão — nada a fazer.`); return }
    setBusy('+'); setErr(''); setMsg('')
    try {
      const res = await tagDecisions.add(hand.hand_id, tag)
      if (res.already_present) {
        setMsg(`"${tag}" já estava nesta mão — não escrevi em duplicado.`)
      } else {
        onUpdate?.({ discord_tags: [...tags, tag] })              // otimista
        setMsg(`"${tag}" acrescentada e selada.`)
      }
      setNewTag(''); setAdding(false)
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
      {adding ? (
        <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
          <input list="tagseal-suggestions" autoFocus value={newTag}
            onChange={e => setNewTag(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') add(); if (e.key === 'Escape') { setAdding(false); setNewTag('') } }}
            placeholder="tag de estudo…"
            style={{ fontSize: 11, padding: '3px 6px', borderRadius: 4, width: 130,
              background: '#0b0d13', border: '1px solid #2a3550', color: '#e2e8f0', outline: 'none' }} />
          <datalist id="tagseal-suggestions">{SUGGESTIONS.map(s => <option key={s} value={s} />)}</datalist>
          <button onClick={add} disabled={busy === '+' || !newTag.trim()}
            style={{ fontSize: 11, padding: '3px 8px', borderRadius: 4, border: 'none', cursor: 'pointer', background: '#22c55e', color: '#052e16', fontWeight: 700 }}>pôr</button>
          <button onClick={() => { setAdding(false); setNewTag('') }}
            style={{ fontSize: 11, padding: '3px 6px', borderRadius: 4, border: '1px solid #475569', cursor: 'pointer', background: 'transparent', color: '#94a3b8' }}>✕</button>
        </span>
      ) : (
        <button onClick={() => { setAdding(true); setMsg(''); setErr('') }}
          title="Acrescentar uma tag de estudo (fica selada)"
          style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, background: 'transparent',
            border: '1px dashed rgba(34,197,94,0.5)', color: '#4ade80', cursor: 'pointer', fontWeight: 600 }}>
          + tag
        </button>
      )}
      {msg && <span style={{ fontSize: 11, color: '#22c55e' }}>{msg}</span>}
      {err && <span style={{ fontSize: 11, color: '#ef4444' }}>Erro: {err}</span>}
    </div>
  )
}
