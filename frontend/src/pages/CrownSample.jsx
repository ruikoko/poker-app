import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ggHealth, API_ROOT } from '../api/client'

// Amostrador de coroas Gold — verificação por RELEITURA (#CROWN-SAMPLE-VERIFY).
// Corre a Vision ATUAL sobre 177 mãos (127 sliver 9 Jul + 50 in-band) e lista as
// divergências vs o gravado, COM imagem, para o olho do Rui. NÃO escreve nada.

const C = {
  card: '#171b21', border: 'rgba(255,255,255,0.10)', text: '#e6e9ee',
  muted: '#8a93a0', yellow: '#f2c14e', red: '#d05a5a', green: '#4ea86b',
}

export default function CrownSample() {
  const [st, setSt] = useState(null)
  const [busy, setBusy] = useState(false)
  const poll = useRef(null)

  const refresh = () => ggHealth.crownSampleState().then(setSt).catch(() => {})
  useEffect(() => { refresh(); return () => clearInterval(poll.current) }, [])

  useEffect(() => {
    clearInterval(poll.current)
    if (st?.status === 'running') poll.current = setInterval(refresh, 3000)
    return () => clearInterval(poll.current)
  }, [st?.status])

  const run = async () => {
    setBusy(true)
    try { await ggHealth.crownSampleRun(); await refresh() } finally { setBusy(false) }
  }
  const cancel = async () => {
    setBusy(true)
    try { await ggHealth.crownSampleCancel(); await refresh() } finally { setBusy(false) }
  }

  const running = st?.status === 'running'
  const done = st?.status === 'done'
  const cancelled = st?.status === 'cancelled'

  return (
    <div style={{ padding: '18px 22px', color: C.text, maxWidth: 980, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, fontWeight: 800, margin: '0 0 4px' }}>Amostrador de coroas Gold</h1>
      <p style={{ color: C.muted, fontSize: 13, margin: '0 0 16px', lineHeight: 1.5 }}>
        Re-lê com o prompt ATUAL uma amostra de coroas Gold (127 do sliver de 9 Jul
        00:05–04:31 + 50 aleatórias do in-band) e lista as divergências vs o valor
        gravado. <b>Verificação — não escreve nada.</b> Onde a releitura divergir,
        é só para o teu olho decidires.
      </p>

      <div style={{ background: 'rgba(242,193,78,0.09)', border: `1px solid ${C.yellow}`,
        borderRadius: 8, padding: '10px 12px', marginBottom: 16, fontSize: 12.5,
        color: C.text, lineHeight: 1.5 }}>
        ⚠️ <b>Limitação:</b> a releitura corre sobre a cópia <b>comprimida</b> guardada
        (1280/JPEG85) — o original da Gold não é retido. Logo um <b>"—"</b> (coroa que
        some na releitura) pode ser <b>degradação da imagem, não prova</b> de erro no
        gravado. Os pares <b>valor→valor</b> (ex. $105→$55) têm muito mais peso.
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 18, flexWrap: 'wrap' }}>
        <button onClick={run} disabled={busy || running}
          style={{ background: running ? '#2a2f37' : C.yellow, color: running ? C.muted : '#0b0d10',
            border: 'none', borderRadius: 8, padding: '9px 16px', fontWeight: 700,
            cursor: busy || running ? 'default' : 'pointer', fontSize: 14 }}>
          {running ? 'A correr…' : busy ? '…' : 'Correr amostrador (177)'}
        </button>
        {running && (
          <button onClick={cancel} disabled={busy}
            style={{ background: 'transparent', color: C.red, border: `1px solid ${C.red}`,
              borderRadius: 8, padding: '9px 16px', fontWeight: 700,
              cursor: busy ? 'default' : 'pointer', fontSize: 14 }}>
            Cancelar amostrador
          </button>
        )}
        {st && st.total > 0 && (
          <span style={{ color: C.muted, fontSize: 13 }}>
            {st.done}/{st.total} lidas · {st.reread_seats} seats comparados
            {cancelled && <b style={{ color: C.red }}> · interrompido</b>}
          </span>
        )}
        {(running || done || cancelled) && (
          <span style={{ fontSize: 16, fontWeight: 800 }}>
            <span style={{ color: st.divergent_hands ? C.red : C.green }}>
              {st.divergent_hands}
            </span>
            <span style={{ color: C.muted, fontWeight: 500 }}> mãos com divergência
              {' '}({st.divergent_seats} seats) / {cancelled ? st.done : st.total}</span>
          </span>
        )}
      </div>

      {st?.error && <div style={{ color: C.red, marginBottom: 12 }}>Erro: {st.error}</div>}
      {(done || cancelled) && st.divergent_hands === 0 &&
        <div style={{ color: C.green, fontSize: 14 }}>✓ Zero divergências
          {cancelled ? ` nas ${st.done} lidas até ao corte.` : ' na amostra.'}</div>}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {(st?.divergences || []).map(d => (
          <div key={d.hand_db_id} style={{ background: C.card, border: `1px solid ${C.border}`,
            borderRadius: 10, padding: 12, display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            {d.entry_id != null && (
              <img src={`${API_ROOT}/api/screenshots/image/${d.entry_id}`} alt="gold"
                onError={e => {
                  e.currentTarget.style.display = 'none'
                  const n = e.currentTarget.nextSibling
                  if (n) n.style.display = 'flex'
                }}
                style={{ width: 300, maxWidth: '100%', borderRadius: 8, objectFit: 'contain',
                  border: `1px solid ${C.border}`, background: '#000' }} />
            )}
            {d.entry_id != null && (
              <div style={{ display: 'none', width: 300, maxWidth: '100%', minHeight: 120,
                alignItems: 'center', justifyContent: 'center', borderRadius: 8,
                border: `1px dashed ${C.border}`, color: C.muted, fontSize: 12 }}>
                imagem indisponível — abre a mão
              </div>
            )}
            <div style={{ flex: 1, minWidth: 240 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                <Link to={`/hrc-results/hand/${d.hand_db_id}`}
                  style={{ color: C.yellow, fontWeight: 700, fontSize: 14, textDecoration: 'none' }}>
                  {d.hand_id}
                </Link>
                <span style={{ color: C.muted, fontSize: 12 }}>{d.tournament}</span>
                {d.sliver && <span style={{ fontSize: 11, color: '#0b0d10', background: C.yellow,
                  borderRadius: 4, padding: '1px 6px', fontWeight: 700 }}>sliver</span>}
              </div>
              <table style={{ marginTop: 8, fontSize: 13, borderCollapse: 'collapse', width: '100%' }}>
                <thead>
                  <tr style={{ color: C.muted, textAlign: 'left' }}>
                    <th style={{ padding: '2px 8px 2px 0' }}>Seat</th>
                    <th style={{ padding: '2px 8px' }}>Gravado</th>
                    <th style={{ padding: '2px 8px' }}>Releitura</th>
                  </tr>
                </thead>
                <tbody>
                  {d.seats.map((s, i) => (
                    <tr key={i}>
                      <td style={{ padding: '2px 8px 2px 0' }}>{s.seat}</td>
                      <td style={{ padding: '2px 8px', color: C.text }}>
                        {s.stored == null ? '—' : `$${s.stored}`}
                      </td>
                      <td style={{ padding: '2px 8px', color: C.red, fontWeight: 700 }}>
                        {s.reread == null ? '—' : `$${s.reread}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
