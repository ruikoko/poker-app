# Visão do Produto — Poker Study App

Documento de referência da intenção do utilizador (Rui). Próximas sessões devem ler ANTES de tocar em código que afecte distribuição de mãos, regras de elegibilidade ou pipeline de ingestão.

## Propósito

Centralizar o estudo de poker MTT, juntando dados que hoje estão espalhados em HM3 (Winamax/WPN/PokerStars) e Discord (GGPoker). Foco principal:
1. Mãos próprias com dúvida marcadas durante a sessão (estudo posterior em GTOWizard/HRC).
2. Mãos de adversários que merecem nota.

## Os 4 vectores da app

1. **ENTRADA** — recolher dados (HM3 .bat, Discord bot, upload manual).
2. **PROCESSAMENTO** — parse, match, enriquecimento, placeholders.
3. **DISTRIBUIÇÃO** — enviar cada dado para a secção certa da app.
4. **ANÁLISE** — Rui trabalha sobre o resultado distribuído.

## Filosofia

Automação na recolha/processamento/distribuição. Controlo manual sempre disponível (alterar tags, remover vilões, eliminar mãos). Um único clique deve ser suficiente para o ciclo "varrer Discord + processar + distribuir"; mas o utilizador pode intervir em qualquer ponto pós-distribuição.

## Secções da app

### Secções de ORIGEM (toda mão entra na respectiva)
- **Dashboard** — hub geral; SS e imagens uploadadas manualmente.
- **HM3** — mãos vindas do script .bat HM3 (Winamax/WPN/PokerStars).
- **Discord** — mãos vindas do bot Discord (canais GG).
- **Torneios** — drill-down por torneio (toda mão GG entra aqui).

### Secções DERIVADAS

Sidebar tem 7 secções: as 4 de ORIGEM acima + **Estudo**, **Vilões**, **GTO**. Estudo e Vilões aplicam regras de elegibilidade estritas (abaixo). GTO é secção dedicada — regras e propósito documentados separadamente desta visão.


#### Estudo

TODAS as condições têm de cumprir-se cumulativamente. Fonte de verdade: `backend/app/routers/hands.py:567-574` (filtros aplicados quando `study_view=true`).

**Condições técnicas:**
- Nicks reais, não hashes — `STUDY_VIEW_GG_MATCH_FILTER` (`hands.py:359-363`): mãos GG exigem `match_method` populado e diferente de `discord_placeholder_*`; outras salas passam livremente.
- HH presente — `STUDY_VIEW_REQUIRES_HH` (`hands.py:395`): `h.raw IS NOT NULL AND h.raw != ''`.
- Não estar em arquivo MTT — `h.study_state != 'mtt_archive'` (default em `hands.py:565-566`).

**Condição de tag** — `STUDY_VIEW_HAS_STUDY_TAG` (`hands.py:402-409`):
- Pelo menos 1 tag de estudo:
  - Tag HM3 que NÃO bate `nota%` (case-insensitive).
  - OU canal Discord que NÃO seja `nota`.

**Excepção (aditiva):**
- Mão com tag `nota` + tag de estudo → entra em Estudo E Vilões.
- Mão SÓ com `nota` → vai apenas para Vilões.

**Não exigido pelo código** (apesar de docs antigas afirmarem): `tournament_name`, `buy_in`, `site`. Parsers PS deixam `tournament_name=None` deliberadamente; parsers WPN deixam `buy_in=None` deliberadamente. Exigir bloquearia mãos legítimas — por isso o filtro do código não os impõe.

#### Vilões

Critérios (basta cumprir um — regras A∨C∨D, definidas em `_classify_villain_categories`):

- **Regra A** — Tag HM3 a começar por `nota` (`nota`, `notas`, `nota+`, `nota++`, derivados).
- **Regra C** — Canal Discord `nota` em `discord_tags` com match SS↔HH real (não `discord_placeholder_*`).
- **Regra D** — Non-hero é nick em `FRIEND_HEROES` (`backend/app/hero_names.py` — actualmente Karluz, flightrisk). Independente de tag; dispara sempre que o nick aparece como non-hero numa mão com nicks reais. Permite ver mãos de amigos sem o Rui ter de marcá-las.

## Regra de cross-post Discord

Toda mão que apareça num canal Discord deve ter o nome desse canal em `discord_tags`. Sem excepções por origem da mão (Discord directo, HM3, GG anon, GG enriched).

Se uma mão é cross-postada em N canais, `discord_tags` deve conter os N nomes.

## Casos canónicos (referência rápida)

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
| 9 | qualquer (com nicks reais) | sem tags; non-hero é Karluz/flightrisk | ✗ | ✓ (Regra D) | secção origem + Vilões |

## Pipeline diário típico do Rui

1. Termina sessão de poker.
2. Importa HH GGPoker do dia (Torneios > Sem SS).
3. Sincroniza Discord (mãos cross-postadas + replayer-links + imagens contexto).
4. Eventualmente: upload manual de SS de amigos (raro).
5. App processa, cataloga e distribui.
6. Dia seguinte: trabalha mãos em Estudo + Vilões.
7. Estuda fora (GTOWizard/HRC).
8. Volta a jogar, marca novas mãos, ciclo repete.

## Áreas futuras (não implementar sem confirmação Rui)

- **Análise post-estudo** — secção dedicada com evolução das mãos estudadas.
- **Estudo de população** — explorar mãos GG sem tag (Caso 7/8) para tendências do field.
- **GTO Brain** — documentado separadamente.
- **Integração GTOWizard / HRC** — futura, não próxima.

## O que a app NUNCA deve fazer

- Mãos GG anonimizadas (sem `match_method`) NÃO podem aparecer em Estudo.
- Mãos só com tag `nota` NÃO podem aparecer em Estudo.
- Mãos sem HH NUNCA aparecem em Estudo (mesmo que tenham tags).
- Cross-post Discord NÃO pode perder canais (regra acima).
