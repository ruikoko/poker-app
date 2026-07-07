import { useCallback, useRef, useState } from 'react'
import { lobbys } from '../api/client'

// Estado por ficheiro nesta sessão de upload (pending → processing → terminal).
// Espelha a UX da janela "SS Mesa", adaptado à semântica do gate de lobby:
//   lobby     = backend confirmou lobby (is_lobby)
//   ignored   = não-lobby genuíno (json_invalid/site_undetected) — ignorado
//   transient = falha transitória da Vision (vision_failed) — volta a tentar
//   error     = erro de transporte / HTTP
const STATUS = {
  pending:    { label: 'em fila',           color: '#64748b' },
  processing: { label: 'a processar…',      color: '#3b82f6' },
  lobby:      { label: 'lobby',             color: '#22c55e' },
  ignored:    { label: 'não-lobby',         color: '#eab308' },
  transient:  { label: 'falha transitória', color: '#f97316' },
  error:      { label: 'erro',              color: '#ef4444' },
}

function Chip({ children, color }) {
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, color: color || 'var(--muted)',
      background: `${color || '#64748b'}1f`, padding: '2px 7px', borderRadius: 4,
      whiteSpace: 'nowrap',
    }}>{children}</span>
  )
}

// Resposta do /api/lobbys/upload → status terminal do ficheiro.
// is_lobby true (inclui dedup) → lobby. Senão, vision_failed é transitório
// (≠ não-lobby genuíno) → retry; o resto é não-lobby ignorado.
function classify(j) {
  if (j?.is_lobby) return 'lobby'
  if (j?.result === 'vision_failed') return 'transient'
  return 'ignored'
}

// captured_at = File.lastModified em hora LOCAL do browser (Lisboa), formatada
// naive (sem offset/Z) — equivalente ao mtime que o appimport usa para lobbys.
// O nome do Windows "Captura de ecrã YYYY-MM-DD HHMMSS" NÃO traz o
// YYYYMMDDHHMMSS que a via table-SS lê do nome; por isso a hora vem do ficheiro.
// NÃO usar toISOString() (converte para UTC com 'Z' → o backend, convenção pt51,
// trataria a wall-clock UTC como Lisboa e deslocava a hora pelo offset).
function lastModifiedToLisbonNaiveISO(ms) {
  const d = new Date(ms)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}` +
         `T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

function money(v) {
  if (v == null || v === '') return '—'
  return typeof v === 'number' ? v.toLocaleString('pt-PT') : String(v)
}

// Linha label/valor do painel de detalhe.
function KV({ k, children }) {
  return (
    <div style={{ display: 'flex', gap: 8, fontSize: 12, lineHeight: 1.7 }}>
      <span style={{ color: 'var(--muted)', flex: '0 0 140px' }}>{k}</span>
      <span style={{ color: 'var(--text)', minWidth: 0, wordBreak: 'break-word' }}>{children}</span>
    </div>
  )
}

const ladderChip = {
  fontSize: 11, fontFamily: 'monospace', color: 'var(--text)',
  background: 'rgba(148,163,184,0.12)', padding: '1px 6px', borderRadius: 4,
}

// Escada de prémios: prizes {pos: valor} + prize_ranges [{rank_from,rank_to,amount}].
function PrizeLadder({ vj }) {
  const prizes = vj?.prizes || {}
  const ranges = vj?.prize_ranges || []
  const pos = Object.entries(prizes).sort((a, b) => Number(a[0]) - Number(b[0]))
  if (!pos.length && !ranges.length) return <span style={{ color: 'var(--muted)' }}>—</span>
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
      {pos.map(([p, amt]) => <span key={p} style={ladderChip}>{p}: {money(amt)}</span>)}
      {ranges.map((r, i) => (
        <span key={`r${i}`} style={ladderChip}>{r.rank_from}~{r.rank_to}: {money(r.amount)}</span>
      ))}
    </div>
  )
}

function RawJson({ label, data }) {
  if (data == null) return null
  return (
    <details style={{ marginTop: 6 }}>
      <summary style={{ cursor: 'pointer', fontSize: 11, color: 'var(--muted)' }}>{label}</summary>
      <pre style={{
        margin: '6px 0 0', padding: 10, fontSize: 11, lineHeight: 1.5,
        background: 'rgba(15,23,42,0.55)', border: '1px solid var(--border)',
        borderRadius: 6, overflowX: 'auto', maxHeight: 280,
      }}>{JSON.stringify(data, null, 2)}</pre>
    </details>
  )
}

// Estado de duplicado/precedência em prosa, a partir da resposta do backend.
function importStateText(r) {
  if (r.dedup) return 'já processado antes (dedup por conteúdo) — nada reescrito'
  if (r.result === 'skipped_precedence')
    return `NÃO sobrescreveu (precedência) — fonte existente: ${r.existing_source || '—'}`
  if (r.action === 'inserted')
    return r.existing_source ? `escrito (substituiu fonte ${r.existing_source})` : 'inserido (torneio novo)'
  if (r.action === 'updated')
    return `actualizado${r.existing_source ? ` (fonte anterior: ${r.existing_source})` : ''}`
  return '—'
}

// Cor do chip de acção de reconcile por item.
const RECON_ACTION = {
  written:            { label: 'escrito',           color: '#22c55e' },
  skipped_precedence: { label: 'precedência',       color: '#f97316' },
  still_unresolved:   { label: 'ainda sem match',   color: '#64748b' },
  still_ambiguous:    { label: 'ainda ambíguo',     color: '#eab308' },
}

// Secção "religar pendentes" — re-resolve lobbys tm_not_found/tm_ambiguous.
// Fluxo: pré-visualizar (dry-run) → se houver resolúveis, aplicar (escreve).
function ReconcilePanel() {
  const [recon, setRecon] = useState(null)   // última resposta (dry ou aplicada)
  const [busy, setBusy] = useState(false)

  async function run(dryRun) {
    setBusy(true)
    try {
      const r = await lobbys.reconcile(dryRun)
      setRecon({ ...r, applied: !dryRun })
    } catch (e) {
      setRecon({ error: String(e.message || e) })
    } finally {
      setBusy(false)
    }
  }

  const canApply = recon && !recon.applied && !recon.error && recon.resolved > 0
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 14, marginBottom: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Religar pendentes</div>
        <span style={{ fontSize: 11, color: 'var(--muted)' }}>
          re-resolve lobbys sem número (tm_not_found / ambíguo) contra a BD actual — sem Vision
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button onClick={() => run(true)} disabled={busy} style={{
            padding: '5px 12px', fontSize: 11, fontWeight: 600, borderRadius: 6,
            background: 'transparent', border: '1px solid var(--accent)', color: 'var(--accent)',
            cursor: busy ? 'wait' : 'pointer', opacity: busy ? 0.5 : 1,
          }}>{busy ? '…' : 'Pré-visualizar'}</button>
          {canApply && (
            <button onClick={() => run(false)} disabled={busy} style={{
              padding: '5px 12px', fontSize: 11, fontWeight: 600, borderRadius: 6,
              background: 'var(--accent)', border: 'none', color: '#fff',
              cursor: busy ? 'wait' : 'pointer', opacity: busy ? 0.5 : 1,
            }}>Aplicar — escrever {recon.resolved} payout(s)</button>
          )}
        </div>
      </div>

      {recon?.error && (
        <div style={{ marginTop: 10, fontSize: 12, color: '#ef4444' }}>Erro: {recon.error}</div>
      )}

      {recon && !recon.error && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>
            {recon.applied ? 'Aplicado' : 'Pré-visualização'} · {recon.scanned} pendente(s) ·{' '}
            <b style={{ color: 'var(--text)' }}>{recon.resolved}</b> resolúvel(is) ·{' '}
            {recon.applied ? `${recon.written} escrito(s)` : `${recon.resolved} a escrever`} ·{' '}
            {recon.skipped_precedence} precedência · {recon.still_unresolved} sem match
          </div>
          {recon.scanned === 0 && (
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>Nenhum lobby pendente.</div>
          )}
          {(recon.items || []).map((it, i) => {
            const a = RECON_ACTION[it.action] || { label: it.action, color: '#64748b' }
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
                fontSize: 12, padding: '4px 0', borderTop: i ? '1px solid rgba(255,255,255,0.04)' : 'none',
              }}>
                {it.lobby_date && (
                  <span style={{ fontFamily: 'monospace', color: 'var(--muted)', fontSize: 11 }}>{it.lobby_date}</span>
                )}
                <span>{it.site} · <b>{it.tournament_name || '—'}</b></span>
                <Chip color={a.color}>{a.label}</Chip>
                {it.resolved_tn && (
                  <span style={{ color: 'var(--muted)' }}>
                    → tn {it.resolved_tn}{it.resolver_tier ? ` (tier ${it.resolver_tier})` : ''}
                  </span>
                )}
                {it.action === 'skipped_precedence' && it.existing_source && (
                  <span style={{ color: 'var(--muted)', opacity: 0.8 }}>fonte: {it.existing_source}</span>
                )}
                {it.action === 'still_ambiguous' && (
                  <span style={{ color: 'var(--muted)', opacity: 0.8 }}>{it.n_candidates} candidatos</span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// Painel de detalhe completo por ficheiro: EXTRAÇÃO (Vision) + IMPORT (backend).
function Detail({ r }) {
  const vj = r.vision_json || {}
  const s0 = (r.payouts_blob?.structures || [])[0] || {}
  return (
    <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
      {/* EXTRAÇÃO */}
      <div>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, color: 'var(--muted)', marginBottom: 6 }}>
          EXTRAÇÃO — o que a Vision leu
        </div>
        <KV k="torneio">{vj.tournament_name || r.tournament_name || '—'}</KV>
        <KV k="tournament_number">{vj.tournament_number || '—'}</KV>
        <KV k="prize pool">{money(vj.prize_pool)}</KV>
        <KV k="buy-in">{money(vj.buy_in)}</KV>
        <KV k="bounty (texto)">{vj.bounty_type_text || '—'}</KV>
        <KV k="players left">{r.players_left ?? vj.players_left ?? '—'}</KV>
        <KV k="prémios"><PrizeLadder vj={vj} /></KV>
        <RawJson label="JSON cru da Vision" data={r.vision_json} />
      </div>
      {/* IMPORT */}
      <div>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, color: 'var(--muted)', marginBottom: 6 }}>
          IMPORT — o que o backend fez
        </div>
        <KV k="result">{r.result || '—'}</KV>
        {r.reason_detail && <KV k="detalhe">{r.reason_detail}</KV>}
        <KV k="site">{r.site || '—'}</KV>
        <KV k="tournament_number">{r.tournament_number || '—'}</KV>
        <KV k="resolvido por">{r.resolver_tier ? `tier ${r.resolver_tier}` : '—'}</KV>
        <KV k="estado">{importStateText(r)}</KV>
        {Array.isArray(r.candidates) && r.candidates.length > 0 && (
          <KV k="candidatos">{r.candidates.length} (ambíguo)</KV>
        )}
        {r.payouts_blob && (
          <>
            <KV k="payouts escrito">
              {s0.name || r.payouts_blob.name || '—'}
              {s0.bountyType ? ` · ${s0.bountyType}` : ''}
              {s0.progressiveFactor != null ? ` · pf ${s0.progressiveFactor}` : ''}
            </KV>
            <RawJson label="blob escrito em tournament_payouts" data={r.payouts_blob} />
          </>
        )}
      </div>
    </div>
  )
}

export default function LobbysPage() {
  const [items, setItems] = useState([])      // uploads desta sessão
  const [dragging, setDragging] = useState(false)
  const [force, setForce] = useState(false)   // forçar releitura (fura o dedup)
  const inputRef = useRef(null)
  const keyRef = useRef(0)

  const patch = (key, fields) =>
    setItems(prev => prev.map(it => (it.key === key ? { ...it, ...fields } : it)))

  const addFiles = useCallback(async (fileList) => {
    const picked = Array.from(fileList).filter(f => /\.(png|jpe?g)$/i.test(f.name))
    if (!picked.length) return
    const entries = picked.map(f => ({
      key: ++keyRef.current, name: f.name, file: f, status: 'pending', result: null,
    }))
    setItems(prev => [...entries, ...prev])
    // Sequencial — evita martelar a Vision em paralelo. O upload devolve o
    // veredicto final (gate síncrono), por isso o estado nunca fica preso.
    for (const e of entries) {
      patch(e.key, { status: 'processing' })
      try {
        const captured_at = lastModifiedToLisbonNaiveISO(e.file.lastModified)
        const r = await lobbys.upload(e.file, { captured_at, force })
        patch(e.key, { status: classify(r), result: r })
      } catch (err) {
        patch(e.key, { status: 'error', result: { reason_detail: String(err.message || err) } })
      }
    }
  }, [force])

  const onDrop = useCallback((ev) => {
    ev.preventDefault(); setDragging(false)
    if (ev.dataTransfer.files.length) addFiles(ev.dataTransfer.files)
  }, [addFiles])
  const onDragOver = useCallback((ev) => { ev.preventDefault(); setDragging(true) }, [])
  const onDragLeave = useCallback(() => setDragging(false), [])

  return (
    <div style={{ padding: 24, maxWidth: 1180, margin: '0 auto' }}>
      {/* Header */}
      <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 4px' }}>Lobbys</h1>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
        Carrega SSs de <b>lobby de torneio</b> (2ª via, fora do Discord). A Vision lê o
        lobby e, se for mesmo um lobby, entra em <code>tournament_payouts</code> pela mesma
        pipeline do sync. Um print qualquer que não seja lobby é <b>ignorado</b> (nada gravado).
        Cada ficheiro abre para o detalhe completo da extração e do import.
      </div>

      {/* Forçar releitura — fura o dedup por conteúdo e re-corre a Vision (refresh
          só do vision_json: open_tab/final_table_size; NÃO toca prémios/payouts). */}
      <label style={{
        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10,
        fontSize: 12, color: 'var(--muted)', cursor: 'pointer', userSelect: 'none',
      }}>
        <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
        <span>
          <b>Forçar releitura</b> (ignora o dedup e volta a correr a Vision) — refresca só
          o <code>vision_json</code>; não altera prémios/payouts.
        </span>
      </label>

      {/* Drop zone */}
      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => inputRef.current?.click()}
        style={{
          border: `2px dashed ${dragging ? 'var(--accent)' : 'var(--border)'}`,
          borderRadius: 10, padding: '28px 16px', textAlign: 'center',
          cursor: 'pointer', background: dragging ? 'rgba(99,102,241,0.06)' : 'transparent',
          color: 'var(--muted)', fontSize: 13, marginBottom: 18,
        }}
      >
        <div style={{ fontSize: 22, marginBottom: 6 }}>⬆</div>
        Arrasta SSs de lobby aqui, ou <span style={{ color: 'var(--accent)' }}>clica para escolher</span>
        <div style={{ fontSize: 11, opacity: 0.7, marginTop: 4 }}>.png .jpg — a hora vem do ficheiro (data de modificação)</div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".png,.jpg,.jpeg"
          style={{ display: 'none' }}
          onChange={(e) => { if (e.target.files.length) addFiles(e.target.files); e.target.value = '' }}
        />
      </div>

      {/* Religar pendentes (re-resolve lobbys tm_not_found/ambíguo) */}
      <ReconcilePanel />

      {/* Resultado por ficheiro (sessão actual) — linha-resumo expansível */}
      {items.length > 0 && (
        <div style={{ marginBottom: 22 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Nesta sessão</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {items.map(it => {
              const st = STATUS[it.status] || STATUS.pending
              const r = it.result || {}
              const terminal = ['lobby', 'ignored', 'transient', 'error'].includes(it.status)
              return (
                <details key={it.key} style={{
                  border: '1px solid var(--border)', borderRadius: 8, padding: '8px 12px',
                }}>
                  <summary style={{
                    display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
                    fontSize: 12, cursor: terminal ? 'pointer' : 'default', listStyle: 'revert',
                  }}>
                    <span style={{ fontFamily: 'monospace' }}>{it.name}</span>
                    <Chip color={st.color}>{st.label}</Chip>
                    {it.status === 'lobby' && (
                      <span style={{ color: 'var(--muted)' }}>
                        {r.site || '—'} · {r.tournament_name || '—'}
                        {r.tournament_number && (
                          <> {' → '}<b style={{ color: 'var(--text)' }}>tn {r.tournament_number}</b></>
                        )}
                        <span style={{ opacity: 0.7 }}> ({r.result}){r.dedup ? ' · dedup' : ''}</span>
                      </span>
                    )}
                    {it.status === 'ignored' && (
                      <span style={{ color: 'var(--muted)', opacity: 0.85 }}>ignorado (não-lobby: {r.result || '—'})</span>
                    )}
                    {it.status === 'transient' && (
                      <span style={{ color: 'var(--muted)', opacity: 0.85 }}>
                        Vision falhou (transitório) — volta a arrastar para tentar de novo
                      </span>
                    )}
                    {it.status === 'error' && (
                      <span style={{ color: 'var(--muted)', opacity: 0.85 }}>{r.reason_detail || r.result || '—'}</span>
                    )}
                  </summary>
                  {terminal && it.result && <Detail r={r} />}
                </details>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
