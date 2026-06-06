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

## Estado atual do build (cdfc7247 / pt42d) — a corrigir
- A parte "configurar → Finish → 1ª run" está CORRETA.
- A seguir à 1ª run o build faz um Prune (errado) + uma run intermédia com configurações
  antigas (redundante) antes da run boa. Correção: a seguir à 1ª run, ir DIRETO a
  seleccionar o nó (1ª ação não-fold) + Selected Subtree + CI=10 + OK + esperar + exportar.
