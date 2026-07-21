# POR ONDE COMEÇAR — mapa de leitura para quem pega na app pela 1ª vez

> **Para quê este documento:** se és um operador novo (Claude Web, Claude Code, ou humano)
> e nunca mexeste nesta app, **lê os documentos por esta ordem** e ficas a par — sem
> ninguém ter de te explicar tudo de novo. **Ler estes documentos = estar a par.**

## O que é a app (em 1 parágrafo)
Uma app para **centralizar o estudo de poker do Rui** — juntar num sítio único, organizado
e trabalhável, as mãos de dúvida espalhadas por várias salas e formatos (tags HM3, canais
Discord, screenshots, HHs em texto). Backend FastAPI + PostgreSQL (Railway); frontend
React. Uma sala — a **GGPoker** — vem **anonimizada** (jogadores como hashes), e por isso
tem um mecanismo extra (cruzar HH ↔ imagem) para entrar com nicks reais. Há ainda uma
pipeline que manda mãos a um solver (**HRC**) num mini-PC (Beelink) via um robot (watcher).

---

## 1. LEITURA OBRIGATÓRIA — por esta ordem (todos os operadores)

| # | Documento | O que cobre |
|---|---|---|
| 1 | **`CLAUDE.md`** (raiz) | **O ponto de entrada.** Instruções do projecto, stack, modelo de domínio, **armadilhas** (chama vs coroa vs verde de KO, âmbito de disco, regra de ouro anti-cheat), e o **histórico de sessões** (o que ficou live em cada uma). Lê primeiro e sempre. |
| 2 | **`docs/FLUXO_DE_TRABALHO.md`** | Regras de eficiência entre operadores (paralelo, recados completos, operador certo, fonte, logging, fecho de sessão, **âmbito de disco §11**). **No topo: ⚖️ `#LEI-FIX-NA-CAUSA`** — todo o fix trata a causa, nunca o sintoma; regra duplicada consolida-se numa fonte de verdade; cosmético proibido; remendo só declarado + registado. **Obrigatório no início de CADA sessão.** |
| 3 | **`docs/PAPEIS_E_RESPONSABILIDADES.md`** | Quem é o Rui, o Claude Web e o Claude Code — quem decide o quê. |
| 4 | **`docs/VISAO_PRODUTO.md`** | Visão alta (propósito, vectores, secções do sidebar). |
| 5 | **`docs/REGRAS_NEGOCIO.md`** | Regras operacionais (entrada, processamento, distribuição, casos canónicos, **regras duras** — ex.: mão sem HH nunca entra em Estudo; GG sem SS não entra). |
| 6 | **`docs/MAPA_ACOPLAMENTO.md`** | Mapa técnico dos conceitos-chave (`match_method`, `study_state`, `origin`, `hm3_tags`, `discord_tags`, `raw_json`…) — onde cada um é produzido/consumido + armadilhas. **Ler antes de mexer em qualquer conceito.** |
| 7 | **`docs/TECH_DEBTS_INVENTARIO.md`** | Backlog vivo de tech debts (estado ACTUAL). O topo tem as sessões mais recentes. |

**Lidos os 7 acima, estás a par do essencial.** Os abaixo lês só se o teu trabalho tocar a área.

## 2. LEITURA CONDICIONAL (só se tocares na área)

| Documento | Lê se tocares em… |
|---|---|
| **`docs/HRC_ANATOMIA_OPERACIONAL.md`** | o robot/watcher HRC ou a pipeline de export (`tools/watcher_src/`, `queue_export.py`). |
| **`docs/WATCHER_FLUXO.md`** | o que o watcher DEVE fazer por mão (spec canónico) — antes de mexer no `tools/watcher_src`. |
| **`docs/GTO_BRAIN.md`** | o GTO Brain (`gto_trees`/`gto_nodes`, tab GTO do replayer, pipeline `.zip`→árvores). |
| **`docs/DESANON_ANATOMIA.md`** | a desanonimização/match GG (nicks reais na mão anónima) — `table_ss*.py`, `screenshot.py`. **§3.2.3 = método actual (âncora Hero+botão).** |
| **`docs/TAGS_CANONICO.md`** | **FONTE DE VERDADE das tags de estudo** (vocabulário GG+HM3, significados, 2 regras de incompatibilidade, pastas do IT, `services/tags_canonical.py`). Lê antes de mexer em tags/normalização/gates que lêem tags. |
| **`docs/GLOSSARIO_POKER.md`** | um termo de poker não óbvio (dicionário de consulta, não leitura corrida). |

## 3. DOCS VIVOS vs IMUTÁVEIS (importante para não te confundires)
- **VIVOS (estado ACTUAL):** `TECH_DEBTS_INVENTARIO.md`, `PENDENTES.md`, `REGISTO_CONCEITO.md`
  (append-only), `LICOES.md`. **É aqui que se lê o que é verdade HOJE.**
- **IMUTÁVEIS (snapshots datados):** `docs/JOURNAL_*` e `archive/`. Registam o que era verdade
  **à data** — NÃO se reescrevem. Um item "aberto" num journal antigo lê-se como "à data";
  confirma o estado actual nos docs vivos.

## 4. Onde está o estado de HOJE
O **fim do `CLAUDE.md`** tem "Última sessão fechada: …" com o resumo das sessões recentes
(o que ficou live, commits, próximos passos). É a foto mais fresca. Para o backlog do que
falta, `PENDENTES.md`.

## 5. Regras de ouro que NÃO podes ignorar (estão no CLAUDE.md, mas repito)
- **Anti-cheat:** o PC de dev é o mesmo onde o Rui joga. Só correr processos "suspeitos"
  com as salas de poker FECHADAS.
- **Âmbito de disco:** o Code só lê/toca paths explicitamente listados; fora disso, pede ao Rui.
- **Chama laranja = VPIP (%), NÃO bounty; coroa dourada = bounty ($); verde numa coroa
  alheia = transferência de KO.** (armadilha recorrente — ver CLAUDE.md.)
- **Decisões de produto/dados = Rui.** Web/Code movem-se dentro do descrito.
