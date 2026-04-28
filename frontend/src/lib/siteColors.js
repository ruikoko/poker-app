// Tech Debt #13b — paleta unificada para cores das salas
//
// Após #13a (centralização) e decisão estética Rui em #13b, a app passa a usar
// 1 paleta única para todas as salas. Substitui as 3 paletas distintas que
// existiam em Villains.jsx / Dashboard.jsx / HandRow.jsx.
//
// Aliases SITE_COLORS_VILLAINS / SITE_COLORS_DASHBOARD / SITE_COLORS_HANDROW
// mantidos durante a transição para retrocompatibilidade — todos apontam para
// a mesma const SITE_COLORS. Limpeza de aliases fica como housekeeping futuro
// após validação visual em prod.

export const SITE_COLORS = {
  Winamax:    '#dc2626',  // vermelho
  WPN:        '#22c55e',  // verde
  GGPoker:    '#3b82f6',  // azul
  PokerStars: '#facc15',  // amarelo
}

export const SITE_COLOR_DEFAULT = '#6366f1'  // índigo (fallback p/ salas não-mapeadas, ex: 888poker)

// ── Aliases legacy (retrocompat #13a) ────────────────────────────────────────
// Apontam todos para a paleta unificada. Callers podem importar qualquer alias
// durante a transição; pós-validação visual Rui, podemos consolidar todos os
// imports para SITE_COLORS directamente.

export const SITE_COLORS_VILLAINS = SITE_COLORS
export const SITE_COLORS_DASHBOARD = SITE_COLORS
export const SITE_COLORS_HANDROW = SITE_COLORS
