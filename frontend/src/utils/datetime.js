// Timestamps da API (played_at, created_at, discord_posted_at) vêm em UTC (ISO
// com offset). A app mostra SEMPRE em hora de Lisboa — storage=UTC, display=Lisboa.
// Ver tech debt #GG-PLAYED-AT-LOCAL-NOT-UTC: a HH GG era gravada em local sem fuso;
// o parser passou a normalizar para UTC, e o display reconverte UTC→Lisboa.
const LISBON = 'Europe/Lisbon'

// "YYYY-MM-DD" no fuso de Lisboa (en-CA produz esse formato ISO de data).
export function isoDateLisbon(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-CA', { timeZone: LISBON })
}

// Data/hora em pt-PT, fuso de Lisboa. `opts` = Intl.DateTimeFormat options.
export function dateTimeLisbon(iso, opts = {}) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('pt-PT', { timeZone: LISBON, ...opts })
}
