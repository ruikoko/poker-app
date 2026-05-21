# Anatomia operacional do HRC

**Estado:** rascunho v4, 21 Maio 2026 (pt29 madrugada).
**Origem:** consolidação dos factos espalhados pelos journals + observações
directas do Rui durante pt28 + smoke tests pt29.
**Responsável de manter actualizado:** quem descobrir um facto novo edita
este ficheiro antes de fechar o trabalho. Sem isto, o conhecimento perde-se.

**Histórico de versões:**
- v1 (pt28 manhã): rascunho inicial — filosofia + 11 secções + 14 lacunas.
- v2 (pt28 tarde): popup Nash detalhado (6 campos descobertos via screenshot)
  + clipboard bug pyperclip 1.11.0 documentado + apps competidoras mapeadas.
- v3 (pt28 fim do dia): **§12 nova "Formato de HH aceite pelo HRC"** — o
  HRC parser identifica formato por prefixo do header; descoberta empírica
  de que GG-format com bounty injectado nas seats é rejeitado, e de que a
  conversão para PokerStars-format funciona (validada manualmente no HRC
  com a mão GG-5944816316). §3.1 e §10 actualizadas com nota sobre o
  auto-import do clipboard pelo HRC quando o wizard abre.
- v4 (pt29 madrugada): **três factos novos sobre interacção com o HRC**,
  descobertos na cascata de bugs do robot pt29-v1 → v2 → v3.
  (a) §3.5 — o HRC (Java) **perde eventos de click instantâneo** no botão
  Finish: `mouse-down + mouse-up` em <50 ms não actua sobre o botão.
  É necessário um "slow-click" (down → sleep ≥100 ms → up) para o evento
  ser registado. Activate da janela pré-click é necessário mas não chega
  sem o slow-click.
  (b) §7 — o HRC **não emite sinal explícito de "calculation done"**.
  O único indicador inferível é a estabilização do uso de memória:
  enquanto calcula, a memória oscila com alocações; quando termina,
  estabiliza. Heurística usável: memória `>100 MB` e variação `<20 MB`
  durante 3 ciclos de 10 s implica run terminada.
  (c) §3.4 — comportamento de Hand Mode "Max Players" descoberto:
  controla quantos jogadores podem estar em pots simultaneamente no
  Monte Carlo. Mesas 8-handed deep PKO requerem **Max 6** (pots 5-way são
  possíveis); Max 4 trunca o cálculo. Foi a causa de discrepâncias de
  tree size entre PC principal (Max 4) e Beelink (Max 6) que se atribuíam
  ao script.

---

## Função deste documento

Tornar o conhecimento operacional sobre o HRC um bem comum do projecto,
em vez de viver só na cabeça do Rui. Quando o Rui se encontrar a explicar
pela enésima vez o mesmo facto, é sintoma de que esse facto faltava aqui.
Quando o documento estiver completo, o Code e o Web podem trabalhar sobre
o HRC sem voltar a pedir-lhe o que ele já sabe.

## Filosofia

1. **Só factos observáveis.** Comportamentos visíveis ao olho ou medíveis
   com ferramentas standard. Não opiniões, não interpretações, não código
   nosso.

2. **Verdade sobre o HRC, não sobre o nosso software.** As coordenadas
   no nosso código são **medições** que pertencem aqui. A forma como o
   nosso robot reage é decisão nossa e vive em
   `tools/watcher_src/patched_funcs.py`.

3. **Baltazar é a base.** O robot original do Baltazar funcionava bem em
   uso single-hand. Bugs descobertos depois de nós alterarmos o robot
   foram introduzidos por nós.

4. **Cada facto com data e contexto.** Quando foi observado pela última
   vez, em que máquina, com que resolução.

5. **Tradução de jargão.** Termos técnicos traduzidos na primeira
   ocorrência (ex: "Strategy Table — a tabela das estratégias"). Audiência
   primária: Web + Code. Rui lê em bónus.

---

## 1. Identificação do HRC

| Item | Valor |
|---|---|
| Nome oficial | Holdem Resources Calculator (HRC) |
| Autor | Baltazar Studios |
| Estado | Descontinuado pelo autor (sem actualizações desde 2024-ish) |
| Versão instalada no Beelink | **LACUNA — Rui confirma número exacto** |
| Instalador moderno | `C:\Users\<user>\AppData\Local\Programs\HoldemResources\HRC\hrc.exe` |
| Instalador legacy "Beta" | `C:\Users\Administrator\AppData\Local\HoldemResources\HRC Beta\hrc.exe` |
| Configuração no Beelink actual | Junction `HRC Beta → HRC` em `Administrator\AppData\Local\HoldemResources\` (resolve mismatch do path interno do robot) |
| API | Nenhuma. Controlável apenas via simulação de cliques e teclas (pyautogui) |
| Scripting interno | JavaScript via Nashorn — usado para configurar sizings e prune actions |

## 2. Janela e foco do HRC main

| Item | Valor |
|---|---|
| Tamanho típico observado no Beelink (não-maximizada) | `width=1050, height=850` |
| Posição típica observada no Beelink | `left=283, top=65` |
| Maximização | **LACUNA — confirmar: o HRC é arrancado maximizado ou em janela?** |
| Persistência de estado entre sessões | A última mão carregada **fica visível** no wizard quando o HRC reabre. A caixa do hand history não fica vazia |
| Sobrescrita | Quando se cola uma mão nova por cima de uma anterior (via `Ctrl+V` ou botão "Paste from Clipboard"), o conteúdo é **substituído**. Mão antiga não atrapalha |
| Borracha (botão de limpar) | Existe um botão na página Basic Hand Data que apaga todo o conteúdo. Usado **opcionalmente** quando o utilizador quer começar do zero. Não é necessário antes de colar mão nova — o paste sobrescreve sozinho |

## 3. Wizard de criação de mão ("Tournament Setup")

O wizard tem páginas em sequência. Cada página tem um botão "Next" para
avançar. A última página termina com "Finish".

### 3.1 Página Basic Hand Data (paste do HH)

| Item | Valor |
|---|---|
| Função | Colar o hand history (HH) da mão a calcular |
| Botão dedicado | "Paste from Clipboard" (lê do clipboard do Windows) |
| Sequência manual (utilizador a fazer à mão) | Apenas `Ctrl+V`. Sobrescreve qualquer conteúdo anterior |
| Borracha (opcional) | Clicar na borracha para limpar a caixa, e depois `Ctrl+V`. **Não é necessário** mas existe |
| Erro conhecido | `"No valid hand-history found in the Clipboard"` — aparece quando o clipboard está vazio ou contém conteúdo não reconhecido como HH |
| **Auto-import do clipboard** | **No momento em que o wizard "New Hand" abre, o HRC lê o clipboard imediatamente e tenta auto-importar. Se o conteúdo for lixo (qualquer texto que não seja HH válido), o popup azul "No valid hand-history" aparece logo, antes do robot ter chance de fazer Ctrl+V** |
| Implicação | O robot tem de pôr o HH no clipboard ANTES de abrir o wizard. Implementado em pt28-v3 (`_set_clipboard_with_verify` em `patched_funcs.py`) |
| Formatos de HH aceites | Ver §12. O HRC só aceita HHs em formatos específicos por sala (PokerStars, Winamax, GG, ...) — qualquer modificação ao formato canónico pode causar rejeição silenciosa |
| Bug histórico do nosso software | Bug I (pt25e, provisório, sem repro consistente) — robot clicava num botão errado neste painel |

### 3.2 Página Equity Model

| Item | Valor |
|---|---|
| Função | Escolher o modelo de equity |
| Posição da caixa (rel à wpos) | `(446, 561)` |
| Método de selecção | Typeahead — escrever as primeiras letras do nome do modelo |
| Typeahead "ma" | Selecciona "Malmuth-Harville ICM" |
| Typeahead "mu" | Selecciona "Multi Table ICM" |
| Typeahead "fg" | Selecciona "FGS" (fora do scope actual) |
| 4º modelo | **LACUNA — qual é o quarto modelo no dropdown?** |

### 3.3 Página MTT Stacks (condicional)

| Item | Valor |
|---|---|
| Quando aparece | Sempre que o equity model é "Multi Table ICM" |
| Campo "Remaining Players" | Coord absoluta `(977, 330)` no Beelink. Click-rel actual no source: `(1230, 289)` |
| Campo "Total Chips" | Coord rel `(677, 438)`. Sequência: click → Ctrl+A → typewrite |
| Campo "Other Tables" | **LACUNA — qual é a coord? Default = 0** |
| Implicação de Other Tables = 0 | Matematicamente equivalente a FT ICM com N jogadores. Cálculo enviesado se o torneio tem mais jogadores em outras mesas |
| Workaround actual | Se `meta.json.stage='MTT'` + `players_left` presentes, preenche Remaining Players. Senão, salta a página clicando "Next" (deixa Other Tables = 0) |

### 3.4 Página Scripting

| Item | Valor |
|---|---|
| Função | Carregar o script JavaScript que define sizings e prune actions |
| Tab "Scripting" | Coord `SCRIPTING_TAB` (**LACUNA — valor literal está no .pyc Baltazar**) |
| Campo Script Folder | Coord `SCRIPT_FOLDER` (**LACUNA — idem**) |
| Sequência | Click no Script Folder → paste do path absoluto do `.js` |
| Script per-mão | O backend gera um `.js` específico para cada mão (Trabalho A pt25f). Path absoluto vai em `payouts.json.script_path` |

### 3.5 Página Finish

| Item | Valor |
|---|---|
| Botão | "Finish" (coord `BTN_FINISH = (568, 640)` relativa à wpos do wizard, validada empíricamente em pt29-v1/v2 no Beelink) |
| Após click bem sucedido | HRC fecha o wizard ("Hand Setup" desaparece do títulos de janelas) e abre a mesa preparada |
| Tempo de carregamento | ~30 segundos para o HRC estabilizar a mesa antes de poder iniciar cálculos |
| **Tipo de click exigido (descoberto pt29)** | **Slow-click obrigatório.** `pyautogui.click()` instantâneo (mouse-down + mouse-up em <50 ms) é frequentemente perdido pelo Java do HRC e o wizard persiste como se nada se tivesse passado. Solução validada: `mouseDown(button='left')` → `time.sleep(0.15)` → `mouseUp(button='left')` |
| **Activate pré-click (descoberto pt29)** | Necessário fazer `w.activate()` da janela "Hand Setup" antes do click (move o foco do SO para esta janela). Confirmado por log `foreground=hwnd=... title='Hand Setup'` no momento do click. **Activate sozinho não chega** sem o slow-click; ambos são necessários em conjunto. |
| **State check pós-click recomendado** | Após o click, verificar se a janela "Hand Setup" deixou de existir nos títulos de janelas do SO. Se ainda existe, o click falhou — log WARN e degradar conforme política do robot. Sem este state check, o robot prossegue cego com setup parado. |

### 3.5.1 Wizard recapitulado — Tree Statistics (página Betting Setup, pós-Scripting)

A última página do wizard antes do Finish é "Betting Setup → Scripting"
e mostra automaticamente, no fundo, um painel "Tree Statistics and
Abstractions":

| Campo | Significado |
|---|---|
| Total Nodes | Número total de nós da árvore que será construída |
| Total Tree Size | Memória estimada para a árvore inteira |
| HRC available | `X / Y` onde Y é a RAM máxima reservável (cap interno do HRC, observado 20.4 GB) e X é o quanto está livre no momento |
| Flop / Turn / River | Buckets de abstracção em cada street (defaults da config UI: 1024 / 256 / 256) |

Se `Total Tree Size > HRC available`, o Finish corre mas o cálculo
crasha logo a seguir por falta de memória. Validar tree size antes do
Finish é boa prática.

### 3.6 Outras páginas observadas no wizard

#### 3.6.1 Hand Mode (Max Players)

| Item | Valor |
|---|---|
| Função | Define quantos jogadores podem estar simultaneamente activos num pot durante o Monte Carlo |
| Observado no log do robot | `Hand Mode: Max Players = 6` |
| Valores típicos vistos | 4, 5, 6 |
| **Impacto descoberto em pt29** | **Mesas 8-handed deep PKO podem produzir pots 5-way.** Com Max 4 o cálculo trunca cenários relevantes; com Max 6 considera-os. Pode causar discrepâncias grandes de tree size entre PC principal e Beelink se os defaults forem diferentes. |
| Default no Beelink (config UI exportada pelo Rui) | Max 6 |
| Recomendação | Para PKO 8-max alinhar em **Max 6** em todas as máquinas de cálculo |

#### 3.6.2 Bounty Mode

| Item | Valor |
|---|---|
| Função | Define a percentagem do prize pool atribuída a bounties em PKO |
| Detecção automática pelo robot | "KO detetado — a selecionar Bounty Mode PKO 50%..." (heurística no source) |
| Valor habitual | "PKO 50%" |
| Outros | **LACUNA — listar opções do dropdown** (Vanilla, PKO 25%, PKO 50%, Mystery KO, ...) |
| Observação | Em GG, a percentagem real depende do `tournament_format` parsed do TS. Hardcoded em 50% no robot Baltazar OG (`#HRC-BOUNTY-HARDCODED-50PCT`, follow-up por fazer) |

## 4. Painel principal da mesa (pós-Finish)

| Item | Valor |
|---|---|
| Botão verde "Calculate" (play) | Coord absoluta `(487, 124)` no Beelink. Coord rel à wpos: `(204, 59)` |
| Função do Calculate | Abre o popup "Nash Calculation" |

## 5. Strategy Table (a tabela das estratégias, visível após cada corrida)

| Item | Valor |
|---|---|
| Quando aparece | Após uma corrida (run) terminar — fica a coluna do lado esquerdo do HRC |
| Foco do teclado por defeito | Já na própria Strategy Table — setas funcionam directamente sem precisar de click prévio |
| Linha seleccionada por defeito | Sempre a 1ª (UTG, primeira acção preflop) |
| Resposta às setas | Instantânea, sem necessidade de timing generoso entre presses |
| Comportamento no fim das linhas | Para. Não cicla |
| Coluna "Player" — labels canónicos | UTG / MP / HJ / CO / BU / SB / BB (usa "BU" não "BTN"). Para N=7+, aparece "MP" entre UTG e HJ |
| Estrutura típica observada (4-handed: CO/BU/SB/BB) | 7 linhas — 2 por posição não-blind (CO/BU = 4 linhas) + 3 para SB (Call/Complete + small raise + all-in) |
| Estrutura típica observada (5-handed: UTG/HJ/BU/SB/BB) | 9 linhas — 2 por não-blind (UTG/HJ/BU = 6 linhas) + 3 para SB |
| Convenção de índices em scripting | UTG = 0 (first-to-act), SB = N-2, BB = N-1 (segundo docs HRC oficiais) |

### Atalhos de teclado da Strategy Table

| Atalho | Acção |
|---|---|
| `Ctrl+D` | Prune Action (na linha actual) |
| `Ctrl+Shift+D` | Prune Children |
| `Ctrl+Shift+A` | Add Action |
| `Alt+L` | Lock/Unlock Range |
| `Ctrl+C` / `Ctrl+Shift+C` | Copy Range / Strategy |
| `Ctrl+V` / `Ctrl+Shift+V` | Paste Range / Strategy |

## 6. Popup "Nash Calculation"

| Item | Valor |
|---|---|
| Quando abre | Ao clicar no botão verde Calculate do main UI |
| Tipo | Dialog modal **separado** do main HRC window (tem rect próprio) |
| Título exacto | `"Nash Calculation"` (case-insensitive para match) |
| Tempo até abrir após click | Tipicamente imediato (poucos segundos) |
| Rect observado 19 Maio | `left=590, top=337, width=436, height=230` |
| Rect observado 18 Maio | `width=416, height=214` |
| **Estabilidade do rect** | **Variável entre sessões** (~5% em width, ~7.5% em height entre 18 e 19 Maio). Não usar fracções; usar pixels rel ao top-left do popup |
| Estrutura do popup | 6 campos em layout vertical + 2 botões (OK, Cancel) em baixo |

### Campos do popup, pela ordem visual (de cima para baixo)

| Posição | Campo | Tipo | Valor por defeito | O robot toca? |
|---|---|---|---|---|
| 1 | CFR Algorithm | dropdown | "HRC 4.0 (Default)" | Não — fica no default |
| 2 | Scope | dropdown | "Full Tree" | **Sim** — quer mudar para "Selected Subtree" na 2ª corrida |
| 3 | Run Sampling | dropdown | "Until CI value is reached" | Não — fica no default |
| 4 | CI Target | campo de texto | 10.0 (ou anterior) | **Sim** — escreve o CI da mão (lido do meta.json) |
| 5 | Reset Regret | checkbox | desligado | Não |
| 6 | Reset Strategies | checkbox | desligado | Não |
| — | OK | botão | — | **Sim** — confirma e fecha o popup |
| — | Cancel | botão | — | Não |

### Widgets do popup (coords pixels-rel ao top-left do popup)

| Widget | Coord rel actual | Origem | Estado |
|---|---|---|---|
| Dropdown "Scope" | `(278, 67)` | smoke 18 Maio pt25f | Suspeita de desfasamento (~12 pixels em Y baseado em estimativa visual de imagem pt28) |
| Opção "Selected Subtree" (lista flutuante do dropdown aberto) | `(274, 108)` | smoke 18 Maio pt25f | Idem |
| Campo "CI Target" | `(270, 109)` | derivado das fracções legacy do Baltazar (0.65×416, 0.51×214) | A funcionar — o robot escreve 10.0 OK |
| Botão OK | **LACUNA** | observado em pt25e como `(895, 568)` absoluto (popup da 1ª corrida) | Precisa coord rel ao popup |
| Botão Cancel | **LACUNA** | — | — |

### Dropdown Scope — comportamento

| Item | Valor |
|---|---|
| Opções disponíveis | 2: "Full Tree" (topo, default) e "Selected Subtree" (baixo) |
| Sequência para mudar para Selected Subtree | (a) click no dropdown (Y=67) para abrir; (b) click na opção "Selected Subtree" (Y=108) na lista flutuante |
| Comportamento se não se mudar | A corrida que arranca é Full Tree (igual à 1ª, inútil para refinamento) |
| Ordem natural do utilizador | "Indiferente" segundo o Rui, mas visualmente Scope aparece em cima e CI em baixo |

### Bug observado em pt28 — robot não muda o scope na 2ª corrida

| Aspecto | Valor |
|---|---|
| Sintoma | Robot abre o popup correctamente; escreve 10.0 no CI Target; clica OK; mas o Scope fica em "Full Tree" (default) em vez de mudar para "Selected Subtree". Resultado: 2ª corrida é Full Tree em vez de Selected Subtree, inútil para refinamento |
| Observação do Rui | "Foi APENAS directo ao CI" — robot não toca no dropdown do Scope visualmente |
| Causa provável (em investigação) | (a) ordem invertida no source — `_fill_ci_target_in_popup` corre antes de `_set_scope_in_popup`; (b) ou os 2 clicks de scope acontecem em sítio errado (coords podem ter desfasamento de ~12 pixels desde a calibração de 18 Maio) |
| Estado actual | Briefing entregue ao Code para inverter ordem + adicionar logging defensivo + smoke real consolidado |

## 7. Corridas (runs)

| Item | Valor |
|---|---|
| 1ª corrida | Tipicamente Scope = Full Tree |
| 2ª corrida | Tipicamente Scope = Selected Subtree, focada na linha do agressor real |
| CI Target — significado | "Confidence Interval" — quanto mais baixo, mais refinado, mais demorado |
| CI = 5 | Muito refinado, ~7.2h para 1ª run completa |
| CI = 10 | Menos refinado, ~76 minutos para 1ª run completa |
| Defaults do nosso software | 1ª e 2ª runs: CI = 10 (era 5/10 split antes de pt27, alinhado em pt27 fix Bloco B) |
| Dialog "Save As" entre runs | Aparece automaticamente entre fim da 1ª corrida e início da 2ª (workflow do Baltazar). O launcher faz `BM_CLICK + wait save as` para fechar este fluxo de export. Importante: este Save As mexe no clipboard como efeito secundário (ver §10) |

### 7.1 Mecânica de início e fim — factos descobertos em pt29

| Item | Valor |
|---|---|
| **Dispatch da run (início)** | O click no botão verde "Calculate" abre o popup Nash; carregar OK no popup **dispara** o cálculo. O HRC retorna o controlo ao processo controlador (robot ou utilizador) imediatamente após o disparo — não bloqueia. |
| **Sinal explícito de fim** | **Não existe.** O HRC não emite mensagem, popup, mudança de título de janela, nem qualquer outro sinal directo que indique "calculation done". |
| **Único indicador inferível** | **Uso de memória do processo HRC.** Durante o cálculo a memória oscila com alocações constantes. Quando o cálculo termina, estabiliza. |
| **Heurística usável (Baltazar OG, `wait_for_calculation()`)** | `mem > 100 MB` e variação `< 20 MB` durante 3 ciclos de 10 s consecutivos implica run terminada. Sleep inicial de 15 s antes de começar a verificar. Timeout global 300 s. |
| **Implicação para qualquer software que controle o HRC** | Após disparar uma run, **bloquear até a memória estabilizar** antes de tentar qualquer acção dependente do resultado (navegação para Selected Subtree, Save As, Export, leitura de Strategy Table). |
| **Pontos do fluxo onde aplicar a espera** | (a) Após 1ª run e antes de navegar para a 2ª. (b) Após 2ª run e antes do export. (c) Em qualquer outro ponto futuro em que uma acção HRC assíncrona seja seguida por outra dependente do resultado. |
| **Modos de falha da heurística** | (i) Memória pode estabilizar transitoriamente cedo demais (improvável mas possível em árvores muito pequenas). (ii) Memória pode continuar a oscilar por GC interno mesmo após o cálculo terminar (improvável). Em qualquer dos casos, afinar os thresholds com dados reais. |

## 8. Export do resultado

| Item | Valor |
|---|---|
| Mecanismo | O launcher Baltazar tem um patch `make_patched_export` que substitui `export_strategies` por uma versão que usa o clipboard para colar o caminho de saída |
| Output | Ficheiro `.zip` |
| Path no Beelink | `C:\Users\Administrator\Documents\Teste completo\done\Exports\<hand_id>.zip` |
| Patch do launcher | `BM_CLICK + wait save as` — força fluxo de export limpo |

## 9. Bugs e limitações observáveis (não nossos)

| Bug | Severidade | Workaround actual |
|---|---|---|
| Rect do popup Nash variável entre sessões | Média (afecta calibração de coordenadas) | Usar pixels-rel ao top-left do popup, nunca fracções absolutas |
| Tree pode chegar a >20 GB de RAM e crashar | Alta (mãos profundas + scripts largos) | Templates JS tight + prune via Selected Subtree |
| Caixa do HH no wizard fica com a última mão entre sessões | Baixa | Não interfere — paste sobrescreve sempre |
| Dialog "Save As" aparece entre runs | Baixa (fluxo previsto) | Launcher Baltazar tem patch para fechar |
| **HRC Java perde clicks instantâneos em botões críticos** (pt29) | **Alta** (afecta o Finish do wizard e potencialmente outros botões críticos) | Slow-click obrigatório: `mouseDown → sleep ≥100 ms → mouseUp`. Validado em pt29-v2 no Finish |
| **Ausência de sinal explícito de fim de cálculo** (pt29) | Alta (qualquer automação tem de inferir) | Polling do uso de memória do HRC; `wait_for_calculation()` do Baltazar OG implementa a heurística |

## 10. Clipboard — comportamento e armadilhas

O clipboard do Windows é um recurso **partilhado** entre todas as apps.
Várias coisas o usam, e ele tem armadilhas conhecidas que afectam o nosso
robot.

### Auto-import do clipboard pelo HRC

Descoberta em pt28: quando o wizard "New Hand" abre, o HRC **lê
automaticamente o clipboard imediatamente** e tenta importá-lo como HH.
Se o conteúdo for inválido, o popup azul "No valid hand-history" aparece
logo — antes de o robot ter chance de fazer Ctrl+V manualmente.

Implicação operacional: o robot tem de **garantir que o HH está no
clipboard ANTES de abrir o wizard**. A ordem das operações é:

1. `_set_clipboard_with_verify(hh_text)` — escreve HH e verifica com read-back.
2. Abrir wizard "New Hand" (atalho ou click).
3. HRC faz auto-import do clipboard → vê o HH válido → preenche campos.
4. `paste_hh` (Ctrl+V manual) corre como rede de segurança.

Antes do pt28, a ordem estava invertida (`open_wizard` → `paste_hh`), o
que causava falha sistemática se qualquer outra app tinha tocado no
clipboard nos segundos antes do robot abrir o wizard (ex: comando do
PowerShell que o utilizador colou para arrancar o robot ficava no
clipboard e o HRC tentava parseá-lo).

### Onde o robot escreve no clipboard

| Origem | Para quê | Quando |
|---|---|---|
| `paste_hh` (Baltazar OG) | Hand history → caixa do wizard | No setup_hand, antes do Ctrl+V |
| `paste_path` (Baltazar OG) | Paths de prizes/scripts | Em `import_prizes` e `setup_scripting` |
| `start_calculation` (Baltazar OG) | Valor do CI Target no popup Nash da 1ª corrida | Por cada corrida |
| `_save_as_set_and_click` (launcher) | Caminho do ficheiro `.zip` do export | No fim de cada mão |
| `_set_filename_via_win32` fallback (launcher) | Caminho do ficheiro (fallback) | Só se a via principal falhar |
| `clipboard_safe_paste` (nosso patch, pt27-v3) | Wrapper defensivo para os pastes do source | Substitui paste_hh, paste_path, _fill_ci_target_in_popup, _set_ci_target_common |

### Bug do `pyperclip 1.11.0` descoberto em pt28

`pyperclip.copy()` pode **falhar em silêncio** no Windows por causa de um
bug em `CheckedCall.__call__` (linha 314-318 de `pyperclip/__init__.py`):

```python
def __call__(self, *args):
    ret = self.f(*args)
    if not ret and get_errno():           # ← AND, devia ser OR e ler GetLastError
        raise PyperclipWindowsException(...)
    return ret
```

`get_errno()` lê o CRT errno, que não é actualizado por chamadas user32
do Windows. As falhas Win32 (do tipo `CreateWindowExA → NULL`) passam por
este guarda sem excepção. O `pyperclip.copy()` retorna normalmente como
se tivesse colado, mas o clipboard fica no estado anterior (ou esvaziado).

Quando isto acontece, o `Ctrl+V` seguinte cola o que estava no clipboard
antes (caminho do `.zip` da mão anterior, ou outro conteúdo), e o HRC
mostra "No valid hand-history found in the Clipboard".

### Porque o Baltazar OG nunca teve este problema

O bug do `pyperclip` está em ambos os builds (Baltazar OG e nosso, mesma
versão). A diferença está no contexto:

- **Baltazar OG**: o Rui usava manualmente, 1 mão de cada vez (abrir HRC,
  correr, fechar). Beelink "limpo", sem HM3 / Discord / RDP / Win+V
  cloud sync activos durante a corrida.
- **Nosso build**: corre em batch via adapter, mãos encadeadas. Beelink
  hoje tem stack completo do Rui — HM3, Discord, OneDrive, possíveis
  clipboard managers, etc. Mais competição pelo clipboard ownership.

A causa raiz do sintoma é uma combinação de:
1. Bug do `pyperclip` que esconde falhas Win32.
2. Várias apps competirem pelo clipboard (qualquer uma pode chamar
   `SetClipboardData` logo a seguir ao nosso e sobrescrever).
3. O nosso uso em batch expõe a flakiness com mais frequência.

### Defesa actual (pt27-v3)

`clipboard_safe_paste` faz: `pyperclip.copy(text)` → ler clipboard de
volta para verificar → retry com pausa entre tentativas (até 5×) → só
manda `Ctrl+V` quando confirma que o clipboard tem o conteúdo certo →
verifica novamente depois (regista warning se foi sobrescrito).

Cobre tanto o cenário interno (bug pyperclip) como o externo (apps
concorrentes). Não é fix da causa raiz, mas evita o sintoma.

### Apps tipicamente competidoras pelo clipboard

| Categoria | Suspeitos prováveis |
|---|---|
| Sync entre máquinas | Win+V cloud sync (Windows 11 default com MS account), RDP clipboard channel, Mouse Without Borders / Synergy / Barrier |
| Poker tools | HM3 (monitora clipboard para auto-import de HHs — suspeito principal), SharkScope HUD, Intuitive Tables |
| Comunicação | Discord (preview de paste de imagens), Slack |
| Clipboard managers | Ditto, ClipboardFusion, ClipX |
| Microsoft built-in | Snipping Tool, OneDrive Personal, Windows Search |
| Extensões browser | LastPass / Bitwarden auto-clear, Grammarly |

## 11. Tabela única de coordenadas calibradas

| Coordenada | Valor | Tipo | Origem | Notas |
|---|---|---|---|---|
| `EQUITY_MODEL_X/Y` | `(446, 561)` | rel à wpos | herdada do Baltazar | OK |
| `CALCULATE_BUTTON_X/Y` | `(204, 59)` | rel à wpos | smoke 19 Maio pt26 | OK |
| `SCOPE_DROPDOWN_REL_X/Y` | `(278, 67)` | rel ao top-left do popup Nash | smoke 18 Maio pt25f | Suspeita de desfasamento ~12px Y; em diagnóstico |
| `SCOPE_OPTION_SELECTED_SUBTREE_REL_X/Y` | `(274, 108)` | rel ao top-left do popup Nash | smoke 18 Maio pt25f | Idem |
| `CI_TARGET_POPUP_REL_X/Y` | `(270, 109)` | rel ao top-left do popup Nash | derivado das fracções legacy do Baltazar | Funciona (escreve "10.0" correctamente) |
| `STRATEGY_TABLE_FOCUS_X/Y` | (não calibrada) | rel à wpos | DEPRECATED em pt28 — Strategy Table já tem foco por default |
| `CI_TARGET_FIELD_X/Y` (main UI) | (não calibrada) | rel à wpos | DEPRECATED em pt25e — set CI no main UI é desnecessário |
| Campo "Remaining Players" (MTT Stacks) | `(977, 330)` abs / `(1230, 289)` rel | smoke 15 Maio pt25e/manhã | Coord abs assume wpos `(283, 65)` |
| Campo "Total Chips" (MTT Stacks) | `(677, 438)` rel à wpos | herdada do Baltazar | OK |
| Campo "Other Tables" (MTT Stacks) | **LACUNA** | — | precisa calibração |
| `SCRIPTING_TAB` | **LACUNA — está no .pyc Baltazar** | rel à wpos | — | Code pode descobrir do source decompilado |
| `SCRIPT_FOLDER` | **LACUNA — idem** | rel à wpos | — | Idem |
| `BTN_NEXT` | **LACUNA — idem** | rel à wpos | — | Idem |
| `BTN_FINISH` | `(568, 640)` | rel à wpos do wizard | observada empiricamente em pt29-v1/v2 nos smokes do Beelink | Funciona com slow-click obrigatório (ver §3.5). wpos do wizard observada `(943, 0, 741, 673)` |
| `OK button no popup Nash` | **LACUNA** | rel ao top-left do popup | pt25e regista `(895, 568)` abs para o popup da 1ª run | Precisa coord rel consolidada |

**Nota sobre o Beelink:** A wpos do main HRC é `(left=283, top=65,
width=1050, height=850)` em janela não-maximizada. Coords absolutas
assumem esta configuração; mudanças invalidam coords absolutas. Coords
rel sobrevivem desde que o tamanho não mude.

---

## 12. Formato de HH aceite pelo HRC

Descoberto empiricamente em pt28 (20 Maio 2026) através de testes A/B no
HRC do Beelink e PC principal, com a mão GG-5944816316. A descoberta veio
em sequência ao bug "paste falha em silêncio": depois de garantirmos que
o clipboard tinha o HH correcto, o HRC continuou a rejeitar — porque a
HH em si tinha problemas de formato.

### 12.1 Como o HRC identifica o formato

O HRC parser examina o **prefixo da primeira linha** (header da mão)
para escolher qual parser usar. Cada parser tem regras próprias sobre o
que aceita no resto do documento.

Lista de sites suportados (do popup azul de erro):

> *Clipboard import works on tournament hands from: PokerStars, Fulltilt,
> PartyPoker, iPoker, Ongame, Cake, Merge, 888, Winamax, Bovada, Winning,
> PKR, GG, CoinPoker, Web Calculator URLs*

Mapping observado de prefixo → parser:

| Prefixo da 1ª linha | Parser activado | Aceita bounty na seat? |
|---|---|---|
| `PokerStars Hand #...` | PokerStars | **Sim** |
| `Winamax Poker - ...` | Winamax | **Sim** (formato próprio) |
| `Poker Hand #TM...` ou `Poker Hand #...` | GGPoker | **Não** |
| Outros | Não testados | — |

### 12.2 Formato GG aceite (HH original, sem bounty nas seats)

Header:

```
Poker Hand #TM<id>: Tournament #<id>, <name> - Level<N>(<sb>/<bb>(<ante>)) - <data>
```

Seats (SEM bounty info):

```
Seat N: <nick> (<chips_com_virgulas> in chips)
```

Observado: HHs originais do GGPoker (anonymized ou com nicks reais) são
aceites. A info de bounty teria de ser configurada via UI nos campos
`KO-T$` e `KO-P$` da página Basic Hand Data — mas o parser GG **rejeita**
qualquer tentativa de embutir bounty na linha Seat.

### 12.3 Formato PokerStars aceite (com bounty na seat)

Exemplo real do Rui (PokerStars `.eu`):

```
PokerStars Hand #260525949543: Tournament #3983883160, €57+€57+€11 EUR Hold'em No Limit - Level XX (4000/8000) - 2026/04/19 23:30:19 WET [2026/04/19 18:30:19 ET]
Table '3983883160 52' 6-max Seat #6 is the button
Seat 1: kokonakueka (457949 in chips, €171 bounty)
...
```

Convenções observadas:
- Espaço entre `Level` e o número (`Level XX`).
- Blinds entre parêntesis com `/` (`(4000/8000)`), sem ante explícito,
  sem vírgulas como separador de milhares.
- Chips na linha Seat **sem vírgulas**.
- Bounty na linha Seat com símbolo da moeda **antes** do valor
  (`€171 bounty`), sem decimais quando inteiro.
- **Hero também tem bounty** na linha Seat — não basta os outros terem.

### 12.4 Formato Winamax aceite (com bounty noutro layout)

Exemplo real do Rui:

```
Winamax Poker - Tournament "HIGHROLLER" buyIn: 232€ + 18€ level: 8 - HandId: #4714884320089604100-138-1779137598 - Holdem no limit (80/350/700) - 2026/05/18 20:53:18 UTC
Table: 'HIGHROLLER(1097769551)#003' 6-max (real money) Seat #3 is the button
Seat 1: thinvalium (92265, 107€ bounty)
...
```

Convenções diferentes do PokerStars:
- Sem `Hand #` literal — usa `HandId: #...` no meio do header.
- Sem `in chips` na linha Seat.
- Bounty com símbolo da moeda **depois** do valor (`107€` em vez de
  `€107`).
- Hero também tem bounty (`thinvalium` é Hero Winamax do Rui).

### 12.5 Rejeição confirmada empiricamente (testes pt28)

Variantes testadas com a mão GG-5944816316 no HRC. Resultado:

| # | Variante | HRC |
|---|---|---|
| 1 | HH GG original (anonymized, sem bounty) | **Aceita** |
| 2 | HH GG + nicks resolvidos (anonymized → reais), sem bounty | **Aceita** |
| 3 | HH GG + apenas bounty `$X.XX` nas seats (mantém vírgulas chips) | **Rejeita** |
| 4 | HH GG + bounty `$X` (sem vírgulas chips, formato PS-like) | **Rejeita** |
| 5 | HH GG + bounty `$X` em todas as seats incluindo Hero | **Rejeita** |
| 6 | HH GG + bounty `€X` em todas as seats | **Rejeita** |
| 7 | HH GG com header `PokerStars Hand #` + bounty `€X` | **Rejeita** |
| 8 | HH GG completamente convertida para formato PokerStars (todas as 11 transformações em §12.6) | **Aceita** |

Conclusão: o parser GG do HRC **não aceita bounty na linha Seat em
nenhuma variante**. Para passar bounty info via HH é obrigatório
**transformar a HH inteira em formato PokerStars** (ou Winamax).

### 12.6 Transformações necessárias GG → PokerStars

Para converter uma HH GG em formato PokerStars que o HRC engula, todas
estas transformações são necessárias (validadas empiricamente):

| # | Transformação | Origem (GG) | Destino (PS) |
|---|---|---|---|
| 1 | Prefixo do header | `Poker Hand #TM<id>` | `PokerStars Hand #<id>` |
| 2 | Level no header | `Level14(1,750/3,500(500))` | `Level 14 (1750/3500)` |
| 3 | Chips nas seats | `(63,483 in chips)` | `(63483 in chips, €250 bounty)` |
| 4 | Hero seat | `Seat 6: Hero (76,360 in chips)` | `Seat 6: Hero (76360 in chips, €250 bounty)` |
| 5 | Símbolo da moeda do bounty | `$` (USD) | `€` (rejeitou `$`) |
| 6 | Decimais no bounty | `$250.00` | `€250` (sem `.00` quando inteiro) |
| 7 | `Dealt to <other>` sem cartas | Presente para todos | Remover excepto Hero |
| 8 | `*** SHOWDOWN ***` em mão sem showdown | Presente | Remover |
| 9 | `<player>: doesn't show hand` depois de `collected` | Ausente | Adicionar |
| 10 | Total pot | `Total pot X \| Rake 0 \| Jackpot 0 \| Bingo 0 \| Fortune 0 \| Tax 0` | `Total pot X \| Rake 0` |
| 11 | Vírgulas em amounts (raises, bets, collected, blinds) | Presentes | Remover todas |

Implementação no backend: `convert_gg_hh_to_pokerstars_compatible` em
`backend/app/services/queue_export.py`. Estado em 20 Maio:
- Commit 078bf93 fez Fase 1 (remover bounty na seat, manter `_replace_hashes`
  e `_format_level_line`).
- Commit subsequente fará Fase 2 (adicionar transformações #7-#11 + re-adicionar
  bounty injection no formato PS).

### 12.7 Scope da conversão (importante)

A conversão GG → PokerStars **só pode ser aplicada na escrita do `hh.txt`
para a pasta da queue do HRC** (`Teste completo\GG-XXXX\hh.txt`). NÃO
pode tocar em:

- HHs de outras salas (PokerStars, Winamax, WPN) — já vêm em formato
  compatível, não precisam de conversão.
- Outros consumers da HH GG no backend: Estudo, Vilões, HM3, Discord
  page, hand_villains. Esses precisam da HH GG **canónica** (anonymized
  ou com nicks resolvidos) sem PS-isation.
- A HH armazenada na base de dados continua canónica. A conversão é
  uma camada de escrita final só para o output HRC.

### 12.8 Tech debt residual (inputs auxiliares incompletos)

Para o HRC calcular PKO equity correctamente precisa de **três** fontes
de informação, das quais hoje só uma chega completa:

**#HRC-GG-KOS-EXTRACTION — bounty por jogador**

Bounties variam ao longo do torneio: cada KO acumula bounty no jogador
que abate. Para uma mão num momento específico, o bounty correcto não é
o **inicial** ($250 base) — é o **acumulado** até esse ponto. Para
implementar isto seria preciso:

- Fonte: tournament_summaries + sequência de KOs antes da mão actual.
- Cálculo: bounty_inicial × (1 + Σ(0.5 × bounty_abatido_kn) / bounty_inicial).

Para a entrega pt28, usar bounty inicial como aproximação. O cálculo PKO
equity do HRC será ligeiramente off mas funcional.

**#HRC-PAYOUTS-INCOMPLETO — prize structure truncada**

O `payouts.json` actual termina no 10º lugar:
```json
"prizes": { "1": 42034.3, ..., "10": 5123.73 }
```

Em torneios com centenas de jogadores restantes (a GG-5944816316 tem 365),
o prize pool paga muito além de top 10. O lobby da própria mão mostra
**180 places paid** com a structure completa visível no painel "Prize
Pool" do screenshot do lobby (extraído em FASE A via Discord):

- Lugares 1-10: individuais (cada um com prémio próprio).
- Lugares agrupados em ranges: 11~12, 13~16, 17~22, 23~32, 33~48,
  49~73, 74~114, 115~180 (todos com o mesmo prémio dentro do range).

O Vision parser hoje captura os 10 individuais correctamente mas não
captura os ranges. Tech debt: estender o parser para apanhar os ranges
e expandir cada um em entries individuais no `payouts.json` (ex:
`"11~12: $3,880.46"` → `"11": 3880.46, "12": 3880.46`). Resultado: 180
entries no `prizes`.

**#HRC-TOTAL-CHIPS-MISSING — total_chips ausente**

Campo `chips: null` no `payouts.json` é o **total de fichas em jogo**
no torneio inteiro. O HRC usa-o para calcular o chip average (`total_chips
/ players_left`), que entra no cálculo ICM como referência para a
distribuição assumida de stacks nos jogadores das outras mesas (Other
Tables na página MTT Stacks).

A info está no **canto superior direito do lobby do torneio** no GGPoker:
- `Players Left: 365 / 1552` — jogadores actuais / cap inicial.
- `Average Stack: 179,530 (51.3 BB)` — chip average.

Cálculo: `total_chips = Average Stack × Players Left` (ex: 179,530 × 365 =
65,528,450 para a mão GG-5944816316).

Sem `total_chips`, o HRC ou usa um default interno (sem garantia de
correcção) ou pede ao utilizador para preencher manualmente. O cálculo
sai aproximado. Tech debt: Vision parser captura `Average Stack` e
`Players Left` do canto superior direito do lobby, multiplica, e
escreve no `payouts.json.chips`.

### 12.9 Lacunas sobre formato (a confirmar empiricamente no futuro)

| # | Lacuna |
|---|---|
| A | Símbolo da moeda para sites USD `.com` — `$` é rejeitado no bounty, mas a conversão para `€` parece incorrecta semanticamente. Investigar se o HRC aceita `$X bounty` em algum formato (ex: PokerStars `.com` em vez de `.eu`). |
| B | Header PokerStars completo — o nosso `PokerStars Hand #5944816316` passou, mas o PS real tem `WET [data ET]` no fim. Pode causar rejeição em casos mais finos. |
| C | Formato Winamax — não testado se o HRC engole HH GG convertida para formato Winamax (alternativa ao PS). |
| D | `*** ANTE/BLINDS ***` no Winamax separa essa fase do resto. PS não tem. Confirmar qual é exigido em cada formato. |

---

## Anexo A: Convenção de índices HRC scripting

Confirmado nos docs oficiais HRC, validado empiricamente em pt25d:

- `UTG = 0` (first-to-act preflop)
- `SB = N - 2`
- `BB = N - 1`
- Restantes: contíguos entre UTG e SB

Atenção: o nosso backend tinha bug pré-pt25d com convenção rotativa SB=0.
Está corrigido. Manifest field `prune_index_convention: "hrc_docs_v1"`
permite distinguir zips pré/pós-pt25d.

API JavaScript do HRC:
- `ctx.getActivePlayer()` devolve índice na convenção docs.
- `ctx.getPlayerIndexButton/SmallBlind/BigBlind()` devolvem índices na
  convenção docs.

## Anexo B: Labels canónicos de posição

Estes são os labels **visíveis na coluna Player da Strategy Table do HRC**,
não os internos do nosso software:

| N | Labels |
|---|---|
| 2 (HU) | `BU/SB` + `BB` |
| 3 | UTG / SB / BB |
| 4 | UTG / BU / SB / BB |
| 5 | UTG / HJ / BU / SB / BB |
| 6 | UTG / HJ / CO / BU / SB / BB |
| 7 | UTG / MP / HJ / CO / BU / SB / BB (confirmado empiricamente em screenshot Q6.hrcz) |
| 8 | UTG / EP / MP / HJ / CO / BU / SB / BB (**LACUNA — confirmar empiricamente**) |
| 9 | UTG / EP1 / EP2 / MP / HJ / CO / BU / SB / BB (**LACUNA — idem**) |

Para N=2 (HU), o agressor pré-flop é o **botão**, que aparece como
`BU/SB` (label dual porque o botão também é o SB em HU).

---

## Lacunas pendentes

Coisas que faltam ao documento, em ordem de prioridade:

| # | Lacuna | Quem responde |
|---|---|---|
| 1 | Coords absolutas re-medidas do popup Nash (Scope dropdown, opção Selected Subtree, OK) com cursor sobreposto | Rui durante próximo smoke devagar |
| 2 | Versão exacta do HRC instalado | Rui |
| 3 | Maximização da janela ao arrancar | Rui |
| 4 | 4º modelo no dropdown Equity Model | Rui (a foto que mandou em pt23 mostra 4 modelos) |
| 5 | Coord do campo "Other Tables" na página MTT Stacks | Smoke devagar |
| 6 | Valores literais de `SCRIPTING_TAB`, `SCRIPT_FOLDER`, `BTN_NEXT`, `BTN_FINISH` | Code (descobre no .pyc Baltazar — read-only) |
| 7 | Coord rel do botão OK e Cancel dentro do popup Nash | Smoke devagar |
| 8 | Labels EP/MP para N=8 e N=9 | Rui se encontrar mãos reais 8/9-handed |
| 9 | Bounty para sites USD `.com` — confirmar se `$` é aceite em algum formato | Smoke real com HH PokerStars `.com` |
| 10 | Cálculo de bounty acumulado real (vs base $250) — fonte: tournament_summaries + KOs | Tech debt `#HRC-GG-KOS-EXTRACTION` |
| 11 | Confirmar formato Winamax como alternativa ao PS (para conversão GG → ?) | Smoke devagar |
| 12 | Prize structure completa em `payouts.json` (hoje termina no 10º; torneios grandes pagam 15-30% do field) | Tech debt `#HRC-PAYOUTS-INCOMPLETO` — Vision parser + pipeline Discord |
| 13 | `total_chips` em `payouts.json` (hoje `null`; necessário para chip average e ICM correcto) | Tech debt `#HRC-TOTAL-CHIPS-MISSING` — fonte: lobby do torneio |

---

## Como manter este documento vivo

- Qualquer descoberta nova sobre o HRC → acrescentar aqui antes de
  fechar o trabalho.
- Quando uma coord é re-calibrada, actualizar a tabela §11 e datar.
- Quando o HRC for actualizado (raro), validar todas as coords. Pode
  forçar reescrita de várias secções.
- Quando dois factos colidem, prevalece o mais recente, com nota
  explicativa.

## Cross-references

- `docs/REGRAS_NEGOCIO.md` §13 (pipeline HRC), §14 (tag-based equity)
- `docs/TECH_DEBTS_INVENTARIO.md` (bugs do nosso software)
- `tools/watcher_src/patched_funcs.py` (onde as coords vivem em código)
- Journals: pt22 (smoke original Baltazar), pt23 (descompilação + fixes
  A/B/C/E), pt25b-c-d (pré-Bloco 2), pt25e (Bloco 1 source-side),
  pt25f (Bloco 2 source-side), pt26 (smoke real pt26 + bugs descobertos),
  pt27 (backend fixes), pt28 (este — clipboard race + scope bug
  + descoberta formato HH PokerStars como conversão obrigatória GG → HRC)
