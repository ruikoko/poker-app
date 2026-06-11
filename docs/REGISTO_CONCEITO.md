# REGISTO DE CONCEITO — alterações ao conceito da app e aos seus elementos

Registo **cumulativo, append-only**. Sempre que uma sessão **altera o CONCEITO da app
ou um dos seus ELEMENTOS** (uma regra de negócio, uma lei, a semântica de um conceito,
uma fonte de input, uma decisão de arquitectura), **acrescenta aqui uma linha** com
**data + resumo + motivo + referência** (ficheiro:secção / journal). Não substituir
entradas antigas — só acrescentar (o histórico é o valor).

**Regra de manutenção (FLUXO):** isto é **checklist obrigatório de fecho de sessão** —
quem mexeu em conceito/elemento e não apendou aqui, não fechou a sessão.

Formato: `- AAAA-MM-DD — <resumo numa linha>. **Porquê:** <motivo>. → <referência>`

---

## 2026-06-10 (pt64–pt67)

- 2026-06-10 — **LEI Max Players (HRC)** = **span posicional âncora→BB, teto 6** (não a contagem de participantes). **Porquê:** o HRC Hand Mode tem de refletir os jogadores entre a decisão e a BB; subcontava com herói tardio. → `REGRAS_NEGOCIO §15`; `JOURNAL pt67`.
- 2026-06-10 — **LEI da âncora da 2ª run** = **LEI B: âncora = a POSIÇÃO certa; a linha é indiferente**. **Porquê:** o Selected Subtree recalcula o ponto de decisão inteiro da posição (qualquer linha dá o mesmo âmbito) → o off-by-one within-bucket é inofensivo; o que importa é acertar a posição. → `REGRAS_NEGOCIO §16`; `HRC_ANATOMIA §14`.
- 2026-06-10 — **Semântica do Selected Subtree do HRC** (descoberta, fonte = 3 fotos do Rui na 4ª volta): recalcula o **ponto de decisão INTEIRO da posição-âncora + tudo a JUSANTE; posições a MONTANTE congeladas**. Estratégia = distribuição mista única → redistribui massa por todas as linhas da posição. **Porquê:** funda a LEI B e corrige a leitura errada "irmãos disjuntos". → `HRC_ANATOMIA §14.2`.
- 2026-06-10 — **Regra dos sizings por stack efetiva** confirmada como lei do Rui: raise non-all-in com **eff ≤ 25 BB → emite `[size, ALLIN]`**; **eff > 25 BB → só `[size]`**; open "pequeno" 2 BB só com eff > 8 BB e não-blind. **Stack efetiva** = `min(stack do raiser, maior stack adversário activo) / BB`, por acção. **Porquê:** condiciona a estrutura de betting gerada para o HRC. → `hrc_script_gen.py:51,60`; `HRC_ANATOMIA §14`.
- 2026-06-10 — **Bounty mode** passa a vir da **estrutura importada** (deixa de forçar PKO 50% no robot). **Porquê:** suportar PKO 75/40, Super KO, etc. sem hardcode. → `JOURNAL pt66` (fix d); `HRC_ANATOMIA §13`.
- 2026-06-11 — **Âmbito de disco no PC principal = só os paths listados** (intocáveis + `Batmen\`); procura fora exige autorização escrita do Rui. **Porquê:** o Code varreu pastas fora do âmbito (pt68) à procura da GG. → `FLUXO §11`, `CLAUDE.md` (ÂMBITO DE DISCO).
- 2026-06-11 — **HH/TS do GG vivem no BACKOFFICE do Rui (fora do PC)** — ele descarrega e coloca à mão em `gg_hh`/`gg_ts`; nunca procurar no disco o que é do ritual manual dele. **Porquê:** corrige o entendimento de que a GG estaria nalgum path local. → `FLUXO §11`.
- 2026-06-11 — **Desktop do Beelink (`riand`) = ZONA LIMPA** (só o atalho do HRC + o que o runbook listar). Runtime vive em `HRCWatch\` (watcher), `C:\hrc\adapter\` (adapter), packs (templates). O `instala_ptXX.bat` passa a varrer `*.bak`/`*.exe.backup-*` além de `*.exe`. **Porquê:** 3+ exes-backup renomeados (~13 MB) sobreviveram no Desktop por extensão → violam a regra «1 só exe». → `CLAUDE.md` (REGRA PERMANENTE — 1 só watcher exe).
- 2026-06-11 — **Regra dos 25 BB CONFIRMADA pelo Rui** + stack efetiva = `min(stack raiser, MAIOR adversário activo)/BB` por acção. **Porquê:** desbloqueia o fix do `#HRC-NODE-OFFSET-IMPLICIT-LINES`. → `REGRAS_NEGOCIO §17`.
- 2026-06-10 — **Cap de upload de resultados HRC = 200 MB (INTERINO)**. **Porquê:** árvores Max=5 (Complete Export = árvore inteira) chegam a ~112 MB e batiam no cap de 50 MB (413). Arquitectura **definitiva em aberto** (A/B/C: chunked/compressão/poda — 72×112 MB≈8 GB BYTEA é insustentável); rede de salvação manual = `/hrc-sessions` (`/import`, sem cap). → `queue.py:53`; `#HRC-RESULT-ZIP-413`.
