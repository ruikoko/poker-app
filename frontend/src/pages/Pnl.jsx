import { useEffect, useState, useCallback } from 'react'
import { tournaments, imports } from '../api/client'

const SITES  = ['Winamax', 'GGPoker', 'PokerStars', 'WPN']
const TYPES  = [{ v: '', l: 'Tipo' }, { v: 'ko', l: 'KO' }, { v: 'nonko', l: 'Non-KO' }]
const SPEEDS = [{ v: '', l: 'Speed' }, { v: 'normal', l: 'Normal' }, { v: 'turbo', l: 'Turbo' }, { v: 'hyper', l: 'Hyper' }]
const RESULT = [{ v: '', l: 'Resultado' }, { v: 'cashed', l: 'Cashed' }, { v: 'no_cash', l: 'Bust' }]

function Badge({ type, speed }) {
  return (
    <span style={{ display: 'inline-flex', gap: 4 }}>
      <span className={`badge badge-${type}`}>{type}</span>
      {speed !== 'normal' && <span className={`badge badge-${speed}`}>{speed}</span>}
    </span>
  )
}

export default function PnlPage() {
  const [filters, setFilters] = useState({ site: '', type: '', speed: '', result: '', page: 1 })
  const [data, setData]       = useState({ data: [], total: 0, pages: 1 })
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  // Import state
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    tournaments.list({ ...filters, page_size: 50 })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [filters])

  useEffect(() => { load() }, [load])

  function set(key, val) {
    setFilters(f => ({ ...f, [key]: val, page: key !== 'page' ? 1 : f.page }))
  }

  async function handleImport(e) {
    const file = e.target.files[0]
    if (!file) return
    setImporting(true)
    setImportResult(null)
    try {
      const res = await imports.upload(file)
      setImportResult(res)
      if (res.inserted > 0) load()
    } catch (err) {
      setImportResult({ error: err.message })
    } finally {
      setImporting(false)
      e.target.value = ''
    }
  }

  const rows = data.data || []

  return (
    <>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <div>
            <div className="page-title">P&L</div>
            <div className="page-subtitle">{data.total} torneios</div>
          </div>
          <label className="btn btn-primary btn-sm" style={{ cursor: 'pointer' }}>
            {importing ? 'A importar…' : '↑ Importar'}
            <input type="file" accept=".txt,.zip" onChange={handleImport} style={{ display: 'none' }} />
          </label>
        </div>
      </div>

      {importResult && (
        <div className="card" style={{ marginBottom: 16, fontSize: 13 }}>
          {importResult.error
            ? <span className="red">{importResult.error}</span>
            : <>
                <strong>{importResult.site}</strong> — {importResult.filename}
                {' · '}encontrados: <strong>{importResult.records_found}</strong>
                {' · '}inseridos: <strong className="green">{importResult.inserted}</strong>
                {' · '}duplicados: <strong className="muted">{importResult.skipped}</strong>
                {importResult.errors > 0 && <> · erros: <strong className="red">{importResult.errors}</strong></>}
              </>
          }
        </div>
      )}

      <div className="filters">
        <select value={filters.site} onChange={e => set('site', e.target.value)}>
          <option value="">Todas as salas</option>
          {SITES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filters.type} onChange={e => set('type', e.target.value)}>
          {TYPES.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
        </select>
        <select value={filters.speed} onChange={e => set('speed', e.target.value)}>
          {SPEEDS.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
        </select>
        <select value={filters.result} onChange={e => set('result', e.target.value)}>
          {RESULT.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
        </select>
        <button className="btn btn-ghost btn-sm" onClick={() => setFilters({ site: '', type: '', speed: '', result: '', page: 1 })}>
          Limpar
        </button>
      </div>

      {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Data</th>
                <th>Sala</th>
                <th>Torneio</th>
                <th>Tipo</th>
                <th>Buy-in</th>
                <th>Cashout</th>
                <th>Pos.</th>
                <th>Resultado</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>A carregar…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={8}><div className="empty-state">Sem resultados.</div></td></tr>
              )}
              {!loading && rows.map(t => {
                const res = Number(t.result)
                const cur = t.currency
                return (
                  <tr key={t.id}>
                    <td className="muted">{t.date}</td>
                    <td>{t.site}</td>
                    <td style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={t.name}>
                      {t.name}
                    </td>
                    <td><Badge type={t.type} speed={t.speed} /></td>
                    <td>{cur}{Number(t.buyin).toFixed(2)}</td>
                    <td>{t.cashout > 0 ? `${cur}${Number(t.cashout).toFixed(2)}` : '—'}</td>
                    <td className="muted">{t.position ?? '—'}</td>
                    <td className={res >= 0 ? 'green' : 'red'}>
                      {res >= 0 ? '+' : ''}{cur}{Math.abs(res).toFixed(2)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {data.pages > 1 && (
          <div className="pagination">
            <button className="btn btn-ghost btn-sm" disabled={filters.page <= 1} onClick={() => set('page', filters.page - 1)}>← Anterior</button>
            <span className="muted">Pág. {filters.page} / {data.pages}</span>
            <button className="btn btn-ghost btn-sm" disabled={filters.page >= data.pages} onClick={() => set('page', filters.page + 1)}>Próxima →</button>
          </div>
        )}
      </div>
    </>
  )
}
