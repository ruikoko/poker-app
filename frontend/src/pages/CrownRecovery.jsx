import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ggHealth, API_ROOT } from '../api/client'

// Bounties recuperáveis (#CROWN-RECOVERY) — ETAPA 1: painel SÓ-LEITURA.
// Grupo 1 = jogador bustou na HH E coroa NULL → recuperável (lê o verde na coroa
// do matador; bounty = verde × 2). A escrita (fluxo A+B) liga-se por cima depois.

const C = {
  card: '#161d19', border: 'rgba(255,255,255,0.10)', text: '#e8ece9',
  muted: '#8b9691', green: '#46c98a', gold: '#e6b34a', red: '#e0705f',
}

export default function CrownRecovery() {
  const [st, setSt] = useState(null)
  const [busy, setBusy] = useState(false)
  const [showOver, setShowOver] = useState(false)
  const poll = useRef(null)

  const refresh = () => ggHealth.crownRecoveryState().then(setSt).catch(() => {})
  useEffect(() => { refresh(); return () => clearInterval(poll.current) }, [])
  useEffect(() => {
    clearInterval(poll.current)
    if (st?.status === 'running') poll.current = setInterval(refresh, 2500)
    return () => clearInterval(poll.current)
  }, [st?.status])

  const scan = async () => {
    setBusy(true)
    try { await ggHealth.crownRecoveryScan(); await refresh() } finally { setBusy(false) }
  }
  const cancel = async () => {
    setBusy(true)
    try { await ggHealth.crownRecoveryCancel(); await refresh() } finally { setBusy(false) }
  }

  const running = st?.status === 'running'
  const idle = !st || st.status === 'idle'
  const g1 = st?.group1 || []

  return (
    <div style={{ padding: '18px 22px', color: C.text, maxWidth: 1000, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, fontWeight: 800, margin: '0 0 4px' }}>Bounties recuperáveis</h1>
      <p style={{ color: C.muted, fontSize: 13, margin: '0 0 14px', lineHeight: 1.5, maxWidth: '70ch' }}>
        Mãos onde um jogador <b style={{ color: C.red }}>bustou</b> (all-in + perdeu, da HH) e a
        coroa dourada dele ficou <b style={{ color: C.red }}>NULL</b> — o bounty está a{' '}
        <b style={{ color: C.green }}>verde</b> na coroa de quem o eliminou. <b>Etapa 1: só leitura</b>
        {' '}— valida a lista à vista; a escrita liga-se por cima depois. Só a imagem arbitra os valores.
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <button onClick={scan} disabled={busy || running}
          style={{ background: running ? '#2a2f37' : C.green, color: running ? C.muted : '#08130d',
            border: 'none', borderRadius: 8, padding: '9px 15px', fontWeight: 700,
            cursor: busy || running ? 'default' : 'pointer', fontSize: 14 }}>
          {running ? 'A varrer…' : busy ? '…' : idle ? 'Correr detetor' : 'Re-correr'}
        </button>
        {running && (
          <button onClick={cancel} disabled={busy}
            style={{ background: 'transparent', color: C.red, border: `1px solid ${C.red}`,
              borderRadius: 8, padding: '9px 15px', fontWeight: 700, cursor: 'pointer', fontSize: 14 }}>
            Cancelar
          </button>
        )}
        {st && st.total > 0 && (
          <span style={{ color: C.muted, fontSize: 13 }}>
            {st.done}/{st.total} varridas ·{' '}
            <b style={{ color: C.green }}>{st.group1_count}</b> recuperáveis ·{' '}
            <b style={{ color: C.gold }}>{st.misread_count ?? 0}</b> re-ler placa ·{' '}
            {st.group2_count} falha real · {st.over_read_count} over-read
          </span>
        )}
      </div>

      {idle && <div style={{ color: C.muted, fontSize: 14 }}>Carrega em “Correr detetor” para varrer as KO/PKO com Gold.</div>}

      {/* grupo 1 — recuperáveis */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {g1.map(h => (
          <div key={h.hand_db_id} style={{ background: C.card, border: `1px solid ${C.border}`,
            borderRadius: 12, padding: 14, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {h.entry_id != null && (
              <img src={`${API_ROOT}/api/screenshots/image/${h.entry_id}`} alt="gold" loading="lazy"
                onError={e => { e.currentTarget.style.display = 'none'
                  const n = e.currentTarget.nextSibling; if (n) n.style.display = 'flex' }}
                style={{ width: 320, maxWidth: '100%', borderRadius: 9, objectFit: 'contain',
                  border: `1px solid ${C.border}`, background: '#000' }} />
            )}
            {h.entry_id != null && (
              <div style={{ display: 'none', width: 320, maxWidth: '100%', minHeight: 120,
                alignItems: 'center', justifyContent: 'center', borderRadius: 9,
                border: `1px dashed ${C.border}`, color: C.muted, fontSize: 12 }}>imagem indisponível</div>
            )}
            <div style={{ flex: 1, minWidth: 250 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                <Link to={`/hand/${h.hand_db_id}`}
                  style={{ color: C.gold, fontWeight: 700, fontSize: 14, textDecoration: 'none',
                    fontFamily: 'ui-monospace,monospace' }}>{h.hand_id}</Link>
                <span style={{ color: C.muted, fontSize: 12 }}>{h.tournament}</span>
              </div>
              <div style={{ marginTop: 10, padding: '9px 11px', borderRadius: 8,
                background: 'rgba(224,112,95,.07)', border: '1px solid rgba(224,112,95,.3)' }}>
                <div style={lbl(C)}>Bustou · coroa em branco</div>
                {h.busted.map((b, i) => (
                  <div key={i} style={{ fontSize: 14 }}><b>{b.name}</b> <span style={pos(C)}>{b.position}</span></div>
                ))}
              </div>
              <div style={{ marginTop: 8, padding: '9px 11px', borderRadius: 8,
                background: 'rgba(70,201,138,.07)', border: '1px solid rgba(70,201,138,.28)' }}>
                <div style={lbl(C)}>Verde do KO → coroa do matador</div>
                {(h.matadores && h.matadores.length)
                  ? h.matadores.map((m, i) => (
                    <div key={i} style={{ fontSize: 14 }}>
                      <b style={{ color: C.green }}>{m.name || '—'}</b> <span style={pos(C)}>{m.position}</span>
                      {m.is_hero && <span style={{ fontSize: 10, color: '#08130d', background: C.gold,
                        borderRadius: 4, padding: '1px 6px', marginLeft: 6, fontWeight: 700 }}>HERO</span>}
                    </div>))
                  : <div style={{ fontSize: 13, color: C.muted }}>matador não identificado na HH</div>}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* re-ler placa — all-in perdido MAS jogador VIVO (resto >= 1 BB) */}
      {st && (st.status === 'done' || st.status === 'cancelled') && (st.misread_count ?? 0) > 0 && (
        <div style={{ marginTop: 22 }}>
          <div style={{ ...lbl(C), color: C.gold, fontSize: 12 }}>
            Re-ler placa — {st.misread_count} vivos (all-in perdido mas ficaram com stack)
          </div>
          <p style={{ color: C.muted, fontSize: 12, margin: '4px 0 8px', maxWidth: '70ch' }}>
            Perderam o all-in mas <b>cobriram o adversário</b> (resto ≥ 1 BB) ou não bustaram —
            a coroa NULL é <b>leitura falhada da placa própria</b>. Recupera-se <b>re-lendo a placa</b>,
            <b> nunca</b> verde × 2. (Inclui os despromovidos pela contraprova da mão-seguinte.)
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {(st.misread || []).map(o => (
              <Link key={o.hand_db_id} to={`/hand/${o.hand_db_id}`}
                style={{ color: C.gold, textDecoration: 'none', border: `1px solid ${C.border}`,
                  borderRadius: 6, padding: '3px 8px', fontSize: 12, fontFamily: 'ui-monospace,monospace' }}>
                {o.hand_id}
                <span style={{ color: C.muted }}> {(o.seats || []).map(s => s.name).join(', ')}
                  {o.reason === 'seated_next_hand' ? ' · sentou-se na mão seguinte' : ''}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* grupo 2 + over-read (à parte) */}
      {st && (st.status === 'done' || st.status === 'cancelled') && (
        <div style={{ marginTop: 22, color: C.muted, fontSize: 13, display: 'flex',
          flexDirection: 'column', gap: 8 }}>
          <div>
            <b style={{ color: C.text }}>{st.group2_count}</b> coroas de <b>falha real</b>{' '}
            (não-bustou + não-Hero + NULL) → vão para o balde das coroas existente.
          </div>
          <div>
            <button onClick={() => setShowOver(v => !v)} style={{ background: 'transparent',
              border: `1px solid ${C.border}`, color: C.text, borderRadius: 6, padding: '3px 10px',
              cursor: 'pointer', fontSize: 12 }}>
              {showOver ? 'Esconder' : 'Ver'} {st.over_read_count} over-read (à parte)
            </button>
            {showOver && (
              <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {st.over_read.map(o => (
                  <Link key={o.hand_db_id} to={`/hand/${o.hand_db_id}`}
                    style={{ color: C.gold, textDecoration: 'none', border: `1px solid ${C.border}`,
                      borderRadius: 6, padding: '3px 8px', fontSize: 12, fontFamily: 'ui-monospace,monospace' }}>
                    {o.hand_id} <span style={{ color: C.muted }}>HH {o.num_hh}≠{o.num_extracted} Gold</span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

const lbl = (C) => ({ fontSize: 11, letterSpacing: '.05em', textTransform: 'uppercase',
  color: C.muted, fontWeight: 700, marginBottom: 4 })
const pos = (C) => ({ fontFamily: 'ui-monospace,monospace', fontSize: 12,
  background: 'rgba(255,255,255,.06)', borderRadius: 5, padding: '1px 7px', marginLeft: 4 })
