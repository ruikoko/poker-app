# Próxima sessão — análise quick scan dos 9 itens em backlog

**Data:** 29 Abril 2026 (sessão de análise prévia, sem implementação)
**Âmbito:** quick scan dos 9 itens em backlog após Pipeline 1 fechado + Tech Debt #9. Inclui 4 Tech Debts novos (#10/#11/#12/#13), 1 anomalia histórica (hand 253), 1 bug latente (mtt.py:786) e 3 housekeeping (#6 endpoint legacy, #7 dead code HM3.jsx, #8 consolidação 8 PokerCard).
**Regras seguidas:** análise por leitura de código real (sem especulação), sem alterações de código, sem commits, sem testes em prod. Q2 (#10) confirmado via SELECT no Railway dashboard pelo Rui.

---

## 1. Sumário executivo

| # | Nome | Tipo | Severidade | Esforço | Prioridade sugerida |
|---|---|---|---|---|---|
| 5 | Bug latente `mtt.py:786` | Bug latente | Latente | ~10 min | Quick win 1 |
| 7 | Dead code HM3.jsx | Housekeeping | Cosmético | ~5 min | Quick win 2 |
| 9 | Anomalia hand 253 | Bug histórico (já fixed) | Histórica | ~15 min validação SQL | Após Pipelines 2-5 |
| 10 | Truncamento parser Winamax | Bug | Funcional | ~1h fix + 10 min cleanup | Bug — primeiro |
| 11 | Botão × eliminar villain | Feature | UX | ~2h (Opção A) | Feature simples |
| 13 | Landing Vilões + filtros sala | Feature | UX | ~1h30 + decisão paleta | Feature simples |
| 12 | Re-arquitectura modal Vilões | Feature major | UX major | ~6-8h | Sessão dedicada |
| 8 | Consolidação 9 PokerCard locais | Housekeeping | Cosmético | ~4-5h | Baixa prioridade |
| 6 | Housekeeping endpoint legacy `/api/villains` | Housekeeping | Cosmético | ~30 min | **BLOQUEADO POR #12** |

**Esforço total: ~25-30h** espalhado por várias sessões.

---

## 2. Análises individuais

### [5] Bug latente `mtt.py:_create_ggpoker_villain_notes_for_hand`

- **Tipo:** Bug latente (code smell idêntico ao corrigido em Tech Debt #9)
- **Severidade:** Latente (não se manifesta em prod hoje — call-sites comitam antes)
- **Localização (path:linha):** `backend/app/routers/mtt.py:766-851`; uso de `_q()` na linha **791-795**.
- **Confirmação:** Mesmo padrão exacto: função recebe `conn` como parâmetro mas usa `from app.db import query as _q` para ler `all_players_actions, raw FROM hands WHERE id=%s`. Cross-connection.
- **Por que NÃO se manifesta:**
  - `screenshot.py:1445` — `_enrich_hand_from_orphan_entry` faz `conn.commit()` em `screenshot.py:1427` antes; `_q()` em conn nova vê o estado.
  - `mtt.py:1860 e mtt.py:1993` (`/mtt/rematch`) — também passam por `_enrich_hand_from_orphan_entry` (commit interno) antes do call.
- **Risco futuro:** Se alguém remover o commit intermédio do `_enrich_hand_from_orphan_entry`, ou criar novo call-site batch, repete-se o Tech Debt #9.
- **Alteração proposta:** Substituir `_q()` por `with conn.cursor() as _cur` (mesmo pattern aplicado preventivamente no `_create_villains_for_hand` em commit `630dc73`). 4 linhas + comentário.
- **Esforço re-estimado:** ~10 min.
- **Edge cases / dúvidas:** Nenhuma — fix mecânico idêntico ao já feito em mtt.py:660-668.
- **Pré-requisitos:** Não.

---

### [7] Dead code HM3.jsx (`ACTION_COLORS` / `actionStyle` / `ActionBadge`)

- **Tipo:** Housekeeping
- **Severidade:** Cosmético
- **Localização (path:linha):**
  - `frontend/src/pages/HM3.jsx:27-34` (`ACTION_COLORS`)
  - `frontend/src/pages/HM3.jsx:103-112` (`actionStyle`)
  - `frontend/src/pages/HM3.jsx:114-117` (`ActionBadge`)
- **Confirmação dead:** Grep no projecto inteiro: zero callers fora destas linhas. Hands.jsx tem cópias suas (linhas 212, 221, 232, 299) que **ainda usa** internamente (analisar separadamente). Em HM3.jsx, **dead confirmado**.
- **Alteração proposta:** Apagar linhas 27-34, 103-112, 114-117 (~21 linhas). Sem outras mudanças.
- **Esforço re-estimado:** ~5 min.
- **Edge cases / dúvidas:** Nenhuma — bloco isolado, sem imports externos.
- **Pré-requisitos:** Não.

---

### [9] Anomalia hand 253 — regra B aplicada à mão, não ao player

- **Tipo:** Bug histórico (já corrigido no helper actual)
- **Severidade:** Funcional **histórica** (rows espúrios em BD pré-wipe). Estado actual em prod (pós-wipe Pipeline 1) NÃO tem o bug — 0 rows `cat='sd'`.
- **Localização (path:linha):** `backend/app/services/hand_service.py:25-88` — função `_classify_villain_categories`.
- **Análise da regra B:** Linha 75 já filtra correctamente:
  ```python
  if has_real_match and hand_meta.get('has_showdown') and has_cards:
      cats.add('sd')
  ```
  Os 2 call-sites (`mtt.py:719, 732` e `hm3.py:825, 839`) passam `has_cards` correctamente.
- **Origem do bug histórico:** O backfill SQL ad-hoc da sessão 28-Abr (Tech Debt #4 Parte B) que populou os 49 rows `cat='sd'` iniciais aplicou a regra ao nível MÃO, sem filtrar `player.cards != None`. Hand 253 (jogador `Upstakes_io` que foldou pré-flop) foi resíduo.
- **Confirmação via backup pré-wipe:** Hand 253 era GG-5873690756, $150 Saturday Secret KO Mystery Bounty, played_at 2026-04-26 00:41:50 UTC. 7 jogadores, **só 2 mostraram cards** (Hero `Lauro Dermio` com [3d Kc] e villain1 `BBHDAMT7ang..` com [Qd Jd]). Apenas villain1 deveria ter sido marcado `cat='sd'`. `Upstakes_io` foldou preflop, sem cards — entrada espúria.
- **Alteração proposta:**
  - **Código:** **NENHUMA** — helper já está correcto.
  - **Validação one-shot Opção A (aprovada):** Após Pipelines 2-5 estarem populados, correr query auditoria:
    ```sql
    SELECT hv.hand_db_id, hv.player_name FROM hand_villains hv
    JOIN hands h ON h.id=hv.hand_db_id
    WHERE hv.category='sd'
      AND NOT EXISTS (SELECT 1 FROM jsonb_each(h.all_players_actions) p
                      WHERE p.key=hv.player_name AND p.value->'cards' IS NOT NULL);
    ```
    Se devolver 0 rows → confirmado limpo. Se >0 → `DELETE` os rows espúrios.
- **Esforço re-estimado:** ~15 min (só verificação SQL pós-pipelines, sem código).
- **Edge cases / dúvidas:** Nenhuma.
- **Pré-requisitos:** Pipelines 2-5 estarem validados (hoje só Pipeline 1 tem dados).

---

### [10] Bug parser truncamento nicks Winamax (CONFIRMADO)

- **Tipo:** Bug
- **Severidade:** Funcional (cria villains espúrios)
- **Localização (path:linha):** `backend/app/routers/hm3.py:688` (regex non-greedy sem âncora forte) + `hm3.py:717` (check `in` em vez de `startswith`).
- **Causa raiz CONFIRMADA via inspecção raw HH (Rui):**
  - **Hand 102** (Winamax MAIN EVENT SPACE KO 120K, 26-Abr 19:38:24): 6 seats incluindo `la louffe`. Não há jogador `la` real — `'la'` é truncamento.
  - **Hand 126** (Winamax ZENITH, 26-Abr 18:37:34): 5 seats incluindo `La m3nace`. Não há jogador `La` real — `'La'` é truncamento.
  - **Padrão comum:** ambos os nicks problemáticos têm ESPAÇO.
- **Análise técnica do bug:**
  - **Linha 688:** `re.match(r"^(.+?)(?::)?\s+(.+)$", line)` — sem âncora forte no fim (apenas `(.+)$`). Para input `"la louffe goes all-in 12000"`, regex devolve `actor="la"`, `action_text="louffe goes all-in 12000"`.
  - **Linha 717:** `elif "all-in" in action_text or "all in" in action_text` — usa `in` (não `startswith`). Confirma `is_vpip=True` mesmo com nick truncado.
  - **Resultado:** `vpip_players["la"] = "all-in"` → entra como candidato → cria row `hand_villains.player_name='la'` separado.
- **Por que as outras regexes (1609, 1647, 55) não disparam:** todas têm âncora forte (`(folds|checks|calls|bets|raises)` ou `shows`) que força regex engine a backtrack até `(.+?)` cobrir o nick completo.
- **Alteração proposta — DECISÃO RUI PENDENTE:**
  - **Opção A (mínima, defensiva):** validar `actor` em 688 contra a lista de seats parseados — se `actor not in {seats[i].name}`, ignorar. Robusto para QUALQUER regex parser que trunque.
  - **Opção B (cirúrgica):** alterar regex 688 para exigir keyword poker no fim: `r"^(.+?)(?::)?\s+(folds|checks|calls|bets|raises|posts|shows|wins|collected|goes|is)\b.*$"`. Mais frágil.
- **Backfill cleanup:** Após fix em prod, correr SQL:
  ```sql
  DELETE FROM hand_villains WHERE player_name IN ('la', 'La') AND hand_db_id IN (102, 126);
  ```
  Ou query mais robusta: identificar nicks `hand_villains` cujo `player_name` é prefixo de outro `player_name` na mesma `hand_db_id` (varre todas as 159 hands).
- **Esforço re-estimado:** ~1h (fix Opção A) + ~10 min (backfill SQL cleanup).
- **Edge cases / dúvidas:** Validar listagem completa de hands afectadas (não só 102/126). Hands com nicks ≤3 chars são candidatos a falsos truncamentos — precisa de cross-check contra all_players_actions seats.
- **Pré-requisitos:** Decisão Rui Opção A vs B antes de implementar.

---

### [6] Housekeeping endpoint legacy `/api/villains`

- **Tipo:** Housekeeping
- **Severidade:** Cosmético
- **Localização (path:linha):** `backend/app/routers/villains.py:102-150` (`list_villains`); endpoints relacionados que dependem de `villain_notes`: `/{id}` (245), `POST` (253), `PUT` (272), `DELETE` (289), `recalculate-hands` (436).
- **Análise dos call-sites frontend:**
  - `client.js:88` — `villains.list({...})` ainda chama `/villains` legacy.
  - **3 callers ainda activos:**
    1. `Dashboard.jsx:128` — recent villains panel (`page_size: 5, sort: 'updated_desc'`)
    2. `Villains.jsx:520` — auto-abrir perfil quando vem `?nick=` na URL.
    3. `Villains.jsx:562` — `openModal(nick)`: faz fetch ao endpoint legacy para obter o `id` numérico de `villain_notes` (necessário para o modal `VillainProfile` poder fazer `villains.update(id)` ao gravar nota — ver linha 89).
- **Conclusão:** O endpoint legacy **NÃO é removível** sem antes:
  1. Migrar `Dashboard.jsx:128` "recent villains" para `/categorized` (não tem `sort=updated_desc` hoje — adicionar suporte).
  2. Resolver o adapter em `Villains.jsx:560-569`: o modal `VillainProfile` precisa de `id` para `villains.update(id, {note, tags})` — significa criar `PUT /api/villains/categorized/by-nick/{nick}` ou similar para gravar nota sem `villain_notes.id`.
- **Alteração proposta:** **NÃO eliminar agora.** Re-classificar como pré-requisito **invertido** de Tech Debt #12 (re-arquitectura modal Vilões), que vai eliminar painel Notas+Tags do modal — e com isso desaparecem as updates a `villain_notes`. Pós-#12, eliminar legacy fica trivial.
- **Esforço re-estimado:** 0h agora (BLOQUEADO POR #12); ~30 min pós-#12 (eliminar 6 endpoints + 3 callers frontend + 1 método em `client.js`).
- **Edge cases / dúvidas:** `villain_notes` ainda é usado como UPSERT em `_create_villains_for_hand` (mtt.py:754) + `_create_ggpoker_villain_notes_for_hand` (linhas 831). Se mantermos `villain_notes` como tabela auxiliar mas eliminarmos os ENDPOINTS, é possível.
- **Pré-requisitos:** **Sim** — Tech Debt #12 (modal Vilões re-arquitectado, sem Notas+Tags). **BLOQUEADO POR #12 — fica trivial após re-arquitectura modal Vilões.**

---

### [13] Landing page Vilões + filtros sala (multi-select com cores)

- **Tipo:** Feature (UX melhoria)
- **Severidade:** UX
- **Localização (path:linha):** `frontend/src/pages/Villains.jsx`
  - Default tab actual: linha **503** — `useState('sd')` (default `'sd'` = "Mãos com SD"). Spec quer `'all'`.
  - Filtros sala actuais: linhas **724-730** — `<select>` single-select. Spec quer multi-select.
  - Cores actuais em `SITE_COLORS` (linhas 433-438): GGPoker `#dc2626`, Winamax `#f59e0b`, PokerStars `#22c55e`, WPN `#3b82f6`. **Spec Rui:** Winamax vermelho, WPN verde, GG azul, PokerStars amarelo. **Não batem.**
- **Backend:** `villains.py:153-242` (`/villains/categorized`) — actualmente aceita `site` como **string única** (linha 156). Mudar para multi-value:
  - Aceitar `site: list[str] = Query(None)` ou parse CSV `site=Winamax,WPN`.
  - SQL muda de `h.site = %(site)s` para `h.site = ANY(%(site_list)s)`.
- **Mapping completo SITE_COLORS no projecto (3 fontes contraditórias):**

  | Sala | Villains.jsx:433-438 | Dashboard.jsx:24-27 | HandRow.jsx:106-110 (inline) | Spec Rui (#13) |
  |---|---|---|---|---|
  | GGPoker | vermelho `#dc2626` | laranja `#f59e0b` | índigo `#6366f1` (default) | **azul** |
  | Winamax | laranja `#f59e0b` | verde `#22c55e` | laranja `#f59e0b` | **vermelho** |
  | PokerStars | verde `#22c55e` | vermelho `#ef4444` | vermelho `#ef4444` | **amarelo** |
  | WPN | azul `#3b82f6` | ciano `#06b6d4` | verde `#22c55e` | **verde** |

  **Cada uma das 3 fontes pinta as mesmas salas com cores diferentes.** Inconsistência total.
- **Alteração proposta (Opção C — centralizar):**
  - Refactor para `lib/siteColors.js` exportada (sem mudar valores ainda) num primeiro passo.
  - Substituir os 3 sítios pelas constantes centralizadas.
  - Segundo passo: decidir paleta (A/B) com Rui via teste visual.
- **Esforço re-estimado:** ~1h centralizar (passo 1) + ~1-2h frontend filtros multi-select + paleta (passo 2). Total ~2-3h.
- **Edge cases / dúvidas:**
  - Decisão paleta pendente Rui (Opção A nova / B manter).
  - Persistência da escolha de filtro sala no localStorage — Rui ainda não decidiu.
  - URL params (`?site=...`) — hoje só `?nick=`.
  - Comportamento "0 salas → página vazia" (respeitar escolha) — confirmado spec.
- **Pré-requisitos:** Não. Decisão paleta pendente Rui antes de implementar passo 2.

---

### [11] Botão × eliminar villain de mão (página /hand/X)

- **Tipo:** Feature
- **Severidade:** UX
- **Localização (path:linha):**
  - Frontend (UI do botão): `frontend/src/components/HandHistoryViewer.jsx:140-175` (bloco MESA) — adicionar prop `villainNicks: Set<string>` + `onDeleteVillain(name)`. Mostrar botão × no row apenas se `p.name in villainNicks`.
  - Caller único: `HandDetailPage.jsx` precisa de carregar lista de villains da mão + passar prop ao `<HandHistoryViewer>`. Refresh após delete.
  - **Importante:** modal Estudo (`Hands.jsx`) e modal HM3 (`HM3.jsx`) também consomem `HandHistoryViewer`. Spec diz "SÓ na página /hand/X" → prop `deletable=false` por defeito; só `HandDetailPage` passa `deletable=true`.
  - Backend: novo endpoint `DELETE /api/hands/{hand_id}/villains/{player_name}` em `backend/app/routers/hands.py` ou `villains.py`. SQL: `DELETE FROM hand_villains WHERE hand_db_id=%s AND player_name=%s`. Apaga **todas as categorias** desse player nesta mão (sd/nota/friend) — comportamento single-action.
- **Alteração proposta:**
  - Frontend: ~30 linhas em `HandHistoryViewer.jsx` (botão + handler) + ~20 linhas em `HandDetailPage.jsx` (fetch villains + state refresh). Sem confirmação modal.
  - Backend: ~15 linhas (endpoint + SQL `RETURNING` para devolver count apagado).
- **Comportamento re-import — DECISÃO RUI PENDENTE:**
  - **Opção A (conservadora, recomendada):** sem persistência → re-import recria villain via `_create_villains_for_hand`. Documentar como "limpeza temporária para a sessão de estudo actual".
  - **Opção B (persistente):** nova tabela `hand_villains_blacklist (hand_db_id, player_name, created_at)` consultada em `_create_villains_for_hand` para skip. Mais complexo.
- **Esforço re-estimado:** ~2h (Opção A). ~3h (Opção B).
- **Edge cases / dúvidas:**
  - Se uma mão tem 2 villains e Rui apaga ambos, `hand_villains` fica sem rows mas a mão permanece em Estudo. OK (já é o comportamento de mãos sem villains).
  - Visual: botão × subtil (cor `#ef4444` ou similar), 14×14px, tooltip "Eliminar villain".
- **Pré-requisitos:** Decisão Rui sobre re-import (A vs B) antes de implementar.

---

### [8] Consolidação 8 (na realidade 9) PokerCard locais

- **Tipo:** Housekeeping
- **Severidade:** Cosmético (refactor)
- **Localização — 9 callers verificados via grep:**

  | # | Ficheiro | Linha def | Variante | Sizes usadas | Notas |
  |---|---|---|---|---|---|
  | 1 | `pages/Discord.jsx:48` | `PokerCard({card, size='sm'})` | sm | sm, md | Compatível |
  | 2 | `pages/Dashboard.jsx:36` | `PokerCard({card})` | sem size prop (24×33 fixo) | n/a | **Incompatível** — dimensões custom não no shared (24×33 vs sm=26×36) |
  | 3 | `pages/HM3.jsx:38` | `PokerCard({card, size='sm'})` | sm | sm, lg | Compatível (e dead code adjacente — #7) |
  | 4 | `pages/Tournaments.jsx:20` | `PokerCard({card, size='sm'})` | sm | sm | Compatível |
  | 5 | `pages/ReplayerPage.jsx:34` | `RCard({card, faceDown, size='md'})` | md, com faceDown | md, board, xl | **Sizes custom** (`board`, `xl`) não no shared |
  | 6 | `pages/Hands.jsx:56` | `PokerCard({card, size='md'})` | md | sm, md, lg | Compatível |
  | 7 | `pages/HandDetailPage.jsx:14` | `RCard({card, size='md'})` | md, sem faceDown | lg | Compatível (já era a fonte da paleta polida) |
  | 8 | `components/HandRow.jsx:24` | `PokerCard({card, size='sm'})` | sm | sm | Compatível |
  | 9 | `components/Replayer.jsx:12` | `RCard({card, faceDown, size='md'})` | md, com faceDown | sm, md, lg | Compatível com partilhado |

- **Comparação shape vs partilhado (`PokerCard.jsx:31` — `card`, `size`, `faceDown`):**
  - 6/9 são drop-in compatíveis (Discord, HM3, Tournaments, Hands, HandRow, Replayer).
  - 1/9 (HandDetailPage:14) já é a paleta canónica — substituição idêntica.
  - **2/9 são incompatíveis** sem extensão do partilhado:
    - Dashboard.jsx:36 — usa **24×33 fixo** (mais pequeno que `sm=26×36`); precisa de variante nova `xs` ou aceitar a mudança visual.
    - ReplayerPage.jsx:34 — usa sizes `'board'` e `'xl'` custom; precisa de adicionar variantes ao partilhado, ou mapear `'board'→lg`, `'xl'→lg`.
- **Alteração proposta (faseada):**
  - Consolidar primeiro os 6 drop-in compatíveis (commit 1, ~1h).
  - Depois decidir Dashboard (variante xs ou aceitar diferença visual ~2px).
  - ReplayerPage por último (mais sensível, mesa circular).
  - Em cada caller: substituir `function PokerCard|RCard...` local por `import PokerCard from '../components/PokerCard'`. Diff típico: −20 a −30 linhas por ficheiro.
- **Esforço re-estimado total:** ~4-5h
  - 6 callers compatíveis: ~10 min cada = 1h
  - Dashboard (decidir + ajustar): ~30 min
  - ReplayerPage (custom sizes): ~45 min
  - Validação visual em prod por caller: ~15 min × 9 = 2h15m
- **Edge cases / dúvidas:**
  - Replayer (mesa circular) — risco de regressão visual; testar em prod com mão 9-max.
  - Dashboard 24×33 — visualmente quase idêntico a 26×36. Pequeno desalinhamento de coluna possível.
- **Pré-requisitos:** Não. Independente.

---

### [12] Re-arquitectura modal Vilões

- **Tipo:** Feature (re-arquitectura major)
- **Severidade:** UX major
- **Localização (path:linha):** `frontend/src/pages/Villains.jsx:55-427` (componente `VillainProfile`).
- **Componentes a eliminar:**
  - Painel "Notas e Tags" esquerdo (linhas 144-186): textarea note, input tags, botão Guardar.
  - States dependentes: `note`, `tags`, `saving` (linhas 58-60).
  - Função `save()` (linhas 86-99) e `villains.update(id, ...)` correspondente.
- **Estrutura nova (spec aprovada Rui):**
  - **Lista colapsada** — summary row tem: data, **villain pos+nick** (dourado), **villain cards** (entre data e pos só se reveladas, NÃO Hero cards), **vs hero pos**, board, **villain BB delta** (não hero result), stakes.
  - **Mão expandida** — split 1/3 + 2/3:
    - **Esquerda (1/3):** MESA cronológica com ★ villain + HERO Hero.
    - **Direita (2/3):** 4 colunas Pre/F/T/R com notação compacta `F/x/C/b/R/3b/4b/AI` em bbs, sem nicks, board cards no header da coluna.
- **Backend mudanças (`backend/app/routers/villains.py`):**
  - Endpoint `/villains/search/hands` (linha 368) precisa de devolver:
    - `villain_position` (já tem via `all_players_actions`)
    - `villain_cards` (filtrar `pdata.cards` apenas se `pdata.cards != null`)
    - `villain_result` em BB (já existe via `_compute_villain_result` linha 295)
    - **Novo:** `actions_compact` por player por street com notação `F/x/C/b/R/3b/4b/AI`. Lógica:
      - Detectar 3-bet = 2º raise pré-flop; 4-bet = 3º raise pré-flop
      - Stack delta em BB para acções com amount
- **Lista de ficheiros a tocar:**
  - `frontend/src/pages/Villains.jsx` — ~370 linhas re-escritas (VillainProfile + listagem de mãos com nova summary)
  - `backend/app/routers/villains.py:368-435` — endpoint `/search/hands` extendido (aprox +50 linhas)
  - `backend/app/services/hand_service.py` ou novo helper — função pura `compute_actions_compact(apa, hero_name, villain_nick) → dict[street → str]`
- **Dependências de shape de dados:**
  - `all_players_actions[nick].actions[street]` lista de strings → tem que ser parseável para extrair acções individuais (raise→3b→4b detection)
  - Adapter `openModal(nick)` em `Villains.jsx:560` ainda precisa do `id` do `villain_notes` para fetch — **com #12 esse fetch desaparece** (sem editor de notas) → endpoint legacy `/api/villains` torna-se removível (#6 fica trivial).
- **Esforço re-estimado:** ~6-8h (sessão dedicada).
- **Edge cases / dúvidas:**
  - **Heads-up (2 players):** SB/BB sem outras posições; 4 colunas Pre/F/T/R ainda fazem sentido?
  - **All-in pré-flop:** Flop/Turn/River vazios na coluna; render placeholder ou esconder colunas?
  - **3-bet pots** em torneios short-stacked: detecção pode confundir-se com all-in directo.
  - **Paleta cor exacta** para destaque villain (★ amarelo `#fbbf24` actual).
  - **Decisão Rui pendente:** acção repetida na mesma street (call após raise) — concatenar como "C R" ou só mostrar última?
- **Pré-requisitos:** Não. Mas após #12 fechado, **#6 fica trivialmente fechável**.

---

## 3. Decisões pendentes Rui antes de implementação

Antes de arrancar a implementação dos respectivos itens, precisa de decisão Rui:

| # | Item | Decisão | Opções |
|---|---|---|---|
| 10 | Estratégia fix parser truncamento | Como validar nick capturado | **A** — defensiva: validar `actor` em 688 contra lista de seats parseados (robusto para qualquer regex que trunque) **B** — cirúrgica: regex 688 com âncora keyword poker (`folds|checks|...|goes|is`) |
| 11 | Comportamento re-import após delete villain | Persistência da escolha | **A** — conservadora: sem persistência, re-import recria villain (~2h) **B** — persistente: tabela `hand_villains_blacklist` consultada em `_create_villains_for_hand` (~3h) |
| 12 | Notação acções repetidas na mesma street | Concatenação | **A** — concatenar (ex: call após raise → `"C R"`) **B** — só mostrar última acção (ex: só `"R"`) |
| 13 | Paleta cor das salas | Refactor visual | **A** — paleta nova spec (Winamax vermelho / WPN verde / GG azul / PokerStars amarelo) **B** — manter actual (Villains.jsx) **C** — centralizar primeiro (sem mudar valores), decidir cores depois |

---

## 4. Ordem sugerida de ataque em sessões futuras

### Quick wins (curtos, baixo risco) — 1ª sessão futura

1. **#5** — fix `mtt.py:786` `_q()` cross-connection (~10 min)
2. **#7** — apagar dead code HM3.jsx (~5 min)
3. **#6** — DEFERIDO (BLOQUEADO POR #12)

**Subtotal: ~15 min**

---

### Bugs (corrigir comportamento incorrecto) — 2ª sessão futura

4. **#10** — fix parser truncamento Winamax + backfill cleanup (~1h10)
5. **#9** — validação SQL pós-Pipelines 2-5 (~15 min, espera Pipelines 2-5)

**Subtotal: ~1h25**

---

### Features simples (UX melhoria, escopo contido) — 3ª sessão futura

6. **#11** — botão × eliminar villain (~2h Opção A) — após decisão Rui
7. **#13a** — centralizar SITE_COLORS em `lib/siteColors.js` (~1h)
8. **#13b** — paleta nova + filtros multi-select (~1-2h) — após decisão paleta

**Subtotal: ~4-5h**

---

### Major (sessão dedicada exclusiva)

9. **#12** — re-arquitectura modal Vilões (~6-8h, sessão dedicada)
   - **Após #12 fechado:** **#6** (housekeeping endpoint legacy) fica trivialmente fechável (~30 min).

**Subtotal: ~6-9h**

---

### Housekeeping (baixa prioridade, refactor opcional)

10. **#8** — consolidação 9 PokerCard locais (~4-5h)
    - Risco moderado em layouts estáveis; faseado por caller.
    - Boa para sessão "limpeza" sem pressão de feature.

**Subtotal: ~4-5h**

---

### Total agregado

**~25-30h** espalhado por **4-5 sessões dedicadas**:

| Bloco | Esforço |
|---|---|
| Quick wins + Bugs | ~1h40 (1 sessão) |
| Features simples | ~4-5h (1 sessão) |
| Major #12 + housekeeping #6 trivial | ~7-9h (1 sessão dedicada) |
| Housekeeping #8 | ~4-5h (1 sessão "limpeza") |
| Buffer pipelines 2-5 + ajustes | ~5-7h |
