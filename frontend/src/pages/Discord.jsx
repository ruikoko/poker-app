import { useEffect, useState, useCallback } from 'react'
import { discord } from '../api/client'

const DATE_FILTERS = [
  { label: 'Todas', value: '' },
  { label: 'Hoje', fn: () => { const d = new Date(); d.setHours(0,0,0,0); return d.toISOString().slice(0,10) } },
  { label: '3 dias', fn: () => { const d = new Date(); d.setDate(d.getDate()-3); return d.toISOString().slice(0,10) } },
  { label: 'Semana', fn: () => { const d = new Date(); d.setDate(d.getDate()-7); return d.toISOString().slice(0,10) } },
  { label: 'Mês', fn: () => { const d = new Date(); d.setDate(d.getDate()-30); return d.toISOString().slice(0,10) } },
]

export default function DiscordPage() {
  const [status, setStatus] = useState(null)
  const [stats, setStats] = useState(null)
  const [syncState, setSyncState] = useState([])
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [dateFrom, setDateFrom] = useState('')

  const load = useCallback(() => {
    discord.status().then(setStatus).catch(e => setError(e.message))
    const params = dateFrom ? { date_from: dateFrom } : {}
    discord.stats(params).then(setStats).catch(() => {})
    discord.syncState().then(setSyncState).catch(() => {})
  }, [dateFrom])

  useEffect(() => { load() }, [load])

  const triggerSync = async () => {
    setSyncing(true)
    setMsg('')
    try {
      const r = await discord.sync()
      setMsg(`Sync iniciado em ${r.servers} servidor(es). Actualiza a página em 30s para ver os resultados.`)
      setTimeout(load, 30000)
    } catch (e) {
      setError(e.message)
    } finally {
      setSyncing(false)
    }
  }

  const fmtDate = (d) => d ? new Date(d).toLocaleString('pt-PT') : '—'

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Discord Bot</div>
          <div className="page-subtitle">Monitorização e sincronização dos canais Discord</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost" onClick={load}>Actualizar</button>
          <button className="btn btn-primary" onClick={triggerSync} disabled={syncing || !status?.online}>
            {syncing ? 'A sincronizar...' : 'Sincronizar Agora'}
          </button>
        </div>
      </div>

      {error && <div className="error-msg" style={{ marginBottom: 16 }}>{error}</div>}
      {msg && <div style={{ background: 'var(--surface)', border: '1px solid var(--accent)', borderRadius: 8, padding: '12px 16px', marginBottom: 16, color: 'var(--accent)' }}>{msg}</div>}

      {/* ── Filtros Temporais ── */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
        {DATE_FILTERS.map(({ label, value, fn }) => {
          const filterValue = fn ? fn() : (value ?? '')
          const isActive = dateFrom === filterValue
          return (
            <button
              key={label}
              onClick={() => setDateFrom(filterValue)}
              style={{
                padding: '5px 14px', borderRadius: 20, fontSize: 12, fontWeight: 500,
                border: '1px solid',
                borderColor: isActive ? '#6366f1' : '#2a2d3a',
                background: isActive ? 'rgba(99,102,241,0.15)' : 'transparent',
                color: isActive ? '#818cf8' : '#64748b',
                cursor: 'pointer', transition: 'all 0.15s',
              }}
            >{label}</button>
          )
        })}
      </div>

      {/* ── Estado do Bot ── */}
      <div className="stat-grid" style={{ marginBottom: 24 }}>
        <div className="stat-card">
          <div className="stat-label">Estado</div>
          <div className="stat-value" style={{ color: status?.online ? '#22c55e' : '#ef4444', fontSize: 18 }}>
            {status?.online ? 'Online' : 'Offline'}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Bot</div>
          <div className="stat-value" style={{ fontSize: 14 }}>{status?.user || '—'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Entries Extraídas</div>
          <div className="stat-value">{stats?.entries?.total_entries ?? '—'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Pendentes</div>
          <div className="stat-value" style={{ color: 'var(--accent)' }}>{stats?.entries?.pending ?? '—'}</div>
        </div>
      </div>

      {/* ── Servidores e Canais ── */}
      {status?.online && status.servers?.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3 style={{ marginBottom: 12 }}>Servidores Monitorizados</h3>
          {status.servers.map(srv => (
            <div key={srv.id} style={{ background: 'var(--surface)', borderRadius: 8, padding: 16, marginBottom: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>{srv.name}</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {srv.channels.map(ch => (
                  <span
                    key={ch.id}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 4,
                      fontSize: 12,
                      background: ch.monitored ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.05)',
                      color: ch.monitored ? 'var(--accent)' : 'var(--muted)',
                      border: ch.monitored ? '1px solid var(--accent)' : '1px solid transparent',
                    }}
                  >
                    #{ch.name}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Estatísticas por Tipo ── */}
      {stats?.by_type?.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3 style={{ marginBottom: 12 }}>Por Tipo de Conteúdo</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Tipo</th>
                <th style={{ textAlign: 'right' }}>Quantidade</th>
              </tr>
            </thead>
            <tbody>
              {stats.by_type.map(r => (
                <tr key={r.entry_type}>
                  <td>{r.entry_type}</td>
                  <td style={{ textAlign: 'right' }}>{r.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Estatísticas por Canal ── */}
      {stats?.by_channel?.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3 style={{ marginBottom: 12 }}>Por Canal</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Canal</th>
                <th style={{ textAlign: 'right' }}>Entries</th>
              </tr>
            </thead>
            <tbody>
              {stats.by_channel.map(r => (
                <tr key={r.channel}>
                  <td>#{r.channel}</td>
                  <td style={{ textAlign: 'right' }}>{r.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Estado de Sync por Canal ── */}
      {syncState.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3 style={{ marginBottom: 12 }}>Histórico de Sincronização</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Canal</th>
                <th style={{ textAlign: 'right' }}>Mensagens</th>
                <th style={{ textAlign: 'right' }}>Último Sync</th>
              </tr>
            </thead>
            <tbody>
              {syncState.map(r => (
                <tr key={r.channel_id}>
                  <td>#{r.channel_name}</td>
                  <td style={{ textAlign: 'right' }}>{r.messages_synced}</td>
                  <td style={{ textAlign: 'right' }}>{fmtDate(r.last_sync_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Info quando offline ── */}
      {status && !status.online && (
        <div style={{ background: 'var(--surface)', borderRadius: 8, padding: 24, textAlign: 'center', color: 'var(--muted)' }}>
          <p style={{ marginBottom: 12 }}>O bot Discord não está online.</p>
          <p style={{ fontSize: 13 }}>
            Verifica que as variáveis <code>DISCORD_BOT_TOKEN</code> e <code>DISCORD_SERVER_IDS</code> estão
            configuradas no Railway.
          </p>
        </div>
      )}
    </>
  )
}
