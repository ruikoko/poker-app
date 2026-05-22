# Runbook — smoke do robot HRC no Beelink

**Estado:** v2, 22 Maio 2026 (pt30-pt34).
**Audiência:** o Rui (operador). Termos técnicos traduzidos em parêntesis
na primeira ocorrência.
**Como manter vivo:** quem aprender um passo novo (ou desmentir um que
está aqui) edita este ficheiro antes de fechar o trabalho.

> **Mudanças na v2 (pt30-pt34):** confirmado por smoke real (a cadeia
> completa da 2ª run correu ponta-a-ponta). Correcções:
> - **Perfil real é `riand` (elevated, UAC), não `Administrator`.** A
>   nota anterior (pt22) de "watcher corre sob Administrator legacy" fica
>   superseded — o smoke pt30-pt34 correu sob `riand`.
> - **Abrir o HRC à mão é opcional** — o robot trata via `ensure_hrc`.
> - **O HRC usa SWT** (não Swing): o robot consegue clicar botões nativos
>   (Finish, OK do popup) sem coord, via Win32. Relevante para o
>   troubleshooting (ver secção 6).
> - **Sequência da 2ª run** documentada (secção 3.1).
> - **Lacuna 8.1 (ordem de arranque) fechada.**

---

## Os 3 actores no Beelink

Antes da sequência, convém ter o mapa de quem é quem. São **três
programas separados** a correr ao mesmo tempo na mini PC (Beelink):

1. **HRC** — o Holdem Resources Calculator (a calculadora de poker, app
   em Java). É quem faz as contas.
2. **Robot** (no código: "watcher", ficheiro `hrc_watcher.exe`) — o
   programa que controla o HRC sozinho, simulando cliques e teclado.
   Vigia uma pasta no disco à espera de mãos para calcular.
3. **Entregador** (no código: "adapter", `hrc_adapter.py`) — o programa
   em Python que fala com a app web (servidor no Railway): vai buscar as
   mãos novas, põe-nas na pasta que o robot vigia, e no fim devolve o
   resultado à app.

Fluxo resumido de uma mão:

```
app web (Railway)
   │  (1) Entregador faz pedido GET e descarrega as mãos novas
   ▼
C:\Users\riand\Documents\Teste completo\<mão>\   ← pasta da fila (perfil riand)
   │  (2) Robot vê a pasta nova, abre o HRC, cola a mão, calcula
   ▼
...\Teste completo\done\Exports\<mão>.zip   ← resultado do robot
   │  (3) Entregador vê o .zip, faz pedido POST e devolve à app
   ▼
app web: hrc_jobs.status = 'done'   ← visível em /hrc-sessions
```

O **robot só lê e escreve ficheiros locais** — não fala com a app web.
Quem fala com a app é o **entregador**, e é só ele que precisa da chave
de acesso (ver pré-condições). Esta separação é importante para o
troubleshooting: se a app não recebe nada, o problema é do entregador,
não do robot; se o HRC não calcula, é do robot.

---

## 1. Propósito

Usa-se este runbook quando queres:

- **Testar uma versão nova do robot** (ex: pt29-v3) ponta-a-ponta no
  Beelink — chamamos a isto um "smoke" (teste real rápido para ver se a
  cadeia toda funciona).
- **Calcular uma mão de teste pontual** para verificar um comportamento.
- **Despistar uma avaria** quando alguma coisa na cadeia parou.

Não cobre: instalar tudo do zero pela primeira vez (isso está no
`tools/hrc_adapter/README.md` para o entregador) nem afinar a config do
HRC (isso está em `docs/HRC_ANATOMIA_OPERACIONAL.md`).

---

## 2. Pré-condições (estado antes de arrancar)

### 2.1 Mini PC e contas

- Beelink ligada e com sessão iniciada no perfil **`riand` (elevated,
  UAC)** — é aqui que o robot pt30-pt34 correu o smoke real. A pasta da
  fila é `C:\Users\riand\Documents\Teste completo\`.
  - *(Nota histórica: a documentação pt22 falava do perfil `Administrator`
    legacy + junctions. Fica superseded — o smoke validado correu sob
    `riand`. Se a pasta no teu Beelink estiver noutro perfil, é o caminho
    configurado no entregador (`DONE_DIR`) que manda.)*
- As subpastas `done\`, `arquivo\`, `replied\` existem dentro de
  `Teste completo\`.

### 2.2 O robot certo instalado

- O `hrc_watcher.exe` no Desktop tem de ser a versão que queres testar.
  Confirma a impressão digital (SHA256 — número único que identifica o
  ficheiro) com o `.bat` de instalação que o Web te deu:
  - Duplo-clique no `instala_ptXX.bat` (no Desktop) → ele compara a SHA,
    faz backup do robot antigo, e instala o novo.
  - Se a SHA não bate, o `.bat` aborta — não instala um ficheiro errado.

### 2.3 A chave de acesso do entregador

- O entregador precisa da `HRC_WATCHER_API_KEY` (Bearer token — chave de
  acesso que o entregador usa para falar com a app web). Está guardada
  como variável de utilizador no Beelink.
- Se mudaste a chave recentemente: o `setx` (comando que grava a
  variável) só fica visível em **janelas de PowerShell abertas depois**
  de o gravar. Fecha a janela e abre outra.

### 2.4 Limpar o que pode interferir (IMPORTANTE)

O robot trabalha pelo **clipboard** (a área de transferência do
Windows — o "copiar/colar"). Tudo o que mexa no clipboard ao mesmo
tempo pode estragar o paste da mão no HRC. Antes do smoke, fecha ou
desliga, na medida do possível:

- **HM3** (HoldemManager 3) — vigia o clipboard à procura de mãos. É o
  suspeito principal de interferência.
- **Discord** — faz preview quando colas imagens.
- **Win+V / sincronização de clipboard na nuvem** (Windows 11) — se
  estiver ligada, qualquer "copiar" feito no PC principal aparece no
  Beelink e vice-versa.
- **Gestores de clipboard** (Ditto, ClipboardFusion, etc.), se tiveres.
- **Sessão de RDP aberta** (ligação remota) — o canal de clipboard do
  RDP também sincroniza.

> Detalhe técnico de porquê isto importa: `docs/HRC_ANATOMIA_OPERACIONAL.md`
> §10 (bug do `pyperclip` + apps concorrentes pelo clipboard). O robot
> pt27-v3+ tem defesa (`clipboard_safe_paste`) mas reduzir a competição
> ajuda na mesma.

### 2.5 Estado da app web

- A app no Railway tem de estar de pé. Teste rápido no browser:
  `https://poker-app-production-34a7.up.railway.app/health` deve mostrar
  algo como `200`/OK.
- A mão de teste tem de estar elegível para o robot a ir buscar: ter
  payout (estrutura de prémios) associado e estar dentro dos filtros de
  tags/estado que o pedido usa. (A mão `GG-5944816316` foi preparada
  para isto nas sessões pt27-pt29.)

---

## 3. Sequência passo-a-passo

> **Ordem de arranque (confirmada pt30-pt34):** fechar as apps que
> interferem (2.4) → arrancar o **entregador** → arrancar o **robot**.
> O HRC pode ficar fechado: o robot abre-o sozinho via `ensure_hrc`
> (espera até 30 s). Tanto o entregador como o robot vigiam em ciclo, por
> isso a ordem entre eles não é crítica — apanham-se um ao outro à mesma.
> O essencial é a **higiene do clipboard** (2.4) estar feita antes de o
> robot abrir o wizard.

1. **Acorda a Beelink** e entra no perfil `riand` (elevated).

2. **Fecha o que interfere** (ver 2.4): HM3, Discord, etc.

3. **Abre o HRC** *(opcional)*. O robot abre-o sozinho via `ensure_hrc`
   (espera até 30 s), por isso este passo é dispensável. Se quiseres
   abri-lo à mão (duplo-clique no atalho), deixa-o na janela inicial — é
   ligeiramente mais previsível, mas não é necessário.

4. **Confirma/instala o robot certo** (ver 2.2): duplo-clique no
   `instala_ptXX.bat` no Desktop. Lê a mensagem: tem de dizer que a SHA
   bate e que instalou.

5. **Arranca o entregador.** Abre uma janela **nova** de PowerShell e:

   ```powershell
   cd C:\hrc\adapter
   .\venv\Scripts\activate
   python hrc_adapter.py
   ```

   Aparece um banner com os caminhos e entra em ciclo. Deixa esta janela
   aberta. `Ctrl+C` pára-o de forma limpa (grava o registo antes de
   sair).

6. **Arranca o robot.** Duplo-clique no `hrc_watcher.exe` no Desktop.
   Abre uma janela preta (consola) com o cabeçalho
   `HRC WATCHER — Cálculo automático de mãos` e fica "A monitorar...".

7. **Espera.** No prazo de ~1 minuto o entregador faz o pedido à app,
   descarrega a mão e cria a pasta `Teste completo\<mão>\`. O robot vê a
   pasta, abre/usa o HRC, e começa a configurar a mão. A partir daqui é
   só observar (secção 4).

### 3.1 O que o robot faz na 2ª run (Selected Subtree)

Para contexto — é a parte que ficou funcional em pt30-pt34. O robot replica
a sequência manual que o Rui fazia à mão:

1. A 1ª run acaba; a Strategy Table fica com a 1ª linha (UTG) seleccionada.
2. O robot desce até à linha do **agressor real** (seta-baixo × N).
3. Clica o **Play** (abre o popup "Nash Calculation").
4. No popup: **Scope = Selected Subtree** + **CI = 10.0** → **OK** (via
   BM_CLICK, porque o Enter não funciona no popup).
5. A 2ª run arranca; o robot espera-a terminar (janela "Monte Carlo
   Sampling") e exporta o `.zip`.

Detalhe técnico completo em `docs/HRC_ANATOMIA_OPERACIONAL.md` §4.1 e §6.

---

## 4. O que olhar enquanto corre

### 4.1 Janela do robot (consola preta do `.exe`)

É aqui que vês o robot a trabalhar, linha a linha. Mensagens-chave a
seguir, por ordem:

- `[SETUP] <mão>` — começou a preparar a mão.
- `A preparar clipboard com HH (pre-open-wizard)...` — pôs a mão na área
  de transferência antes de abrir o wizard (assistente de criação de mão
  do HRC).
- `A colar HH...` — colou a mão.
- `[finish-wait] calculo do tree size comecou (Finish disabled)` →
  `[finish-wait] tree estavel em X.Xs (Finish enabled)` — o HRC acabou de
  calcular o tamanho da árvore; o Finish já pode ser clicado (pt30).
- `Finish...` → `[finish-diag pos-click] OK — wizard fechou.` — o Finish
  funcionou (slow-click).
- `A calcular (1ª run)...` → `A aguardar fim da 1ª run...` →
  `[run-wait] 1ª run: janela detectada title='Hand Setup'` →
  `[run-wait] 1ª run: run terminou em Xs (Y.Y min)` → `1ª run terminou.`
- `navigate_to_target_node: N (down) presses` — navegou na tabela até à
  linha do agressor real.
- `A calcular (2ª run, Selected Subtree)...` →
  `[calc-diag pre-click] coord=(...) hrc_window=(...)` →
  `_wait_for_nash_popup: matched title='Nash Calculation' ...` →
  `Scope: Selected Subtree` → `CI Target (popup): 10.0` →
  `[ok-click] hwnd=... result=BM_CLICK_sent` — popup configurado e
  confirmado (pt32/pt33).
- `A aguardar fim da 2ª run...` →
  `[run-wait] 2ª run: janela detectada title='H-...: Monte Carlo Sampling'`
  → `[run-wait] 2ª run: run terminou em Xs` → `2ª run terminou.` (pt34).
- `A fazer queue do export (finalize após 2ª run)...` →
  `[QUEUED] <mão> -> <mão>.zip`.

> Esta consola **não grava ficheiro de log** — o que vês é só na janela.
> Se a janela fechar perde-se. Por isso o `.bat` de arranque tem `pause`
> e o próprio robot pára em `[CRASH] Pressiona Enter para fechar` quando
> rebenta — para teres tempo de ler. (Ver lacuna 8.2.)

> **Como capturar o output para partilhar (recomendado em smoke):** deixa o
> robot correr a mão toda. No fim (ou quando quiseres parar), na janela do
> robot faz **selecção do texto** (arrastar o rato sobre as linhas, ou
> botão direito → "Select All" na consola) e **`Enter`/`Ctrl+C`** para
> copiar; cola num ficheiro de texto ou directamente no chat. Foi assim
> que se diagnosticou toda a cadeia pt30-pt34 (o logging `[calc-diag]` /
> `[run-wait]` / `[ok-click]` só vive na consola). Se preferires, podes
> arrancar o robot a partir de um PowerShell com `... | Tee-Object log.txt`
> para gravar em paralelo.

### 4.2 Janela do entregador (PowerShell)

Mostra os pedidos à app. E grava também em ficheiro:

- **Ficheiro de log:** `C:\hrc\adapter\logs\hrc_adapter.log` (roda
  diariamente, guarda 14 dias).
- **Detalhe de cada descarga:**
  `C:\hrc\adapter\logs\manifests\manifest_<data>.json`.
- **Registo local do que já passou:** `C:\hrc\adapter\state.json`.

### 4.3 App web

- Página `/hrc-sessions` no site mostra o estado das mãos no pipeline
  (HRC Import Pipeline v1, pt25e). É onde aparece quando uma mão fica
  `done`.

### 4.4 Pastas no disco

- `Teste completo\<mão>\` — a mão a ser processada (criada pelo
  entregador).
- `Teste completo\done\Exports\<mão>.zip` — o resultado, quando o robot
  acaba.
- `Teste completo\arquivo\` — mãos já processadas com sucesso (o robot
  move para aqui no fim).

---

## 5. Como saber que correu bem

Critérios objectivos, por ordem da cadeia:

1. **Robot:** a consola mostra `[QUEUED] <mão> → <mão>.zip` sem nenhum
   `[WARN]`/`[ERROR]` pelo meio.
2. **Disco:** aparece `Teste completo\done\Exports\<mão>.zip`.
3. **Entregador:** o log mostra um `POST .../api/queue/hrc/results` a
   devolver `200` (sucesso) para essa mão, com `status=done`.
4. **App web:** em `/hrc-sessions` a mão fica `done` (e o resultado fica
   guardado — `hrc_jobs.status='done'` com o zip).
5. **Tempo das contas:** os `[CALC] Terminado em Xs` da 1ª e 2ª corridas
   dão-te uma ideia de quanto demorou cada uma — útil para comparar a 2ª
   corrida (que devia ser mais rápida, por ser focada).

Se os critérios 1-4 baterem, o smoke passou. O critério 5 (tempo das
contas) é informativo — útil para comparar com smokes futuros, não é
pass/fail.

---

## 6. Modos de falha conhecidos e o que fazer

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| HRC mostra popup azul **"No valid hand-history found in the Clipboard"** | O clipboard tinha lixo quando o wizard abriu (outra app mexeu lá), ou o paste falhou (corrida de clipboard). | Fecha as apps da secção 2.4. O robot pt28-v3+ já prepara o clipboard antes de abrir o wizard e tenta de novo; se mesmo assim falha, ele pára a mão de propósito (não processa lixo). Detalhe: `HRC_ANATOMIA` §3.1 e §10. |
| Robot anuncia `Finish...` mas o **wizard não fecha** (consola mostra `[WARN] ... "Hand Setup" ainda presente`) | O clique no botão Finish não pegou (a janela do HRC em Java às vezes perde cliques instantâneos). | É o bug que o pt29-v2 resolveu com o "slow-click". Se voltar a acontecer com a versão pt29-v2+, é caso novo — guarda a foto da consola e reporta ao Web. Tech debt relacionado em `HRC_ANATOMIA` §3.5 e §9. |
| **2ª corrida arranca antes da 1ª acabar** / Save As tenta abrir cedo demais | O robot não esperava o fim do cálculo. | Resolvido em pt29-v3 (`wait_for_calculation`). Se a consola já mostra `A aguardar fim da 1ª run...` e mesmo assim falha, reporta. |
| **Entregador não puxa nada** (log sem descargas) | (a) a mão já está marcada como passada no `state.json` local; (b) a mão não está elegível na app (sem payout, fora dos filtros); (c) chave de acesso errada (`pull: 401`). | (a) ver secção 7. (b) confirma na app que a mão tem payout. (c) confere o token no Railway (service `poker-app` → variables). |
| `pull: 401` repetido no entregador | Chave de acesso (token) errada. | Recopia o token do Railway e volta a fazer `setx` numa janela nova. |
| `pull: zip corrupto` | Falha de rede momentânea. | Testa `/health` da app no browser. Em geral resolve sozinho no pull seguinte. |
| Pastas a acumular em `Teste completo\arquivo\` | Normal — o robot arquiva o que processou. | Limpa à mão quando quiseres. Não afecta nada. |

---

## 7. Como repetir o smoke com a MESMA mão

**O problema:** depois de uma mão passar, ela fica registada como
processada no `state.json` do entregador. No próximo ciclo o entregador
vê que já a tratou e **não a puxa outra vez** — mesmo que a app continue
a oferecê-la.

> Bom de saber: a app **não** filtra as mãos já feitas (o pedido
> `GET /api/queue/hrc` devolve a mão na mesma, mesmo com `hrc_jobs.status='done'`).
> Logo, **não precisas de mexer na base de dados nem na app** para
> repetir — o bloqueio é só local, no `state.json`. (Confirmado por
> leitura do código do endpoint; é o comportamento esperado segundo o
> `README` do entregador.)

**Passos para destrancar (soft reset — re-fazer só uma mão):**

1. **Pára o entregador** (`Ctrl+C` na janela do PowerShell).
2. Abre o `C:\hrc\adapter\state.json` num editor de texto e **apaga a
   entrada dessa mão** (o bloco com o id da mão). Grava.
3. **Apaga a pasta** `Teste completo\<mão>\` se ainda existir (evita
   processar duas vezes em simultâneo).
4. (Opcional) apaga o `Teste completo\done\Exports\<mão>.zip` antigo, se
   quiseres confirmar que o novo é gerado de fresco.
5. **Re-arranca o entregador.** No próximo ciclo ele descarrega a mão de
   novo.

**Hard reset (re-fazer tudo):** pára o entregador → apaga o
`state.json` inteiro → apaga as pastas de mãos pendentes em
`Teste completo\` → arranca. (No `README` do entregador, secção "Reset /
cleanup".)

---

## 8. Lacunas (a confirmar empiricamente)

Coisas que não consegui apurar só por leitura de código/journals:

1. ~~**Ordem ideal de arranque.**~~ **FECHADA (pt30-pt34):** fechar apps do
   clipboard (2.4) → entregador → robot; HRC fica opcional (`ensure_hrc`
   abre-o). A ordem entre entregador e robot não é crítica (ambos vigiam em
   ciclo). Ver a nota no topo da secção 3.
2. **Logs do robot só na consola.** Pelo código decompilado, o robot só
   imprime na janela — não vi gravação em ficheiro. Se houver um ficheiro
   de log do robot algures, não o encontrei. Confirmar com o Rui.
3. **Caminho exacto do `instala_ptXX.bat`** — vem dos outputs do chat com
   o Web, não está no repositório. O Rui descarrega-o para o Desktop do
   Beelink a cada versão nova.
4. **Onde o robot vai buscar o `hrc_watcher.exe` a instalar** — o `.bat`
   assume um caminho (provavelmente `Downloads`). Confirmar no `.bat`
   real.
5. **Versão exacta do HRC** instalada no Beelink (lacuna herdada do
   `HRC_ANATOMIA` §1).
6. **Estado/config do HRC entre smokes** — se for preciso fechar e
   reabrir o HRC entre mãos, ou se ele aguenta várias mãos seguidas na
   mesma sessão. O robot processa em ciclo, mas o comportamento do HRC
   ao fim de várias mãos não está confirmado.
7. **`/hrc-sessions` — o que mostra exactamente** e se há um indicador
   visual claro de "done" vs "failed" para o Rui confirmar sem olhar à
   base de dados. Confirmar na app.

---

## Cross-references

- `tools/hrc_adapter/README.md` — setup e operação do entregador.
- `docs/HRC_ANATOMIA_OPERACIONAL.md` — anatomia do HRC (wizard, clipboard,
  coords, popup Nash, janelas de progresso, formato de mão aceite).
- `docs/JOURNAL_2026-05-22-pt30-pt34.md` — fecho da cadeia da 2ª run.
- `docs/JOURNAL_2026-05-21-pt29.md` — mecânica de entrega de exes + estado
  da cascata pt29.
- `tools/watcher_src/patched_funcs.py` — código do robot (parte que
  alterámos).
