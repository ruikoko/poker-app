# Regras de Negócio — Poker Study App

Documento operacional. Detalha as regras que regem entrada, processamento, distribuição e análise de dados na app. Próximas sessões DEVEM ler este documento ANTES de tocar em código que afecte qualquer um destes vectores.

Complementa `docs/VISAO_PRODUTO.md` (visão alta) e `docs/MAPA_ACOPLAMENTO.md` (mapa técnico).

## Os 4 vectores da app

1. **ENTRADA** — recolha de dados (HM3 .bat, Discord bot, Upload manual).
2. **PROCESSAMENTO** — parse, match, enriquecimento.
3. **DISTRIBUIÇÃO** — envio de cada dado para a secção certa.
4. **ANÁLISE** — Rui trabalha sobre o resultado distribuído.

---

## 1. ENTRADA

### 1.1. HM3 (.bat local)

- **Trigger:** manual, corre quando Rui decide. Não há agendamento.
- **Período:** Rui escolhe (últimos 3 dias, 7 dias, etc).
- **Critério de importação:** importa SÓ mãos COM tags HM3 dentro do período. Mãos "rotina" sem tag NUNCA entram via HM3.
- **Salas cobertas:** Winamax, WPN, PokerStars.

### 1.2. Discord bot (manual via app)

- **Trigger:** botão "Sincronizar" na página Discord. `DISCORD_AUTO_SYNC=false` em produção (não corre sozinho).
- **Janelas pré-definidas:** 24h, 72h, 1 semana, 15 dias, 1 mês.
- **Janela custom:** Rui escolhe `De` e `Até` (calendário inline).
- **Cutoff absoluto:** 1 Jan 2026 Lisboa. Nenhuma mensagem anterior é varrida (regra de negócio Rui — é o início da era da app).
- **Cobertura de canais:** todos os canais do servidor monitorizado.
- **Conteúdo apanhado:** replayer-links GG + imagens (anexos directos + links Gyazo).

### 1.3. Upload manual (na app)

- SS GGPoker (`.png`, `.jpg`, `.webp`).
- HH em texto (qualquer sala) — upload de ficheiro `.txt`.
- ZIPs (HHs em massa) — caminho separado para o GG (não vem via HM3 .bat porque é anonimizada).
- Outras imagens (contexto).

---

## 2. PROCESSAMENTO

### 2.1. Parse

Lê o input cru e extrai info estruturada:
- Hand histories texto → mãos + acções + jogadores.
- Screenshots (Vision GPT-4o-mini) → seats + nicks + stacks; identifica o Hero (centro-baixo).
- Replayer-links Discord → screenshot embebida na URL.
- Imagens Discord/Gyazo → ficam como anexos (não viram mãos).

### 2.2. Match

Tenta unir peças que pertencem juntas:
- **SS ↔ HH (mesma mão GG):**
  - Match por `hand_id = GG-{TM_number}`.
  - Resolve hashes anonimizados → nicks reais por âncoras (Hero/SB/BB) + aritmética de stacks + eliminação para o resto.
- **Discord entry ↔ HH existente:**
  - Append discord_tags via helper centralizado `append_discord_channel_to_hand` (#B12 fix pt9).
- **Imagem ↔ mão (galeria):**
  - Manual. Rui escolhe via UI.

### 2.3. Enriquecimento

Adiciona informação derivada:
- Posições calculadas (BTN, SB, BB, UTG, etc).
- Tags auto-geradas (showdown, position, etc).
- `tournament_format` (KO/PKO/Mystery/Vanilla).
- `buy_in` numérico extraído do nome do torneio.
- `result` (lucro/perda em BB).

---

## 3. DISTRIBUIÇÃO

### 3.1. Secções de ORIGEM

Toda mão entra na sua secção de origem.

| Secção | Conteúdo |
|---|---|
| HM3 | Mãos do .bat HM3 (Winamax/WPN/PokerStars). |
| Discord | Mãos do bot Discord. |
| Torneios | Drill-down por torneio (toda mão GG). |
| Dashboard | SS e imagens uploadadas manualmente. |

### 3.2. Secções DERIVADAS — Estudo

#### 3.2.1. Regras de elegibilidade (TODAS obrigatórias)

**Condições técnicas:**
- Nicks reais (não hashes). Para GG: requer `match_method` populado e diferente de `discord_placeholder_*`.
- Mão TEM HH. Mãos só com SS, sem HH, NUNCA aparecem em Estudo.
- Nome de torneio (`tournament_name`) preenchido.
- Sala (`site`) preenchida.

**Condição de tag:**
- Pelo menos 1 tag de estudo:
  - Tag HM3 que NÃO seja `nota` / `notas` / `nota+` / `nota++` / derivados.
  - OU canal Discord que NÃO seja `nota`.

**Excepção (aditiva):**
- Mão com tag `nota` + tag de estudo → entra em Estudo E Vilões.
- Mão SÓ com `nota` → vai apenas para Vilões.

**Nota sobre buy_in:** NÃO é obrigatório (parsers WPN e PS frequentemente falham em extrair; obrigar bloquearia mãos legítimas).

#### 3.2.2. Apresentação em Estudo (DIVERGÊNCIA 5 — actualmente NÃO implementada)

**Regra:** tags HM3 e canais Discord são o MESMO conceito. Rui nomeou os canais Discord para coincidirem com tags HM3 (ex: canal "icm-pko" ≡ tag "ICM PKO").

**Apresentação desejada:**
- 1 chip por nome de tag/canal (não 1 chip por origem).
- Dentro da chip: TODAS as mãos com essa tag, vindas de qualquer origem.
- Cada mão mostra a sua origem como rótulo discreto (HM3 / Discord).

**Estado actual da app (a corrigir):**
- Estudo separa em secções por origem: PRINCIPAIS/SECUNDÁRIAS/SPOTS (HM3) + CANAIS DISCORD + DISCORD — SÓ SS (SEM HH).
- Resultado: a mesma chip "pos-pko" aparece em 3 sítios diferentes.
- Secção "DISCORD — SÓ SS (SEM HH)" tem 119 mãos sem HH visíveis em Estudo, violando regra 3.2.1.

**Tech debt aberto:** ver inventário (#B17 a abrir após criação deste doc).

### 3.3. Secções DERIVADAS — Vilões

Critérios de elegibilidade (regras canónicas A∨C∨D — `_classify_villain_categories` em `backend/app/services/hand_service.py`):

- **Regra A** — `hm3_tags` contém tag a começar por `nota` (`nota`, `notas`, `nota+`, `nota++`, etc) → `category='nota'`.
- **Regra C** — canal Discord `nota` em `discord_tags` E `match_method` real (não `discord_placeholder_*`) → `category='nota'`.
- **Regra D** — `villain_nick` em `FRIEND_HEROES` (lista em `backend/app/hero_names.py` — Karluz, flightrisk) → `category='friend'`. Independente de tag; sempre dispara quando o nick aparece como non-hero. Permite ver mãos de amigos sem o Rui ter de marcá-las explicitamente.

**Pré-condição padrão** do classificador: villain tem `has_cards` (showdown) OU `has_vpip` (call/raise/bet preflop). Sem nenhuma das duas evidências, normalmente não é villain a registar.

**Excepção #B19 (pt9)** — quando a mão tem tag HM3 `nota%`, a pré-condição é ignorada: qualquer non-hero que **viu o flop** (acção em street ≠ `preflop` no `all_players_actions`) é elegível, mesmo sem VPIP nem cards. Justificação: a tag explícita do Rui é sinal de intenção — se ele marcou a mão para Vilões, o non-hero relevante pode ser o BB que fez check preflop e agiu postflop sem chegar a SD. Sem esta excepção, perdiam-se 2/140 mãos `nota%` na BD.

**Implementação** da excepção: alargamento de candidates em `_create_villains_for_hand` (`backend/app/routers/mtt.py`) + bypass da pré-condição em `_classify_villain_categories` (`backend/app/services/hand_service.py`). Escopo restrito a tag HM3 `nota%` — Discord e outras tags mantêm pré-condição original.

### 3.4. Regra de Cross-post Discord

Toda mão que apareça num canal Discord deve ter o nome desse canal em `discord_tags`. Sem excepções por origem da mão.

Implementado via helper `append_discord_channel_to_hand` em `backend/app/services/hand_service.py` (#B12 fix pt9).

### 3.5. Casos canónicos (referência rápida)

| # | Origem da mão | Tags / canais | Estudo? | Vilões? | Aparece em |
|---|---|---|---|---|---|
| 1 | HM3 | `["ICM PKO"]` | ✓ | ✗ | HM3, Estudo |
| 2 | HM3 | `["nota"]` | ✗ | ✓ | HM3, Vilões |
| 3 | HM3 | `["nota", "ICM PKO"]` | ✓ | ✓ | HM3, Estudo, Vilões |
| 4 | Discord | canal `pos-pko` | ✓ | ✗ | Discord, Estudo |
| 5 | Discord | canal `nota` | ✗ | ✓ | Discord, Vilões |
| 6 | Discord | canais `["nota", "pos-pko"]` | ✓ | ✓ | Discord, Estudo, Vilões |
| 7 | GG anon (sem SS, sem match) | — | ✗ | ✗ | Torneios |
| 8 | HH bulk + SS match, sem tags | — | ✗ | ✗ | Torneios |

---

## 4. ANÁLISE

Rui trabalha mãos em Estudo + Vilões. Detalhes do fluxo de análise não documentados nesta versão (foco actual: vector ENTRADA + DISTRIBUIÇÃO).

---

## 5. Regras de identificação de TORNEIO (por sala)

Necessário para alimentar `tournament_name` e `tournament_format` (campos obrigatórios para Estudo).

### 5.1. PokerStars

**Nome construído:** `<número_torneio> + <buy_in_total> + <formato>`.
Exemplo: `3983883171 - €50.00 - Mystery KO`.

**Formato (regra dura):**
- buy_in com 1 parte (ex: `€10`) → **Vanilla**.
- buy_in com 3 partes (ex: `€22.50+€22.50+€5.00`) → tem bounty:
  - Se as stacks dos seats mostram bounty value → **PKO**.
  - Se NÃO mostram bounty value → **Mystery KO**.

**KO regular:** PokerStars não corre KO regular hoje. Ignorar essa categoria.

### 5.2. Winamax

**Igual ao PokerStars** (mesmo formato de buy_in, mesma regra de bounty nas stacks).

### 5.3. WPN

**Nome construído:** `<número_torneio> + <GTD garantido>`.
Exemplo: `Tournament 12345 — $30,000 GTD`.

**Formato:** indeterminado. WPN não define nada útil na HH. Aceitar e seguir.

### 5.4. GGPoker

**Nome:** já vem na HH (linha 1, ex: `WSOP-SC HR: $525 Bounty Hunters Circuit HR`).

**Formato (deduzido pelo nome):**
- "Mystery" no nome → **Mystery KO**.
- "Bounty" no nome (sem "Mystery") → **PKO**.
- Sem "Mystery" nem "Bounty" → **Vanilla**.

**Particularidade:** GG não mostra bounty value nas stacks (todas anonimizadas). Por isso a regra de stacks do PS/Wina não se aplica — só o nome conta.

---

## 6. Regras DURAS — o que a app NUNCA pode fazer

- Mãos GG anonimizadas (sem `match_method`) NÃO podem aparecer em Estudo.
- Mãos só com tag `nota` NÃO podem aparecer em Estudo.
- Mãos sem nome de torneio + sala NÃO podem aparecer em Estudo.
- Mãos sem HH NUNCA aparecem em Estudo (mesmo que tenham tags).
- Cross-post Discord NÃO pode perder canais.
- Mensagens Discord anteriores a 1 Jan 2026 Lisboa NÃO são varridas.
- HM3 .bat NÃO importa mãos sem tag.

---

## 7. Áreas futuras (NÃO implementar sem confirmação Rui)

- Análise post-estudo (evolução das mãos estudadas).
- Estudo de população (mãos GG sem tag — Caso 7/8).
- GTO Brain (documentado separadamente).
- Integração GTOWizard / HRC.
