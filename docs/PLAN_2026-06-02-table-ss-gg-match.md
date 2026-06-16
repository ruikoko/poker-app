> ⚠️ **SUPERSEDED (P1) pela DECISÃO pt73 (2026-06-16) — hand-id do filename.** O match
> SS de mesa ↔ mão GG (Pergunta 1: QUAL é a mão) passa a ser PRIMARIAMENTE por **hand-id
> extraído do nome do ficheiro** (TM antes do timestamp → `GG-{TM}`), determinístico, que
> **mata o multi-tabling de raiz**. O desenho central deste plano — **nome-directo +
> impressão digital (hero_stack ±20% + big_blind)** — fica **REDUZIDO a FALLBACK** (só
> quando o ID falta no nome, formato antigo). **DECIDIDO / POR IMPLEMENTAR — ainda NÃO no
> código.** A parte de **cobertura `players_left`** (alvo `#HRC-MTT-STACKS-PAGE-SKIPPED`)
> mantém-se válida. Nota: o hand-id resolve só P1; o "quem senta onde" (P2, bug dos vilões
> trocados) continua aberto. Ver `docs/DESANON_ANATOMIA.md` + `REGISTO_CONCEITO` 2026-06-16.

# PLAN — Match SS de mesa ↔ mão GG (multi-tabling) + cobertura players_left

**Data:** 2026-06-02. **Tipo:** investigação read-only (zero código alterado) + plano para a próxima sessão.
**Origem:** a partir do `#HRC-MTT-STACKS-PAGE-SKIPPED-ON-NULL-PLAYERS-LEFT` — o HRC colapsa o ICM à
final table dos sentados quando `players_left=None`. O caminho per-mão fidedigno é o pipeline de
SS de mesa (Intuitive Tables → Vision → `table_ss_processing_log` → `hands.context_table_ss_id`).
O Rui fez uma importação em massa dos SS do IT e a maioria não ligou. Esta sessão diagnosticou
porquê e desenhou o fix.

> **Nota:** toda a evidência abaixo veio de queries read-only à BD de produção (proxy público
> `ballast.proxy.rlwy.net`, padrão pt37+). Os números mexem (o Rui ainda estava a importar);
> ler em proporções.

---

## 1. O que descobrimos (diagnóstico)

### 1.1 Como o `players_left` chega à mão (`queue_export._resolve_players_left`)
3 fontes, por prioridade:
1. `hand["players_left"]` — coluna inexistente em `hands` → **nunca dispara**.
2. **Table-SS (Intuitive Tables)** — `hands.context_table_ss_id` → `table_ss_processing_log.players_left`.
   Per-mão, fidedigno. Adicionado pt38 (`61fe349`).
3. **Lobby (#lobbys)** — `lobby_processing_log.players_left` por `tournament_number`, **snapshot mais
   recente, SEM janela temporal** → aplica o mesmo número a TODAS as mãos do torneio.

`total_chips` no `meta.json` está **hardcoded `None`** (`queue_export.py:1113`, legacy). O `chips` da
estrutura (`payouts.json structures[0].chips`) é outra coisa: `lobby_vision` calcula `avg_stack ×
players_left` (∴ também depende do players_left). Conclusão: o HRC nunca recebe um Total Chips útil
por esta via.

### 1.2 Cobertura sobre o pipeline HRC (não sobre todo o arquivo)
Conjunto elegível real (gates de `select_andar1_rows`, janela default 30d): **367 mãos** (80 GG,
283 WN, 4 PS). Destas: **56% sem `players_left`**, 39% via lobby (per-torneio, grosseiro), **só 5%
via table-SS (per-mão, o bom)**. O 5% é baixo porque o input (SS do IT) ainda não estava todo
importado — não é defeito do mecanismo.

### 1.3 Resultado da importação em massa dos SS do IT
- 85 SS na BD, 82 com `players_left`; **só 42 mãos ligadas**.
- **Timezone OK** — nas que ligaram, `captured_at` vs `played_at` tem offset médio **+0.3 min** (±1 min).
  A conversão filename (Lisboa) → UTC está certa.
- Taxa de ligação por site: **Winamax 73%** (38/52) vs **GGPoker 33%** (26/79) vs WPN 11%.

### 1.4 Causa raiz da diferença GG vs WN — densidade de multi-tabling
| Site | torneios concorrentes na janela ±5min (média) | máx | SS "limpos" (1 só torneio) |
|---|---|---|---|
| Winamax | 1.6 | 4 | 16/52 |
| **GGPoker** | **3.2** | **8** | **0/79** |
| WPN | 0.3 | 1 | — |

O Rui joga **muitas mesas GG ao mesmo tempo** (até 8). Ao segundo da captura, há mãos de várias
mesas na janela → **a hora sozinha não desempata** (a mão da foto nem é a mais próxima no tempo:
num caso real, a +42s era de OUTRO torneio, a do torneio certo estava a +73s). É preciso um sinal
**por-mão** para escolher a mesa.

### 1.5 Onde o matcher falha (`table_ss.py:_resolve_match`)
- Match é **temporal-primeiro** (candidatos = mãos do mesmo site, ±5min, `study_state != 'mtt_archive'`,
  `tournament_number` presente — `_find_candidate_hands:225`).
- No ramo **single_tn**: valida nome via `name_tokens_subset` (guard pt39, correcto).
- No ramo **multi-tn (multi-tabling)**: desambigua via `resolve_tournament_number` (**resolver externo
  frágil**) — NÃO compara o nome da imagem directamente com o nome das mãos candidatas. É aqui que parte.

### 1.6 Atribuição das falhas GG (99 SS GG falhados)
- **68/99 não têm NENHUMA mão GG na janela ±5min** → o momento/mão **não está importado** (nem em arquivo).
- **0/99 só-arquivo** → NÃO é problema de promoção arquivo→estudo.
- **31/99 têm mão na janela**; destes **~9 deviam ligar** (nome fiel ou fingerprint) e o matcher falha
  por usar o resolver.
- **2/99** (`EXPLORER 150K`, `GALACTI`) são **Winamax mal classificados como GGPoker pelo Vision** →
  bug de site, não de nome.

### 1.7 Regras de domínio (corrigidas pelo Rui — IMPORTANTE)
- **GG: nomes FIÉIS, prefixos de série para MANTER.** `250-H:` / `211-H:` é o discriminador do evento
  de série (variante H/M + nº). **NÃO limpar o GG.** (Confirmado: 72/99 nomes "GG" correspondem a um
  torneio GG real na BD.)
- **Winamax: nome clean.** O `#013`/`#032` que aparece no SS é o **nº de mesa do cliente** → lixo a
  aparar. Já tratado por `clean_tournament_name` (pt39): `_TABLE_SUFFIX_RE = r"\s*#\d+\s*$"` apara só
  `#NNN` **trailing**.
- **Winamax: o garantido fica.** Um número que seja o GTD (`€100.000 GTD`, `$70,000 GTD`) é parte do
  nome real e **não tem `#`** → a regra acima não lhe toca. Prefixo de série Winamax (`#220 - W SERIES`)
  também fica (o `#` não está no fim).

### 1.8 Viabilidade da impressão digital (fingerprint)
Sinal por-mão = **stack do Hero + blinds**, ambos no SS (`vision_json.hero_stack_bb`,
`blinds_level.big_blind`) e na mão (`all_players_actions._meta.bb` + hero `stack`/`is_hero`).
Teste em prod sobre os 31 SS GG falhados com candidato: **6 resolvem um torneio único, 0 ambíguos**
(blinds exacto + stack ±20%). O nome-directo-fiel dá resultado equivalente (5, 0 ambíguos). Os ~25
restantes não batem porque o torneio do SS não tem mão na janela (≡ não importado). **NÃO usar
`hero_position`** (roda a cada mão → frágil ao desfasamento de 1 mão). `players_left` é um número de
torneio (muda devagar) → SS da mão a seguir continua a dar o valor certo.

---

## 2. O que vamos fazer (plano para a próxima sessão)

### 2.1 Fix do match em `_resolve_match` (chokepoint único — usado pelo upload ao vivo E pelo re-link)
`relink_orphan_table_ss` (`table_ss.py:361`) usa o mesmo `_find_candidate_hands` + `_resolve_match`
(391-392). **Logo este fix faz com que, quando o Rui importar as HH em falta, o re-link automático
ligue os SS GG de multi-tabling** (hoje ressaltariam no resolver de nomes).

Desenho (ramo **multi-tn** apenas; single_tn e WN-que-já-funciona intactos):
1. **Nome directo por-site** contra os candidatos:
   - GG → nome **fiel** (sem limpeza, prefixos de série mantidos).
   - WN → `clean_tournament_name` (apara só `#NNN` de mesa; garantido/prefixo preservados).
   - Se exactamente **um** torneio candidato bate → liga. `reason="disambiguated_by_name_direct"`.
2. **Fallback: impressão digital** — `big_blind` exacto + `hero_stack_bb` ±`_FINGERPRINT_STACK_TOL`
   (0.20). Se exactamente **um** torneio bate → liga. `reason="disambiguated_by_fingerprint"`.
3. **Último recurso:** o `resolve_tournament_number` actual (ou largá-lo). Senão → `multi_tn_unresolved`.

Mudanças concretas:
- `_find_candidate_hands` SELECT: **+ `all_players_actions`** (para o fingerprint ler bb + hero stack).
- `import json` no topo (defensivo a apa str/dict).
- 2 helpers novos: `_hero_fp_from_hand(apa) -> (hero_stack_bb, big_blind)` e
  `_fingerprint_tn(vj, candidates) -> tournament_number|None` (só aceita se UM torneio bate; 0 falsos
  positivos garantidos — devolve None se 0 ou >1).
- Comparação de nome directa contra `candidates` (não via resolver) no ramo multi-tn.
- **Guards:** single_tn intacto (guard pt39); WN intacto; 0 falsos positivos (validado em 31).
- Testes novos em `test_table_ss.py` (os existentes passam — candidatos mock sem `all_players_actions`
  → fingerprint None → cai no comportamento legacy).

Diff completo desenhado em buffer nesta sessão (ver histórico do chat / reconstruir a partir deste
plano). **Não foi aplicado.**

### 2.2 Importar as HH GG em falta (o bloqueio dominante)
68/99 dos SS GG falham porque a mão do momento **não está importada**. Depois do fix 2.1 estar no
sítio, importar os zips de HH GG em falta → o re-link liga-os por nome-fiel/fingerprint. **Ordem
sugerida: 2.1 ANTES de 2.2**, senão o re-link volta a falhar no resolver de nomes.

### 2.3 Bug à parte — Vision classifica mal o site (Winamax → GG)
2 SS (`EXPLORER 150K`, `GALACTI`) marcados `GGPoker` sendo Winamax. Abrir tech debt
`#TABLE-SS-VISION-SITE-MISCLASS` (LOW). Candidato: o prompt do `table_ss_vision` reforçar a
detecção de site, ou um pós-passo que corrige o site quando o nome bate um torneio de outro site.

### 2.4 (Contexto) O objectivo final continua a ser `#HRC-MTT-STACKS-PAGE-SKIPPED`
Mais cobertura de `players_left` per-mão (via table-SS bem ligado) → menos mãos a colapsar o ICM à
FT no HRC. O fix 2.1 + import 2.2 sobem a fatia "per-mão" muito acima dos 5% actuais.

---

## 3. Decisões/constantes fixadas nesta sessão
- `_FINGERPRINT_STACK_TOL = 0.20` (±20% absorve 1-2 mãos de drift; stacks entre mesas concorrentes são
  muito diferentes → 0 colisões em 31 SS).
- Blinds: match **exacto** do `big_blind`.
- `hero_position`: **NÃO usar** (roda por mão).
- GG: **nunca limpar** o nome. WN: manter `clean_tournament_name` (só `#NNN` trailing).
- Match continua **temporal-primeiro** (shortlist da janela) + nome/fingerprint para **escolher a mesa**.

## 4. Cross-ref tech debts
- `#HRC-MTT-STACKS-PAGE-SKIPPED-ON-NULL-PLAYERS-LEFT` (HIGH, aberto) — alvo final.
- `#TABLE-SS-PIPELINE-DEPENDENCIES` (MED) — o linking depende do resolver; este fix reduz essa dependência.
- `#TABLE-SS-RESOLVER-COLLISION` (fechado pt39) — o guard de nome que mantemos no single_tn.
- Novo a abrir: `#TABLE-SS-GG-MULTITABLING-MATCH` (este plano) + `#TABLE-SS-VISION-SITE-MISCLASS`.
