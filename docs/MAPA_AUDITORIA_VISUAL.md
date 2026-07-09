# Mapa de Auditoria Visual da App

**Para que serve:** guia para o Rui **percorrer a app com os olhos** e confirmar que tudo o que
entrou está são. Construído a partir do **frontend real** (código das páginas) + **números reais
de produção**. Lê-se enquanto se clica.

> **⚠️ Números "à data de 10 Jul 2026" — e o contexto manda.** Estamos **pós-wipe, a meio do
> reimporte**: só entraram **GG (3548 mãos) + Winamax (219)**; **PS/WPN = 0**; **tudo em `new`**;
> **GTO e HRC ainda vazios** (biblioteca e fila por alimentar). Muitos números "baixos" ou "zero"
> são **esperados** nesta fase. Depois da **Etapa 2** (resto do reimporte) regeneram-se — cada
> secção diz o que renasce sozinho.

Legenda dos veredictos: **✓ saudável** · **⚠ conhecido-e-explicado** · **🔴 fora do esperado
(parar e reportar, nunca consertar à mão)**.

---

## ROTEIRO DE AUDITORIA (a ordem por que se percorre)

Faz isto de cima a baixo; em cada paragem confirma o resultado esperado.

1. **Dashboard** — "Total de mãos" bate com o esperado (hoje ~3767, GG+WN). "Mãos por estudar"
   mostra a repartição por tag/sala. Sparkline do tempo de estudo faz sentido.
2. **Dashboard → SS strip** — "SS com Match" verde; "SS Sem Match" e "Discord sem Match" com
   números pequenos e explicáveis (não centenas).
3. **Dashboard → Marcadas por captura** — a fila de triagem tem o que esperas (mãos GG por SS).
4. **Saúde Import** — escolhe o dia-de-jogo do último import; cada cano (hands/mesa/lobby/hh_ts)
   com falhas explicáveis, `deanon.alert` **não** vermelho.
5. **Saúde GG → "Nomes em conflito"** — a quarentena de nomes **não** tem cartões novos por decidir
   (ou tens de os carimbar tu). "Fronteira FT (rever)" idem.
6. **Saúde GG → scans** (os 3 gates das coroas, ver secção) — **contaminação = 0** nos três.
7. **Mãos suspeitas** — "bounty abaixo de metade" e "nome do Hero num vilão" ≈ **0** nas mãos novas.
8. **SS Mesa** — as capturas do dia casaram (`success`); **órfãs do dia = 0**.
9. **Lobbys** — os lobbys do dia resolveram (ou aguardam TS em falta, com motivo claro).
10. **Torneios** — os torneios do dia aparecem com mãos + TS + formato coerentes.
11. **Estudo** — as tagadas com nomes reais estão lá; **nenhuma GG anónima** aparece no Estudo.
12. **Vilões** — nicks novos coerentes; **nenhum vilão numa mão GG sem match**.
13. **HM3** — só WN/PS/WPN, zero GG; tags presentes.
14. **Discord** — (dormente) só confirmar que não está a re-sincronizar sozinho.
15. **HRC** — a fila mostra as elegíveis; nada preso por engano (o que falta payout diz-se no banner).
16. **GTO / HRC Sessões** — a biblioteca/sessões refletem o que importaste (hoje: vazias).

**Se em qualquer paragem vires um 🔴 (contaminação >0, GG anónima no Estudo, vilão em mão sem
match): PÁRA e reporta. Nunca consertar à mão** — os dados reimportam-se; o que interessa é o core.

---

## 1. Dashboard  (menu "Dashboard", `/`)

**1. O QUE É** — o hub. Junta contadores de mãos/estudo, tempo de estudo da semana, saúde do
match de screenshots, últimas mãos importadas e a fila de "Marcadas por captura". Dados de
`/api/hands/stats`, `/api/study/week`, `/api/capture-triage`, `/api/hands/ss-without-match`.

**2. O QUE VÊS**
- **Total de mãos** — nº grande (todas as mãos 2026) + "esta semana" + "revistas". Clica → Estudo.
- **Mãos por estudar** — total em `new` + repartição por **tag** e por **sala** (GG/PS/WN/WPN).
- **Tempo de estudo** — segundos da semana + média/dia + sparkline (hoje realçado).
- **Strip de SS** (4 contadores): **SS Total**, **SS com Match** (verde), **SS Sem Match (import
  manual)** (âmbar), **Discord sem Match** (com sub-contas Replayer/Imagem).
- **Órfãos (OrphanList)** — SS sem HH, por tipo (Manual/Replayer/Imagem), com TM, data, ficheiro.
- **Últimas mãos importadas** — cada linha: estado, cartas, posição, resultado BB, tags, sala, data.
- **Marcadas por captura** — mãos GG desanonimizadas por SS mas sem tag; botões de tag.

**3. NÚMERO ESPERADO HOJE**
- Total de mãos: **~3767** (GG 3548 + WN 219). **✓** (pós-wipe, só estas 2 salas até agora).
- Mãos por estudar: **~3767** — **⚠ tudo em `new`** (o reimporte mete tudo em `new`; é o mislabel
  conhecido `#STUDY-STATE-REGRESSION`, inócuo — as GG anónimas ficam escondidas do Estudo à mesma).
- SS com Match verde; SS/Discord sem Match: **números pequenos** e explicáveis. **✓**

**4. AÇÕES QUE PODES TOMAR**
- Clicar nos painéis / "Ver todas" → navegação (não muda nada).
- **× (apagar mão recente)** → apaga a mão. **DEFINITIVO.** (pede confirmação se tiver tags/notas).
- **Rematch todos / Rematch (órfão)** → tenta ligar SS órfãs a mãos. **Reversível** (só liga).
- **Ignorar (órfão)** → esconde (muda status). **Reversível.**
- **Apagar (órfão)** → apaga o entry. **DEFINITIVO.**
- **Botões de tag (Marcadas)** → tagam a mão (entra no Estudo/Vilões) ou **descartam**. Consequente.

**5. SINAIS DE ALARME**
- "Discord sem Match" às **centenas** → algo se dessincronizou (o Discord está dormente).
- "SS Sem Match" a crescer sem parar → capturas sem HH (esperado só até a HH entrar).
- Não apagues mãos recentes "para limpar" — se te parecer a mais, **reporta**.

**6. RELAÇÃO COM O REIMPORTE** — todos os contadores são vista ao vivo; **regeneram-se** no
reimporte. Nada aqui é decisão manual que se perca.

---

## 2. Saúde Import  (menu "Saúde Import", `/import-health`)

**1. O QUE É** — diagnóstico **só-leitura** do pipeline de importação, por **dia-de-jogo**
(janela 15:00→15:00). Uma chamada: `/api/import-health?day=`.

**2. O QUE VÊS** — um cartão por cano: **hands / mesa / lobby / hh_ts / inbox**. Cada um com:
chips de total/ok/falha/parcial/GG-sem-match; repartição `by_result` (verde=success,
âmbar=tm_not_found/ambiguous/no_match, vermelho=vision_failed/erro); tabelas de **falhas**, **runs**
e **failed_items** (com hora, motivo, ficheiro). Mais dois cartões: **Desanon por SS de mesa**
(total/completa/parcial + alerta epistémico) e **Buracos de logging** (falhas sem rasto).

**3. NÚMERO ESPERADO HOJE** — depende do dia que escolheres. Para o **9 Jul**: hands ~926, mesa
~65 success, lobby 22, e a desanon com `partial_rate` baixo. **✓** se as falhas forem as
conhecidas (tm_not_found de lobbys à espera de TS; no_match de mesas à espera de HH).

**4. AÇÕES** — **Aplicar** (escolhe o dia) e **Todas as datas**. **Tudo só-leitura** — esta página
não escreve nada.

**5. SINAIS DE ALARME** — **`deanon.alert` a vermelho** (guarda epistémica: desanon a inventar);
`vision_failed` em massa num cano; um cano a `error`. → reporta.

**6. RELAÇÃO COM O REIMPORTE** — é um espelho; regenera-se. É a **primeira paragem** para ver se
um import correu bem.

---

## 3. Estudo  (menu "Estudo", `/hands`)

**1. O QUE É** — a razão nº1 da app: as mãos de dúvida **com nomes reais** (tagadas + com match).
Exclui as GG em bloco anónimo. Vistas: Por Tags / Por Torneio / Cards / Tabela. Dados de
`/api/hands/tag-groups` e `/api/hands`.

**2. O QUE VÊS** — grupos por tag (Principais >100 / Secundárias / Spots <10), cada um com
contagem + W/L/BB; filtros por data, showdown, **IRE** (≥13/≥9/≥5.1), site, posição, vilão. Modal
da mão: notas, tags, replayer, análise Pot Odds/MDF/MBF, screenshot inline. Badges de HRC por linha.

**3. NÚMERO ESPERADO HOJE** — **só as tagadas com nomes reais**. Exemplo medido do 9 Jul: **33
mãos GG tagadas+desanonimizadas** elegíveis. A **esmagadora maioria das 3548 GG NÃO aparece aqui**
(são arquivo anónimo, sem tag/match) — **✓ é assim mesmo**.

**4. AÇÕES** — **Guardar** (notas/tags, reversível), **Revista ✓** (muda estado, reversível),
**Análise** (só calcula), **× Apagar mão** (**DEFINITIVO**), **Enviar N ao HRC** (mete na fila;
reversível pela própria fila). Copiar HH / Replayer = navegação.

**5. SINAIS DE ALARME** — 🔴 **uma mão GG anónima (hashes em vez de nomes) no Estudo** → o gate
`match_method` falhou; **pára e reporta**. Tag errada numa mão → corrige a tag (reversível), não
apagues a mão.

**6. RELAÇÃO COM O REIMPORTE** — as tags de estudo vêm da **pasta do IT** e renascem no reimporte;
as **notas** que escreves à mão **não** — são tuas, repetem-se só se as voltares a pôr.

---

## 4. Discord  (menu "Discord", `/discord`)

**1. O QUE É** — centro de controlo da ingestão Discord. **Está DESCONTINUADO como entrada** (não
se sincroniza; morreu com o replayer-image GG). Mantém-se dormente e intacto. As tags de estudo
chegam hoje pela **pasta do IT**, não pelo Discord.

**2. O QUE VÊS** — 2 abas: "Mãos Importadas" (grupos por canal + galeria de imagens) e "Estado do
Bot" (online/offline, stats por tipo/canal, histórico de sync). Painéis de sync (janela + histórico)
e de sync de lobbys.

**3. NÚMERO ESPERADO HOJE** — bot **Offline** (esperado, dormente). Mãos importadas: as históricas.
**✓** se **não** estiver a sincronizar sozinho.

**4. AÇÕES** — **Sincronizar histórico / Sincronizar ▾ / Sincronizar Lobbys** → **escrevem** (importam
mãos, correm Vision). **Não usar sem intenção clara** (o Discord está dormente por decisão). Apagar
mão = **DEFINITIVO**. Dry-run do lobby = seguro.

**5. SINAIS DE ALARME** — o bot **Online** e a importar sozinho (não devia); uma sync a criar mãos
inesperadas. → reporta.

**6. RELAÇÃO COM O REIMPORTE** — dormente; não faz parte do fluxo actual. Ignora-o na auditoria
(só confirmar que está quieto).

---

## 5. Torneios  (menu "Torneios", `/tournaments`)

**1. O QUE É** — navegação das mãos por **Data → Torneio → Mão**, em 2 abas: **GG** e **HM3 com
Nota** (WN/PS/WPN tagadas 'nota'). É também a porta de **importar** SS de mesa GG, **Tournament
Summaries** e **Tournament Results** (backoffice). Dados de `/api/mtt/*`, `/api/hm3/nota-*`.

**2. O QUE VÊS** — barra de stats (Mãos, Com SS, Torneios, Villains); sub-navegação Com SS / Sem SS;
grupos por dia e por torneio (nome, TM, horas, buy-in, blinds, formato, nº SS, nº villains); detalhe
por mão (villains VPIP + mesa por screenshot).

**3. NÚMERO ESPERADO HOJE** — GG: **3548 mãos**, **56 Tournament Summaries**, **35 estruturas de
payout**. Do 9 Jul: **22 torneios** (17 com TS, 3 sem TS ainda). **✓** (os 3 TS entram na próxima
ida ao backoffice).

**4. AÇÕES** — **Importar TS / Importar Results** (aditivo, idempotente). **Apagar mão / Apagar
Screenshot** → **DEFINITIVO** (o apagar SS reverte o match). Copiar HH / Replayer = navegação.

**5. SINAIS DE ALARME** — um torneio com formato errado (ex.: PKO marcado Vanilla) → o gatilho do TS
corrige quando o TS entra; se persistir, reporta. Villains numa mão GG sem SS → não deve acontecer.

**6. RELAÇÃO COM O REIMPORTE** — tudo renasce (HH + TS + Results reimportam-se). Os drill-downs são
vista ao vivo.

---

## 6. Lobbys  (menu "Lobbys", `/lobbys`)

**1. O QUE É** — 2ª via (fora do Discord) para meter **estruturas de prémios** (`tournament_payouts`)
a partir de screenshots de lobby. A IA lê; se for mesmo lobby, escreve o payout. Reconcilia lobbys
pendentes. Dados: `/api/lobbys/upload`, `/api/lobbys/reconcile`.

**2. O QUE VÊS** — chips por ficheiro (lobby verde / não-lobby amarelo / falha). Painel de
**Reconcile** (pendentes/resolúveis/escritos). Detalhe: Extração (IA: nome, tn, prémios) vs Import
(resultado, tier, payouts escritos).

**3. NÚMERO ESPERADO HOJE** — do 9 Jul: **22 lobbys, todos resolvidos** após os TS entrarem (o
reconcile religou-os). **8 torneios com payout**. **✓** Ficam por resolver só os que dependem dos
**3 TS em falta**.

**4. AÇÕES** — **Upload** (escreve payout, respeita precedência — não sobrepõe fonte melhor).
**Forçar releitura** (refresca só a leitura, não os prémios). **Pré-visualizar** (só-leitura).
**Aplicar N payouts** (escreve; aditivo/update, não apaga).

**5. SINAIS DE ALARME** — um payout escrito num torneio errado (nome mal resolvido) → reporta (há a
guarda de âncora no Hero, mas confirma). Aba **Info** a escrever prémios → não deve (regra
`#LOBBY-INFO-NO-PAYOUT`).

**6. RELAÇÃO COM O REIMPORTE** — os payouts vêm dos lobbys/backoffice e reimportam-se. O reconcile
volta a ligar sozinho quando os TS entram.

---

## 7. HM3  (menu "HM3", `/hm3`)

**1. O QUE É** — as mãos do Holdem Manager 3: **só Winamax/PokerStars/WPN** (nunca GG). Navegação
por semana→dia→torneio + import de CSV. Dados: `/api/hands`, `/api/hm3/*`.

**2. O QUE VÊS** — cartões por sala (novas/rev/est/res); painel de import (dias-atrás, só-nota,
Re-parse); filtros (estado, sala, tag, BB min/max); grupos por dia/torneio; modal da mão.

**3. NÚMERO ESPERADO HOJE** — hoje só **Winamax (219 mãos)**; **PS/WPN = 0** (ainda não
reimportadas). Do 9 Jul: **53 mãos WN**, todas com hm3_tags. **✓ zero GG** (invariante).

**4. AÇÕES** — **Import CSV** (aditivo, dedup). **Re-parse** (re-extrai acções, update). **Guardar /
Revista** (reversível). **Apagar mão** (**DEFINITIVO**).

**5. SINAIS DE ALARME** — 🔴 **uma mão GG nesta página** (só devia haver WN/PS/WPN). Re-parse a
mudar resultados de forma estranha → reporta.

**6. RELAÇÃO COM O REIMPORTE** — as mãos HM3 reimportam-se do CSV; as tags do HM3 vêm no próprio CSV.

---

## 8. SS Mesa  (menu "SS Mesa", `/table-ss`)

**1. O QUE É** — upload dos **prints de mesa** do Intuitive Tables, para dar ao HRC um
`players_left` fiável por mão e desanonimizar GG. A IA lê o painel; liga à mão jogada ±5 min.
Dados: `/api/table-ss/upload`, `/api/table-ss/recent`.

**2. O QUE VÊS** — chips por ficheiro (ligada verde / sem match amarelo / erro). Tabela "Últimas
processadas": captura, site, torneio, players_left, entries, mão, resultado, tentativas.

**3. NÚMERO ESPERADO HOJE** — **387 capturas** no total. Do 9 Jul: **65 success, 0 órfãs** (as 37
que estavam órfãs casaram quando as HH de 9 Jul entraram). **✓**

**4. AÇÕES** — **Upload** (cria a captura, corre IA, liga à mão). **↻ Refresh** (só-leitura). **Sem
apagar** — página de upload + ver.

**5. SINAIS DE ALARME** — muitas `no_match_to_hand` de um dia com HH já importadas (deviam casar);
`vision_failed` em massa. → reporta. (Órfãs de dias **sem** HH ainda são esperadas.)

**6. RELAÇÃO COM O REIMPORTE** — as capturas reimportam-se da pasta do IT; **a subpasta = a tag**
(o move do `done` agora preserva a subpasta, senão a tag morria — `#ICM-FT-TAG-NOT-LANDING`).

---

## 9. Saúde GG  (menu "Saúde GG", `/gg-health`)

**1. O QUE É** — o **posto de qualidade** das mãos GG (as anonimizadas). Vista por imagem +
painéis de decisão: suspeitas de troca, conflitos de tags, **fronteira FT**, **nomes em conflito**.
Dados: `/api/gg-health/*`.

**2. O QUE VÊS** — dashboard de contadores (Gold sem tag, Órfãs, Suspeitas de troca, Conflito de
tags, Fronteira FT, Nomes em conflito) + a lista por imagem. Painéis: **Fronteira FT** (ensaio por
torneio, Aprovar/Confirmar/Corrigir/Promover/Dispensar) e **Nomes em conflito** (dois lados de cada
"nome→2 lugares", com re-entrada).

**3. NÚMERO ESPERADO HOJE** — **Gold sem tag: 11** · **Órfãs: 19** (capturas de Jun sem HH; descem
a 0 na Etapa 2) · **Fronteira FT: 2 dispensados + 2 promovidos, 0 pendentes** · **Nomes em conflito:
os que estiverem por carimbar**. **⚠ conhecido** (as 19 órfãs).

**4. AÇÕES** — **Aplicar tags** (ACRESCENTA, reversível). **Ligar órfã** (liga captura a mão,
confirmação). **Resolver suspeita** ("É esta a dona" — pode reverter a mão antiga a anónima).
**FT: Confirmar/Corrigir** (fixa a fronteira, não escreve tags) vs **Promover** (**escreve** as
tags -ft, com ensaio antes) vs **Dispensar** (só anota, não toca mãos). **Nomes: "É este"/"Confirmar
o forte"/"Mesma pessoa (re-entrada)"/"Dispensar"** (dispensar = ambos ficam brancos, honesto).

**5. SINAIS DE ALARME** — **🔴 os 3 gates das coroas com contaminação >0** (ver §"Gates" abaixo);
cartões de nome novos que não reconheces; uma suspeita de troca com stacks óbvios. → **decidir com
calma ou reportar; nunca "consertar à mão" o core**.

**6. RELAÇÃO COM O REIMPORTE** — a desanon e as coroas renascem do ingest; as **decisões manuais**
(nomes carimbados, FT promovidas) **repetem-se** — é o teste de aceitação do wipe (nascer limpo).

### Os 3 GATES das coroas (regra permanente, endpoints em Saúde GG)
Correr sobre as **tagadas** e confirmar **0** nos três:
- `eliminated-crown-scan` → `vision_origin_contamination` = **0** (coroa de eliminado nunca vem do vizinho).
- `live-crown-zero-scan` → `silent_zero_contamination` = **0** (vivo com $0 nunca grava $0 silencioso).
- `spurious-crown-non-ko-scan` → `spurious_crown_contamination` = **0** (coroa inventada em torneio sem bounty).

**Medido no 9 Jul (tagadas): 0 / 0 / 0** — ✓ **primeira sessão a nascer com as coroas limpas.**
**Qualquer um >0 = PARAR + investigar. Nunca dar por curado com o scan >0.**

---

## 10. Marcadas/captura  (menu "Marcadas/captura", `/marcadas-por-captura`)

**1. O QUE É** — fila de triagem das mãos GG desanonimizadas por **SS de mesa** mas **sem tag**.
Para cada uma escolhes UMA tag (que a injecta no Estudo/Vilões) ou descartas. `/api/capture-triage`.

**2. O QUE VÊS** — cartões: miniatura da captura (zoom), nome/torneio, data, badge "parcial"
(desanon incompleta), jogadores (Hero destacado). 5 botões de tag + descartar.

**3. NÚMERO ESPERADO HOJE** — o que estiver por triar. **✓** (fila de trabalho; varia).

**4. AÇÕES** — **icm-pko / pos-pko / icm / nota** → taga (entra no fluxo, pode criar vilões).
**descartar** → tira da fila. Ambos consequentes; reversíveis re-tagando noutro sítio (sem undo aqui).

**5. SINAIS DE ALARME** — muitas "parcial" (desanon a falhar bancos); uma mão sem captura. → reporta.

**6. RELAÇÃO COM O REIMPORTE** — a triagem baseia-se na captura+tag da pasta; renasce. A escolha de
tag manual repete-se se não vier já da pasta.

---

## 11. Mãos suspeitas  (menu "Mãos suspeitas", `/suspeitas`)

**1. O QUE É** — fila de revisão viva (só GG, 2026) das mãos apanhadas pelos venenos das coroas.
Só mostra e aponta (sem edição no sítio). `/api/suspicious`.

**2. O QUE VÊS** — grupos: **"bounty abaixo de metade"** (coroa < base÷2) e **"nome do Hero num
vilão"**. Cada linha aponta para a mão (abre para ver a imagem).

**3. NÚMERO ESPERADO HOJE** — **~0 nas mãos novas** (o fix das coroas + os gates). Medido 9 Jul:
suspeitas <base÷2 não-confirmadas = **0**. **✓**

**4. AÇÕES** — nenhuma aqui (é só apontar). A correcção faz-se no **lápis da coroa** no detalhe da
mão (editar/confirmar; o Hero **também** tem lápis agora).

**5. SINAIS DE ALARME** — este grupo a **encher** nas mãos novas → uma guarda das coroas regrediu.
→ correr os 3 gates e reportar.

**6. RELAÇÃO COM O REIMPORTE** — vista ao vivo; pós-reimporte deve nascer **~0** (só bordos legítimos).

---

## 12. Vilões  (menu "Vilões", `/villains`)

**1. O QUE É** — lista categorizada de adversários (Todos / Mãos com SD / Notas / Amigos), perfil
por vilão com as mãos em comum, + operações de manutenção. `/api/villains/*`.

**2. O QUE VÊS** — por vilão: nick, badges de categoria (SD/Notas/Friends), total de mãos, visto há,
salas, datas. Perfil: mãos em comum com grelha de acções por rua.

**3. NÚMERO ESPERADO HOJE** — **118 nicks**, **172 linhas** (hoje todas categoria **`nota`** —
SD/friend ainda por gerar no reimporte). **✓**

**4. AÇÕES** — **+ Novo** (cria, reversível). **Recalcular / Re-enrich / Re-parse DB / Migrar BD** →
re-processamentos pesados (recomputam/reescrevem; o Re-parse mexe em dados parseados — usar com
cuidado). Perfil = navegação/clipboard.

**5. SINAIS DE ALARME** — 🔴 **um vilão numa mão GG sem match** (invariante quebrado). Medido: **0**.
→ se aparecer, reporta.

**6. RELAÇÃO COM O REIMPORTE** — os vilões renascem das regras A/C/D no ingest. As notas manuais nos
vilões repetem-se só se as voltares a pôr.

---

## 13. GTO  (menu "GTO", `/gto`)

**1. O QUE É** — biblioteca das árvores do solver (HRC), importadas de "Complete Export". Gerir/
filtrar/importar/editar/apagar. `/api/gto/*`.

**2. O QUE VÊS** — contadores (nº trees, nº nós, por formato); tabela (nome, formato, mesa, posição,
stack, cobertura, fase, nós, contribuidor).

**3. NÚMERO ESPERADO HOJE** — **0 trees / 0 nós**. **⚠ esperado** — a biblioteca está vazia
(pós-wipe; alimenta-se quando o pipeline HRC voltar a correr).

**4. AÇÕES** — **Importar Tree** (aditivo). **Editar** (metadados, reversível). **Apagar** (tree +
nós, **DEFINITIVO**, dois cliques).

**5. SINAIS DE ALARME** — nada crítico nesta fase (vazia). Um formato mal atribuído numa tree futura.

**6. RELAÇÃO COM O REIMPORTE** — a biblioteca reconstrói-se à medida que o robot HRC processa mãos.

---

## 14. HRC  (menu "HRC", `/hrc`)

**1. O QUE É** — espelho dos gates da **fila HRC**: mostra exactamente o que o robot puxaria agora.
Fila **100% manual** (só "Enviar ao HRC" liberta). Gere enviadas + verificação HH↔HRC. `/api/queue/hrc/*`.

**2. O QUE VÊS** — painel **FILA MANUAL** (em curso / disponíveis / elegíveis / já feitas); banner
**"mãos escondidas"** (sem TS → importar TS, ou Mystery não suportado); tabela de elegíveis (por
mão: torneio, formato, posição, 1ºVPIP, stack, restantes, agressor, tags); painel **Enviadas**
(estado resolvida/por-resolver/cancelada + verificação ✓/⚠/✗).

**3. NÚMERO ESPERADO HOJE** — **0 enviadas / 0 done** (fila por alimentar; robot não correu
pós-wipe). As **elegíveis** aparecem consoante tags+TS. **⚠ esperado.** As **Speed Racer** só
aparecem quando a **tag `speed-racer`** aterrar (hoje já em 11 mãos).

**4. AÇÕES** — **Enviar marcadas** (liberta ao robot, reversível). **Limpar fila** (pausa,
reversível). **↻ Re-pôr na fila** (re-queue de cancelada). **⬇ HRC** (download do pack, só-leitura).
**Verificar resolvidas** (só-leitura). **Nova/Revista** (reversível).

**5. SINAIS DE ALARME** — uma mão elegível que **não devia** (formato/tag errados) — vem do formato,
que o gatilho do TS corrige; se persistir, reporta. Banner "mãos escondidas" grande → faltam TS.

**6. RELAÇÃO COM O REIMPORTE** — a elegibilidade é vista ao vivo (depende de tags+TS+payout). O que
o robot já solveu (`hrc_jobs`) desaparece no wipe e re-solve-se.

---

## 15. HRC Sessões  (menu "HRC Sessões", `/hrc-sessions`)

**1. O QUE É** — importar um "Complete Export" do HRC e navegar as sessões de estratégia importadas.
`/api/hrc/sessions`, `/api/hrc/import`.

**2. O QUE VÊS** — dropzone de import; tabela de sessões (#, nome, nº nós, source [watcher/manual],
importado, mão). Detalhe: settings da mesa/estrutura + a matriz de ranges do nó-raiz (13×13).

**3. NÚMERO ESPERADO HOJE** — **0 sessões**. **⚠ esperado** (pós-wipe).

**4. AÇÕES** — **Upload** (aditivo). **Apagar sessão** (sessão + nós, **DEFINITIVO**). Abrir/ver =
navegação.

**5. SINAIS DE ALARME** — nada crítico nesta fase.

**6. RELAÇÃO COM O REIMPORTE** — as sessões vêm do robot; reconstroem-se.

---

## Nota de manutenção

Os números "esperados hoje" são **datados de 10 Jul 2026** e refletem o **estado pós-wipe/
meio-de-reimporte**. **Depois da Etapa 2** (resto do reimporte) muitos crescem/regeneram — este mapa
é também o **instrumento de validação visual pós-wipe**: percorrer o roteiro e confirmar que tudo
nasce são (com destaque para os **3 gates das coroas a 0** e **nenhuma GG anónima no Estudo**).
Actualizar a data + os números após cada grande import.
