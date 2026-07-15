import { useState, useEffect, useCallback } from 'react'

// COMPONENTE-BASE ÚNICO de worklist (LEI 3, CLAUDE.md "LEIS DE ENTREGA"). O FILTRO AO-VIVO
// está EMBUTIDO aqui — nenhuma lista de resolução se constrói à mão:
//   • resolvido SAI DA LISTA NA HORA (remoção otimista via o `resolve()` que o card recebe);
//   • a lista RE-CONFERE a BD ao vivo — re-`load()` após cada resolução E no `focus` do
//     separador (correção por OUTRA via também sai). Um caso resolvido NUNCA reaparece.
// Assim como HandImage/ZoomImg são a fonte única das imagens, isto é a fonte única das listas.
//
// Uso:
//   <Worklist title="…" subtitle={<p>…</p>} emptyText="…"
//     load={() => api.getCases().then(r => r.cases)}   // -> array de items
//     keyOf={(item) => `${item.hand_id}|${item.player}`}
//     renderCard={(item, { resolve }) => <MeuCard item={item} onResolved={resolve} />} />
export default function Worklist({
  load, keyOf, renderCard, title, subtitle, emptyText = 'Nada a rever.',
  countLabel = 'casos', headerRight = null,
}) {
  const [items, setItems] = useState(null)
  const [loading, setLoading] = useState(false)
  const [resolved, setResolved] = useState(() => new Set())
  const reload = useCallback(() => {
    setLoading(true)
    Promise.resolve(load())
      .then(list => { setItems(Array.isArray(list) ? list : []); setResolved(new Set()) })
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [load])
  useEffect(() => { reload() }, [reload])
  // RE-CONFERE a BD ao voltar ao separador (correções por outra via saem sem Recarregar).
  useEffect(() => {
    const onFocus = () => reload()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [reload])
  // resolvido no card → sai NA HORA (otimista) + re-confere a BD a seguir.
  const resolve = (key) => { setResolved(s => new Set(s).add(key)); setTimeout(reload, 500) }
  const visible = (items || []).filter(it => !resolved.has(keyOf(it)))
  return (
    <div style={{ marginTop: 22 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6, flexWrap: 'wrap' }}>
        {title && <h2 style={{ fontSize: 16, fontWeight: 800, margin: 0, color: '#e8ece9' }}>{title}</h2>}
        <span style={{ color: '#8b9691', fontSize: 12 }}>{loading ? 'a carregar…' : `${visible.length} ${countLabel}`}</span>
        <button onClick={reload} disabled={loading} style={{ background: 'transparent', color: '#e8ece9',
          border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, padding: '3px 10px',
          cursor: loading ? 'default' : 'pointer', fontSize: 12 }}>Recarregar</button>
        {headerRight}
      </div>
      {subtitle}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {visible.map(it => (
          <div key={keyOf(it)}>{renderCard(it, { resolve: () => resolve(keyOf(it)) })}</div>
        ))}
        {!loading && visible.length === 0 && (
          <div style={{ color: '#8b9691', fontSize: 13 }}>{emptyText}</div>
        )}
      </div>
    </div>
  )
}
