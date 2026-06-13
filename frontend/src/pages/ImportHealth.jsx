import { useCallback, useEffect, useState } from 'react'
import { importHealth } from '../api/client'

// Saúde do Import (pt68 v1) — instrumento de validação da Etapa 1.
// Mostra, por pipeline, contagens + falhas/sem-match com motivo + timestamp.
// Janela "dia-de-jogo" 15:00→15:00 (só faz sentido em campos de HORA-DE-JOGO:
// mesa.captured_at e hands.played_at; inbox/imports são por hora-de-import).

const RESULT_COLOR = (r) => {
  if (r === 'success') return '#22c55e'
  if (['tm_not_found', 'tm_ambiguous', 'no_match_to_hand', 'site_undetected'].includes(r)) return '#eab308'
  if (['vision_failed', 'json_invalid', 'upsert_error', 'error'].includes(r)) return '#ef4444'
  return '#94a3b8'
}

function Chip({ children, color }) {
  return (
    <span style={{
      fontSize: 11, fontWeight: 700, color: color || 'var(--muted)',
      background: `${color || '#64748b'}1f`, padding: '2px 8px', borderRadius: 5,
      whiteSpace: 'nowrap', marginRight: 6,
    }}>{children}</span>
  )
}

function fmt(ts) {
  if (!ts) return '—'
  return String(ts).replace('T', ' ').replace('Z', '').slice(0, 19)
}

const card = {
  background: 'var(--card, #161b22)', border: '1px solid var(--border, #30363d)',
  borderRadius: 8, padding: 16, marginBottom: 16,
}
const th = { textAlign: 'left', padding: '4px 8px', color: 'var(--muted)', fontWeight: 600, fontSize: 11, borderBottom: '1px solid var(--border,#30363d)' }
const td = { padding: '4px 8px', fontSize: 12, borderBottom: '1px solid rgba(255,255,255,0.04)', verticalAlign: 'top' }

function PipelineCard({ p }) {
  if (!p) return null
  if (p.error) {
    return <div style={card}><b>{p.label || '—'}</b> <Chip color="#ef4444">erro</Chip>
      <div style={{ fontSize: 12, color: '#ef4444', marginTop: 6 }}>{p.error}</div></div>
  }
  return (
    <div style={card}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <b style={{ fontSize: 15 }}>{p.label}</b>
        {'total' in p && <Chip>{p.total} total</Chip>}
        {'ok' in p && <Chip color="#22c55e">{p.ok} ok</Chip>}
        {'fail' in p && p.fail > 0 && <Chip color="#ef4444">{p.fail} falha</Chip>}
        {'errors' in p && p.errors > 0 && <Chip color="#ef4444">{p.errors} erro</Chip>}
        {'partial' in p && p.partial > 0 && <Chip color="#eab308">{p.partial} parcial</Chip>}
        {'failed' in p && p.failed > 0 && <Chip color="#ef4444">{p.failed} falhadas</Chip>}
        {'gg_sem_match' in p && p.gg_sem_match > 0 && <Chip color="#eab308">{p.gg_sem_match} GG s/ match</Chip>}
      </div>
      <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>janela: {p.time_field}</div>

      {p.by_result && p.by_result.length > 0 && (
        <div style={{ marginTop: 8 }}>
          {p.by_result.map((r) => (
            <Chip key={r.result} color={RESULT_COLOR(r.result)}>{r.result}: {r.n}</Chip>
          ))}
        </div>
      )}
      {p.by_site_state && (
        <div style={{ marginTop: 8 }}>
          {p.by_site_state.map((r, i) => (
            <Chip key={i}>{r.site || '—'} / {r.study_state}: {r.n}</Chip>
          ))}
        </div>
      )}
      {p.by_source_type_status && (
        <div style={{ marginTop: 8 }}>
          {p.by_source_type_status.map((r, i) => (
            <Chip key={i} color={r.status === 'failed' ? '#ef4444' : undefined}>
              {r.source}/{r.entry_type}/{r.status}: {r.n}
            </Chip>
          ))}
        </div>
      )}

      {/* Listas de detalhe */}
      {p.failures && p.failures.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 10 }}>
          <thead><tr><th style={th}>quando</th><th style={th}>motivo</th><th style={th}>site</th><th style={th}>torneio</th><th style={th}>ficheiro / id</th></tr></thead>
          <tbody>
            {p.failures.map((f, i) => (
              <tr key={i}>
                <td style={td}>{fmt(f.at)}</td>
                <td style={td}><Chip color={RESULT_COLOR(f.result)}>{f.result}</Chip>{f.reason || ''}</td>
                <td style={td}>{f.site || '—'}</td>
                <td style={td}>{f.tournament_number || '—'}</td>
                <td style={{ ...td, color: 'var(--muted)', wordBreak: 'break-all' }}>{f.filename || f.id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {p.runs && p.runs.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 10 }}>
          <thead><tr><th style={th}>quando</th><th style={th}>estado</th><th style={th}>found/ok/skip/err</th><th style={th}>site</th><th style={th}>ficheiro</th></tr></thead>
          <tbody>
            {p.runs.map((r, i) => (
              <tr key={i}>
                <td style={td}>{fmt(r.at)}</td>
                <td style={td}><Chip color={r.status === 'ok' ? '#22c55e' : r.status === 'partial' ? '#eab308' : '#ef4444'}>{r.status}</Chip></td>
                <td style={td}>{r.records_found}/{r.records_ok}/{r.records_skipped}/{r.records_error}</td>
                <td style={td}>{r.site || '—'}</td>
                <td style={{ ...td, color: 'var(--muted)', wordBreak: 'break-all' }} title={r.log || ''}>{r.filename}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {p.failed_items && p.failed_items.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 10 }}>
          <thead><tr><th style={th}>quando</th><th style={th}>source</th><th style={th}>tipo</th><th style={th}>id</th></tr></thead>
          <tbody>
            {p.failed_items.map((f, i) => (
              <tr key={i}><td style={td}>{fmt(f.at)}</td><td style={td}>{f.source}</td><td style={td}>{f.entry_type}</td><td style={td}>{f.id}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

const ORDER = ['hands', 'mesa', 'lobby', 'hh_ts', 'inbox']

export default function ImportHealth() {
  const [day, setDay] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async (d) => {
    setLoading(true); setError(null)
    try { setData(await importHealth.get(d || undefined)) }
    catch (e) { setError(e.message || String(e)) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load('') }, [load])

  return (
    <div style={{ padding: 20, maxWidth: 1100 }}>
      <h1 style={{ marginBottom: 4 }}>Saúde do Import</h1>
      <p style={{ color: 'var(--muted)', marginTop: 0, fontSize: 13 }}>
        Falhas, rejeitados e sem-match da fase de importação, por pipeline. v1 sobre os logs existentes.
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '14px 0' }}>
        <label style={{ fontSize: 13 }}>Dia-de-jogo (15:00→15:00):</label>
        <input type="date" value={day} onChange={(e) => setDay(e.target.value)}
          style={{ background: 'var(--card,#161b22)', color: 'inherit', border: '1px solid var(--border,#30363d)', borderRadius: 6, padding: '4px 8px' }} />
        <button onClick={() => load(day)} disabled={loading}>{loading ? '…' : 'Aplicar'}</button>
        <button onClick={() => { setDay(''); load('') }} disabled={loading}>Todas as datas</button>
        {data?.filter?.from && <span style={{ fontSize: 12, color: 'var(--muted)' }}>{fmt(data.filter.from)} → {fmt(data.filter.to)}</span>}
      </div>

      {error && <div style={{ color: '#ef4444', marginBottom: 12 }}>Erro: {error}</div>}
      {loading && !data && <div style={{ color: 'var(--muted)' }}>a carregar…</div>}

      {data && ORDER.map((k) => <PipelineCard key={k} p={data.pipelines[k]} />)}

      {data?.deanon && !data.deanon.error && data.deanon.total > 0 && (
        <div style={{ ...card, borderColor: data.deanon.alert ? '#ef4444' : 'var(--border)' }}>
          <b>Desanonimização por SS de mesa (guarda epistémica)</b>
          <div style={{ fontSize: 13, marginTop: 6 }}>
            {data.deanon.total} mãos · {data.deanon.complete} completas · {data.deanon.partial} parciais
            {' '}(<span style={{ color: data.deanon.alert ? '#ef4444' : 'var(--muted)' }}>
              {Math.round(data.deanon.partial_rate * 100)}% por mapear</span>)
          </div>
          <div style={{ fontSize: 11, color: data.deanon.alert ? '#ef4444' : 'var(--muted)', marginTop: 4 }}>
            {data.deanon.alert
              ? '⚠️ ALERTA: muitas mãos parciais — as maiorias da votação cross-mão podem estar a colapsar (hash-estabilidade / Vision a degradar). Investigar.'
              : 'Saudável. Parciais = empates honestos da votação (banco ambíguo fica por mapear, nunca nome trocado).'}
          </div>
        </div>
      )}

      {data?.holes && (
        <div style={{ ...card, borderColor: '#a16207' }}>
          <b>⚠️ Buracos de logging (v2 — falhas que hoje NÃO deixam rasto queryable)</b>
          <ul style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 0 }}>
            {data.holes.map((h, i) => <li key={i}>{h}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}
