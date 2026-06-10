# Fluxo do Watcher HRC (comportamento desejado)

**Propósito:** spec canónico de como o watcher deve processar cada mão. Referência
obrigatória antes de mexer no código do watcher (tools/watcher_src) ou de diagnosticar
o seu comportamento. Em caso de dúvida sobre o que o watcher DEVE fazer, manda este
documento — não o que o código atual faz.

## Fluxo por mão
1. Configurar a mão no wizard: stacks, blinds, prémios, equity model, MTT stacks/players,
   scripting.
2. Clicar **Finish**. É o Finish que lança a 1ª run (NÃO arranca sozinha). A 1ª run usa
   as configurações do próprio HRC: 10 milhões de iterações, full tree. Serve apenas para
   distribuir as cartas pelos jogadores. Deixar acabar.
3. No fim da 1ª run, fazer a 2ª run:
   - Seleccionar o nó da 1ª ação que NÃO seja fold (a primeira ação voluntária da mão;
     ex.: se o BTN foi o primeiro a entrar a abrir, seleccionar o nó do BTN open).
   - Scope = Selected Subtree.
   - CI target = 10.
   - Clicar OK.
   - Esperar que a 2ª run termine.
4. Exportar no fim da 2ª run (o save é feito quando a 2ª run acaba).

## O que NÃO se faz
- Sem Prune. O watcher não corta linhas na árvore (procedimento antigo, abandonado).
- Sem run redundante. São exatamente DUAS runs: a 1ª (lançada pelo Finish) e a 2ª
  (Selected Subtree, CI=10, focada no nó da 1ª ação não-fold). Nenhuma run intermédia
  com configurações antigas.

## Estado do build (pt66 `9ea51ce4`) — RESOLVIDO

O build pt66 implementa este spec (em buffer/release; pendente **re-smoke real** —
ver `docs/JOURNAL_2026-06-10-pt66.md`):

- A **run intermédia redundante foi REMOVIDA** (`#HRC-REDUNDANT-SECOND-RUN-OLD-CONFIGS`):
  a 1ª run é lançada pelo **Finish**; a seguir vai-se **DIRETO** a seleccionar o nó (via
  `target_node_offset` do `meta.json`) → Selected Subtree → OK → esperar → exportar.
  São **exatamente 2 runs, sem prune**.
- O **CI já NÃO é escrito** pelo watcher: o default do popup Nash é sempre **10.0** (= o
  alvo); há uma **salvaguarda só-leitura** que avisa se ≠ 10 (regra operacional: ninguém
  altera o CI à mão no Beelink).
- O **Bounty Mode** vem da **estrutura importada** (`import_prizes`), não de um hardcode.

> **Builds anteriores** (`cdfc7247`/pt42d, `3fb1b512`/pt64) **faziam** a run intermédia
> (disparada *durante* a 1ª run, que o HRC enfileirava → 3 runs). O `meta.json` já trazia
> `target_node_offset` + `aggressor_real_action`; faltava o watcher consumi-los sem a run
> a mais. pt66 fá-lo.
