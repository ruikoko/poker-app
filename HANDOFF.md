# HANDOFF — continuação poker-app

**Data desta sessão:** 21 Abril 2026 (madrugada)
**Sessão anterior:** 20 Abril 2026 (noite) — ver `git log` para contexto histórico.
**Utilizador:** Rui (ruikoko/poker-app)
**Stack:** FastAPI + PostgreSQL backend (Railway) + React/Vite frontend (Railway)
**Login:** rui@pokerapp.com
**Deploy URL backend:** https://poker-app-production-34a7.up.railway.app
**Deploy URL frontend:** https://comfortable-hope-production-a87a.up.railway.app

---

## Contexto rápido

Sou Rui. Solo developer, jogador MTT. App importa e estuda hand histories de GGPoker, PokerStars, Winamax, WPN, iPoker, 888.

Regras que se mantêm desde as sessões anteriores:
- **Nunca especules.** Verifica no código ou marca como não-verificado. Ler literal > inferir.
- **Não peças comandos de consola repetidamente.** Usa as ferramentas (Read/Edit/Grep) directamente.
- **Admite erros sem autojustificar.** Se estás a dar voltas, pede para rever em vez de insistir.
- **Regra de ouro (CLAUDE.md):** verificar que não há sessão de poker activa antes de arrancar processos.

Mudança face ao HANDOFF anterior: passei a ter **Railway CLI instalado (v4.40.0)** e linked a `trustworthy-dedication / production / Postgres`. Comandos `railway run python <script>.py` agora funcionam directamente — já não é tudo via interface web. O git local também ficou configurado (`Rui Dias <ruidias@ilhavo.org>`); commits/pushes feitos directamente da máquina.

---

## O que foi resolvido nesta sessão

### 1. Três bugs no parser PS/WN/WPN (commits `13196e6` + `46c2ca8`)

Todos em `backend/app/routers/hm3.py` e `backend/app/routers/mtt.py`. Identificados por inspecção exaustiva do código após sintomas em BD (`all_players_actions` com chaves corrompidas tipo `"lenon318es showed [Qh Qc] and won"`, players com `cards` mas sem `seat`, 2 entries para o mesmo nick).

| Bug | Ficheiro:linha | Causa | Fix |
|---|---|---|---|
| Regex de seats engolia secção SUMMARY | `hm3.py:239` + `hm3.py:218` | `re.finditer` aplicado a `hh_text` inteiro; em torneios PS/WPN, linhas `Seat N: nick ... (chips_won)` do summary batiam no padrão e sobrescreviam os seats reais. | Restringir scan a `hh_text[:preflop_marker]`. |
| WPN: stacks decimais não matched | `hm3.py:239` | `[\d,]+` não aceita `.`. WPN emite `(176676.00)` nos seats. | Trocar por `[\d,.]+`. |
| Winamax: nicks terminados em `.` ignorados | `hm3.py:277` | `\b` é zero-width entre `\w` e `\W`; para nicks `Madjidov D.`, `Frousse.`, `&LOVE.` o char final é `.` (non-word) e o seguinte `space` também, logo `\b` nunca bate e o player era marcado sitting-out. | Trocar `\b` por `(?=\s|$)` lookahead. |
| `has_showdown` nunca era escrito em imports HM3 | `hm3.py:import_hm3` | INSERT e UPDATE on conflict omitiam a coluna; só o path `hand_service._insert_hand` (GG) escrevia. | Calcular `has_showdown` a partir do `all_players` final e incluir no INSERT + UPDATE (inclui `EXCLUDED.has_showdown` no ON CONFLICT). |
| `_create_villains_for_hand` hardcoded em `'GGPoker'` no INSERT do `villain_notes` | `mtt.py:688` | Sem parâmetro de site; villains WN/PS/WPN ficariam em `villain_notes(site='GGPoker')`, conflitos de chave e aggregation errada. | Adicionar parâmetro `site: str = "GGPoker"` (default preserva caller existente). Novo caller passa o site real. |
| Faltava migration schema idempotente para `has_showdown` | novo `hands.py:ensure_has_showdown_column` + wire em `main.py` | Coluna criada ad-hoc em prod; fresh deploys iriam falhar. | `ALTER TABLE hands ADD COLUMN IF NOT EXISTS has_showdown BOOLEAN DEFAULT FALSE` + índice parcial, chamado no lifespan. |

### 2. Migrações de dados

Scripts ad-hoc em root do repo (não versionados — `.gitignore` exclui `query_*.py` e `*_output.txt`, os outros ficam untracked por opção). Todos seguem o mesmo padrão: dry-run default, `--execute` com snapshot CSV antes de UPDATE/INSERT, transacção única, zero DELETEs.

- `reparse_corrupted.py` — mãos com chaves corrompidas no `all_players_actions`. Rodou em produção, todas validadas depois.
- `reparse_missing_showdown.py` — mãos WN/WPN com `shows [` no raw mas `has_showdown=FALSE` (não cobertas pelo backfill SQL ad-hoc do Manus, que era GG-only).
- `reparse_selective.py` — 134 mãos WN/WPN com `player(cards)+sem seat` (só reveladas após fixes do parser).
- `backfill_villains.py` — cria villains para gap: `has_showdown=TRUE ∧ hm3_tags ILIKE 'nota%' ∧ sem villains`, reusa `_create_villains_for_hand(showdown_only=True, site=<real>)`.

### 3. Estado final validado em BD

- **1233 mãos** no universo-alvo (regra: `(hm3_tags starts 'nota') OR (player_names.match_method != NULL)` ∧ `has_showdown=TRUE`).
- **1413 villains** em `hand_villains`, todos com `hand_db_id` preenchido (zero via `mtt_hand_id` apenas).
- **100% cobertura**: todas as 1233 mãos têm ≥1 villain; zero villains apontam a mãos fora do universo.
- Zero `all_players_actions` com chaves corrompidas; zero players com `cards` mas sem `seat`.

### 4. Ficheiros tracked

Commits nesta sessão:
- `13196e6` — `fix(hm3): anchor seat regex to header; populate has_showdown on HM3 import; add ensure_has_showdown_column`
- `46c2ca8` — `fix(hm3): allow decimal stacks for WPN; handle trailing-dot nicks on Winamax; parameterize site in villain creation`
- (este commit HANDOFF.md)

Ficheiros de produto alterados: `backend/app/routers/hm3.py`, `backend/app/routers/hands.py`, `backend/app/routers/mtt.py`, `backend/app/main.py`, `.gitignore`, e o script de teste `test_parser_fix.py` (committed como referência).

Deploys Railway validados após cada push (`railway status --json` → SUCCESS, startup limpo).

---

## Untracked no working tree (opção deliberada)

- `CLAUDE.md`, `HANDOFF.md` — documentação; só este último entra agora em git.
- `query_*.py` — investigação ad-hoc (ignorado via `.gitignore`).
- `reparse_*.py`, `backfill_villains.py`, `test_parser_fix.py` — one-shot scripts. `test_parser_fix.py` foi committed; os de migração não, embora possam ser committed para histórico se se desejar.
- `reparse_*_snapshot_*.csv`, `backfill_villains_snapshot_*.csv` — snapshots locais antes dos UPDATEs/INSERTs em execute. Guardar até não fazerem falta.
- `*.txt` outputs de dry-runs — locais, descartáveis.

---

## Por fazer (pendente de futura sessão)

### Produto / UX
- **Nenhum frontend tocado nesta sessão.** O flag `has_showdown` e a cobertura total de villains não estão expostos na UI. Decidir se faz sentido:
  - Filtro "só mãos com showdown" na página de estudo.
  - Página de villains/HUD por nick usando `hand_villains` agregado.
  - Badge na lista de mãos a indicar se há villains.

### Integrações
- **SharkScope** — herdado do HANDOFF anterior, continua **parado**. Objectivo: enriquecer mãos com buyin, prize pool, field, ITM rank, posição final — dados externos à HH, usando `tournament_id`. Rui tem subscrição Gold (username `thinvalium`). Precisa de investigação API externa.

### Dívida técnica ligeira
- Dois sítios no código replicam a detecção de `has_showdown` (`hand_service._insert_hand:57-65` e `hm3.py` em duas zonas do `import_hm3`). Se um terceiro caller aparecer, extrair helper. Enquanto forem 3, inline está ok (CLAUDE.md desencoraja abstrações prematuras).
- `_build_seat_to_name_map` em `mtt.py:477` foi desenhado para desanonimizar GG via stacks. Em sites não-GG onde os nicks são reais, cai num fallback silencioso. Funciona, mas é acoplamento frágil — se um dia o pipeline SS se estender a WN/PS/WPN, esta função precisa de revisão.
- Os 3 scripts `reparse_*.py` duplicam `simulate_reparse()`. Se forem mantidos, podiam ser consolidados num módulo — mas é trabalho de manutenção, não urgente.

### Monitorização
- Após o fix de `has_showdown` no caminho `import_hm3`, novas importações HM3 devem populá-lo automaticamente. Verificar numa futura importação real que o valor aparece correcto em BD — sem isto, fica apenas teorizado.

---

## Como o Rui trabalha

- Agora tem **Railway CLI e git local funcionais** — já pode correr migrações via `railway run` e committar da máquina. A interface web do GitHub deixou de ser o único caminho.
- Deploy automático Railway após push. Confirmar com `railway status --json` + `railway logs --service poker-app --deployment`.
- **Prefere explicações curtas, PT-PT.**
- Escolheu padrão de trabalho "tu escreves script / mostras diff; eu reviso e aprovo; eu corro as coisas que tocam em BD" — respeitar este ciclo.
- Valida sempre antes de avançar: dry-run → validação → execute → validação → commit → push → validação de deploy.

---

## Lições/avisos para Claude em próximas sessões

1. **Verifica antes de afirmar.** Vários bugs nesta sessão foram encontrados porque o utilizador insistiu em ler o código literal em vez de aceitar inferências. Aplica o mesmo rigor por ti.
2. **Um bug resolvido pode esconder outro.** O fix do regex anchor (1a) revelou o bug do decimal WPN e do word-boundary WN. Não assumas que a primeira causa é a única.
3. **Separar produto e investigação no git.** Scripts one-shot e snapshots não devem poluir histórico. Já tens `.gitignore` a cobrir `query_*.py` e `*_output.txt` — estender se aparecerem novos patterns.
4. **Tests em memória antes de tocar em BD.** O `test_parser_fix.py` serviu de gate antes de cada re-parse massivo. Replicar padrão sempre que um fix afecte muitas linhas.
5. **Não assumas paridade entre parsers.** `gg_hands.py`, `_parse_hand(Winamax)`, `_parse_hand(PokerStars)`, `_parse_hand(WPN)` têm regex, convenções e formatos de summary diferentes. Tratar cada um individualmente.

---

## Como começar a próxima sessão

1. Ler este documento + CLAUDE.md.
2. `git log -20 --oneline` para ver o trabalho recente.
3. Ver `railway status --json` para confirmar deploy vivo.
4. Perguntar ao Rui o foco — provavelmente:
   - (a) Expor `has_showdown` / villains na UI, ou
   - (b) Avançar na SharkScope integration, ou
   - (c) Outra prioridade que só ele sabe.
