// Convenção pt51: as horas-de-evento da API (played_at, discord_posted_at,
// start_time, captured_at) vêm já em hora de LISBOA, NAIVE (ISO sem offset) —
// mostram-se tal e qual, sem conversão. Os timestamps de metadados de registo
// (created_at, uploaded_at) continuam em UTC (ISO com offset/Z) e reconvertem-se
// UTC→Lisboa. Esta util distingue os dois pela presença (ou não) de fuso no ISO.
const LISBON = 'Europe/Lisbon'
const HAS_TZ = /([zZ]|[+-]\d{2}:?\d{2})$/

// Componentes de um ISO naive → Date no fuso do browser com o MESMO wall-clock
// (assim toLocaleString sem timeZone mostra exactamente esse wall-clock, seja
// qual for o fuso do browser).
function naiveLocalDate(iso) {
  const m = iso.match(/(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/)
  if (!m) return null
  return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0))
}

// "YYYY-MM-DD" em Lisboa.
export function isoDateLisbon(iso) {
  if (!iso) return ''
  if (!HAS_TZ.test(iso)) return iso.slice(0, 10)   // naive = já Lisboa → directo
  return new Date(iso).toLocaleDateString('en-CA', { timeZone: LISBON })
}

// Data/hora em pt-PT, hora de Lisboa. `opts` = Intl.DateTimeFormat options.
export function dateTimeLisbon(iso, opts = {}) {
  if (!iso) return ''
  if (!HAS_TZ.test(iso)) {
    const d = naiveLocalDate(iso)
    if (d) return d.toLocaleString('pt-PT', opts)   // sem timeZone: wall-clock directo
  }
  return new Date(iso).toLocaleString('pt-PT', { timeZone: LISBON, ...opts })
}
