# tools/watcher_src — patched watcher functions

Funções modificadas do `hrc_watcher_apr19.pyc` (watcher do Baltazar) que são
**injectadas no bytecode original via marshal code-object swap** durante a
re-bundle PyInstaller (PASSO 5 de pt23). O ficheiro fonte do watcher não está
acessível — Baltazar emigrou sem deixar source. As reconstruções partiram de:

1. `pycdc` 0.x build local (`_local_only/watcher_decompile/pycdc/`) — recuperou
   ~72% das funções do main module limpas;
2. `dis` disassembly manual (host Python 3.12) para as ~28% partials que pycdc
   abandonou com `Decompyle incomplete`, em particular `setup_hand` (caller
   crítico dos 3 bugs);
3. `docs/_local_only/ANALYSIS.md` como referência funcional (mapa do flow
   completo: ensure_hrc → open_wizard → paste_hh → wizard pages → export).

## Porquê estas 4 funções?

Em pt22 o smoke real Beelink ↔ poker-app expôs 3 bugs funcionais no watcher:

| Bug | Sintoma | Função alvo |
|---|---|---|
| **A** | Equity model fixo em Malmuth-Harville; mid-MTT pede Multi-Table FGS | `set_equity_model` + caller `setup_hand` |
| **B** | Max players conta seats da HH em vez de jogadores relevantes à decisão | `get_player_count_from_hh` + caller `setup_hand` |
| **C** | Nome do script HRC Pro hardcoded → tree >20GB → OOM crash | `setup_scripting` + caller `setup_hand` |

A solução adoptada (pt22 decisão Web+Rui, formalizada em `REGRAS_NEGOCIO.md §14`)
é **tag-based via hints no `payouts.json`**: o backend (`queue_export.py`)
escreve top-level keys `equity_model`, `max_players`, `script_path` no
`payouts.json` de cada mão; o watcher lê esses hints em `setup_hand` e despacha
para as 3 funções alteradas.

## Estratégia: marshal swap em vez de refactor completo

Tech debt `#WATCHER-DECOMPILE-FULL` regista que o **refactor completo do
watcher** (recuperar ~900 linhas de source limpo) fica para pt24+. Por agora
fazemos só o mínimo cirúrgico: compilamos estas 4 funções com `compile()` no
host Python 3.12, extraímos os 4 code objects, e substituímos nos
`co_consts` do module code do `hrc_watcher_apr19.pyc` original via `marshal`.
Re-marshal + re-bundle PyInstaller produz um `.exe` funcionalmente equivalente
ao Apr19 do Baltazar **excepto nas 4 funções**.

## Resolução de globais em runtime

`patched_funcs.py` **não importa** os símbolos não-stdlib usados pelo corpo
das funções (`click_rel`, `pyautogui`, `paste_path`, `ensure_hrc`,
`open_wizard`, `get_win_pos`, `paste_hh`, `set_hand_mode_players`,
`import_prizes`, `is_ko_tournament`, `select_bounty_mode`,
`handle_mtt_stacks_page`, `start_calculation`, `export_strategies`, nem as
constantes `BTN_NEXT`, `BTN_FINISH`, `SCRIPT_FILE`, `SCRIPTING_TAB`,
`SCRIPT_FOLDER`, `DONE_DIR`). Estes são **module-level no watcher original**
e serão resolvidos em runtime via `LOAD_GLOBAL` contra o namespace do módulo
em que as funções são injectadas (i.e., o módulo do `hrc_watcher_apr19.pyc`
após exec do launcher). O ficheiro importa apenas `json`, `os`, `re`, `time`
que correspondem aos símbolos stdlib usados localmente — estes serão
re-resolvidos contra o module namespace na mesma altura (e estão lá: o
original importa as 4).

## Validação de sintaxe

```
python -c "import ast; ast.parse(open('tools/watcher_src/patched_funcs.py').read())"
python -c "compile(open('tools/watcher_src/patched_funcs.py').read(), 'patched_funcs.py', 'exec')"
```

Ambos passam (pt23 passo 4 validation).

## Não correr standalone

`python patched_funcs.py` falha porque `click_rel`, `pyautogui`, etc. não
existem fora do namespace do watcher. **Só serve como source para o marshal
swap.** Tentar testar isoladamente é red herring.
