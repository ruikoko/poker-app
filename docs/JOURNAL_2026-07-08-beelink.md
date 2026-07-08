# JOURNAL — 2026-07-08 — Beelink (frente WATCHER/HRC, branch `watcher-front`)

Sessão paralela ao Code do PC principal. Faixa: `tools/watcher_src/`,
`tools/hrc_adapter/`, este journal, `_local_only/`. Nunca em `main`.

## Arranque — ambiente sondado

| Item | Estado |
|---|---|
| Checkout | Clonado em `C:\Users\riand\poker-app` (não havia checkout no Beelink; só artefactos implantados) |
| Branch | `watcher-front` criado de `origin/main` (⚠️ ver "Achado 2" — base errada para o watcher) |
| Python 3.12 | Instalado `3.12.10` via `py install 3.12` (só havia 3.14.5). Build venv = 3.12.0 |
| PyInstaller | `6.21.0` no 3.12 (scripts fora do PATH → usar `py -3.12 -m PyInstaller`) |
| `HRC_WATCHER_API_KEY` | Definida (User+Process, 64 chars) — valor não impresso |
| Material de build | `_local_only/watcher_decompile/` copiado à mão pelo Rui (decompiled/, swap_and_smoke.py, build_pyi/wrapper.py+spec, patched_pyc/, pycdc/, venv/) |
| Exe instalado | `C:\Users\riand\HRCWatch\hrc_watcher.exe`, 30/06 18:58, SHA256 `8390D405…090E1` |
| ↳ Release | Não bate com pt90 (`69e741c2…`), pt93 (`af124d8c…`) nem pt87 (`e1dced5a…`). Build posterior ao pt93 (provável pt94 — SHA não registada nos docs). Mapeamento exato pendente. |

## Alvo: `#WATCHER-LOG-FILE-REGRESSION-PT90` — DIAGNÓSTICO (causa raiz confirmada)

**Não é bug de build nem de fonte.** A fonte está intacta: `_ensure_file_logging`
(`patched_funcs.py:1954`) é chamada como 1ª linha do `setup_hand` (`:2299`), em
`main` e `watcher-gate`. O spec é `console=True` (não windowed) → `sys.stdout`
é stream real. Prova nos logs (`C:\hrc\watcher_logs`), grep por `[log] a gravar em`:

- 24–25 Jun (pré-pt90): `hrc_watcher_*.log` com a marca. ✅
- **26 Jun (smoke pt90): zero `hrc_watcher_*.log`**; só `pt90_stdout/stderr_*`
  (redirect externo por `.bat`, workaround do Rui). **Nem `[log] a gravar em`
  nem `_ensure_file_logging falhou`** → a função **nunca foi chamada** (nenhuma
  mão chegou ao `setup_hand`; a sessão pt90 era validação de OCR/tree-guard).
- 27 Jun 09:55+: `hrc_watcher_*.log` voltam; o `pt90_stdout_20260627_094635.log`
  contém ao vivo `[log] a gravar em …095523.log` → mal uma mão real correu,
  o self-log arrancou. 27–30 Jun: 14 sessões, todas com a marca → **o exe
  instalado loga bem em batch**.

**Causa raiz = inicialização preguiçosa (hipótese 3 do tech debt):** o log só
nasce na 1ª `setup_hand`. Sessões sem mão (fila vazia, arranque-só, smokes de
OCR, abort antes da 1ª mão) ficam sem ficheiro. O pt90 **expôs** (não introduziu)
— foi validado precisamente em sessões sem mão. Hipóteses 1 (bundle/trampoline)
e 2 (windowed) **descartadas**: a função tem sucesso sempre que uma mão corre.

## Fix aplicado (fonte; rebuild pendente)

`_local_only/watcher_decompile/build_pyi/wrapper.py` — entre `exec(code, g)` e
`g["main"]()`, chamar `g["_ensure_file_logging"]()` no BOOT (antes do loop/banner),
independente da fila. Idempotente (`_FILE_LOGGING_READY`) → a chamada no
`setup_hand` fica backstop. `patched_funcs.py` **intocado**. `_ensure_file_logging`
está em `EXPECTED_APPENDS` (`swap_and_smoke.py:151`) → presente em `g`.

## Passo 2 (harness) — 2 achados, PARADO antes de rebuild

**Achado 1 — portabilidade (corrigido).** `swap_and_smoke.py` tinha
`REPO = Path(r"C:\Users\User\Desktop\pokerapp\poker-app-actual")` hardcoded (PC
principal) → crash de `mkdir` em `C:\Users\User` no Beelink. Fix in-lane:
`REPO = Path(__file__).resolve().parents[2]` (portável nas duas máquinas).

**Achado 2 — a fonte do watcher está em `watcher-gate`, NÃO em `main`.** Após o
fix de portabilidade o harness correu e falhou com `patched_funcs.py lost an
EXPECTED_APPEND` (19 funções em falta: tree-guard/OCR pt90, watchdog de foco
pt95, verify save-as pt87). Git confirma: `main` vs `watcher-gate` = 133/14
commits; `patched_funcs.py` 76 vs 100 defs; `tree_stats.py` só existe em
`watcher-gate`. Os 14 commits gate-only são pt87→pt95 do watcher. **O exe
instalado (pt93/pt94) e o harness copiado correspondem ao `watcher-gate`.**
Rebuild a partir do `main` REGREDIRIA o watcher → o gate do harness travou-o (bom).

**Estado:** exe instalado intocado; rebuild NÃO feito. Pendente decisão do Rui:
re-basar `watcher-front` em `origin/watcher-gate` (recomendado) e re-correr o
harness. O fix do log aplica-se igual sobre o gate (`_ensure_file_logging` é pt68,
existe lá).

**RESOLVIDO (Rui aprovou (a)):** `watcher-front` re-criado de
`origin/watcher-gate` (HEAD `049cd4b` pt95). `tree_stats.py` presente,
`patched_funcs.py` 100 defs; edições em `_local_only` e este journal intactos
(untracked/gitignored). A base errada foi do prompt de arranque ("a partir de
`origin/main`"), não do trabalho — travado pelo gate do harness.

## Lições (para o Code do Beelink)

1. **Scripts de `_local_only/` nasceram colados ao PC principal.** Caminhos
   absolutos de máquina (ex.: `C:\Users\User\Desktop\...`) partem no Beelink.
   Padrão ao reutilizá-los aqui: **derivar caminhos da localização do script**
   (`Path(__file__).resolve().parents[N]`), nunca hardcode de máquina. (Aplicado
   a `swap_and_smoke.py`.)
2. **A fonte-de-registo do watcher é `watcher-gate`, não `main`** (14 commits
   pt87→pt95 nunca merged). Buildar o watcher a partir do `main` regride-o.
   Confirmar sempre a base contra o harness (`EXPECTED_APPENDS`) e o exe instalado.
3. **Dívida de repositório (não é do Beelink, não é agora):** a divergência
   `watcher-gate` ↔ `main` (133/14 commits) fica registada para o **PC principal
   arrumar pós-wipe** — decidir o merge/reconciliação dos dois ramos. O Beelink
   apenas builda a partir do `watcher-gate` enquanto essa reconciliação não acontece.

## `#WATCHER-LOG-FILE-REGRESSION-PT90` → ✅ RESOLVIDO (cadeia diagnóstico→fix→prova)

- **Diagnóstico:** init preguiçosa — `_ensure_file_logging` só corria na 1ª
  `setup_hand`; sessões sem mão (o modo do pt90: validação OCR/tree-guard) não
  geravam ficheiro. Não era build nem fonte (hipóteses 1/2 descartadas: a função
  tem sucesso sempre que uma mão corre; `console=True`, não windowed).
- **Fix (in-lane, trampoline `_local_only/watcher_decompile/build_pyi/wrapper.py`):**
  chamar `_ensure_file_logging()` no BOOT, entre `exec(code, g)` e `g["main"]()`:
  ```python
  exec(code, g)
  _boot_log = g.get("_ensure_file_logging")   # #WATCHER-LOG-FILE-REGRESSION-PT90
  if _boot_log:
      _boot_log()
  g["MAX_CONCURRENT"] = 1
  g["main"]()
  ```
  `patched_funcs.py` intocado; idempotente (`_FILE_LOGGING_READY`) → a chamada no
  `setup_hand` fica backstop. (⚠️ o `wrapper.py` é gitignored → o diff fica
  **registado aqui** para o PC principal replicar; ver lição 4.)
- **Build:** deps de runtime instaladas no `py -3.12` do Beelink
  (`pyautogui==0.9.54`, `pygetwindow==0.0.9`, `pyperclip==1.11.0`, `pillow`,
  `winsdk`) + PyInstaller 6.21.0. `.spec` tornado portável (`SPECPATH`) e datas do
  launcher pyc removida (não existe no Beelink e não é carregado). Bundle verificado
  por TOC: `tree_stats` + winsdk OCR (`media.ocr`/`graphics.imaging`/`globalization`/
  `storage.streams`) + `_winrt` presentes → **guarda de árvore VIVA**.
- **Harness `swap_and_smoke.py`:** ALL OK (sub-testes a–q) sobre `watcher-gate`.
- **Prova (boot-log smoke, de `dist`, sem HRC, sem fila):** log novo
  `hrc_watcher_20260708_210840.log` nasceu ~1.8s após o arranque, HRC não abriu;
  1ª linha = `   [log] a gravar em C:\hrc\watcher_logs\hrc_watcher_20260708_210840.log`.
- **Instalado (regra «1 só exe»):** `C:\Users\riand\HRCWatch\hrc_watcher.exe`,
  32 096 806 B, **SHA256 `4417698DD8B820316011E943A32016A43C0210521686DA5F9EC3E8A13E4FEA31`**.
  Substituiu o exe antigo (`8390D405…`, 82 MB). Stray `Downloads\hrc_watcher.zip`
  removido. HRCWatch fica com 1 exe.

## Lição 4 (nova)
- **O fix do watcher vive no `wrapper.py`/`.spec` do trampoline, que são
  gitignored (`_local_only/`).** Não viajam por git → o diff exato tem de ficar
  **no journal** (feito acima) para o PC principal replicar. Sugestão de dívida:
  ponderar versionar o trampoline (fora do `_local_only`) para reprodutibilidade.

## Pendente à entrada da próxima ação
- **Backup pt87 — MANTER (decisão do Rui):** `C:\hrc\backup_watcher\hrc_watcher_pt87_e1dced5a.exe`
  fica FORA das 3 zonas do «1 só exe» — **backup mantido por decisão do Rui,
  rollback único**; o exe novo estreou hoje. Reavaliar quando o novo tiver
  semanas de voo. **Não apagar** entretanto.
- **PC principal (dívida de repo — para o `docs/PENDENTES.md`, que é do Code do PC):**
  ao item já registado da reconciliação `watcher-gate` ↔ `main` (pós-wipe),
  **acrescentar** a nota: replicar o 1-liner do `wrapper.py` (hook de boot do
  `_ensure_file_logging`) no `_local_only` do PC principal — o `wrapper.py` é
  gitignored, logo o diff exato vive na secção "RESOLVIDO" **deste** journal.
  *(Não editei o `PENDENTES.md` a partir do Beelink — fora da minha faixa /
  regra de não-colisão; fica para o Code do PC integrar.)*
- **Opcional (agora moot):** o exe antigo `8390D405…` foi substituído; mapear a sua
  Release deixou de ser necessário.
- Commit+push do journal para `watcher-front` (a aguardar OK do Rui sobre o timing).
