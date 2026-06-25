# APRENDIZADOS_HRC.md

Conclusões **empíricas** de estudo sobre o HRC e a pipeline — para consulta futura.
Não é anatomia mecânica (isso vive em `HRC_ANATOMIA_OPERACIONAL.md`) nem código:
são **aprendizados** de "o que mexe a estratégia / o que não mexe", com as ressalvas
honestas de cada um. Append-only; cada entrada datada.

---

## #APRENDIZADO-CI-16-VS-10 — CI 16 vs CI 10 não muda a estratégia (caso campo largo) — 24 Jun 2026

**Mão:** `GG-6084129607` (campo largo, multiway, stacks 18–81bb, `multi_table_icm`).

**Teste:** a MESMA run, dois retratos — **CI 16** (cedo) vs **CI 10** (atingido ~45 min
depois) — comparando as estratégias contra o open do HJ.

**Resultado: as ESTRATÉGIAS NÃO MUDAM entre CI 16 e CI 10.**
- **Sizes idênticos** nos dois retratos: open 2.0; 3-bets 4.60 / 6.00 / 8.00 / 18.0;
  jams 49.4 / 80.1 / 35.4. Nenhum size aparece, desaparece ou muda.
- **Ações idênticas por posição** (call / 3bet / jam) — nenhuma mão salta de fold para
  3-bet (nem o inverso).
- **Frequências** oscilam no máximo **~0.9 ponto percentual** (CO call 1.8→2.4; BU call
  1.7→2.5; resto em décimos; SB praticamente congelado). É **ruído de convergência**,
  não decisão.

**Conclusão prática:** para mãos deste tipo (campo largo, multiway, stacks médias),
**CI 16 entrega a mesma estratégia de estudo que CI 10** — os ~45 min extra para descer
a 10 não mudam nenhuma decisão. Suporta a regra operacional **"trees caras → CI mais
alto sem perda de qualidade de estudo"**.

**⚠️ RESSALVAS (honestidade — ler junto da conclusão):**
1. **É UM caso.** Não generalizar para spots **muito marginais** (ICM apertado, bolha)
   sem testar — aí os últimos pontos de CI **podem** mexer numa decisão.
2. **Esta tree tinha o bug do all-in contaminado** (`#GTO-OPEN-SIZE-NOT-PER-POSITION`,
   fechado em pt89) — estava **inflada**. Após o fix, os **tempos de convergência mudam**;
   a **regra final de CI deve ser fixada DEPOIS do fix**, com tempos reais. Esta entrada
   mede *estratégia* (que é robusta ao CI), não *tempo* (que muda com o fix).
