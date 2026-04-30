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
- **HM3** — mãos vindas do script .bat HM3.
- **Discord** — mãos vindas do bot Discord.
- **Torneios** — drill-down por torneio (toda mão GG entra aqui).
- **Dashboard** — SS e imagens uploadadas manualmente.

### Secções DERIVADAS (com regras de elegibilidade estritas)

#### Estudo

TODAS as condições têm de cumprir-se cumulativamente:

**Condições técnicas:**
- Nicks reais, não hashes (mãos GG: requer `match_method` preenchido e diferente de `discord_placeholder_*`).
- Nome de torneio (`tournament_name`) preenchido.
- Buy-in (`buy_in`) preenchido.
- Sala (`site`) preenchida.

**Condição de tag:**
- Pelo menos 1 tag de estudo:
  - Tag HM3 que NÃO seja `nota` / `notas` / `nota+` / `nota++` / derivados.
  - OU canal Discord que NÃO seja `nota`.

**Excepção (aditiva):**
- Mão com tag `nota` + tag de estudo → entra em Estudo E Vilões.
- Mão SÓ com `nota` → vai apenas para Vilões.

#### Vilões

Critério único:
- Tag HM3 `nota` / `notas` / `nota+` / `nota++` / derivados, OU
- Canal Discord `nota`.

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
- Mãos sem nome de torneio / buy-in / sala NÃO podem aparecer em Estudo.
- Cross-post Discord NÃO pode perder canais (regra acima).
