# FLUXO DE TRABALHO — regras de eficiência (v1, 10 Jun 2026)

Leitura obrigatória no início de CADA sessão, por TODOS os operadores (Web e Code), independentemente de há quanto tempo trabalham no projeto. Nasceu da frustração real do pt61-pt64: meses de projeto, dois operadores, e o Rui à 01:30 a lutar com um zip. Quem violar uma regra, corrige e regista.

## 1. Nunca esperar parado (regra do paralelo)
Sempre que um operador entrega trabalho a outro (Web→Code, Code→Rui, Rui→Beelink), o entregador COMEÇA IMEDIATAMENTE uma tarefa paralela útil e declara-a ("enquanto esperas/executas, eu faço X"). Espera ociosa é defeito de processo. Exemplos válidos: pré-validar dados, rever runbooks, preparar o passo seguinte, escrever o journal em rascunho, priorizar dívidas.

## 2. Recados completos, com contingências (regra do round-trip único)
Cada instrução leva: o caminho feliz + o que fazer se falhar (plano B embutido) + o output esperado. Objetivo: o destinatário resolve sozinho sem voltar atrás. Proibido entregar passos que dependem de "se der erro, pergunta". Para o Rui em particular: comandos prontos a colar, com "o que deves ver" e "se vires X, faz Y" — nunca jargão, nunca passos implícitos.

## 3. O Rui não faz trabalho de máquina (regra do operador certo)
Se um passo do Rui pode ser um script/bat de duplo-clique, o Code ENTREGA o script — não instruções manuais. Reset de fila, limpeza de state, arranque com logging, transferência de ficheiros: tudo scriptável é scriptado ANTES de chegar ao Rui. O Rui opera onde só ele pode: olhos no ecrã, decisões de produto, ações físicas no Beelink.

## 4. Entrega de binários sem dor (regra do canal único)
Acabou o zip pelo Discord. O Code publica cada exe novo como GitHub Release asset do repo (público) e o instala_ptXX.bat passa a DESCARREGAR o exe diretamente (irm <release-url>) e a verificar a SHA — o Rui só corre 1 bat no Beelink, zero transferências manuais, zero extrações, zero Defender a meio. Implementar já no pt64: criar a release com o exe 3fb1b512…f8e6 e adaptar o bat (a verificação de SHA já existe e mantém-se obrigatória).

## 5. Nada de cor (regra da fonte)
Nenhum operador instrui de memória. Antes de guiar um procedimento: abrir o runbook/doc/código e citar a fonte. Se a realidade desmentir o doc (ex.: pasta riand vs Administrator), corrige-se o doc NA HORA, na mesma sessão. Os docs são o produto tanto quanto o código.

## 6. Logging à prova de perda (regra da caixa-negra)
Todo o processo observável grava para ficheiro POR DEFEITO, sem depender de o operador copiar consolas (lição: Tee-Object com buffer perdeu o log decisivo do pt61b). O watcher/adapter/scripts entregues já vêm com logging para ficheiro embutido ou com bat de arranque que o garante (PYTHONUNBUFFERED incluído).

## 7. Fechar sempre a sessão (regra do journal)
Nenhuma sessão termina sem: journal committado + push + lista "pendente à entrada da próxima sessão" com o PRÓXIMO PASSO CONCRETO de cada frente. Um chat novo tem de conseguir arrancar só com o repo.

**Checklist de fecho — dois registos cumulativos append-only (ordem do Rui, pt67):**
- **`docs/REGISTO_CONCEITO.md`** — se a sessão **alterou o conceito da app ou um elemento** (regra de negócio, lei, semântica de um conceito, fonte de input, decisão de arquitectura), **APPENDA** uma linha datada (resumo + motivo + referência). Não substituir entradas antigas.
- **`docs/LICOES.md`** — APPENDA as lições **problema→solução→êxito** da sessão (uma linha cada, com link ao journal).

Quem mexeu em conceito/elemento e não apendou ao `REGISTO_CONCEITO.md`, **não fechou a sessão**.

## 8. Janelas de Rui são ouro (regra do horário)
O Rui joga e dorme tarde; o tempo dele entre sessões é escasso. Trabalho que precise do Rui presente é preparado ANTES (tudo pronto a colar/clicar); trabalho que não precise dele é feito SEM ele (Web+Code decidem engenharia sozinhos, como mandam os PAPEIS). Se passar da 01:00 e a tarefa não for crítica, propõe-se fecho — o cansaço produz erros que custam mais que a pausa.

## 9. Auditoria contínua
Qualquer operador que detete violação destas regras (própria ou alheia) regista-a no journal da sessão com a correção aplicada. O Rui tem autoridade para parar qualquer fluxo que as viole.

## 10. Fix de backend valida-se DEPLOYADO (regra do objeto-de-teste)
A regra "push no fecho" (commit local, push só no fim) **NÃO se aplica quando a produção é o objeto do teste**. Um fix de backend só vale quando a **Railway fez o deploy** dele — caso contrário a smoke corre contra o backend **antigo** e o resultado é falso. Nasceu da frustração real do pt67: a re-smoke das 18:09 regenerou os packs com a derivação **antiga** (Max=2) porque os commits nunca tinham sido pushed/deployados; só a metade do watcher (visão/2 runs/CI) ficou validada. **Antes de uma smoke que depende de backend novo:** (1) push; (2) **esperar o deploy ficar LIVE** (`railway status --json` → `latestDeployment.status=SUCCESS` no commit certo); (3) **verificar a derivação no backend deployado** (ex.: `GET /api/queue/hrc/hand/<id>` e inspecionar o `meta.json`). Só depois se corre a smoke.

## 11. Âmbito de disco no PC principal (regra do território — pt68)
O Code **só LÊ/TOCA paths explicitamente listados**: a **tabela dos intocáveis** (BD do HM3, `LOBBY_DIR`=Capturas) **+ `C:\Users\User\Desktop\Batmen\`** (e subpastas). **Qualquer procura/leitura fora desses paths exige autorização prévia do Rui, pedida e dada por escrito** — sem exceções "úteis" por iniciativa própria. Nasceu de pt68: o Code andou a varrer `Documents\Poker\GG`, `POKER-GGPCOM-LIVE`, etc. à procura da GG, fora do âmbito.

**Facto associado (corrige o entendimento):** as **HH/TS do GG vivem no BACKOFFICE do Rui (fora do PC)**; é **ele** que as descarrega e coloca manualmente em `gg_hh`/`gg_ts`. **Nunca procurar no disco o que é do ritual manual dele** — se falta a GG, pede-se ao Rui, não se vasculha o disco.

**Reafirmação de papéis (`PAPEIS_E_RESPONSABILIDADES`):** decisões de produto, dados e operação manual = **Rui**; Web e Code movem-se **dentro do que está descrito**; as autorizações funcionam como documentado — **nada se estende por iniciativa própria**.
