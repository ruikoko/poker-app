// Tech Debt #13b — paleta unificada para cores das salas.
// Após #13a (centralização) e decisão estética Rui em #13b, a app usa 1
// paleta única para todas as salas (Villains/Dashboard/HandRow).
// Aliases legacy removidos em #13c (pt12).

export const SITE_COLORS = {
  Winamax:    '#dc2626',  // vermelho
  WPN:        '#22c55e',  // verde
  GGPoker:    '#3b82f6',  // azul
  PokerStars: '#facc15',  // amarelo
}

export const SITE_COLOR_DEFAULT = '#6366f1'  // índigo (fallback p/ salas não-mapeadas, ex: 888poker)
