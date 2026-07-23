# Pendentes — backlog vivo

## ★★ FOCO ATUAL (23 Jul, ordem do Rui): SÓ WINAMAX — a GG está EM ESPERA

**Tudo o que diga respeito à GG fica PARQUEADO** até o Rui voltar à GG (ver secção
«parqueado» abaixo). Stars/WPN também de lado (poucas mãos).

**LIVE 23 Jul (journal `journal/2026-07-23.md`):** ① alias `kostadin0v` (nick novo WN;
`thinvalium` fica p/ mãos antigas; confirmado sem colisão) · ② **guarda do Info POR SALA**
(`6326a8d`, fix-na-causa): «print Info nunca escreve prémios» era lei da GG mas estava
GLOBAL e matava a única fonte de prémios da WN (na WN Info+Payout vêm no mesmo ecrã) —
agora GG→não escreve, WN→escreve; GG byte-a-byte igual; **automático daqui p/ a frente**
(qualquer print de lobby WN importado escreve prémios) · ③ **5 torneios WN destravados**
(ZENITH 21 Jun · INTERSTELLAR 11+14 Jul · GRAVITY 13 Jul · HIGHROLLER 16 Jun): payouts
escritos (`reconcile_lobby_vision:`) + **21/21 mãos ICM exportadas HTTP 200**, provado com
query fresca. Nota: 3 dos 5 prints com reg ainda aberta — escada é a melhor disponível;
print mais tardio sobrepõe-se (last-write-wins da mesma fonte). Verificado também: HRC WN
íntegro (966 mãos, 22c) e **as coroas WN aparecem no estudo** (estão no apa/`bounty` € e
no replayer — não estavam em falta).

**LIVE 24 Jul (journal `journal/2026-07-24.md`) — ★ TOTAL DE FICHAS WN PELO LOBBY
(`#WN-TOTAL-CHIPS-FROM-LOBBY`, plano de 5 fases aprovado e construído):** regra única em
`services/lobby_chips_rule.py` (RUNNING preferido > mais tardio; total = entradas×stack;
guarda não-desce; avg = sinalizador; «provisórias» sem print RUNNING; histórico = opção A
«estado desconhecido», SEM inferência de fecho) · Vision ensina estado WN + `re_entries`
(INFO-ONLY: vision_json + coluna no torneio, sem consumidores) · live+reconcile passam
pela regra (F5 automático) · GG byte-a-byte (caminho legado preservado). **✅ F4 APLICADO
24 Jul (tabela dos 96 aprovada pelo Rui):** 96 atualizados via `POST /wn-chips/apply
{confirm:true}` — 11 corrigidos (pior +140% INTERSTELLAR 13/07), 4 «finais» (RUNNING),
92 «provisórias» (29 late-reg + 63 estado desconhecido), 4 por-rever `avg_incoherent`;
sources preservados; 22 solves WN intactos (último carimbo 13 Jul); 0 linhas não-WN
tocadas. `re_entries`: coluna assente mas VAZIA no histórico (prints antigos não tinham o
campo lido; imagens não guardadas → irrecuperável) — preenche daqui em diante. Decisão
22 Jul do TS encerrada e assinada (`REGISTO_CONCEITO 2026-07-24 (b)`).

**PENDENTES (por ordem, foco Winamax):**
1. **Destravar as restantes ~167 mãos ICM WN sem prémios (~55 torneios)** — o Rui importa
   os PRINTS DE LOBBY que tem no PC (página Lobbys ou pasta `lobby` do Batmen; escrevem
   prémios automaticamente desde o `6326a8d`). Começar pelo **ZENITH FUNDAY 70K 12 Jul**
   (print já enviado, +19 mãos) e pelas noites que mais rendem: **9 Jun (35 mãos) · 11 Jun
   (25) · 12 Jun (HIGHROLLER 250€ = 20) · 14 Jun Space Sunday (17)**. Lista completa dos
   61 torneios: journal `2026-07-23 §5`.
2. **MAPA das regras GG que contaminam a Winamax** — a guarda do Info era a pior mas NÃO a
   única. Mapear todas as regras GG que disparam fora da GG e isolá-las por sala (é a raiz
   do «a Winamax parece mais complicada do que devia»). Já identificada: regra C dos
   vilões exige `match_method` (GG) em todas as salas (latente na WN, 0 mãos hoje).
3. **Régua dos 6s na Winamax** — a proteção «print ≤6s → mão anterior» é só-GG
   (`table_ss.py:1780`); as tags WN não a têm. Medido 23 Jul: **97 capturas WN com atraso
   NEGATIVO** (tiradas ANTES da mão casada começar; pior −54 min; 37 com tag) + 10 com
   ≤6s (5 com tag) — nunca auditadas (~45 das 227 pasta-tags WN em risco). Estender a
   proteção à WN (guarda de direção + regra dos 6s por sala).

**PARQUEADO (GG — só quando o Rui voltar à GG):** família grande (casador de capturas
5→1 · re-entrada por bust-HH · nomes/cadeiras · **22 suspeitas — «Aceitar» continua
PROIBIDO**) · conceitos das coroas 3/4/5 (+`#REGUA-COROAS`) · re-solve GG-6139792066 ·
Fase 2 das órfãs · `#MTT-DESANON-MORTO`.

**AÇÃO DO RUI (fora do código, pendente há dias): rotação dos segredos** — a password
só-leitura da BD foi exposta em logs locais (ecoada de novo em 22c §6).

## ★ FECHO DO BLOCO 22.1 (madrugada 22→23 Jul) — o que ficou LIVE e o que espera o Rui

**LIVE:** ① **auto-confirmação FT** (`a8f21aa`; testemunha independente obrigatória; app revê
a própria decisão; nunca pisa o Rui; 1ª corrida: 0 auto — 21 já decididas, 1 sem sinal) ·
② **régua única «quantos restam nesta mão»** (`00f2d84`; `services/players_left.py`:
captura→lobby-mais-próximo-no-tempo→vazio honesto; zero-lido=desconhecido; o «mais recente»
morreu; painel Enviadas corrigido; prova LIVE 22→34 + 5 casos inalterados). **VERIFICADO
sem mexer:** HRC Winamax íntegro (966 mãos, desvio máx 24 fichas = arredondamento).
Journal: `journal/2026-07-22c.md`.

**Pendentes de DECISÃO do Rui (novos):**
- **Re-solve da GG-6139792066** (solve feito com 22 restantes; eram ~34; export futuro já certo).
- ~~**TS Winamax: NÃO avança** (decisão do Rui, risco>ganho)~~ **ENCERRADA 24 Jul,
  assinada pelo Rui** (`REGISTO_CONCEITO 2026-07-24 (b)`): a fonte do total de fichas WN
  passa a ser o **print de lobby** pela régua `#WN-TOTAL-CHIPS-FROM-LOBBY`; o TS WN
  continua sem se importar (parser dormante). Defeito do parser (2 blocos lê o 1º;
  `hero_re_entries`=0) fica anotado, sem urgência.
- **Família grande «isto pertence aqui?» — inventário COMPLETO** (14 réguas→3 fontes;
  journal 22c §4). Ordem: casador (A1-A6→1) → re-entrada HH-first (bust manda; régua já
  ditada no jiwalegenda) → nomes → 22 suspeitas. **É maquinaria GG — fica para o regresso
  à GG.** ⚠️ «Aceitar» das 22 continua PROIBIDO até a fonte única existir.

## ★ PRÓXIMA SESSÃO — ordem do Rui (22 Jul 2026, fecho da sessão 2)

1. ✅ **AUTO-CONFIRMAÇÃO das fronteiras FT — SHIPPED 23 Jul** (`a8f21aa`; desenho:
   `REGISTO_CONCEITO 2026-07-22 (d)`). Fonte única `auto_confirm_witness` (fronteira +
   cross-check match + testemunha independente TS/lobby-N); match trivial não confirma;
   a app revê a própria decisão com dados novos; decisões do Rui intocáveis; dispensa
   reativada renasce pendente; promoção continua manual. Painel: crachá «pela app».
   Detalhe: `FT_BOUNDARY_ANATOMIA §8`.
2. **A FAMÍLIA GRANDE «este artefacto pertence a este torneio/mão?»** — consolidar as 4+
   réguas (prints fora de tempo <9s · régua dos 6s · suspeitas de troca [22 imagens, TODAS
   ecos `auto_moved` da régua dos 6s] · casador de capturas · resolver de lobbys) numa fonte
   única `capture_ownership` (PERTENCE/DA_ANTERIOR/NÃO-SEI) + painéis-montra + 1 rasto de
   decisão. Inventário e desenho: journal `2026-07-22b §3`. ⚠️ **Até lá, NÃO usar o
   «Aceitar» das 22 suspeitas** (desfaria decisões da régua dos 6s + reverteria desanon).
3. **Conceito 3 — MÍNIMO DA COROA** (3 decisões já tomadas pelo Rui).
4. **Conceito 4 — COROA VÁLIDA** (+ `#REGUA-COROAS`; precisa de 2 palavras do Rui: «âncora
   fiável» e se o fill da testemunha sela).
5. **Conceito 5 — QUEM SENTA ONDE** + remoção do `#MTT-DESANON-MORTO`.
6. **Pendentes do Rui:** Toruk na quarentena de nomes · 21 «à espera de tag» · 660 mãos do
   acidente do disco · 43 coroas anuladas · **rotação dos segredos** (a password só-leitura
   da BD ficou ecoada em logs locais várias vezes — rodar).

*(Fechados nesta sessão: fonte (T) da fronteira FT + `hand_ft_state` + recuos/recuperações +
undo 991 [`c0e2b71`]; guarda de causalidade no resolver + morte do prestart [`d9b0995`] +
re-resolução dos 7 prints com 297003773/297008916 recuperados e mãos destravadas no HRC —
prova por export 200. Journal `2026-07-22b`.)*

## ~~★ EM CURSO (22 Jul, sessão 2b) — guarda de causalidade no resolver de lobbys~~ ✅ FECHADO (ver acima)

Régua do Rui (carimbada): **print de lobby anterior ao arranque = IMPOSSÍVEL** (ele só tira
prints DURANTE o jogo, mãos HRC/ICM). Código feito em local (diff ao Rui antes do push):
resolver com janela **só-para-trás** para todos (`anchor_mode`/`prestart` REMOVIDOS — a
premissa pt40 «lobby=inscrição» era da era Discord e está morta); `reconcile` com
`message_ids` re-resolve **qualquer** estado (via de correção). **Após OK+deploy, operações:**
`POST /api/lobbys/reconcile` (1º `dry_run=true`, depois real) com os **7 mids**: os 5 roubados
(614cb1d6…, a40e3f80…, 74cc1185…, 1300715a…, 9ae3a475…) + os 2 cruzados do Deepstack $88
30 Jun (98721a9b… entrants=217→dono 294738291; e4807c9d… entrants=305→dono 294711510).
**Prova de aceitação:** 297003773 e 297008916 ganham payouts; 294711510 perde os ERRADOS
(eram do gémeo — hoje source `file_lobby_vision:98721a9b…`) e ganha os dele; 294738291 ganha
os dele (a guarda de coerência tinha, e bem, recusado os do gémeo — era esse o «sem payouts»).
Alguns dos 7 podem cair em `edition_quarantine` (honesto — Rui decide no painel de edições).

## ~~★ EM CURSO (22 Jul, sessão 2) — fronteira FT pela TRANSIÇÃO DA HH~~ ✅ FECHADO (executado por inteiro; journal 2026-07-22b §1)

Decisão do Rui (22 Jul): fonte (T) transição do -max é a primária da fronteira; recuar as
5 fronteiras atrasadas; recuperar o dispensado 289176860; depois desfazer a captura 991
(GG-6083363843 → religar à GG-6083363849). **Código feito em local (3 peças a/b/c +
`hand_ft_state` + `/regra6s/undo`), diff apresentado ao Rui — falta: OK do Rui → push/deploy
→ operações por endpoint (o `/ft/confirm`/`/ft/correct` recomputam na hora, não é preciso
gatilho):** (1) 4 promovidas: `POST /ft/correct {override_boundary}` → `/ft/promote
{confirm:true}` — 289898535→`2026-06-12 23:39:05` · 290349007→`2026-06-15 02:23:32` ·
293321688→`2026-06-25 18:05:40` · 295219051→`2026-07-02 19:18:36`; (2) pendente 298159649:
`/ft/confirm` (a fonte T dá `2026-07-14 20:52:54`); (3) dispensada 289176860: `/ft/confirm`
(fronteira `2026-06-09 19:07:18`); (4) por fim `POST /table-ss/regra6s/undo {ssid:991,
back_to:'GG-6083363849'}`. Os 3 FTs sem registo (287863839 · vitória 289883772 · 293657420)
aparecem no painel «Prontas a aprovar» no próximo refresh (import) — carimbo do Rui lá.
Detalhe: `FT_BOUNDARY_ANATOMIA §2/§11`, `REGISTO_CONCEITO 2026-07-22 (b)`.

## ★ PRÓXIMA SESSÃO — ordem do Rui (21 Jul 2026): consolidar o Tier 1 da auditoria `#LEI-FIX-NA-CAUSA`

Auditoria transversal fechada (família "regra num sítio, ausente noutro"; detalhe em
`TECH_DEBTS_INVENTARIO.md`, secção 21 Jul noite). **Ordem acordada:**

1. ✅ **`#BUST-NO-COVERAGE-GUARD`** — **FEITO 21 Jul** (`eliminated_bounty.allin_outcomes` = fonte única;
   12 call-sites herdaram a guarda; `crown_recovery` sem régua própria). 1 227 lugares deixam de sair
   mortos, 0 busts reais perdidos, os dois lados do ecrã concordam em 29 007/29 007. Detalhe e provas no
   `TECH_DEBTS_INVENTARIO.md`. **Fica por tratar, declarado à parte: as 43 coroas já anuladas** (sintoma —
   reparação é trabalho separado) e a revisão dos `derived_green_ko` selados que possam ter nascido daí.
2. ✅ **CONCEITO SELO FECHADO — 21 Jul (noite 2)**, com a REGRA DOS DOIS CARIMBOS do Rui (para trás
   tudo intocável; para a frente `bounty_stamp` placa/aceitacao + `origin` por painel — só REGISTO, o
   "aceitação cede" NÃO foi construído). Fechados: `#GOLD-BACKFILL-NO-SEAL`, `#REENRICH-SEAL-LOST`,
   `#SET-ANON-MAP-BOUNTY-UNSEALED` (+ achado do lápis do nome: a reconstrução do apa zerava/des-selava
   coroas — transportador único `merge_sealed_crowns_apa`). Detalhe/provas: `TECH_DEBTS_INVENTARIO.md`
   secção 21 Jul noite. **`#CROWN-FALLBACK-NO-ELIM-GUARD` continua ABERTO** (a guarda de eliminado é do
   conceito COROA VÁLIDA; o fallback-fill ganhou só o check de selo). Novo p/ o conceito COROA VÁLIDA:
   `#CROSS-WRITERS-PL-ONLY` (assimetria das gavetas — cross_* escrevem só no players_list).
3. ✅ **`#RETAG-NO-PIPELINE` — FECHADO 22 Jul (Fase 1 das órfãs).** Gatilho único
   `study_pipeline.on_hand_tagged` (vilões + funil c/ TS live + propagação + FT); os 3 caminhos de
   re-tag são camadas finas. Detalhe/provas em `TECH_DEBTS_INVENTARIO.md` (secção 21 Jul noite).
4. **🔴 FASE 2 das órfãs — POR AUTORIZAR (ensaio primeiro, escrita só com OK do Rui).** As 110 mãos
   Gold-sem-tag-sem-captura (funil nunca correu: 7 bustados com coroa fantasma, 12 vivos-$0 sem marca;
   lista completa entregue 21 Jul) + os **6 pares provados de print-atrasado** (mover a tag `pos-*` da
   seguinte para a órfã, pelo selo, e correr o pipeline): GG-6170287515 ← GG-6170287647 ·
   GG-6174850882 ← GG-6174850954 · GG-6177133372 ← GG-6177133418 · GG-6182664803 ← GG-6182664856 ·
   GG-6179890563 ← GG-6179890664 · GG-6184091080 ← GG-6184091134. A GG-6090481360 (Lauro, coroa
   fantasma $421) é o ensaio do funil à parte. As 217 «Gold sem tag COM captura» (achatamento 10-11
   Jul, folder-tag perdida no disco) = re-tag manual, fila no painel «Gold sem tag» da Saúde GG.
5. **★ `#REGUA-COROAS` (DITADA PELO RUI, 22 Jul)** — a régua completa das coroas: CASCATA
   (verde×2 → SS direta → histórico, nunca desistir) + TRAVÃO MÍNIMO (base÷2 folga zero, 0+rever)
   + TRAVÃO PROGRESSIVE (coroas nunca descem no torneio; âncoras fiáveis estabelecem o piso; a app
   marca erro SOZINHA — ressalva: definir «âncora fiável»=selada/forte com o Rui) + FALLBACK
   HONESTO (marca «Coroa eliminada» visível; as marcas já existem nos dados, falta o frontend).
   **Ataca-se DENTRO dos conceitos 3 (mínimo) e 4 (coroa válida) — não é frente nova.** Detalhe
   completo + mapa dos 8 painéis (leitores da régua única, LEI 3) + medição do progressive
   (11 violações / 8 jogador-torneio / 2 027 trajetórias) em `TECH_DEBTS_INVENTARIO.md`
   §`#REGUA-COROAS` (secção 21 Jul noite).
6. ✅ **PAINEL DE RECONCILIAÇÃO — SHIPPED 22 Jul** (extensão do «Prints fora de tempo», régua do Rui:
   gatilho <9s pos/nota → confirmação na anterior pela HH — pos=ronda de apostas pós-flop do Hero
   [all-in pré NÃO conta, caso GG-6180819531] · nota=showdown REAL [regra só-deste-exercício] · FT
   fora). PROVADO vs SÓ-SUSPEITA com razão; «Aceitar todos» move pelo selo (preview+batch) + pipeline
   Fase 1; Dispensar persistido (`late_print_review`). Helpers ÚNICOS `services/hh_facts.py`
   (`hero_postflop_betting`/`real_showdown` — o `had_flop` morreu). Checklist LEI 1 ✓.
7. ✅ **RÉGUA DOS 6s AUTOMÁTICA — SHIPPED 22 Jul** (lei do Rui): captura table-SS tirada **≤6s**
   do início pertence à **MÃO ANTERIOR** — qualquer tag e SEM tag (FT fora, como sempre). **A app
   move SOZINHA no processamento** (`table_ss.apply_regra_6s`, no gatilho dos imports/reconcile —
   `trigger_import_reconciles`, antes do crossing): com tag move tag+imagem; sem tag move só a
   imagem e a dona entra em **«À ESPERA DE TAG»** no painel (o Rui taga quando quiser). A IMAGEM
   liga-se **SEM re-desanon** (`_manual_link_ss(deanon=False)`, âncora manual_link — a foto tem
   os stacks FINAIS da anterior e o botão avançado) e vira **testemunha** → o cruzamento corre a
   seguir no mesmo gatilho (coroas em falta = propostas crivadas; contradições → Olho) — **nada
   escreve em silêncio**. Rasto TOTAL: selo origem `regra6s.auto` (manual = `regra6s.move`) +
   marca `auto_moved` por captura. O painel fica: (a) À espera de tag · (b) o que a régua não
   decidiu (sem anterior/anterior-FT) · (6,9)s = listas de veredito intactas. Ensaio pré-ligação
   (dry-run nas 33): 32 moveriam (1 tag+imagem — a icm da GG-6179315485→451 — + 31 só-imagem),
   1 dispensada, 0 indecisas. Endpoints: `POST /table-ss/regra6s/apply` {dry_run} +
   `/{ss}/move-to-prev` (manual).
8. **`#MTT-DESANON-MORTO`** — remoção do código órfão (provado morto), **quando houver espaço** e com o
   diff à vista (remoção em produção merece o Rui fresco, não o fim de um dia longo).

Cada fix declara-se causa-vs-remendo antes (pela `#LEI-FIX-NA-CAUSA`).

## 🔴 DECISÃO DO RUI — voto fantasma do botão (54 mãos anónimas em branco)

*(19 Jul 2026. Só escrita em docs; código e dados intocados. Detalhe:
`journal/2026-07-19.md`; debt: `#DESANON-BUTTON-PHANTOM-VOTE-WHEN-HERO-IS-BUTTON`.)*

**O problema, em claro.** Ao colar os nomes lidos da captura aos lugares da mão, a app tem de
escolher **um de dois sentidos** à volta da mesa. Pergunta a duas testemunhas — o **botão** e
os **stacks**. Se discordarem, desiste e deixa a mão **em branco** (de propósito: em branco é
honesto, com nomes trocados não). **Quando o Rui está no botão, a testemunha "botão" não tem
nada para dizer — mas responde na mesma, e responde sempre a mesma coisa.** Quando os stacks
dizem o contrário, a app julga que há discórdia e desiste sem motivo.

**Escala medida:** 54 mãos travadas por este alarme; **42** são o caso degenerado (Rui no
botão). Caso âncora: **`GG-6183902336`**.

**Plano acordado, por esta ordem:**

1. **(A) — carimbar 1 mão à imagem.** Ver a captura da `GG-6183902336` ao lado da mão e
   confirmar (ou desmentir) o mapa que os stacks propõem:
   `Hero→Lauro Dermio · a8fa35df→FlightRisk · 3010956→R Romanovskyi · 9c404eef→mak10`.
   Escrita por `/set-anon-map` (`verified_by_user`). **A imagem é que arbitra** — os stacks são
   indício forte, não prova.
2. **(B) — só se (A) acertar.** Quando o botão coincide com a âncora, deixar de o contar como
   voto (`btn_dir = None`) e deixar os stacks decidir sozinhos, como já fazem quando não há
   botão. Destranca as 42. **É mudança a uma guarda do core da desanon → não se toca sem ordem
   explícita do Rui.**

**FORA deste saco (não mexer):** as **14** mãos de Hero-noutra-posição (desacordo possivelmente
genuíno) e os **85** `seat_count_mismatch`.

## 👀 Para olho do Rui — saldo do import de 19 Jul

- **3 "Vivo com coroa $0"** — `GG-6180152095` (WillyBlaze) · `GG-6182097413` (Lauro Dermio +
  OneLastRun!). Novas: mãos de 13–14 Jul, os dias que este import trouxe.
- **4 "Nomes em conflito"** novos (1 → 5): 3 `strong_weak_mismatch`, 1 `same_hash` (4 variantes
  de OCR do `fungus_among_us`), 1 `name_2_hash` (`AmigoCrypto` em 2 hashes).
- **2 "Prints fora de tempo"** novos (10 → 12).

## 📌 PROVENIÊNCIA DA LEITURA (Vision) — não medido / a decidir

*(Registado nesta sessão; relógio do sistema reportou 17 Jul 2026. Ordem do Rui: só escrita em docs.)*

### 🟠 Pendente — o `vision_json` não guarda proveniência nenhuma da leitura

- **Facto:** o `vision_json` (das capturas table-SS, `table_ss_processing_log`) **não guarda
  proveniência** da leitura — **sem modelo, sem versão de prompt, sem timestamp da leitura,
  sem tentativas reais de Vision**. (O `attempt_count` da tabela **não** é isso — é um contador
  comum, ex.: 161 capturas partilham `attempt=16`; não indica nada sobre a leitura.)
- **Consequência PROVADA:** não foi possível dizer **com que prompt** a captura **`ssid 202`
  (GG-6132707211)** foi lida — a única anomalia de leitura-ao-meio conhecida. A pergunta
  ficou sem resposta por o dado não existir.
- **Consequência ESTRUTURAL:** sem segunda fonte, **uma leitura é juiz de si própria**. Onde
  **não há Gold**, **nada audita a captura** — o valor lido entra sem contraditório. (A grelha
  dos degraus **não** serve de auditoria: liberta tudo o que é ≥2B e a assinatura < 1B já é
  removida pela guarda do piso — ver o caso encerrado abaixo.)
- **Proposta (para quando for decidido — NÃO é para agora):** toda a leitura futura grava
  `{modelo, versão-do-prompt, timestamp-da-leitura}` no `vision_json` (ou colunas próprias).
  **Sem proveniência, não se audita nada.**
- **NÃO MEDIDO (assim se escreve):** "quantas leituras-ao-meio existem em mãos SEM Gold" —
  **não se sabe**; só se saberia **relendo as imagens**. Não há número; não se inventa um.

### ✅ Caso ENCERRADO — GG-6132707211 (leitura-ao-meio isolada)

- A **Vision leu METADE** em **7 de 7 lugares** da captura (`ssid 202`), casados por nome,
  **sem ninguém eliminado** na mão (logo não é "verde" de KO).
- A **placa foi confirmada pelo Rui**: mostra a coroa **CHEIA** — **$593,75 no astrol0g**
  (a Vision gravara $296,875 = metade). A leitura-ao-meio **não está na imagem**.
- A **coroa Gold gravada está CORRETA** (o `stored` não está contaminado); os cards do olho
  desta mão são **falsos-conflitos** que o Rui arbitra.
- **Anomalia ISOLADA: 1 em 1234** capturas GG com `vision_json` (0 casos parciais/near-miss).
- **Causa desconhecida; NÃO investigada — decisão do Rui** (1 em 1234 não justifica).
- **`#KO-CROWN-INSTANT-FIX` CANCELADO:** a premissa ("a captura mostra a coroa instantânea =
  metade") foi **desmentida pela placa** (mostra a cheia). Fazer a máquina reconciliar o ×2 a
  partir dessa premissa **inflacionaria coroas em silêncio** — escrita automática que não se
  faz. Não reconstruir/re-propor sem prova nova. (Lição de método: sem a imagem, a resposta é
  "não sei", não uma teoria nova — duas explicações anteriores [verde, instantâneo] vinham com
  ar de facto e estavam erradas.)

---


## 📌 FECHO DO DIA 19 Jul 2026 — Etapa 2 dos bounties + selo de nomes (3 fantasmas) + saga do $437.5

*(Relógio do sistema reportou "15 Jul"; segue o fecho de 18 Jul → datado 19 Jul. Ver `JOURNAL_2026-07-19.md`.)*

### 🔴🔴 1ª ENTREGA DE AMANHÃ — A COLHEITA ESTÁ PARADA ATÉ ISTO (nada de novo se constrói antes):

**LISTA COMPLETA dos carimbos do Rui de HOJE, mão a mão, com gravado/não-gravado na BD.** A
resposta ficou **4× por dar** hoje — é a primeira coisa a entregar. Âmbito:
- **bounties recuperáveis** carimbados (Etapa 2, `derived_green_ko`) + qualquer `/set-bounties manual`;
- **quedas** corrigidas/dispensadas (tabela `crown_drop_dismissed` + `bounty_source=manual` recentes);
- os dois casos conhecidos: **$421.87 na GG-6090481210** (corrigido por endpoint, selado `manual` —
  confirmado nos 2 stores) e **$31.25 na GG-6118062432** (o Rui carimbou — CONFIRMAR se gravou);
- para cada: valor carimbado · `bounty_source` · gravado em `all_players_actions` E `player_names`? ·
  link da mão.
- Query pronta: `bounty_source IN ('manual','derived_green_ko')` com `created_at`/uploaded recente,
  cruzado com o `crown_suggestion_cache` e `crown_drop_dismissed`.

### 🔴 RETOMA (depois da lista):
- **PROVA do selo de nomes** (GG-6177132682): o Rui corrige o HJ 1× → forço reconcile + re-link +
  re-deanon → o nome tem de sobreviver. Só então fecha a reincidência.
- **Auditoria de tags** — fechar o tamanho do buraco **só-folder-tag** do pós-wipe (destrinçar
  Gold-lane que nunca tagou vs reimport-flat do `done`). Quadro parcial no journal.
- **$437.5 → $421.87 FECHADO** (misread provado pela imagem; LICÃO "só a placa arbitra o valor").
- Fase 2 Wizard · rodar `~/.pokerapp_db_ro.env` + **a chave HRC `~/.pokerapp_watcher.env`** (ambas
  re-expostas hoje) · worklists (Marcadas · Gold sem tag · FT Sunday Special).

**✅ LIVE hoje:** selo coroas/nomes (`46e5f11`, provado na 6570) · gate >3× extinto (`5dea94a`, +112
mãos) · Etapa 2 (`4768e9b`) · worklist quedas + Sugerir-todos + cache + lightbox universal + input
vazio + Dispensar + migração de unidade (`fce4af1`→`5ce23e0`) · 3 fantasmas de nomes curados
(`8cb9fe4`) · LICÃO da imagem (`3029241`). Suite 1482 passed.

---

## 📌 FECHO DO DIA 18 Jul 2026 — régua do resto-em-BB provada + detetor re-medido + forense da 6570 FECHADA

*(Relógio do sistema reportou "14 Jul"; segue o fecho de 17 Jul → datado 18 Jul. Ver `JOURNAL_2026-07-18.md`.)*

**✅ LIVE hoje:** régua do **resto-em-BB** provada (3/3 nas imagens do Rui — sobreviventes têm
placa própria; corrige a confirmação anterior do #1) · **detetor re-medido** (488 varridas →
**33 busts reais** / **10 coroas mal-lidas** / 18 falha real / 11 over-read) · fix do detetor
(`161c7a3`: split resto-em-BB + **contraprova da mão-seguinte** que apanhou o 1042 + balde
"re-ler placa") · fix dos cards (`ba74e25`: linkam à **página normal** `/hand/<id>`, não à
Wizard) · **forense da 6570 (GG-6104058222) FECHADA** (culpado = re-apply do table-SS re-cola a
leitura guardada; raiz = **coroas sem proveniência por-seat**). **Etapa 2 continua BLOQUEADA.**

**🔴 RETOMA — por ordem:**

- **a) DECISÃO DO RUI — cura do carimbo A/B** (recomendação Web: **A** — `bounty_source='manual'`
  por-seat; todo o re-apply salta seats com `bounty_source ∈ {manual, green_ko}`. B = `crowns_locked`
  à mão, mais grosso). **Tem de aterrar antes de qualquer escrita nova.**
- **b) OLHO DO RUI nos 3 do balde 1** (todos `confirmed_gone` pela contraprova):
  [GG-6132507189](https://comfortable-hope-production-a87a.up.railway.app/hand/2564) Ward E (SB)→Lauro (BTN·HERO) ·
  [GG-6138747688](https://comfortable-hope-production-a87a.up.railway.app/hand/613) mahanluvalla (UTG)→MaLong07 (SB) ·
  [GG-6101401982](https://comfortable-hope-production-a87a.up.railway.app/hand/7530) betosalada (BTN)→Lauro (BB·HERO).
- **c) Com (a)+(b): construir a CURA PRIMEIRO → só depois Etapa 2** (estreia: **AVRELIY $265.62 ·
  Phil $375** na 2480) → o Rui corrige a 6570 uma **5ª e última vez**, já protegida.
- **d) Restante:** Fase 2 Wizard (veredicto + HH viewer + contexto do torneio) · rodar o
  `~/.pokerapp_db_ro.env` · over-reads (**5 duros + 11 do detetor**) · worklists (Marcadas ~313 ·
  Gold sem tag ~303 · FT do Sunday Special).

---

## 📌 FECHO DO DIA 17 Jul 2026 — coroas (censos=0, régua, verde-KO) + cura no core + detetor de bounties recuperáveis

*(Relógio do sistema reportou "14 Jul", mas segue o fecho de 16 Jul → datado 17 Jul. Ver `JOURNAL_2026-07-17.md`.)*

**✅ LIVE hoje:** cura no core do reconcile (varredor independente + re-Vision; **27/27** no 1º
sweep) · amostrador de coroas (modo "Ver candidatas" + Cancelar + banner de limitação; âmbito
177→155) · censos pré-pt95 = **0** (×2, wipe saldou) · régua do delta corrigida (**150/155** delta
0; era a chave `_meta`) · detetor de bounties recuperáveis (núcleo 4/4 + 488 varridas: **40 mãos/48
seats G1 · 19 G2 · 11 over-read**) + **painel "Bounties recuperáveis" Etapa 1 (só-leitura)** + fix
do matador sem nome (0/40). **Regra permanente:** todo o lote tem Cancelar.

**🔴 RETOMA AMANHÃ — por ordem:**

- **a) REENVIAR os 6 casos de validação COM LINKS** (violei `feedback_hand_refs_by_link` — o #6
  saiu com link partido; sem links não há validação). Lista corrigida (`<frontend>/hrc-results/hand/<id>`):
  1. [/hand/2491](https://comfortable-hope-production-a87a.up.railway.app/hrc-results/hand/2491) BH HR $525 — bustou **M Dziubdzie.. (SB)** → matador **Fergiac (UTG)**.
  2. [/hand/8920](https://comfortable-hope-production-a87a.up.railway.app/hrc-results/hand/8920) Speed Racer $10 — bustou **bigscam (BTN)** → **Lauro Dermio (SB) · HERO**.
  3. [/hand/1160](https://comfortable-hope-production-a87a.up.railway.app/hrc-results/hand/1160) Speed Racer $32 — bustou **PUGLIFE (BTN)** → **Tiziano991 (CO) + Lauro (SB) HERO** (multi-vencedor).
  4. [/hand/1041](https://comfortable-hope-production-a87a.up.railway.app/hrc-results/hand/1041) BH HR $525 — bustou **Pokermen777 (UTG) + Golden Goos.. (MP)** → matador **Joao Da Sil.. (BB)**.
  5. [/hand/3005](https://comfortable-hope-production-a87a.up.railway.app/hrc-results/hand/3005) Speed Racer $10 — bustou **jinx36 (CO)** → matador **Im88erAufOwn (BB)**.
  6. [/hand/27503](https://comfortable-hope-production-a87a.up.railway.app/hrc-results/hand/27503) (GG-6177132682, o caso podre) — matador **Lauro Dermio (MP1) · HERO** (era o "—", agora nomeado).
- **b) Após validação dos 6 → Etapa 2 (fluxo A+B, escrita só por carimbo):** abre imagem → botão
  "sugerir" (Vision só ao verde) → escreve com `bounty_source='derived_green_ko'` + correção da
  dourada do matador. **Estreia com os 2 carimbos da 2480:** AVRELIY dourada **$265.62** · Phil
  bounty **$375** (`derived_green_ko`, o 1º carimbo). *A escrita NÃO liga até os 6 estarem sãos.*
- **c) Over-reads à parte:** 5 duros da re-auditoria + 11 do detetor → revisão separada (não entram
  no grupo-1 automático).
- **d) Fase 2 Wizard:** veredicto do Rui (validar a página) + **HH viewer** (formato HM3/Winamax) +
  **contexto do torneio** no cabeçalho (fase/prémios/top pago). Construção após validação.
- **e) Env RO:** rodar o `~/.pokerapp_db_ro.env` — do lado do Rui (Railway).
- **f) Worklists do Rui:** Marcadas ~313 · Gold sem tag ~303 · **Golds por ler = 0** (fecharam) ·
  FT do Sunday Special (carimbo).

---

## 📌 FECHO DO DIA 16 Jul 2026 — ✅ VALE v3 + arranque Resultados HRC

**✅ VALE DO RUI — LEI v3 VERIFICADA EM PRODUÇÃO.** Relatório tree-a-tree sobre 13 mãos reais
resolvidas pelo robot: **187 nós, 0 violações**, todos os cenários provados (KO 9.0 · 4-bet 10.3 ·
squeeze 9.0 · BB-vs-limp 3.0+ALLIN · SBvsBB open+3bet+4bet · colapso · call garantido no
sobre-allin). A lei `2026-07-15-sizings-v3` **rege tudo o que o robot resolver a partir de agora**.
Ver `JOURNAL_2026-07-16.md` + `LEI_SIZINGS_2026-07-15-v3.md` (estado ✅). Etiqueta=conteúdo
confirmado por timeline de deploy (LICAO 16 Jul).

**🟢 EM CURSO — Secção RESULTADOS HRC (por FASES; o Rui valida cada página no ar):**
- **Fase 1 (landing) — NO AR + VALIDADA.** 3 cartões + lista colapsável por instância. Ajustes
  do Rui aplicados: Cartão 3 `nome · dd/mm · #tn`; linhas `Data·Hora·Tree·Nº·Left·Hero·Stack·1ª ação`;
  **WN = final do ID**. Tudo SQL, sem abrir zips.
- **Fase 1b (Cartão 2 "Top EV perdido") — NO AR + VALIDADA.** Motor `hrc_ev` (% equity ICM,
  casamento por VALOR); cache + `POST …/ev-loss/compute` incremental. **Ajuste (feito): mãos
  CLICÁVEIS na landing** (Top 5 + linhas → `openHand`; hoje `/hand/:id`, re-aponta ao Wizard).
- **Fase 2 (página da mão Wizard) — AUTORIZADA, EM CURSO.** Backend pronto (`hrc_hand.node_detail`
  grelha 13×13 + endpoints `…/hand/{id}` e `…/node/{ni}`); `HRCHandPage.jsx` escrito. **FALTA:
  ligar a rota `/hrc-results/hand/:id` + re-apontar `openHand`** (1º passo da retoma). Coroas $ na
  barra diferidas (fonte $ = `all_players_actions`, não o zip). EV = % equity ICM; árvore por API.

**🔵 FEATURE FUTURA — `#VILLAIN-AUTO-NOTES-NO-SHOWDOWN` (ditada 16 Jul; BACKLOG, NÃO implementar; desenho a ditar pelo Rui antes de construir):**
Vilões — **notas automáticas de tendência por jogador, SEM depender de showdown**.
- **Princípio do Rui:** a **ação em contexto já é informação** (não fazem falta as cartas). Ex.: **CO 30bb faz all-in de 3-bet sobre open do HJ 40bb pós-late-reg** = pouco ortodoxo / duvidoso / possível *spew* → nota de tendência.
- **Motor:** avaliar **cada ação observada** do vilão contra o **espectro razoável do spot** (stacks, posições, fase do torneio, PKO); usar as **trees HRC como árbitro** quando existir spot equivalente (**ação com freq ~0% na solução = fora do mapa**).
- **Fontes:** HH (ações, com OU sem showdown) · trees HRC · stats HM3 · **notas do Rui como semente**.
- **Em aberto (decisão do Rui):** regras vs IA vs híbrido · apresentação na ficha do vilão · gatilho (quando/como se dispara).

**🔵 FEATURE FUTURA — `#HRC-PARTILHA` (ditada 16 Jul; BACKLOG):** partilha da secção HRC —
**logins / owner / fila** (vários utilizadores; dono da mão/torneio; fila partilhada). Desenho a
ditar pelo Rui.

**🔵 FEATURE FUTURA — `#WATCHER-SAVE-HRCZ` (ditada 16 Jul; BACKLOG):** botão "Abrir no HRC" com
**save nativo `.hrcz`** (opção (a) das 3 do 14 Jul). **Teste do Rui — mecânica CONFIRMADA no PC:**
os diálogos são **Save Resource → Guardar como / Save As** (conforme locale); o **`.hrcz` do
formato do robot ≈ 67 MB** (vs **3-7 GB** das sims manuais); a escrita **pode levar minutos** em
trees gordas. **FALTA:** prova de **reabertura** do `.hrcz` + **spike no Beelink** (correr no
robot). Só depois se decide (a) save nativo vs (c) importar o Complete Export.

**Pós-VALE / dívidas que continuam:**
- **Fase 2 (retoma):** ligar rota + re-apontar `openHand` → validar a página da mão à vista.
- **Falhas restantes do 2º run (lobbys 500) + Saúde vs baseline — POR REPORTAR/fechar.** Parcial
  feito (16 Jul): Golds por ler 0→**55** (12-13/07, Vision background não os leu) · SS sem match
  0→**27** (12/07) · Gold sem tag 303→316 · órfãs 1→1 · quarentena nomes 6 · lobbys 2º run sem 500
  no DB (transitório). **Falta:** destrinçar os 27 SS sem match · correr coroas (`/crowns`) ·
  Marcadas (sem métrica no código) · consumir resíduo `it=12`+`gg_hh=1`.
- **Epoch durável + botão "Reenviar ao HRC"** (dorme): `hrc_queue_release` é apagada por
  `set-aside`/`clear-released`/`reset-done` → o epoch perde o high-water-mark e o adapter salta em
  silêncio. Fix = epoch na linha da mão (`hands`). Não bloqueia as 15 (frescas).
- **Censo das coroas pré-pt95 plausíveis** (resposta em dívida).
- Caixa de pesquisa por nº no painel HRC · limpeza dos helpers Python mortos (CASO A/B etc).
- **2 Golds de 13 Jul sem assentar** (+ 1 TS) · worklists de triagem.
- **⚠️ Rodar o `~/.pokerapp_db_ro.env`** (URL read-only re-exposto no output).

## 📌 FECHO DO DIA 15 Jul 2026 — LEI DE SIZINGS v3 + smoke ao robot

**★ LEI v3 implementada e LIVE (Fases 0-4), smoke lançado.** Ver `docs/JOURNAL_2026-07-15.md`
+ `docs/LEI_SIZINGS_2026-07-15-v3.md`. Backend v3 **confirmado ATIVO** (root
`sizing_rules=2026-07-15-sizings-v3`). O Beelink resolve as 5 mãos do smoke **durante a noite**.

**🔴 AMANHÃ (crítico — o "VALE" da lei depende disto):**
- **Relatório tree-a-tree das 4** que correram a noite (sizings reais por nó): **colapso
  (GG-6162937781) · 3-bet KO (GG-6164941286) · 4-bet (WN-…-231) · squeeze (WN-…-185)** →
  **o Rui dá o "VALE"** à lei v3. Fila fechada até lá.
- **★ Ajuste do smoke (decisão Rui, noite 15 Jul):** a **open-allin `GG-6139199035`** (árvore
  gorda, raiz UTG deep, ~9h) foi **CANCELADA** no HRC — mas o Rui **validou o script dela
  VISUALMENTE** (nó de open com **`[2bb, ALLIN]` correto → v3 sã**). O cenário open-allin fica
  com essa validação visual; **decide-se depois de ver as 4** se precisa de solve próprio (a
  âncora/export prova-se nas outras 4).
- Links (por link, regra permanente): `<frontend>/api/queue/hrc/hand/<id>`.

**Em curso (paralelo ao smoke):**
- **Caixa de pesquisa por nº de mão no painel HRC** (370 linhas sem busca não se usa).
- **Limpeza dos helpers Python mortos** (CASO A/B, `_compute_default_*`, `_array_for_*`,
  `_bucket_*` — inertes; ~40 testes espalhados). Passagem dedicada.

**🔴 Resposta em dívida:**
- **Censo das coroas pré-pt95 plausíveis** — quantas leituras de coroa antigas podem estar
  silenciosamente erradas sem cair na quarentena (caso `/hand/6570`, chamas curadas por re-leitura).

**Após o VALE:**
- **Implementação da secção Resultados HRC** (protótipo validado 14 Jul; ver fecho abaixo).

**Dívidas antigas que continuam:**
- 2 Golds + 1 TS de 13 Jul sem assentar (dedup/falha silenciosa/path).
- Saves `.hrcz` / testar se o HRC importa o Complete Export (o Rui ainda não testou — opção (c)).
- Worklists: 137 Golds por ler · Marcadas 431 · Gold sem tag ~315 · caso `Andre Figue..`.

**⚠️ Rodar o `~/.pokerapp_db_ro.env`** (URL read-only exposto num comando por engano do Code).

## 📌 FECHO INTERCALAR 14 Jul 2026 — Resultados HRC (em curso)

**★ Implementação da secção "Resultados HRC" EM CURSO.** Caderno de encargos ditado pelo Rui
(estilo GTO Wizard; paleta fold-azul/call-verde/raise-amarelo/**3bet-vermelho**/**allin-laranja**;
página principal 3 cartões + painel colapsável **por instância de torneio**; página da mão com
barra de posições clicável + stacks reais + **coroas $ por cima** (PKO), grelha 13×13, navegação
da árvore, **abre neutra**, **EV perdido discreto em % de equity ICM** — não $; botão HRC amarelo
nas listas). **Protótipo validado à primeira** (`_local_only/proto_hrc_resultados/`, dados reais,
não commitado). Detalhe: `docs/JOURNAL_2026-07-14.md`. **Falta: implementar na app.**

**Decisões de arquitetura já registadas:** árvore **servida por API** por-clique (zip ~32 MB/mão;
`build_verify_tree` já lazy); "% left" do Cartão 1 = **slot** (ligar a `players_left`); EV = **%
equity de torneio (ICM)**, comparável entre torneios (recomendado — confirmar).

**🔴 Respostas em dívida:**
- **(a) SB sem all-in / §19 BvB ≤30 — RESPONDIDA, falta DECISÃO do Rui.** §19 **está** no caminho
  da SB (unificada, não é fresta); sem jam porque mede pela stack **INDIVIDUAL** (37.8bb>30), não
  a efetiva (24bb). Decisão: **(A)** deixar como está · **(B)** em BvB (heads-up, sem risco pt29)
  medir por efetiva `min(SB,BB)` — obriga template + `hrc_node_offset.count_lines_for_position` em
  **lockstep** + smoke. Ver `JOURNAL_2026-07-14` + `REGRAS_NEGOCIO §19`.
- **(b) saves `.hrcz` no Beelink (botão "Abrir no HRC")** — hoje **não existem** (só Complete
  Export = dados, não reabrível). Opções (a) save nativo / (b) re-solve / **(c) testar se o HRC
  importa o Complete Export** (recomendado, só o Rui testa).
- **(c) 2 Golds + 1 TS de 13 Jul sem assentar** — herdado do fecho 13 Jul (abaixo); investigar
  (dedup / falha silenciosa / path).

**Worklists de triagem do Rui (continuam):** "Ler todas" das Golds por ler (**137**) · Marcadas
(**431**) · Gold sem tag (**~315**) · caso **`Andre Figue..`** (nome truncado nas 2 variantes →
melhoria de UI "nome manual / fundir variantes truncadas").

## 📌 FECHO DO DIA 13 Jul 2026 — pendentes ativos

**⛔ REGRA DO RUI (permanente):** SEM imports/processamentos massivos até a app estar 100%.
Afinação primeiro; volume (reimport, robot em lotes) só com **ordem explícita**. Ver memória
`feedback_no_mass_processing_until_100`.

**🔴 POR EXPLICAR (resposta em dívida):**
- **2 Golds + 1 TS enviados hoje sem assentar** — foram enviados mas não aterraram na BD (o
  audit da leva viu golds 16/18 e TS 0/1). Investigar porquê (dedup? falha silenciosa? path).

**Triagem/decisões do Rui (worklists e casos abertos):**
- **Caso `Andre Figue..`** — nome truncado nas DUAS variantes → o stack confirma o lugar mas não
  escolhe a grafia. **Melhoria de UI pedida:** opção "nome manual / fundir variantes truncadas"
  no painel Nomes em conflito (o "confirmar o forte" não serve quando ambas estão cortadas).
- **"Ler todas" das Golds por ler (137)** — clique do Rui (a via existe: painel "Golds por ler").
- **Marcadas 431 + Gold sem tag ~315** — worklists de triagem manual (CSVs em `_local_only`).
- **Nomes em conflito** — R Romanovsky ✓ · Gooddecision91 ✓ · SuchAGooodBoy [confirmar] carimbados.

**Consolidado de produto (backlog de UX/limpeza):**
- Apagar-imagem nas órfãs · rótulo "Remover da mão" · botão não-FT + as **2 mãos de 11/06
  marcadas não-FT** · duplicados físicos · regra "endpoint nos relatórios" (operações de prod
  via servidor). 

**Fila HRC:** FECHADA (anti-massivo) com **3 elegíveis de hoje em espera** (GG-6170862643 PKO ·
GG-6171629160 + GG-6171849992 Vanilla) — libertação manual do Rui (sizing `2026-07-11-3bet-v2`).

---

## 📌 FECHO DO DIA 12 Jul 2026 — pendentes ativos

**⛔ REGRA DO RUI (permanente):** SEM imports/processamentos massivos até a app estar 100%.
Afinação primeiro; volume (reimport, robot em lotes) só com **ordem explícita**. O robot HRC fica
**em espera por esta regra** (a largada técnica está destrancada, mas o gatilho é do Rui). Ver
`REGISTO_CONCEITO 2026-07-12` + memória `feedback_no_mass_processing_until_100`.

**Bloco COROAS — fechado; sobram só carimbos à vista (por desenho, decisão do Rui):**
- **9 cliques "Valor alto"** — confirmar as 9 mãos > 3×base que divergiram no auto-carimbo (sobretudo
  O Sander $819≈$813, wobble de OCR; lado a lado no painel). 1 clique cada.
- **11 seats "por rever"** — placa tapada em TODAS as testemunhas (Hero com cartas/all-in por cima);
  **aguardam um print futuro** com a placa visível. Ficam fora do export (base÷2 trava-as).

**Verificação visual Saúde Import (painel a painel) — em curso:**
- ✓ Edições · ✓ Coroas · ✓ Suspeitas (7→0) · ✓ **Hero-alheio (3→0)** · ✓ **Marcadas (432)**.
- **✓ Marcadas (432) — RESPONDIDO (12 Jul):** todas `folder_tag=NULL` (nenhuma de subpasta
  etiquetada) → **0 falhas de propagação**; vieram da RAIZ do `it\` (não ordenadas). Cruzado
  em 3 ângulos (BD + via import + disco: 427/432 na raiz do `done\it`, 0 em subpasta). 302/432
  em 15 torneios que já têm tags tuas (referência p/ arrumar). CSVs em `_local_only\`
  (`marcadas_432_por_torneio.csv` + `_detalhe.csv`). Triagem manual fica contigo (a 1 clique).
- **✓ Hero-alheio (3→0, 12 Jul):** ângulo cego do veneno "nome num vilão" (o teu nome ESTÁ
  AUSENTE, não num vilão). Scan novo `pn.hero ∉ HERO_NAMES_ALL` → exatamente 3 em toda a BD,
  todas **pré-guarda** (11 Jul 17:31; veneno antigo, guarda sem furo). 212/734 = cosméticas
  (apa já tinha Lauro; só o rótulo dessincronizou → set-anon-map); 515 = veneno real (print
  pós-bust sem o Rui → revert-to-anon). LIVE `f8ce806`: Guarda 4 da âncora
  (#DESANON-ANCHOR-REQUIRES-HERO-IN-IMAGE) + veneno 3 no painel Mãos suspeitas + endpoint
  `revert-to-anon`.
- **Conflitos 1 + 11 + 3** — por ver (**próximo**).
- **Timeline** por validar + **estética das cartas** por afinar.
- **Amostragem final** do conjunto.

**Sizing (em aberto):** **sobre-jam** por ditar (regra do Rui).

---

## 🟢 REGRA DE LARGADA DESTRANCADA — robot livre para lotes grandes (11 Jul 2026)

**O último bloqueio à largada de lotes grandes ao robot HRC caiu.** A contaminação de edição
`294738291` (payout de edição errada, escrito por um lobby que pertencia à `294711510` — prova dura
`entrants 305 > campo 219 impossível`) foi **fechada por repoint**: `POST /api/gg-health/lobby-edition-repoint`
(`payout_tn 294738291 → correct_tn 294711510`, dry-run→OK do Rui→escrita) apagou o payout envenenado
(1 row) e reapontou o log do escritor; a `294711510` mantém o payout correto dela. **`lobby-edition-scan`
= edition_contamination 0** (146 clean, 0 suspect). Sem payout de edição errada a alimentar o ICM →
**o robot pode processar lotes grandes sem risco de premiar com prémios da edição errada.** (Repoint =
mecanismo geral p/ contaminações JÁ escritas — a quarentena só trata prints novos.)

## 🔎 Lote da auditoria visual (10 Jul) — 23 achados, por prioridade

**A e C fechados** (diagnóstico + A1 fix + C decidido). Restantes na fila pela ordem do lote.

- **✅ A1 (`#DEDUP-DROPS-FOLDER-TAG`) — LIVE + ACEITE (10 Jul).** Dedup do table-SS deitava fora a
  folder_tag de um re-envio. Cura `_reapply_folder_tag_on_dedup` (Opção A). **Aceite:** o Rui
  re-correu o import de `it\SpeedRacer\` (`ImportaSpeedRacerAoVivo.bat`) → as 3 mãos
  (GG-6138218252/6138218069/6137938737) ficaram `discord_tags=['speed-racer']` (mm=table_ss) + a row
  da captura com `folder_tag=speed-racer`; grupo speed-racer no Estudo **6→9** (torneio 295211698,
  02/07). Confirmado read-only na BD. Fechado.
- **A2/A3/A4 — não-bug** (desanon recusa nomes incertos; contas batem; regra C estrita). Sem acção.
- **✅ C (IRE) — decidido, sem cura.** IRE = métrica de estudo KO; 'nota' fora por desenho
  (REGISTO_CONCEITO 10 Jul). Não reabrir.
- **✅ B (core) — FECHADO (só documentação, 10 Jul).** Quadro de definições do verde/coroa escrito
  (REGISTO_CONCEITO 10 Jul, âncora Deepstack Turbo $88 / bounty $40 / instant 0.5). Verificado
  consumidor a consumidor (IRE ÷bib×0.5, queue_export/HRC ×2, scan/backfill vs base÷2, verde-KO,
  hover) — **todos tratam a coroa como INSTANTÂNEO, nenhum como total → SEM fator-de-2 latente**.
  Nota latente menor: `0.5` duplicado (`ire.py:77` + `queue_export.py:845`) — fonte única resolveria;
  sem acção.
- **✅ D — Raiz 1 CURADA (LIVE).** Zombie FT: o painel reacordava a dispensa com o print Info
  PRÉ-EXISTENTE. Regra ÚNICA `has_new_ft_signal(tn, decided_at)` (refresh + painel): só reacorda com
  sinal POSTERIOR à dispensa (Info `posted_at>decided_at`) ou tag -ft manual. +5 testes.
- **✅ D — Raiz 2 CONSTRUÍDA + LIVE (11 Jul, opção A + ressalva do Rui).** Resolver de lobbys deixa
  de escolher a edição "mais próxima às cegas". Provas DURAS (`tournament_resolver._disambiguate_editions`,
  GG-only, só lobby prestart): **H1** nome-exacto (mata "…Europe…") · **H2** impossibilidade
  (`entrants` do print > campo final da edição → exclui; UNIDIRECIONAL — `entrants` < campo é NORMAL,
  nunca prova) · **H3** não-arrancada-com-eliminações (`players_left < entrants` numa edição que ainda
  não começou → exclui) · **H4** janela de mãos (`[1ª mão−45min, última mão+120min]`, âncora
  **UTC→Lisboa**). 2+ sobrevivem sem containment estrito → **quarentena** (`result='edition_quarantine'`,
  não cola). **Crivo** `GET /api/gg-health/lobby-edition-scan` (irmão do eliminated-crown-scan, gate
  duro) + **painel de quarentena** `LobbyEditionPanel` (Saúde GG) + decisão manual
  `POST /lobby-edition-resolve`. **Simulação com código real:** 85 GG → 78 certos · 5 corrigidos
  (2 zombie→295219051 + 3 BH$88 provados por `entrants`) · 2 quarentena; 29 WN intactos (fora de
  âmbito — decisão Rui); **0 regressões**. **Crivo hoje = 1 CONTAMINAÇÃO real:** tn **294738291**
  (BH Deepstack $88) tem payout escrito por lobby da edição **294711510** (`entrants` 287/305 > campo
  219) — **NÃO consumido por nenhum solve do lote** (o BH do lote era o $32 294698433) → morre no
  reimporte. Os **3 mal-colados** (297032961/297027787/295258986) = payout LIMPO (escritores re-resolvem
  a si próprios); **id=19 (297032961) = LIMPO** (payout de 315da0e6, entrants 347 coerente).
- **FILA (por atacar, pela ordem):** ~~Raiz 2~~ (✅ 11 Jul) → **E** → **F** → **G-K** → cosmética → `#HRC-ANCHOR-IN-SENT`.
  - **E:** falso positivo no scan "coroa impossível" — excecionar `bounty_source='green_ko'` (régua
    ≥base÷2 é para VIVOS). Barato.
  - **F (verificação):** âmbito do bust no reentry_hint varre as SEATED todas (não só tagadas)?
  - **G-K:** vistas (rótulos/contas): G Dashboard "SS TOTAL"=127; H HM3 (janela/tag); I Torneios
    238 vs 230; J HRC 187 vs 172; K SS Mesa "tent."=3 sempre.
  - **Cosmética:** fusão das tags na triagem; "IMAGENS ANEXADAS(0) vs DA MÃO(6)"; echos da
    TidyDoneIT_Aplicar.bat (já limpos 10 Jul); grafias antigas nos filtros GTO.
- **`#HRC-ANCHOR-IN-SENT` (UX, queued DEPOIS de B-K — via já decidida).** Expor no painel
  "Enviadas ao HRC" a POSIÇÃO onde a 2ª run ancorou (Selected Subtree) + auto-validação. **Via
  (Opção B, backend, NÃO tocar watcher):** é o **C6 do `hrc_verify`** (já previsto no comentário
  do módulo: "target_node_offset vs spot do Hero — v2"). Esperada = `first_vpip_position` (já
  existe, LEI B); real = derivada do `result_zip` (reconstruir a Strategy Table via `parse_hrc_zip`,
  método pt92, + `target_node_offset`). Comparar → ✓/⚠ no passo "Verificar resolvidas" (badge, sem
  botão novo); não verificável → ⚠ honesto. Recusada a Opção A (watcher grava no manifest) por
  exigir rebuild+reinstalação no Beelink (regra "1 exe", frágil). Não cruza de graça com D/G-K.
- **🚨 REGRA DE LARGADA:** **lote GRANDE do robot SÓ com o CRIVO da Raiz 2 no ar** (senão payouts na
  edição errada envenenam o ICM em silêncio). ✅ **Crivo no ar (11 Jul)** — reporta **1 contaminação
  (tn 294738291)** → o gate FALHA.
  - **DECISÃO do Rui (11 Jul):** a contaminação do **294738291** (BH Deepstack $88, payout da edição
    irmã 294711510) **NÃO se resolve à mão — morre no reimporte da Etapa 2.** Consequência **aceite**:
    o gate `lobby-edition-scan` fica a **1** e o robot fica **travado para lotes GRANDES até à Etapa 2**;
    **mãos avulsas podem correr**. O lote da noite (10 Jul) NÃO a consumiu (não tocou 294738291) → limpo.
  - **GUIÃO DE ACEITAÇÃO da Etapa 2 (acrescentar):** os **4 gates a 0 pós-reimporte** — os **3 das
    coroas** (eliminated-crown-scan `vision_origin_contamination`; guarda vivo-$0; guarda vanilla) **+
    o das edições** (`lobby-edition-scan` `edition_contamination`). E o **294738291 nascer colado à
    edição CERTA** é o **caso de aceitação do resolver novo** (a Raiz 2 a funcionar de raiz no reimporte).
- **Pendentes do Rui:** 2 lobbys de 2 Jul por capturar (Deepstack Turbo $88, Hyper Special $108) p/
  desbloquear 4 mãos tagadas no HRC; 3 coroas do lápis (#24, speed-racer "IRE bounty ilegível").
- **Vigiar:** cancelada **GG-6138896036** re-enfileirada (2ª vida) — confirmar no próximo run do robot.
- **✅ 1ª prova real TS-depois-das-mãos (10 Jul):** os 3 TS atrasados de 9 Jul ENTRARAM (295428546/
  295428550/297033978, todos PKO) → reconcile religou os 22 lobbys de dia 9 (payout de 295428550
  escrito via `reconcile_lobby_vision`); reclassificação de formato = no-op (nomes já PKO). Gatilho
  TS-tardio validado em produção.
- **Registar (sem acção):** quarentena de nomes a ZERO (FabiSt7 re-entrada); Daily Hyper $80
  dispensado; espécime #23 WN-4832780523824742404-104 (fallback_root, guardar p/ os fallbacks);
  **#24 (informativo):** 3 das 9 speed-racer mostram "IRE — bounty ilegível" (coroas por rever,
  honestas) — comportamento correcto; o Rui preenche pelo lápis quando quiser. Sem código.


## ✅ Cura verde-KO das coroas de ELIMINADOS — LIVE + PROVADA em prod (9 Jul)

**Frente FECHADA (LIVE, `main`→`26db552`; ligação `13c6177`).** Anatomia: `JOURNAL_2026-07-09.md`,
`REGISTO_CONCEITO 2026-07-09`. Defeito: um jogador eliminado num KO deixa de ter coroa própria e a
leitura colava-lhe a coroa do seat **vizinho** (GG-6140169166: Hero levou $170.63 do KamikazzE97).
Cura: guarda **HH-determinística** (all-in e perdeu) num **funil único** `services/eliminated_bounty.py`
(`scrub_eliminated_bounties`/`scrub_and_persist`), **só-tagadas** (APA §B.6), ligada a 5 sítios (2
famílias, cobertura transitiva por `_apply_folder_tag_to_hand`), idempotente (preserva `green_ko`),
fail-safe raw, log-alto. Eliminado → **verde-derivado** (`green_ko`, o instantâneo; ×2 = total,
`#KO-CROWN-INSTANT-FIX`) OU **NULL+"por rever"**, NUNCA a coroa do vizinho.

- **PROVADO nos dados atuais:** crivo (`GET /api/gg-health/eliminated-crown-scan`, só-tagadas)
  `vision_origin_contamination` **29 → 0** (gate DURO: >0 = PARAR+investigar). Mão-troféu
  GG-6140169166 = **$204.54** (verde $102.27 ×2), GG-6139653123 = $20; nunca $170.63.
- **ACEITAÇÃO REAL = REIMPORTE:** as tagadas nascem verde-derivadas (ingest com Vision fresca) ou
  "por rever", nunca a coroa do vizinho. Os 36+2 seats de agora são demonstração (o reimporte apaga).
- **GATE DURO permanente:** após o reimporte E após qualquer ingest GG, correr o scan; `>0` =
  PARAR + investigar + corrigir, nunca "dado por curado".
- **Deferido (nice-to-have):** onde o scrub sabe os bustados mas a escrita falha, tentar o NULL
  fail-safe desses seats (hoje: log-alto + o crivo apanha).

## ✅ Guarda VIVO-$0 (coroa visível lida $0 num jogador VIVO) — LIVE (9 Jul)

**Decisão do Rui (verificada; GG-6132925926 = evidência + caso de aceitação, NÃO dado a
consertar).** Reenquadra o antigo `#CROWN-VISIBLE-READ-ZERO`: **não é oclusão** (o Rui confirmou
coroas bem visíveis) — é a Vision a falhar coroas à vista, raramente, no **VIVO** (o eliminado é a
verde-KO). Resíduo pós-cura+prompt+reread minúsculo (1 mão real: Hero da GG-6132925926, $0 devia
ser $100 — ele tinha 2 KOs → instantâneo $100).

- **Convenção confirmada:** a coroa de um VIVO = **INSTANTÂNEO** (metade do total, PKO 50/50). Hero
  com KOs acumulados tem coroa **> base÷2** — é LEGÍTIMO (o scan não aperta nesse sentido).
- **Guarda (core, ingest):** KO (buy_in_bounty do TS > 0) + VIVO (pela HH) + coroa $0 → **NUNCA
  gravar o $0** → NULL + `bounty_review='live_crown_read_zero'`. **NUNCA derivar da base** (o vivo
  pode ter KOs → subvaloriza; inventar é veneno). Só-tagadas. No mesmo funil `eliminated_bounty.py`
  (`resolve_seat_bounty`/`scrub_eliminated_bounties`/`scrub_and_persist` com `bounty_base` do TS) →
  cobre os 5 escritores por transitividade.
- **Gate DURO:** `GET /api/gg-health/live-crown-zero-scan` → `silent_zero_contamination` (coroa $0
  sem review) tem de ser **0** pós-reimporte / pós-ingest GG.
- **Lápis do Hero:** `{!isHero}` levantado no `CrownCell` (`HandHistoryViewer.jsx`) — o Hero edita/
  confirma a própria coroa como qualquer vilão (capacidade permanente).
- **ACEITAÇÃO = REIMPORTE:** GG-6132925926 nasce com o Hero NULL+"por rever", nunca $0 gravado.

## 📋 `docs/MAPA_AUDITORIA_VISUAL.md` — instrumento de validação visual pós-wipe (10 Jul)

Mapa por secção do sidebar (o QUE É / o QUE VÊS / número esperado datado / AÇÕES / SINAIS DE
ALARME / relação com o reimporte) + **roteiro de auditoria** no topo. Construído do frontend real
+ números reais de prod. **É também o guião de aceitação do wipe:** percorrer o roteiro e confirmar
que tudo nasce são — com destaque nos **3 gates das coroas a 0** e **nenhuma GG anónima no Estudo**.
Números datados de **10 Jul 2026** (pós-wipe/meio-de-reimporte); actualizar após cada grande import.

## ✅ Guarda VANILLA (coroa espúria em torneio SEM bounty) — LIVE (9 Jul)

**`#SPURIOUS-CROWN-NON-KO` — APROVADO pelo Rui + implementado.** Facet INVERSA (GG-6138905902 Daily
Hyper $60: Ale Mantovani $50 + Heiaheisen $20 **inventados** pela Vision num vanilla).
- **RAIZ (diagnóstico na fonte):** `table_ss_deanon._seats_to_vision_data:76-78` copia `bounty_usd`
  da Vision do table-SS para `bounty_value_usd` de **cada** seat **sem gate** de "o torneio tem
  bounty?". O prompt do table-SS (`table_ss_vision.py`) é cuidadoso (`null` se não houver coroa),
  mas a Vision **alucinou** $50/$20 num vanilla e o writer copiou-os. O **formato NÃO é circular**
  aqui: o TS diz `format='None'` (vanilla) e a HH (`gg_hands.py:369`) classifica por NOME → vanilla.
- **Guarda (core, mesmo funil):** torneio **GG + TS presente + buy_in_bounty nulo/0** (`has_ts_no_bounty`)
  → um vivo NÃO pode ter coroa → **coroa FORÇADA a NULL** em `resolve_seat_bounty`/`scrub_*`/
  `scrub_and_persist`. Sem TS = passthrough (não se decide às cegas). Prova read-only na mão real:
  6/6 coroas → NULL.
- **Gate DURO:** `GET /api/gg-health/spurious-crown-non-ko-scan` → `spurious_crown_contamination` = 0
  pós-reimporte / pós-ingest GG.

## ABERTO — próxima sessão

- **`#BOUNTY-SIGNAL-CROWN-FALLBACK-CIRCULAR` (TEÓRICO/latente — decisão Rui 9 Jul: NÃO MEXER)** —
  `_has_real_bounty_signal` (`mtt.py:773`) alimenta `detect_tournament_format(has_player_bounty=…)`:
  prefere o TS, mas sem TS cai nas COROAS → coroa inventada classificaria KO (leitura→formato). O
  cenário que o arma (GG sem TS à hora da classificação) **NÃO existe no fluxo real** (os TS da GG
  entram sempre primeiro — ritual do Rui). **Mantém-se como está** (fallback = caminho morto).
  Reabrir só se o ritual mudar. Não é acção.
### ✅ `#TS-LATE-NO-FORMAT-RECALC` — gatilho no import do TS GG — LIVE (9 Jul)

**APROVADO + implementado (GG-only).** O import de TS (`tournament_summaries.py:500` + o ramo TS
do `import_.py:623`) dispara agora, fire-and-forget, `ts_reclassify.reclassify_and_rescrub_for_tns`
para os `tn` GG upsertados:
1. **Reclassifica** o formato das mãos GG do tn com o sinal do TS (`_reclassified_format` puro:
   `detect_tournament_format(..., has_player_bounty=buy_in_bounty>0)`; nome ganha; não rebaixa
   Mystery/Super KO → PKO). Corrige a classificação name-only da HH.
2. **Re-scrub das coroas** (`scrub_and_persist`, só-tagadas, DB-aware, idempotente) → as guardas
   vanilla/vivo-$0 disparam quando o TS chega DEPOIS da HH (o scrub lê o TS live → idêntico a
   TS-primeiro). Fecha a fresta por inteiro.
3. **Jusante:** solves HRC afectados por mudança de formato são **listados no log** (`hrc_stale`),
   NÃO re-solvidos (espírito da F6 dormente).

**TS-primeiro (ritual normal) byte-idêntico:** quando o TS entra sem mãos ainda desse tn → no-op.
**Impacto medido (read-only, 2622 mãos GG 2026 com TS): 0 formatos mudariam** (o nome GG já
classifica bem) → a reclassificação é rede de segurança; o valor real é o re-scrub. Teste puro:
`test_ts_reclassify.py`. Verificação ao vivo pós-deploy: largar um TS e ver o log `[ts_import] reclassify`.
- **`#TABLE-SS-SPEEDRACER-NO-MATCH` — diagnóstico ATUALIZADO 9 Jul (a versão "HH em falta" era só
  METADE).** Sintoma que destapou o resto: **0 mãos Speed Racer na secção HRC**. Investigação
  read-only em prod (como se chegou cá: contar mãos → contar capturas por source/folder_tag → ler o
  gate do HRC):
  - **218 mãos Speed Racer GG 2026** — 206 anónimas · 8 por Gold (`position_v3`) · 4 por print IT
    (`table_ss`); **217/218 SEM etiqueta nenhuma**.
  - **31 prints de mesa (IT)** do Speed Racer, TODOS `source='manual_upload'` (soltos, sem pasta) →
    **0 com `folder_tag='speed-racer'`**. Destes: **19 `no_match_to_hand`** (faltam as HH de
    15/16/18 Jun; a BD só tem 30 Jun–2 Jul) + **12 `success`** (casaram) — mas **nenhum aplicou
    etiqueta** (não a traziam).
  - **0 capturas Gold** na tabela de capturas; a Gold deu nome a 8 mãos mas **a Gold NUNCA etiqueta**
    (só põe nomes reais).
  - **São DOIS bloqueios, não um:** (a) 19 capturas não casam (HH em falta) — **NÃO afrouxar o match**
    (mão de nome igual mais próxima a 12-17 dias = match errado); (b) **a etiqueta `speed-racer` não
    existe em NENHUM print** → nenhuma mão fica etiquetada → o gate do HRC, que **exige** etiqueta do
    basket (`hrc_queue.py:158-163`, e bem — só mãos de estudo entram), exclui-as **todas**.
  - **NÃO é bug do HRC nem do matcher.** Resolve quando os **prints da pasta "SpeedRacer"** (que
    trazem `folder_tag='speed-racer'`) entrarem E casarem → a etiqueta aterra → HRC. Depende do
    `#ICM-FT-TAG-NOT-LANDING` (a etiqueta aterrar mesmo em linhas casadas). **Tudo fecha no
    wipe+reimporte** (HH todas + prints com pasta). Bloco antigo (8 Jul) mais abaixo = superseded.
- **`#ICM-FT-TAG-NOT-LANDING` — RAIZ ENCONTRADA + fix do core LIVE (9 Jul).** Diagnóstico (código+BD):
  a máquina de etiquetar **funciona** (286 capturas com `folder_tag`: icm-pko 103, pos-pko 85, nota 66,
  icm 19, icm-pko-ft 9, pos-pko-ft 2, pos-nko 2). O `icm-ft`/`speed-racer` = 0 porque os prints **não
  vieram na subpasta** (Speed Racer: 30/31 soltos na raiz `it\`, 1 na pasta errada). **★ Bug do core
  achado pelo Rui:** o move pós-2xx **achatava** `it\<SUB>\x → done\it\x` → a subpasta (=a tag)
  **morria no disco** → um reimporte a partir do `done` nascia SEM tag (a doença fabricada por nós).
  - **FIX (Task 1, LIVE):** `_process_it_dir` preserva a subpasta (`_done_subdir` → `done\it\<SUB>\`;
    raiz→raiz); `CANONICAL_FOLDER_FOR_TAG` (reverso tag→pasta) round-trip garantido por teste
    (`test_done_subfolder.py`). Reimporte lê a subpasta → mesma tag. **55 testes appimport verdes.**
  - **Arrumar o `done` já achatado (Task 2, entregue — à espera do dry-run do Rui):** endpoint
    `GET /api/table-ss/folder-tags` (nome→tag, BD = fonte de verdade) + `tidy_done_it.py` +
    `TidyDoneIT.bat`/`TidyDoneIT_Aplicar.bat`: realoja cada print na subpasta da sua tag; **sem tag na
    BD → fica na raiz (não adivinhar)**; dry-run primeiro, `--apply` move. Só dentro de `Batmen\`.
  - **ICM FT sem evidência (decisão Rui):** se entraram soltos, ficam na raiz do done (não adivinhar);
    a máquina FT (`ft_boundary`) repõe os `-ft` das tags base no reimporte — a perda é do sinal manual.
  - **`it\Lobbys` — DECIDIDO (Rui 9 Jul): deixar como está, NÃO mapear, NÃO investigar.** Os lobbys
    entram pelo routing por NOME (raiz ou subpasta, indiferente); a pasta é arrumação pessoal do Rui.
    O aviso "subpasta fora da tabela (IT_FOLDER_TAGS)" para `Lobbys` é **ruído esperado** — ignorar.
  - **Etapa 2 desbloqueada** deste lado (o done deixa de destruir a tag).


## ✅ Sistema de nomes (quarentena Fase 3 + RE-ENTRADA + detetor de evidência dura) — LIVE (8 Jul)

**LIVE (`main`→`5774bc2`).** Painel de conflitos de nomes na Saúde GG (grupo `name_quarantine`): mostra os
**DOIS lados** de cada "nome→2 lugares" (mãos clicáveis + fonte forte/fraca + **Seats do raw** + imagens +
**"+ imagem"** para anexar Gold do disco) + o **selo "nome em revisão"** na mão. Verbos: **É este /
Escolher / Fundir / Mesma pessoa (re-entrada) / Dispensar**. Conceito re-entrada (o hash é por ENTRADA,
não por pessoa): `DESANON_ANATOMIA §3.3`, `REGRAS_NEGOCIO §24`, `REGISTO_CONCEITO 2026-07-08`. Motor:
`services/name_propagation.py`.

- **Detetor `reentry_hint`** — `confirmed` (bust da 1ª + bala fresca da 2ª + gap curto) vs `likely` (só
  sinais fracos). Usa mãos **SEATED** (não NAMED); `same_nick` compara só a leitura **FORTE** (ignora
  misreads fracos). Nota de honestidade: falta de bust legível nunca despromove.
- **Scrub** (`propagation_plan.corrected` + `_clean_stale_villains`): a decisão VERIFICADA **corrige** o
  misread fraco na mão (não fica agarrado) e **limpa vilões stale**. Mão forte / mapa não-verificado intocado.
- **★ kind `strong_weak_mismatch` (novo, LIVE):** hash com nome FORTE X + leitura(s) FRACA(s) divergente(s)
  (Y≠X, não OCR) → **cartão** (detectado no `build_name_map`; não-bloqueante, o forte propaga na mesma).
  Confirmar o forte → scrub das fracas. Tapa o buraco de core (passava em silêncio; ex. `93d63976`
  Vadzim+Diego). Varrimento pré-wipe: **59 hashes / 93 mãos tagadas / 98 torneios** — serve o **pipeline
  pós-wipe**. O upgrade **automático** fraco→`position_v3` continua **deferido** (este cartão é a via
  manual pelo circuito normal).
- **⏳ PENDENTE do carimbo do Rui (3 cartões):** **OHmyBUDDHA** (`confirmed`), **M_R_Z_E_** (`confirmed`),
  **Silin O** (`likely`). Ao carimbar OHmyBUDDHA, verificar à vista na mão `200072` que o "Vadzim" saiu do
  Seat 6. **Quando a quarentena zerar → wipe+reimport** é o teste de aceitação (tagadas GG desanonimizadas
  + re-entradas resolvidas à primeira).
- **Deferido:** upgrade automático fraco→`position_v3` (só decisão manual verificada corrige hoje); misread
  "Diego Emperador" no hash `93d63976` (outro nome-real-lugar-errado, fora do cartão OHmyBUDDHA).
- **★ D (8 Jul) — `#IRE-SK` (Super KO) — AGUARDA validação empírica do Rui:** o IRE do Super KO
  fica **escondido** (deny-list `SUPER_KO_NEEDLE`, `ire.py:507`) porque a **fração instantânea** do
  bounty ao eliminar no Super KO GG **não está confirmada** — mostrar daria um IRE potencialmente
  errado. Destranca-se quando o Rui confirmar a fração (então deriva-se a constante como no PKO e
  mostra-se). Descido do pré-wipe (casa limpa) para D por falta de dado, decisão do Rui 8 Jul.
- **★ D (decisão de arquitetura, 8 Jul) — `#STACK-ELIMINATION-ABANDON`:** abandonar de vez a
  **stack-elimination** como método de desanon do table-SS (usada nas 185 capturas antigas + painel
  SB/BB ~10/19 mal-lidos, `#STACK-LEGACY-TABLE-SS-AND-PANEL`). Substituir pela **âncora Hero+botão**
  (`#DESANON-HERO-BUTTON-ANCHOR`) em TODA a table-SS. **FORA do pré-wipe** (os 185 são dados condenados
  + o core cure neutraliza o veneno: o fraco não semeia, os cartões `strong_weak_mismatch` apanham a
  divergência). Entra pós-wipe se o Rui quiser table-SS 100% por âncora. Esforço M.

## ✅ Propagação FT (`ft_boundary`) — F1–F5 CONSTRUÍDA POR INTEIRO e LIVE (8 Jul); F6 dormente

**Frente FECHADA (LIVE, `main`→`874bd7e`).** Anatomia consolidada: **`docs/FT_BOUNDARY_ANATOMIA.md`**.
Só falta o **wipe+reimport** (teste de aceitação — as `-ft` entram a sério quando as mãos de FT
chegarem com tags base) e a **F6** (dormente, 0 solves afectados). Plano original (histórico) +
estado por fase abaixo. Escrita **sempre manual** (dry-run → OK do Rui);
**CONFIRMAR/CORRIGIR na quarentena fixa a fronteira e devolve o ensaio** (2 passos: decidir a
fronteira ≠ aprovar a escrita). Decisões: D1 quarentena se N ilegível; D2 cross-check também no
fallback (players_left da fronteira = N); D3 `folder_ft_source='auto'`; D4 manter as 2 escritas do
`_ft_applies`; D5 construir ANTES do wipe (é cura do core).

- **F1 ✅ (7 Jul)** — `_persist_ft_correction` grava `folder_ft_source='auto'` (não a via
  `propagated_*`, que poluía o filtro "-ft auto") + `CASE` preserva `'manual'` (pasta -ft manda). +1 teste.
- **F2 ✅ (7 Jul)** — gate `open_tab='Info'` + cross-check HH; **snap-to-N + coerência pós-pico** (política da
  fronteira, 5 casos reais); **fonte (0) tag manual** no topo da cascata `(0)→(a)→(b)→none`. Ver `REGISTO_CONCEITO 2026-07-07`.
- **F3 ✅ (8 Jul)** — tabela `ft_boundary_review` + endpoints `GET /ft/preview`, `POST /ft/confirm|correct|promote`.
  **Emenda:** confirmar/corrigir FIXA a fronteira mas **NÃO** promove; a escrita (`promote`, dry_run default,
  `confirm=true`) é sempre o 2º passo explícito. Preview mostra fronteira+via (incl. fonte 0), N+sentados,
  cross-check, mãos que mudam (from→to), avisos do fallback e mãos HRC stale. +13 testes.
- **F4 ✅ (8 Jul)** — UI da quarentena na Saúde GG: grupo `ft_quarantine`. **Gate APERTADO** (validação do Rui:
  o ramo IT do `_candidate_tns` passou de `players_left IS NOT NULL` [qualquer captura, mesmo a meio] para
  `<= FT_CAP` → **99→6**, resolve também a lentidão). **DUAS secções** (nomes do Rui): **"Precisam de ti"**
  (só o que exige decisão — `none`-com-sinal/mismatch/disagreement/n_unavailable/incoherent; é o que `/summary`
  conta) e **"Prontas a aprovar"** (match limpo — ensaio dry-run → Confirmar → Promover/escrita explícita; a
  **cobertura parcial N=5** fica VISÍVEL na linha). Lista compacta → clicar expande o ensaio FULL por torneio
  (fetch `?tn=`): lado-a-lado, avisos + sequência da via-b, mãos que mudam (from→to).
- **F4 afinações (8 Jul):** (1) **IMAGENS no ensaio** (`_ft_images`, preview FULL) — capturas de mesa (miniaturas
  clicáveis/lightbox, ordenadas por `captured_at`, com o `players_left` por baixo, ≤9 a verde), lobbys (leitura +
  hora, "imagem não guardada") e outras imagens das mãos. (2) **DISPENSAR ("sem FT")** — `POST /ft/dismiss` →
  `decision='dismissed'` na `ft_boundary_review` APENAS (⚠️ **não toca mãos/tags/study_state/vilões** — guarda
  testada: mãos intactas); sai de "Precisam de ti", `/summary` deixa de contar; secção **"Dispensados"**;
  **reversível** — volta a pendente com sinal novo forte (tag manual -ft OU print do Info, `_ft_dismiss_reactivated`).
  Caso real: 290775453/292235768 = bolha da FT (o Rui rebentou), o motor esteve certo em não ancorar → dispensados.
- **F5 ✅ (8 Jul) — LIGAR A MÁQUINA.** (1) **Gatilhos de CÁLCULO** (nunca escrevem tags): `refresh_ft_boundaries`
  fire-and-forget em `import_`, `import_hm3`, `tournament_summaries` (`asyncio.create_task`) e no reconcile de
  lobbys on-demand (thread daemon). Recomputa o estado por torneio e sincroniza a `ft_boundary_review`,
  **RESPEITANDO decisões**: `promoted` não recalcula; `confirmed`/`corrected` mantêm a fronteira fixada;
  `dismissed` só renasce (→pending) com sinal novo forte (`has_new_ft_signal`); pending/novo → snapshot.
  **Idempotente** (recompute = mesmo resultado). **Perf:** F&F + gate apertado → não pesa nos imports. (2) **Fluxo
  de APROVAÇÃO** na secção "Prontas a aprovar": **Aprovar** → confirm (fixa) + plano dry-run (mãos que mudam +
  HRC stale + **aviso de cobertura parcial à vista**) → **Escrever** explícito → `propagate_ft(confirm=true)` →
  `promoted`, sai da secção. `review_status` = fonte única (services/ft_boundary). +6 testes. **F6** (re-solve HRC
  stale) fica dormente (hoje 0 solves afectados). **Frente FT F1–F5 construída por inteiro.**
- **F6 (re-solve das mãos HRC stale) — DORMENTE.** Quando uma mão >= fronteira que foi promovida a `-ft` tiver
  um `hrc_jobs` associado, o solve fica stale (a tag pode mudar o equity model) e precisa de re-solve. Hoje **0
  solves afectados** (o preview mostra a contagem "HRC stale" — está a 0). Acende sozinha quando aparecer a 1ª.
- **★ Teste do invariante dos hashes GG (8 Jul, read-only) — a EVIDÊNCIA que fundou a APROVAÇÃO do core.**
  25 torneios GG 2026 ≥100 mãos = 38 488 aparições → **0 violações** do invariante posicional (hash nunca em
  2 mesas à mesma hora); 40 hashes seguem o jogador entre mesas. Conflitos de nome = **bug da desanon**, não do
  hash. Números em `JOURNAL_2026-07-08.md`, `REGISTO_CONCEITO 2026-07-08`, agora **LEI** em `REGRAS_NEGOCIO §23`.
  **Com esta evidência o Rui APROVOU o core (8 Jul)** → ver a secção "★★ CORE — apa por hash" abaixo.
- **★ Endpoint `GET /api/gg-health/ft/raw-material` (SÓ LEITURA, `require_auth_or_api_key`)** — matéria-prima
  da F4b: torneios GG 2026 por dia com pista de FT (`min_players_left` + `latest_hand_seats` +
  `has_lobby` + `ft_candidate`). **REUTILIZADO pela Fase 3** (o preview/quarentena parte das mesmas
  leituras: fronteira + cross-check) e **RE-CORRÍVEL após o wipe+reimport** (recomputa de raiz, nada
  persistido) → serve de sanity-check pós-reimport. +3 testes.

- **CONVENÇÃO do print de arranque da FT (via 1) — 7 Jul, ver `REGISTO_CONCEITO 2026-07-07`.** A fonte
  (a) do motor só pode ancorar em lobbys com a **aba "Info" ABERTA** (`vision_json.open_tab=='Info'`),
  onde se lê "N players at the final table"; o N vem daí (`final_table_size`). Prints de outras abas
  (Players/Prize Pool) **nunca** ancoram. **A `lobby_vision` WIP já tem `open_tab` + `final_table_size`**
  (lado da Vision) → **commitar/deployar com a F2**; o `ft_boundary._lobby_ft_boundary` tem de passar a
  **gatear por `open_tab='Info'`** (hoje usa `players_left<=FT_CAP` de qualquer print — corrigir na F2
  ANTES de ligar a escrita).

- **★ Caso de teste da 4b — VIA 1 ponta-a-ponta (Daily Hyper $60, 2 Jul):** started 17:45, 172 entradas;
  **print do Info ~19:19 → "7 players at the final table", 7/172 restantes** (Hero **Lauro Dermio**, 5º,
  7 BB). Teste: fronteira **pelo print do Info** + **N=7** + cross-check com os sentados da 1ª mão
  pós-fronteira (deve dar 7). **Controlo NEGATIVO:** 2º print do mesmo nome nessa noite — **edição das
  21:27, 169 entradas, nível 13, 107 restantes, aba Prize Pool** → o motor **não** o pode usar como
  fronteira nem confundir a edição. ⚠️ **Dependências para correr:** (1) confirmar que a HH+TS do Daily
  Hyper entraram (tournament_number + nº de mãos — pendente `railway login`); (2) a via-1 só corre com a
  `lobby_vision` nova **deployada** e o print do Info **re-Visionado** (senão o `vision_json` não traz
  `open_tab`/`final_table_size`).

- **4 FTs de Jun (16-26) — testam a VIA 2 (fallback) + cross-check D2.** Não têm print do Info (o Rui só
  começou a tirá-los a 2 Jul) → fronteira por `players_left` coerente das capturas IT + cross-check com
  `players_left` da fronteira como N. A tabela do endpoint cruza-as (o Rui identifica-as por
  `min_players_left`/`latest_hand_seats`).

## ★ Melhorias futuras da propagação FT (registadas 7 Jul, NÃO agora)

- **`#FT-GUARD-BY-LOBBY-STATUS` — reforço do guarda por ESTADO do lobby.** Os lobbys GG mostram a **fase** no canto superior direito — **"Late Reg."** / **"Running"** — visível em **QUALQUER aba** (incluindo os prints de PRÉMIOS tirados a meio do torneio). Quando a Vision extrair um campo **`tournament_status`**, o guarda da via-b pode usar leituras de lobbys **"Late Reg." como PRÉ-PICO por definição** (reforça o `_post_peak_tail`, que hoje infere o pico só pelo máximo dos `players_left`). **A hora de fecho do late-reg (aba Info) NÃO serve** — só existe quando o Rui fez FT, e aí a **via-1 (print do Info) já resolve**. O mecanismo-base continua a ser o **pico** (funciona só com capturas IT, sem depender da Vision de lobby). Cross-ref `REGISTO_CONCEITO 2026-07-07` (política da fronteira).
- **`#FT-N-FROM-NONGG-LOBBY` — N direto do lobby nas salas não-GG.** Os lobbys de **PS/Winamax/WPN** mostram o **tamanho da mesa final DIRETAMENTE** no lobby (ao contrário da GG, onde o N só aparece na aba **Info** — daí o gate `open_tab='Info'`). **Quando/se** o motor FT se estender **além da GG** (ou o snap quiser refinar tags manuais não-GG), o **N** dessas salas extrai-se de **qualquer print de lobby**, **sem** convenção de aba. Facilitador futuro. **Âmbito ATUAL do motor: só-GG** (a cobertura TOTAL de mãos é pré-condição da propagação e do cross-check; as não-GG têm nicks reais e tagam por HM3/pasta, sem o mecanismo de desanon que motiva a FT-propagation na GG).
- ~~**`#FT-ENSAIO-VIA-F3-ENDPOINT` — mover os ensaios para a F3.**~~ ✅ **FEITO (F3, 8 Jul):** os ensaios correm por `GET /api/gg-health/ft/preview` (mesmo caminho da app, sem script local nem proxy).

## ★ `#LOBBY-IMAGE-NOT-STORED` — guardar a IMAGEM do lobby no pipeline (futuro, 9 Jul)

**Registado a pedido do Rui (9 Jul).** Hoje o pipeline de lobbys **NÃO guarda a imagem** — o
`lobby_processing_log` só tem a **leitura** da Vision (`vision_json`, `players_left`, `open_tab`,
`final_table_size`) + `posted_at`, **não os bytes** (ao contrário do table-SS, que guarda
`img_b64`, e das entries Gold/replayer). Por isso a secção **🏦 Lobby** do painel da mão
(`HandImagesSection`, `GET /api/hands/<id>/images`, regra 9 Jul) e o ensaio da FT (`_ft_images`)
mostram só a leitura + hora com a nota **"imagem não guardada"** — não há foto para mostrar nem
para re-Visionar o histórico.

- **O que falta:** persistir a imagem do lobby (à imagem do `table_ss_processing_log.img_b64`:
  comprimir 1280/JPEG85 e guardar) nas DUAS vias de entrada — Discord `#lobbys`
  (`services/lobby_sync.py` / `discord_bot`) e upload por pasta (`POST /api/lobbys/upload`,
  `services/lobby_vision.py`) — + servir por endpoint (`/api/lobbys/image/<id>`) e ligar na secção
  Lobby do `HandImagesSection` (hoje já reserva o sítio; passa a mostrar a foto quando existir).
- **Porquê guardar:** (a) mostrar a foto do lobby na mão/FT; (b) **re-Vision** do histórico
  (players_left/open_tab/final_table_size) quando o prompt melhorar, sem re-pedir o ficheiro ao Rui
  (o mesmo motivo que levou o table-SS a guardar a imagem). Só a Vision lê a **original**; a cópia
  comprimida é para guardar.
- **Âmbito/decisão:** produto — **quando o Rui mandar**. Retroativo impossível (as imagens
  antigas foram descartadas; só as novas ficam guardadas a partir da mudança). Cross-ref
  `HandImagesSection`, `_ft_images` (`gg_health.py`), `#LOBBY-INFO-NO-PAYOUT`.

## ✅ Infra — token Railway de vida curta (MITIGADO via ficheiro local, 8 Jul)

**Resolvido na prática:** DB reads por `~/.pokerapp_db_ro.env` (fora do repo, só-leitura) +
deploys por OpenAPI/liveness → railway CLI dispensado do fluxo. Detalhe da causa e do setup abaixo.

- **7 Jul 2026 — `#RAILWAY-TOKEN-SHORT-LIVED` (investigado, causa provável com evidência).** O `railway` CLI obriga a `railway login` **de ~1 em ~1 h** (4× num dia). **FACTOS medidos:** (a) `user.tokenExpiresAt` no `config.json` = **exatamente 1 h após o login** → o *access token* tem TTL de **1 hora**; (b) CLI **4.40.0**, pacote npm **datado 21 Abr, INALTERADO** → **não foi upgrade do CLI**; (c) **UM só** `config.json` (`C:\Users\User\.railway\config.json`), partilhado pelo shell do Code e pelo login do Rui (mtime segue os logins) → **NÃO** é o problema dos "dois ficheiros de sessão"; (d) o *refresh* falha com `invalid_grant` quando o access token expira. **CAUSA PROVÁVEL:** o access token dura 1 h e o **refresh automático está partido** — como o CLI não mudou, a mudança é do lado do **servidor Railway** (política de refresh/rotação de refresh-tokens mais estrita, recente — bate com "começou há poucos dias"), possivelmente **agravada pelas chamadas frequentes/concorrentes** do Code (pollers de deploy a cada 15 s + queries em paralelo) que correm o rotativo do refresh-token. **FIX DEFINITIVO:** (1) **DB reads** — guardar o **URL público do Postgres** (`ballast.proxy.rlwy.net:37559`) num ficheiro **gitignored** que o shell lê → psycopg2 direto, **sem railway, sem expiração** (âmbito = leitura a 1 BD); (2) **deploy status** — `RAILWAY_TOKEN` (project token, env `production`) cobre `railway status`/redeploy (o docs diz que é deploy-scoped; **não** cobre `railway variables`), OU dispensa-se (push→auto-deploy confirma-se por `/openapi.json` + liveness). Mitigação imediata do Code: **deixar de correr pollers `railway status` de 15 s** (usar OpenAPI/liveness). Ver memória `reference_railway_cli_auth`.
  - **SETUP escolhido (7 Jul, via 1):** as DB reads passam por um ficheiro **fora do repo, gitignored, só-leitura** — `~/.pokerapp_db_ro.env` (mode 600) com o URL público do Postgres. O shell lê `DBURL=$(cat ~/.pokerapp_db_ro.env)`; **nunca** se imprime o URL/creds em outputs nem entra em commits. Deploys: só OpenAPI/liveness (railway CLI dispensado do fluxo normal). **⚠️ ROTAÇÃO OBRIGATÓRIA:** se estas credenciais **alguma vez aparecerem num output/commit/log**, **rodar já** a password do Postgres no Railway (dashboard → serviço Postgres → variáveis) e regenerar o ficheiro. O ficheiro guarda a password viva do `DATABASE_URL` do `poker-app` (host público `ballast.proxy.rlwy.net`).

## ★ Infra/git — `origin/watcher-gate` diverge de `main` (pt87–95 do watcher nunca fundidas) — arrumar pós-wipe

**Registado 8 Jul.** O branch **`watcher-gate`** tem **14 commits** do robot/watcher (pt87–95) que
**nunca foram fundidos em `main`** (medido: `main...origin/watcher-gate` = 135 à frente / **14 atrás**;
HEAD do branch = `049cd4b` "pt95 — robustez de foco `#HRC-FOCUS-ROBUSTNESS` [SEM build ainda]"). Enquanto
os dois branches divergirem, o histórico do watcher vive **fora do `main`** e o próximo build do `.exe`
arrisca sair de uma base incompleta.

- **Acção (pós-wipe):** reconciliar `watcher-gate` → `main` (merge ou rebase), resolver conflitos do
  source do watcher (`tools/watcher_src/`), e **só depois** rebuildar o `.exe` (junto com o `#HRC-FOCUS-ROBUSTNESS`
  e a guarda de tempo/janela, ambos já pendentes de build). Confirmar que nenhum fix pt87–95 se perde.
- **Porquê pós-wipe:** o foco actual é a **casa limpa + wipe+reimport** (backend/dados); mexer no branch do
  watcher agora abre uma frente paralela sem necessidade. Fica arrumado quando o robot voltar a ser tocado.

## ★ "Mãos suspeitas" (bounty < base÷2) — CICATRIZ confirmada → critério de aceitação do reimport (8 Jul)

**Triagem read-only pedida pelo Rui.** A secção lista GG PKO/KO 2026 com ≥1 coroa gravada **< base÷2**
(base = `tournament_summaries.buy_in_bounty`; = provável leitura da **chama/VPIP** em vez da coroa). Fix
chama-vs-coroa = **`824f23d` (1 Jul)** (prompt distingue coroa$/chama% + guarda dura `crown >= base/2`).

**Distribuição (107 mãos):** **107/107 PRÉ-fix, 0 PÓS-fix.** (⚠️ um scan intermédio deu 112 por o `LEFT JOIN
table_ss` multiplicar mãos com >1 linha de log — **107 é o número certo**, bate com o contador da secção.)
Por `hands.created_at`: todas criadas **18–26 Jun** (< 1 Jul). Por `table_ss_processing_log.uploaded_at`
(63 com SS de desanon casada): todas **18–26 Jun**; as sem SS casada = `table_ss` (log limpo em resets
antigos) + `position_v3`, mãos na mesma criadas pré-fix. **Zero** entries replayer/SS criadas após 1 Jul;
**zero** uploads table-SS após 1 Jul; o único caminho de escrita pós-fix (backfill gold-carry `6edf785`,
2 Jul) **TEM a guarda** (0 rejeitadas) e só **acrescenta** a coroas vazias → não criou estas.

**Forma das 107 (perfil chama sistémica vs bordo):** seats abaixo-de-metade por mão →
`{1:40, 2:20, 3:12, 4:7, 5:2, 6:2, 7:9, 8:15}`. Os **≥7 seats (24 mãos)** = mesa quase inteira lida como
chama/VPIP = bug sistémico do prompt antigo (morre com o prompt novo). Os **1-seat (40)** = população onde
um **bordo legítimo** (coroa-verde/eliminação: a coroa própria do eliminado some, aparece a verde na do
eliminador) pode reaparecer pós-fix. 349 seats no total, 57 a `$0`.

**Veredicto: CICATRIZ.** Escritas todas na desanon de Junho, antes do prompt chama/coroa. **Morrem no wipe.**
→ **Critério de aceitação do reimport:** pós-reimport a secção deve nascer **~0** (só bordos legítimos de
coroa-verde/eliminação, subconjunto dos 1-seat). Se nascer alta (ressurgirem mãos multi-seat), a leitura
chama/coroa **regrediu**.

**⚠️ DECISÃO DE ARQUITETURA REABERTA (8 Jul, pendente do Rui — `FLUXO §12`):** onde vive a defesa das
coroas. Não é furo que gerou as 107 (é defesa-em-profundidade). Hoje a protecção *sistémica* é o **PROMPT**
(`824f23d`); a guarda `crown>=base/2` só existe nos **dois backfills** (`screenshot.py:2144/2395`) e no
**gate do HRC** (`queue_export.py:1694`); o enrich **live** (`screenshot.py:1044`) grava o `bounty_value_usd`
da Vision **cru**. **Quadro A vs B apresentado ao Rui** — aguarda decisão (não implementar até decidir).

## 🔴 `#TABLE-SS-SPEEDRACER-NO-MATCH` — investigação OBRIGATÓRIA antes da Etapa 2 (8 Jul)

> ⚠️ **SUPERSEDED pelo diagnóstico ATUALIZADO 9 Jul no topo (secção ABERTO).** O no-match (HH em
> falta) é só METADE; o bloqueio que mantém o Speed Racer FORA do HRC é a **etiqueta que nunca
> existiu** (0 prints com `folder_tag='speed-racer'`; todos soltos por web). Ler o topo primeiro.

**Descoberto no reimport (Cano 3, Etapa 1).** As **19 capturas GG `no_match_to_hand` são TODAS Speed
Racer** — e as **218 mãos Speed Racer EXISTEM na BD** (HH importada). Logo não é "HH em falta": é um
**gap de match por NOME** específico do Speed Racer. Suspeitos: o nome traz `[10 BB]` e buy-ins atípicos
(`$21.60`, `$32`, `$108`, `Speed Racer Bounty Europe`) que partem a tokenização/janela do
`_resolve_match`/`_find_candidate_hands` (as capturas Speed Racer estão no formato IT antigo → `tn=None`
→ caem no match por tempo+nome). **Na Etapa 1 = 19 mãos; no REIMPORT COMPLETO afeta CENTENAS** (o Rui
joga Speed Racer todos os dias). **Atacar quando o guião de hoje fechar, ANTES de arrancar a Etapa 2.**
Refs: `routers/table_ss.py:_resolve_match`/`_find_candidate_hands`; formato do nome Speed Racer.

## ★ UX — fundir "Marcadas por captura" + "Mãos suspeitas" na Saúde GG (desenho aprovado? executar pós-blocos)

**Decisão UX do Rui (8 Jul) — registar para executar quando ele mandar.** `Marcadas por captura`
(`/marcadas-por-captura`, `CaptureTriage.jsx`) e `Mãos suspeitas` (`/suspeitas`, `SuspiciousHands.jsx`)
são AMBAS revisão manual de mãos GG e vivem FORA da Saúde GG — que já é a casa disto (tem lá o "Gold
sem tag", o gémeo). **Fundir as duas na Saúde GG como secções próprias** (sidebar mais limpa; tirar as 2
entradas `/marcadas-por-captura` e `/suspeitas`). A **"Marcadas por captura" precisa de:** (a) as **11
tags canónicas** (hoje só mostra 4) + (b) **multi-tags em toggle + 1 Aplicar** (o mecanismo que o
"Gold sem tag" acabou de ganhar em `abfef49` — a barra de toggles é PARTILHÁVEL). É **UX** (não toca
arquitetura de dados: o endpoint `/gg-health/tag` já acrescenta/canónico/multi). **✅ DESENHO APROVADO
pelo Rui (8 Jul).** Executar **quando os 3 blocos pré-Etapa-2 fecharem** (ou antes se der jeito no meio —
o Code gere a ordem). Detalhe do desenho aprovado: `/gg-health` casa única; `/marcadas-por-captura` e
`/suspeitas` redirecionam p/ `/gg-health`; barra de toggles (11 tags, ACRESCENTA, multi) vira componente
partilhado por Gold-sem-tag + Marcadas-por-captura.

**📌 INSTRUÇÃO das 3 SR marcadas-por-captura (`6138218252`/`6138218069`/`6137938737`):** o Rui etiqueta-as
à mão com **`speed-racer`** SÓ **DEPOIS** de a arrumação dar a barra completa (11 tags) a essa secção —
hoje a secção nem tem a tag `speed-racer`. **Até lá ficam quietas** (não tocar; não confiar no fix SR).

**⚠️ As 3 Speed Racer em "Marcadas por captura" (`6138218252`/`6138218069`/`6137938737`) NÃO são o gap
no_match** — CASARAM (`result=success`, `mm=table_ss`), desanon OK, mas `tags=[]` porque a captura que
casou (web upload, `folder_tag=None`) não trouxe tag. É o **web-first-sem-tag** (entrelaçado com
`#ICM-FT-TAG-NOT-LANDING`, não com o no_match). O fix do `#TABLE-SS-SPEEDRACER-NO-MATCH` corrige as **19
capturas no_match** (as da pasta `SpeedRacer`); se entre elas houver capturas destes 3 hands com
`folder_tag='speed-racer'`, o re-match aplicaria a tag — **MAS só se a tag aterrar** (o `#ICM-FT-TAG-NOT-LANDING`
mostra que em rows já-casadas por web NÃO aterra fiável). **Risco: ficam tagless → tag manual** (via a
Marcadas-por-captura melhorada). Não são auto-resolvidas com garantia pelo fix SR sozinho.

## 🔴 `#CROWN-VISIBLE-READ-ZERO` — Vision lê $0 em coroas VISÍVEIS (3º bloco pré-Etapa-2, 8 Jul)

**Investigação visual das 8 "Mãos suspeitas" (inspecção imagem-a-imagem).** Todas $0 (coroas por ler,
não valores trocados — o padrão chama-vs-coroa NÃO voltou). Classificação: **7 espécie 1** (coroa
CLARAMENTE VISÍVEL na imagem, gravada $0 = falha de leitura da Vision) + **1 espécie 2** (`6140169166`,
sem captura de mesa; fonte = **Gold** `position_v3`, coroa $0 por ler na Gold) + **0 espécie 3** (casamento
errado — o varrimento do reimport deu **0 casamentos cruzados** `capture_tn != hand_tn`; o `6139761400`,
suspeito de imagem alheia, é **casamento CORRETO**: captura `tn=295228486` = tn da mão, Big Game $215 PKO,
8 nicks da imagem batem com a HH). **Espécie 3 NÃO existe** — contexto não envenenado.
- **Padrão da espécie 1:** o lugar lido $0 tem o **AVATAR obscurecido** (cartas viradas vermelhas / texto
  "All-In" / cartas do Hero por cima), MAS o **banner dourado da coroa (por cima) está legível**. Apanha
  **Hero E vilões** (4× Lauro Dermio + PhilVsSandwich $375, RaresSD $13.12, Golden Goose $125, Cornel $20,
  Diagonale/SagradaFamilia/TripleL). A Vision devolve $0 quando o avatar está tapado, apesar da coroa à vista.
- **Âmbito/IRE:** **25/166 mãos GG PKO desanon (15%)** têm ≥1 coroa $0; **18 ocorrências Hero-$0 + 100
  vilão-$0** → IRE coxo em ~15% (o painel "suspeitas"=8 SUBCONTA: só apanha mãos com TS + $0 < base÷2). No
  reimport completo multiplica por dezenas.
- **Fixes propostos:** (1) **leitura** — afinar o prompt da Vision (a coroa dourada é ACIMA do avatar; ler
  SEMPRE, mesmo com cartas/all-in a tapar o avatar) + **re-ler as imagens afetadas** (as compressas servem —
  as coroas estão legíveis nas guardadas); (2) **filtro** — separar `coroa por ler ($0)` de `valor impossível
  (>0 e <base÷2)`, estados/alarmes distintos (o alarme vermelho é só para o 2º). Espécie 3 sem fix (não existe).

## 🔴 `#ICM-FT-TAG-NOT-LANDING` — a tag `icm-ft` do IT não aterra (investigação pré-Etapa-2, 8 Jul)

**Descoberto no reimport (Cano 7, A4).** 3 mãos de FT da FT VALIDADA `295219051` (Daily Hyper $60,
`6139251935/69/175`) ficaram **sem a tag `icm-ft`** apesar de terem captura casada. **`table_ss` tem
0 rows com `folder_tag='icm-ft'` em toda a BD** — a pasta `ICM FT` do appimport **nunca produziu uma
row tagada**, embora o dry-run mostre `folder_tag=icm-ft` e o backend `canonicalize_tag('icm-ft')='icm-ft'`
(válido). Um **re-run `--only it` da pasta ICM FT** (mesa=4, falhas=0) **NÃO criou/tocou nenhuma row**
(última atividade `table_ss` 00:05 UTC, o re-run ~01:40 não aterrou) → os 4 POST à `/table-ss/upload` ou
não chegaram ou devolveram algo contado como sucesso sem gravar. **Precisa do LOG do appimport** (retorno
dos 4 POST) — não se diagnostica pela BD. Distinto do Speed Racer (aqui o match existe) e do web-first
(as 3 vieram por web sem tag e o appimport não as re-tagou). **Nota:** `icm-pko-ft` (9) e `pos-pko-ft` (2)
aterraram bem → é específico do fluxo `ICM FT`→`icm-ft`. **Impacto:** só a métrica A4 (`-ft` subcontado);
a FT em si está bem promovida. Atacar com o Speed Racer, ANTES da Etapa 2.

## ★★ MUDANÇA DE ESTRATÉGIA (3 Jul 2026) — LER ANTES DE TOCAR NO BACKLOG DE DADOS GG

A sessão de **3 Jul** virou a estratégia (registada em `docs/APA_INDEXACAO_E_COLAPSO.md`):
**os dados actuais da app vão ser APAGADOS e REIMPORTADOS.** Consequência directa no backlog:

- **(a) A cura de DADOS históricos foi ABANDONADA.** As "pontas" de bounties/desanon
  históricos (1 presa `GG-6102580840`, 2 por rever, 5 seats truncados, mãos consertadas à
  mão, lote das 44 partidas) **podem morrer com o wipe** → **NÃO as trabalhar sem o Rui
  confirmar** que ainda fazem sentido depois do reimport. O esforço mudou de "curar os dados"
  para **"curar o CORE"** (o código que produz o apa) para que os mesmos dados entrem
  direitos quando reimportados.
- **(b) `#HRC-REIMPORT-REDEANON-CASADAS` DEIXA de ser diferível — prioridade SUBIU.** Sem
  ele, o reimport de HH **parte a desanon das mãos com captura já casada** (repõe o apa cru +
  esvazia o `anon_map` sem re-disparar a desanon das SS **casadas**, só das órfãs). Passa de
  "melhoria futura, NÃO agora" (pt93) a **pré-requisito do wipe**. Ver secção própria abaixo.
- **(c) ✅ A decisão do CORE está APROVADA (8 Jul 2026).** O Rui aprovou o **apa indexado por
  HASH + propagação por torneio (sistema misto, só-tagadas)**, com a evidência do invariante
  (0 violações em 38 488 aparições). Desenho canónico em **`APA_INDEXACAO_E_COLAPSO §B.6`** +
  `REGISTO_CONCEITO 2026-07-08`. Ver secção própria abaixo (**★★ CORE — apa por hash APROVADO**).

## ★★ CORE — apa por hash + propagação por torneio APROVADO (8 Jul 2026) — plano faseado + dry-run

Desenho: `APA_INDEXACAO_E_COLAPSO §B.6`. **Só-tagadas** (escreve só nas mãos tagadas; lê de todas
as com desanon). **Só fonte FORTE semeia** (`position_v3` OU `verified_by_user`); fraca não propaga.
Guardas: (b) nome-já-noutro-hash → branco+quarentena; (c) conflito no mesmo hash forte-vs-forte →
branco+quarentena; (d) branco honesto > nome errado.

**FASES (leitores → writer; ordem obrigatória; OK do Rui entre cada):**
- **Fase 0 — dry-run** ✅ (8 Jul, read-only, números abaixo). Aprovado pelo Rui.
- **Fase 1 — leitores ✅ FEITA e LIVE (`d9c504f`, 8 Jul)** → `real_name || chave`. 7 leitores migrados
  (`villain_rules._build_candidates`, `ire._assemble_ire`, `hand_service._resolve_hashes_in_raw`, `mtt`
  `seat_to_name`, `hands` filtro `villain`, `table_ss.set_bounties`, frontend `handParser`). Byte-idêntico:
  premissa `real_name==chave` provada em toda a BD (68 664 entradas, 0 divergem); +6 testes antigo==novo; suite
  1306 passed (6 falhas pré-existentes: 5 Postgres-local + `#NORAISE-ANCHOR`).
- **Fase 2 — writer ✅ FEITA e LIVE (`dc20ad1`, 8 Jul):** `_enrich_all_players_actions` deixa de re-indexar
  por nome (chave = hash/nick/"Hero"; `real_name`=atributo). Fecha a fusão de seats (MaLong07/4321) e a queda
  de lugares por desenho; cobre os 2 sites do `mtt.py`; `_rekey_apa_to_hashes` no-op. **Guarda (b) mínima**
  no `/set-anon-map` (`_assert_no_duplicate_real_names` → 409 no nome-já-usado). Mãos antigas NÃO migram.
  +8 testes; suite alvo verde.
- **Fase 3 — propagação ✅ FEITA e LIVE (`2c8fe8a`, 8 Jul):** motor `name_propagation.py` (só fonte forte
  semeia; escreve só brancos das tagadas; `hash_propagation_v1`, não re-semeia). Guardas a–d. **OCR-merge
  ENDURECIDO** (`_ocr_variant`: truncagem-prefixo OU dist. edição ≤1-2; rejeita "Daniel Filipe"/"Ferreira").
  **Quarentena** `name_quarantine_review` + painel `NamePropagationPanel` (escolher/fundir/dispensar) +
  endpoints `/names/*`. Gatilhos F&F + botão "Aplicar propagação". Dry-run: 494 cobertas, 104 preench., 9
  quarentena; troféu 293321688 12/12. +11 testes.

**✅ CORE CURADO — Fases 1-3 LIVE (`d9c504f`→`dc20ad1`→`2c8fe8a`).** Falta só o **wipe+reimport** (teste de
aceitação: as tagadas GG entram desanonimizadas à primeira). Escolhas de scope registadas: preenche só
brancos (upgrade fraco→forte = futuro); Gold-só usa o botão "Aplicar propagação".

**DRY-RUN (laboratório atual, sistema misto):**
- **98 torneios GG tagados / 738 mãos tagadas.** 80 têm ≥1 semente FORTE; 18 sem semente (propagação dá 0 → branco honesto).
- **437 mãos tagadas ficam 100% desanon-forte após propagação**; **ganho de +44 mãos NOVAS** (não estavam completas antes).
- **Só 24 hashes em branco honesto** e **25 em quarentena** — de 738 mãos. Conflitos genuínos (após colapsar truncação/OCR): **17**.
- **DOIS tipos de conflito:** (i) **9 "mesmo-hash→nomes-dif"** = variantes OCR do MESMO nome (`wvvMasteRwvw`/`wvwMasteRwvw`,
  `Footloose`/`Footlose`) → **não são conflito real**; expõem necessidade de **dedup fuzzy dos reads da Vision** (auto-merge
  ou 1-clique). (ii) **8 "nome→2-hashes"** = mesmo nome em 2 hashes diferentes (`Juan Marquez`, `Otto274`) = **veneno genuíno**
  (pelo invariante, 2 hashes = 2 pessoas → 1 está errado) → guarda (b) a fazer bem o trabalho, quarentena correcta.
- Concentração: quase tudo em 2 torneios grandes (`292758023` 62 tagadas/34 fortes; `292179612`). O critério de sucesso
  real é o **reimport** produzir as tagadas desanon à primeira, não os números do laboratório (que vai ser apagado).

## ★ pt97 (1 Jul 2026, Web) — pós crachá/guardião/tags/saúde GG

- **Fase 2 da "Saúde das mãos GG" (ações):** hoje a secção só MOSTRA (Fase 1, `a3deb74`). A Fase 2 traz as ações e **absorve a "Marcadas por captura"**: tag de **1-clique** (11 tags canónicas), **corrigir nomes** (via `/set-anon-map`), confirmar **unverified→verified**, e **propagação de nome por hash no torneio** (1 confirmação → ~3 mãos tagadas; o hash segue o jogador entre mesas — `DESANON_ANATOMIA §3.3`). Herdar: estado `capture_triage`, `folder_ft_source`, `apply_villain_rules`.
- **2 mãos de CAPTURA TROCADA por resolver** (a captura pertence a outra mão — não é erro de nomes): `GG-6104057685` (dona verdadeira `GG-6104057552`, hoje sem captura) · `GG-6105043278` (dona `GG-6105043116`). **Bloqueadas por 2 primitivas que NÃO existem:** (1) **"reverter uma mão a anónima"** (repor `player_names={}` + apa hash-keyed do raw + limpar villains + `context_table_ss_id=NULL`) — hoje tirar a captura NÃO reverte, a mão fica com o anon_map errado; (2) **guarda que protege `position_v3`** (`_REAL_MATCH_METHODS` só tem `anchors_stack_elimination_v2` → ligar uma captura IT a uma mão gold **clobbera** o position_v3). Só depois destas duas é seguro religar a Gold/IT certa.
- **2 mãos em CONFLITO DE TAGS (formato)** a resolver — a mesma mão (`GG-6117985931`) com `icm` (não-PKO) + `icm-pko` (PKO). Ver R1 em `TAGS_CANONICO.md`.
- **Enforcement das 2 regras de incompatibilidade de tags** (R1 formato, R2 fase) — definidas em `TAGS_CANONICO.md`, hoje só **sinalizadas** (Saúde GG), não impedidas na escrita.
- **Decisão Gold-vence-IT — via premium:** onde o IT falha (captura trocada / nomes por verificar), **descarregar a Gold** dessa mão (casa 1:1 exato). 0 Golds à espera nas 382 só-IT; é acção manual do Rui.
- **2 buracos novos destapados (2 Jul, editor Saúde GG):** (1) **excluir jogador que não jogou** — o `players_list` guarda o sentado-sem-cartas (ex. `Afonso Neto` em `GG-6083771298`, coroa 0.0) e a **guarda de suspeitas (`suspicious.py`) lê `players_list`** → falsa `bounty_below_half` (floor 25); falta primitiva "excluir do players_list" OU a guarda só contar seats mapeados (`anon_map.values()`). (2) **confirmar coroa <½-base como legítima** — `detect_bounty_below_half` é pura/live, SEM whitelist; falta flag persistido (`bounty_confirmed`) que a guarda respeite. Ambos entram no **editor por-mão do Saúde GG** (desenho 2 Jul, à espera de aprovação do Rui — não codificar antes).

## ★ 1 Jul 2026 — pendências pós-frentes (bounties + desanon por âncora)
- **Build do watcher (foco + guarda de TEMPO):** o foco (`#HRC-FOCUS-ROBUSTNESS`, `049cd4b` em `watcher-gate`, NÃO buildado) + a **guarda de tempo** (teto **5h/1ª run** decidido; falta o **print do painel do HRC com o tempo** + escrever o OCR do tempo em `tree_stats.py`) — **um build só** com `min_children=60`.
- **Pontas dos bounties (histórico):** **1 presa** (`GG-6102580840`, seat `G Sieemshchikov` — reread OCR l/i não casou) + **2 por rever** (`6101135610` parcial, `6104865113` sem imagem em Transferências) + **5 seats truncados**. Consertam re-lendo a coroa certa.
- **Desanon por âncora — VERIFICAÇÃO VISUAL do Rui** das 14 (fichas de verificação geradas: hand/torneio/hora + seat a seat + âncora que resolveu). + o `arieloo` (bounty a **verde** na coroa do `mirroring`, `GG-6114944767`).
- **Inventário Vision:** 4 pontos Claude Sonnet 4.6 (table-SS, replayer, lobby, backoffice) + 1 OCR winsdk (`tree_stats`, watcher). Rever qualidade/prompts de cada.
- **Guardião de validação automática** (pedido do Rui): detectar `bounty < base÷2` / vilão=nome do Hero / desanon `review_alarm` e **alertar** (não deixar passar em silêncio). **v1 construída** — secção **"Mãos suspeitas"** (endpoint `GET /api/suspicious-hands`, page + badge na sidebar) cobre os **2 venenos PUROS** (bounty<½ ≈91 · nome-do-Hero-num-vilão =6). Falta: **veneno 3 (`review_alarm`)** — não é persistido, precisa de coluna/log próprio para ser listável.
- **Reorganização da barra lateral (pedido do Rui):** o Rui quer **reavaliar a disposição/organização da sidebar mais tarde**, quando a app estiver ao gosto dele (ordem/agrupamento dos itens — ex. juntar as filas de revisão «Marcadas/captura» + «Mãos suspeitas»). Não mexer agora; só quando ele pedir.
- **8549 (`#STUDY-STATE-REGRESSION-HH-IMPORT`):** Opção A (deixar). Opção B só COMPLETA (3 peças) em sessão dedicada — ver TECH_DEBTS.

## ★ pt91 (26–27 Jun 2026) — FECHO DE DIA (import Junho + Vision + fix posições HRC + GTO Nível 2 mapa técnico)

> ⚠️ **Reconciliação com a nota ditada do Rui:** 2 itens da nota de fecho avançaram NESTA
> sessão e a redacção dela ficou stale — registado o estado **verificado** (confirmar):
> **(item 3)** o `GG-6101135610` foi **diagnosticado e Fase 1 corrigida** (`8c9ef66`) — é o
> `#POSITION-LABELS-PYTHON-JS-DRIFT`, **NÃO** money-vs-BB (descartado: stacks corretas em BB);
> **(item 7)** o import `--ao-vivo` 21–26 Jun **FOI corrido e concluído** nesta sessão.

### ✅ Feito/confirmado nesta sessão (verificado)
- **#POSITION-LABELS-PYTHON-JS-DRIFT Fase 1** (`8c9ef66`, deployed) — label do 1º a agir 6-max
  `MP→UTG` em `_POSITION_LABELS_BY_N[6]`. Corrige o `GG-6101135610` (UTG ~3,3 BB: dava
  `R 2.00 + R 3.16`, passa a só `ALLIN`). +7 testes migrados; prova local `SIZES_OPEN_UTG=['ALLIN']`.
  Ver entrada no `TECH_DEBTS`.
- **Import 21–26 Jun `--ao-vivo`** corrido e concluído (~1968 ficheiros em `done`: mesa 1145,
  lobby 457, gold 315, mãos/TS). Fora-da-janela (datas ≠ 21–26) saltadas, como esperado.
- **Vision destrancada** — a IA Anthropic estava **sem créditos** (todas as chamadas 400
  "credit balance too low"); após recarga do Rui, backfill `POST /api/screenshots/vision/backfill`
  processou as 244 pendentes → **SS sem match 145 → 0**; gold ligadas às mãos.
- **Lobbys**: 303/319 casaram (95%); os 16 pendentes são capturas inválidas/lixo (login,
  "late registration", WPN com data partida) — não casam por não terem torneio real. **ZENITH**
  (Winamax, lobby 15 Jun) fica `tm_not_found` porque **não há mãos ZENITH de 15 Jun** na app
  (só 16/21/22/23/25/26) — falta-lhe a edição desse dia, não é bug.
- **Nível 1 (badge HRC na Estudo)** — **JÁ EXISTE desde pt69**, funciona (provider envolve
  `Hands.jsx`; `HrcStateBadge` em `HandRow.jsx:241`; `/api/queue/hrc/states` devolve
  `concluída/na fila/falhou`; vocab bate). **Nada a fazer.** Estado prod: gate **ABERTO**,
  **71 mãos resolvidas (done)**, 36 por resolver, 17 falhou, 373 não enviadas.
- **#APPIMPORT-DATE-FILTER-IT-GOLD** (item 5) — FECHADO (`de2fa18` + `d3bdfa2`). [já registado abaixo]
- **#HRC-NODE-OFFSET-IMPLICIT-LINES** — confirmado **já FECHADO** (`8096f3c`, pt86b); a nota
  "fila travada por este bug" (pt67) está **stale**. A fila está aberta; ~0 solves era falso.

### EM ABERTO — para retomar amanhã
1. **GTO Nível 2 (mostrar estratégia HRC na mão + NAVEGAR a árvore)** — **decisão tomada** (Rui):
   o MEU spot + navegação multi-spot, com a **solve exata 1:1**. **Mapa técnico FEITO (leitura):**
   a navegação da tab GTO (`ReplayerPage.jsx`) **NÃO está presa ao match** — `POST /api/gto/navigate`
   e `getNode` só precisam de um `tree_id`; o `gtoApi.match` (l.287) é apenas a fonte do `tree_id`.
   **Desenho ideal:** parsear a solve 1:1 (`hrc_jobs.result_zip` → `parse_hrc_zip()` já existe) para
   uma árvore `gto_trees` **própria**, ligá-la à mão (coluna nova `source_hand_db_id`), endpoint
   `GET /api/hands/{id}/gto-tree` → `tree_id`, e no frontend usar **esse** `tree_id` em vez do
   `bestMatch.tree_id` (fallback ao match para mãos sem solve). Reaproveita `parse_hrc_zip`,
   `gto_trees/gto_nodes`, `/navigate`, `/node` e a tab GTO inteira. **3 DETALHES POR DECIDIR:**
   (a) **excluir** as árvores por-mão do `/match` difuso (`AND source_hand_db_id IS NULL`);
   (b) **storage** — descartar o zip bruto após parsear ou manter para auditoria;
   (c) **solves "stale"** pré-correções (offset pt86b + posições pt91) — re-gerar as antigas.
   **FALTA: a proposta de implementação faseada.** NÃO construído.
2. **(item 3 resto) Sizes em stack curto** — UTG **FIXO** (Fase 1). **Por verificar:** o caso
   **BTN <5BB** (nota Rui) também a dar 2 sizes — provavelmente **causa distinta** (o BTN já
   normalizava `BTN→BU`, a Fase 1 não o muda). **Fase 2** (n=7/8/9, drift estrutural + `EP/UTG1`)
   aberta. Ver `#POSITION-LABELS-PYTHON-JS-DRIFT`.
3. **(item 4) OCR pt90 não dispara** — *(fio do Code principal, branch `watcher-gate`)*. Diagnóstico
   Beelink: solves grandes/reais não registaram nodes/GB; **0 OCR em log nenhum de sempre**. Causa
   provável: call-site do OCR **não alcançado** no `.exe` (chamada ausente do fluxo OU try/except a
   engolir). Por achar no código-fonte do watcher. *(Não tocado nesta sessão.)*
4. **(item 7 resto) HM3 — 6 dias por importar** *(operacional do Rui)*. O appimport faz-se à mão
   (`python app_import.py --ao-vivo --desde 2026-06-21 --ate 2026-06-26`, salas fechadas), **NÃO** o
   RunAll/appmaster (força Discord). O **import de mãos GG/IT/gold** já foi nesta sessão; **falta o
   HM3** (mãos WN/PS/WPN dos 6 dias). *(Nota: o HM3 já foi corrido pelo Rui a meio da sessão p/
   destrancar os lobbys WN; confirmar cobertura dos 6 dias.)*
5. **(item 8) Fila partilhada — 5 pessoas do backer team a partilhar o Beelink** (recepção→HRC→envio).
   FUTURO, sem pressa. Em discussão: regra de fila (à vez vs pequena-primeiro) + realidade de
   1 máquina / 1 mão de cada vez. **Depende do OCR (tamanho da árvore) funcionar.** NÃO começado.

### ✅ Fechado hoje (confirmado, não reabrir)
- **(item 6) Reinício do HRC a cada 5 mãos** — confirmado a funcionar no pt90 (**falso alarme**).
- **(item 5) #APPIMPORT-DATE-FILTER-IT-GOLD** — `de2fa18` + `d3bdfa2`.

---

## ★ pt90 (25 Jun 2026) — watcher OCR tree-size: instalar `watcher-pt90` + smoke end-to-end

`#HRC-TREE-GIGANTE` **fix shipped** (`watcher-gate` `9609ab6`+`7384ed2`; Release `watcher-pt90`).
Source + harness + OCR (smoke #1 no Beelink) + bundle do `.exe` **verificados**. **`.exe`:**
SHA256 `69e741c2f8b80e3f1323aaa1fe6150adb046d3b83ef87debadf7613321cc673c` (32 988 546 B);
Release https://github.com/ruikoko/poker-app/releases/tag/watcher-pt90.

**Instalado no Beelink — REPORTADO pelo Rui (26 Jun):** o `.exe` `watcher-pt90` (SHA acima) foi
instalado; o **pt87 foi guardado em `C:\hrc\backup_watcher`** como rollback. ⚠️ Nota: um backup do
exe anterior no Beelink **fricciona com a regra «1 só watcher exe»** (o histórico devia viver no
PC+git) — registado aqui para não se perder; decidir se `C:\hrc\backup_watcher` fica ou se limpa
depois do smoke OK. *(Estado da instalação por confirmação de SHA round-trip no próprio Beelink.)*

**Smoke happy-path — 1ª tentativa (26 Jun), NÃO concluída.** A 1ª mão (`GG-6083866641`) caiu no
**ramo `tree=0`** → o OCR **não disparou** (ver `#WATCHER-OCR-NOT-READ-ON-TREE-ZERO-BRANCH` em
`TECH_DEBTS`). **Esclarecido: NÃO era gigante** — árvore **~2 GB** (os **8.6 GB** eram **RAM do
processo**, não a árvore); os **33 min** são **normais** para o perfil **MP/multiway** (confirmado
no histórico: solves longos são todos early/multiway HJ). **Sem falha de guarda, sem drama**; mão
em `C:\hrc\queue_hold`, **recuperável**. **FALTA:** correr o happy-path com uma mão de **árvore
média** que dispare **"tree estável" limpo** (e ver `nodes/gb` no `meta.json` + `ocr_ok:true`).

**Falta (operacional, Rui+Web no Beelink):**
1. ~~Descarregar da Release + confirmar o SHA256~~ / ~~Instalar no Beelink~~ — **reportado feito** (ver acima; SHA round-trip a confirmar no Beelink).
2. **Smoke end-to-end no `.exe`:** (a) mão normal corre; (b) tree gigante forçada → `.failed`
   com motivo "tree gigante: X GB > 15"; (c) OCR forçado a falhar → corre na mesma (`ocr_ok:false`).
3. Só depois de (2) OK: dar `#HRC-TREE-GIGANTE` por **fechado** e ponderar merge `watcher-gate`→`main`.

## ★ `#WATCHER-JANELA-DE-TRABALHO-ETA` (FUTURO, URGENTE) — janela de trabalho + travão por ETA/custo

**Ideia:** definir uma **janela de trabalho** (ex.: 8h) e o watcher **gerir a fila** para a encher
da forma mais produtiva, usando o **ETA da janela "Monte Carlo Sampling" do HRC** como **travão em
tempo real** (*Via C*). Liga-se ao pt90 (captura OCR) — **reutiliza a mesma infra** de OCR de
janela do HRC (`tools/watcher_src/tree_stats.py`, PrintWindow + `Windows.Media.Ocr`).

**Comportamento desenhado até agora:**
- O watcher **lê o ETA assim que aparece** (logo após o Finish, no início do solve).
- **Critério de corte: POR FECHAR** — decidir entre **teto fixo por mão + margem no fim da janela**
  (recomendado) vs. **só tempo-restante**.
- **Mão saltada** (ETA grande de mais) → **marcada para OUTRA janela** (mais longa), **NÃO se perde**.
- **Se o ETA crescer depois de começar:** comportamento **POR DECIDIR**.

**Obstáculos conhecidos (registar):**
1. O ETA **só aparece DEPOIS de o solve começar** (visível na barra ~13%), **não antes** → não dá
   para **ordenar à partida**, só **travar em tempo real**.
2. Percorrer N mãos só para **"espreitar" o ETA** de cada uma **CONSOME tempo real da janela** →
   viabilidade depende de **quanto custa ler o ETA por mão** (**medição pendente no Beelink**:
   setup→Finish, Finish→ETA estável, overhead de troca de mão).
3. Ler o ETA exige **OCR da janela "Monte Carlo Sampling"** — **ainda NÃO testado** se essa janela
   se lê (pode ser opaca, como o painel Tree Statistics era; talvez precise do **mesmo PrintWindow**).
   **Validação pendente.**

**SINAIS PRECOCES DE CUSTO (ideia Rui — alternativa/complemento ao ETA, que é caro):**
em vez de esperar o ETA estabilizar (obriga a **gastar solve** por mão), usar sinais que aparecem
**MAIS CEDO** como proxy do tamanho/tempo da tree:
1. **Tamanho da tree (nós/GB)** — **JÁ lido por OCR antes do Finish** (pt90). O **mais precoce**.
2. **NOVO (Rui):** o **tempo de espera até à 1ª run** / a **lentidão dos primeiros instantes** do
   Monte Carlo Sampling **correlaciona com o tamanho da tree** → dá pista do custo **antes** de o
   ETA estabilizar.
3. **ETA estabilizado** — o **mais tarde e caro**.

**Implicação:** a "janela de trabalho" **pode talvez dispensar a leitura cara do ETA** e gerir-se
pelos **sinais 1+2** (baratos, precoces). **A validar** quando se medir no Beelink
(setup→Finish, Finish→1ª run, evolução do ETA) — **cruzar os 3 sinais contra o tempo real de mãos
conhecidas** para ver qual prevê melhor.

**Alternativa a considerar — *Via A*:** **ordenar pelo TAMANHO da tree** (que já lemos por OCR
**ANTES** do Finish, sem gastar solve), como **proxy do tempo**. Pode ser melhor que a *Via C* se a
leitura do ETA for cara.

> Estado: **FUTURO/URGENTE — medição pendente no Beelink**. Não construir antes de medir os 3 sinais.
> Cross-ref: pt90 (`#HRC-TREE-GIGANTE`, infra OCR), `TECH_DEBTS_INVENTARIO.md` (secção homónima).

## ✅ FECHADO (`de2fa18`, 26 Jun) — `#APPIMPORT-DATE-FILTER-IT-GOLD`

**Construído e validado.** O `gold` era o **único gap** de cobertura de janela; depois do fix, as
**5 fontes de imagem** (`manual`, `it`, `lobby`-subpasta, `gold`, `LOBBY_DIR`) respeitam
`--desde/--ate`. `process_gold_dir` ganhou `window=` e filtra pela **data do NOME** (helper
`_gold_name_date`, regexes alinhadas com `screenshot._parse_filename`; **decisão pt91: data/hora de
download = de jogo** → a objecção download-vs-play dissolveu-se). Nome sem data/hora legível →
**incluído por defeito + aviso** ("na dúvida inclui"). Conta/reporta `fora da janela` no resumo.
Critério não-uniforme **por desenho**: data-do-nome onde existe (`it`, `gold`); `mtime` onde o nome
não tem data (`manual`, `lobby`). **Dry-run `--desde 2026-06-01`:** gold **325 dentro / 89 fora**
(Março), fronteira dia-de-jogo 15:00 correcta, **0 avisos**. **Tool-side, sem deploy** → `git pull`
na máquina do appimport. Detalhe em `TECH_DEBTS pt91`. Mantém-se o registo da investigação original abaixo.

Pedido do Rui: filtrar `--desde/--ate` também por **data do NOME** do ficheiro nas fontes de
imagem `it` e `gold`, para **não ter de mover ficheiros à mão por data**. **Investigação read-only
feita (26 Jun):**

- **`it` — JÁ FUNCIONA, nada a fazer.** O filtro `--desde/--ate` já se aplica aos `it` e já lê a
  data **do NOME** (`classify_it_file` extrai `YYYYMMDDHHMMSS` da cauda `-YYYYMMDDHHMMSS-NN`;
  `_img_date(path, captured)` em `process_it_mixed`). **Provado** correndo as funções sobre nomes
  reais: 22/06 e 25/06 saem **FORA**, 23/06 **DENTRO** com `--desde/--ate 2026-06-23`. (Formato
  novo `GGnet.exe-<Título>-<YYYYMMDDHHMMSS>-<NN>.png`; antigo `Shot<N>-<Site>-<YYYYMMDDHHMMSS>` →
  `_OLD_SHOT_RE`, também com data; nome sem data → SKIP, nem é enviado, ou fallback a `mtime`.)
- **`gold` — FALTA. É o único gap.** `process_gold_dir(session, live)` **não tem parâmetro
  `window`** e é chamada sem janela (de propósito: "SEM filtro de mês"). Os nomes gold/manual são
  `YYYY-MM-DD_ HH-MM_AM|PM_$SB_$BB_#TM.png` (data **no início**, hora **12h AM/PM**).
  **Mudança** (1 ficheiro, `tools/appimport/app_import.py`): helper `_gold_name_date(fname)`
  (regex `^(\d{4}-\d{2}-\d{2})_\s*(\d{2})-(\d{2})_(AM|PM)` → datetime 24h, **fallback a `mtime`**
  se não casar, para nunca descartar em silêncio) + `process_gold_dir(..., window=None)` + passar
  `window=img_window` no `main()` + contagem "fora da janela".
- ⚠️ **Decisão de produto POR FECHAR antes de construir:** a data do nome gold/manual é a do
  **DOWNLOAD**, **não** a hora de jogo (`#GG-DOWNLOAD-IMG-FILENAME-TIME-AND-BLINDS-UNRELIABLE`).
  Para "não enviar meses antigos" serve (≈ `mtime`, que o `manual`/`lobby` já usam); se o objetivo
  fosse filtrar pela **hora a que a mão foi jogada**, o nome do gold **não** ta dá. Confirmar o
  objetivo antes de desenhar.
- **Contexto (mudança de hoje):** o `GOLD_DIR` do `config_local.py` passou de `Documents` (raiz)
  para a **subpasta dedicada `Documents\Gold`** — `config_local.py` é gitignored, mas o
  `config_local.example.py` foi alinhado (a raiz era perigosa: o read é **não-recursivo** e
  enviaria **todas** as imagens da pasta). Ver `#GOLD-DIR-DEDICATED-SUBFOLDER`.

> Estado: ✅ **FECHADO** (`de2fa18`, 26 Jun) — ver topo desta secção. A decisão download-vs-play
> foi tomada (pt91: download = play na prática) e o fix shipped.

**Import de mãos — mapa levantado, por EXECUTAR (26 Jun).** As pipelines de entrada estão todas
mapeadas: **`RunAll.bat`** (appmaster → appimport + HM3 + Discord, um clique) · **`ImportAoVivo.bat`**
(só appimport: `gg_hh`/`gg_ts`/`manual`/`it`/`lobby`/`gold`) · **`Import.bat`** (dry-run de ensaio).
A **execução real** fica para amanhã (regra de sessão: **salas fechadas**). Ordem embutida no
appimport (HH→TS→imagens→lobby→gold) + reconciles automáticos no servidor; ver também a ordem
gold↔HH em "★ pt75 — operacional".

## ★ pt88 (24 Jun 2026) — 2 fixes em prod + reclassificação do study-state

- ✅ **`#POST-TABLE-SS-MOVE-EM-VISION-FAILED`** (commit `c5a2a29`, origin/main) — table-SS `vision_failed`
  deixa de ser movida com ✓ falso; passa a `retry` (fica, re-envia no próximo run), paridade com o
  lobby. Tool local appimport, sem deploy. (Detalhe em `TECH_DEBTS pt88`.)
- ✅ **`#include_no_payout-mismatch`** (commit `078072f`, deploy Railway SUCCESS) — `/hrc/release`
  alinhado a `include_no_payout=False`; mão sem payout **rejeitada com motivo claro**
  (`sem payout — não pode ir ao HRC (torneio sem estrutura de prémios)` no tooltip de "ignoradas")
  em vez de **released-fantasma** presa sem nunca correr.
- 🟢 **`#STUDY-STATE-REGRESSION-HH-IMPORT` reclassificado — NÃO é bug.** As não-GG (PS/WN/WPN) são
  mãos de estudo → `'new'`/Estudo é **correto e documentado** ("PS/WN/WPN HH sem SS → Estudo directo").
  A premissa "deviam arquivar" vinha da spec pt27 "Duas pistas", que era **só para GG anonimizada**.
  Só a **GG bulk** tem mislabel cosmético (`'new'` vs `'mtt_archive'`) **sem sintoma** (escondida do
  Estudo pelo gate `match_method`; visível em Torneios na mesma). Acionável = **só doc, sem backfill**;
  nota acrescentada à spec "Duas pistas" no `CLAUDE.md`. (Detalhe em `TECH_DEBTS pt88`.)

## ★ pt87 (24 Jun 2026) — verify-gate do save-as FEITO + VALIDADO EM PRODUÇÃO; 3 problemas novos do smoke

**`#HRC-WATCHER-SAVE-NOT-PERSISTED` ✅ FEITO + VALIDADO EM PRODUÇÃO (24 Jun).** Causa: o
`_close_hand_tab` (Ctrl+F4) corria contra o write assíncrono do Complete Export (40-70 MB) e
**cancelava o save** → 0/38 mãos persistiam, watcher preso 24h. Fix (watcher-gate `6522278`):
`_verify_export_zip` passa a **barreira** (existe + tamanho estável + `testzip`) que gateia o
close-tab; trata overwrite; 1 retry; em falha `.failed`+avança; `EXPORT_WAIT_TIMEOUT` 24h→30 min.
Harness 19/19. Exe `e1dced5a` (Release `watcher-pt87`) **instalado no Beelink e validado**: a WN
de 36 MB drenou ponta-a-ponta com `[SAVE-AS-CHECK] OK`; lote a drenar (33+). É o **1º exe a conter
de facto pt84 (watchdog) + pt85 + pt87** (a Release `watcher-pt84` enviara o exe pré-pt84 `5e1414`).

**Reconciliação — saem do backlog (✅ FEITO + validado no smoke pt87 24/06; código no `main` + no
exe que correu hoje):** `#HRC-WATCHER-TAB-ACCUMULATION`, `#WATCHER-LOG-TO-FILE`,
`#HRC-CLOSE-TAB-BREAKS-CHORD-FOCUS`, `#OPEN-WIZARD-CHORD-FALLBACK-BLIND`,
`#HRC-RUN-WINDOW-DETECTION-BLIND`, `#HRC-BOUNTY-HARDCODED-50PCT`,
`#HRC-REDUNDANT-SECOND-RUN-OLD-CONFIGS`, `#CI-TARGET-INITIAL-NOT-CALIBRATED` (8 itens watcher
pt66-70 que estavam listados "re-smoke pendente / fix em buffer").

**3 problemas NOVOS do smoke 24/06 (detalhe em `TECH_DEBTS pt87`):**
- 🔴 `#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN` **REABERTO / REGRESSÃO** — a 2ª run não dispara
  o popup Nash (estava fechado em pt32-34; voltou). **Investigar porque o fix antigo deixou de pegar.**
- 🟠 `#HRC-EXPORT-DIALOG-32770-NO-OPEN` **NOVO** — o diálogo Export Strategies (`#32770`) não abre
  (≠ popup Nash, com que partilha a classe).
- 🟢 `#HRC-TREE-GIGANTE` **FIX SHIPPED em pt90** (Release `watcher-pt90`) — guarda preventiva
  construída (OCR do painel "Tree Statistics" + abort por dupla leitura, ANTES da 1ª run). Falta
  só o **smoke end-to-end no `.exe`** (ver "★ pt90" no topo).

**Continuam pendentes (não tocados pelo pt87):** `#HRC-ADAPTER-STATE-DESYNC-SILENT` (🔴, abaixo),
`#HRC-WATCHER-BETTING-SCRIPT-STALL` (🟠, abaixo), `#HRC-ANCHOR-NONBLIND-LIMP` (Passo 2, abaixo).

## ✅ FECHADO (pt89, `bf2da9a`, deployed) — `#HRC-ADAPTER-STATE-DESYNC-SILENT`

**Era 🔴 HIGH diferido.** Causa-raiz operacional resolvida do **lado do servidor**: o
re-envio (`POST /hrc/release`) usava `ON CONFLICT DO NOTHING` → re-enviar uma mão já
libertada era no-op, o `requeue_epoch` não subia, e o adapter saltava-a em silêncio
(`hrc_adapter.py:262`). **Fix:** `ON CONFLICT DO UPDATE` incrementa `requeue_epoch` (+1)
no re-envio → `served_epoch > stored` → o adapter re-puxa sozinho e loga `re-queue`
(mecanismo pt83, já existente). Release fresco = epoch 0 (adapter puxa na mesma). **Sem
mudanças no adapter, sem rebuild.** Consumidor único verificado (manifest → dedup do
adapter). +teste `test_release_rerelease_bumps_epoch`. Ver `JOURNAL_2026-06-25-pt89.md`,
`TECH_DEBTS pt89`.

As opções (a)/(b)/(c) abaixo (robustez do `state.json` no adapter) ficam **dispensáveis**
para o sintoma real (re-envio não corre); só voltam a interessar se aparecer um desync de
outra natureza. Registo histórico do plano:

**(diferido — robustez adicional do adapter, não necessária agora).** O adapter saltava em silêncio mãos que já constavam do
`state.json` local mesmo quando o servidor as volta a oferecer (dedup `hrc_adapter.py:262`);
fica em "entering main loop" a puxar 0 — opaco para o Rui. O "Disparar" da app não toca no
state local → desencontro garantido. **Já não há razão para o skip permanente:** desde o
pt43 o servidor já exclui as `done`, por isso o que ele serve **precisa mesmo** de correr.
**Plano (não implementar até o Rui aprovar):** **(a)** auto-reconciliação — confiar no
servidor e re-puxar, com guarda de in-flight + cooldown pós-done (custo BAIXO-MÉD, adapter
Python puro sem rebuild, exige smoke Beelink); **(b)** aviso claro em PT na consola quando
salta N mãos (custo muito baixo — pode entrar já); **(c)** ressincronizar sem mexer em
ficheiros (sentinela `RESYNC`, custo baixo; ou botão na app, custo méd-alto, dispensável com
(a)). **Recomendado: (a) + (b).** Objetivo: o Rui nunca mais tocar no `state.json` à mão.

## ★ pt86c — bug do robot: stall no betting script (`#HRC-WATCHER-BETTING-SCRIPT-STALL`)

**NOVO** (ver `TECH_DEBTS pt86c`, `JOURNAL_2026-06-23-pt86c.md` fecho 24 Jun). Na validação
visual do Passo 1 do anchor (**as 2 mãos CONFIRMADAS à vista ✓**, âncora no BTN), o robot
**encravou (STALL)** no passo de seleção do **betting script** na GG-6083363843 (3-max):
janela Open/Browse **aberta e pronta**, robot **parado sem avançar nem dar erro**, exigiu
**mão humana** (o Rui desencravou → a mão terminou). **Sem timeout nem recuperação.** Pista:
`setup_scripting` (`watcher_src/patched_funcs.py:912`) carrega o script às cegas + o
`_wait_for_finish_ready` (2480) sem saída se o Open dialog ficar aberto. **Investigar** esse
passo. **Distinto** do incidente do chord do wizard a falhar 2×→reinício (esse **recuperou
sozinho** — não fundir). Relacionado: arco **pt79 / hang-watchdog** atrás do gate (não
ativo). **Prioridade a definir pelo Rui.**

## ★ pt86c — Passo 2 do anchor: limp de não-blind (`#HRC-ANCHOR-NONBLIND-LIMP`) — ADIÁVEL

**Passo 1 do `#HRC-ANCHOR-FALLS-TO-ROOT-NOT-HERO` ✅ FEITO** em pt86c (commit, sem push;
ver `TECH_DEBTS pt86c` + `JOURNAL pt86c`). Regra do Rui aplicada: âncora = nó que governa
a 1ª decisão do Hero (open do próprio Hero / complete da SB; walk → skip). Cobre **6 das 7**
mãos sem-raise (5 Hero-open + 1 walk-skip; 0 Hero=BB-vs-SB-limp hoje). A moldura antiga
"decisão de produto Hero=BB / vs-limp" **dissolveu-se** (Hero=BB-vs-SB-limp ancora no
Complete da SB, que já existe).

**Falta só o Passo 2 — `#HRC-ANCHOR-NONBLIND-LIMP` (1 mão, mexe na árvore → exige smoke):**
o limp de **NÃO-blind** antes do Hero (#7 GG-6083363633, MP limpa, Hero=BTN folda atrás).
O template só modela limp da SB → não há nó. Fix em 3 peças:
- **template** `LIMP_POSITIONS` (default `[]`, override per-mão com o índice HRC do limper)
  + `canFlatCallPreflop` a aceitá-lo;
- **parser de limp** no gerador (`_parse_preflop_actions` hoje só emite raises);
- `count_lines_for_position` **limp-aware** (o bucket do limper ganha +1 linha Complete,
  desloca os offsets seguintes — hoje só a SB).

Confinado (`LIMP_POSITIONS=[]` nas outras = byte-idêntico), mas **toca a árvore → smoke
obrigatório**. Por **1 mão**; não bloqueia nada (fica fallback_root como hoje). **Não
construir até o Rui mandar.**

## ★ pt86 — RE-GERAR trees desalinhadas com a regra nova do ALLIN implícito (25/30)

`#HRC-NODE-OFFSET-IMPLICIT-LINES` ✅ corrigido e **pushed** (`8096f3c`): o template
(`mtt_advanced_canonical_2026.js`) passou de **30 BB geral** para **25 BB geral / 30 BB
só blind-vs-blind** no `shouldAddPreflopAllIn`, e o `count_lines_for_position`
(`hrc_node_offset.py`) passou a espelhar o template com a stack individual de cada
posição (limiar 25/30, colapso, Complete da SB) em vez de `len(array)`.

- **Consequência:** as trees **já geradas/resolvidas com o template 30-geral** (todas
  as do `hrc_jobs` até agora) ficam **desalinhadas** com a regra nova — o `script.js`
  que correu nelas usava 30-geral, logo a contagem de linhas / âncora da 2ª run
  podia divergir. **Re-geração futura no robot** (re-exportar com o template novo +
  re-correr) quando o Rui mandar e o robot estiver livre. **Não fazer agora.**
- Cruza com a re-corrida WN do `#DERIVE-MAX-PLAYERS-WINAMAX-COLON-BLIND` (PENDENTES
  abaixo) — quando se re-correr, é com **ambos** os fixes (max_players + template 25/30).
- GG/PS/WN/WPN todas afetadas (o template é cross-site). Não há corrupção de dados
  na app; é a qualidade da **tree/âncora** que melhora com a re-geração.

## ✅ FECHADO (pt89, `90c07ad`) — `#GTO-OPEN-SIZE-NOT-PER-POSITION`

**Era FUTURO; foi feito em pt89.** Os opens passaram a **per-posição** (cada não-blind
tem a sua var `SIZES_OPEN_UTG/UTG1/MP/HJ/CO`, como os 3-bets em pt42b); o gerador faz
override **só** ao bucket do opener real, as restantes ficam no default do template `[2]`.
Acabou a propagação pela var partilhada `SIZES_OPEN_OTHERS`.

- **Regra do Rui satisfeita:** só o **opener** usa o seu size real; posições **à frente**
  usam o standard **2 BB**; a **SB** usa o seu próprio size de blind; posições atrás
  (foldadas) indiferentes.
- **Smoke do gerador PROVADO (25 Jun, read-only, sem HRC)** — `GG-6084129607` (HJ abre
  2.0bb, eff 18.02bb): `SIZES_OPEN_HJ = [2, ALLIN]` (ALLIN confinado ao opener curto);
  `SIZES_OPEN_UTG/_MP/_CO = [2]` (fundos 36.9/32.5/49.5bb **limpos, sem allin**).
  **Contaminação confinada ao HJ.**
- **Falta só o smoke da ÂNCORA no HRC** (navegação real ao nó) — para mão que flua
  naturalmente; **não** soltar mão de propósito.
- **Não afetou o `#HRC-NODE-OFFSET-IMPLICIT-LINES`** (o valor do size não gateia o offset,
  só o comprimento/ALLIN do array).
- Detalhe: `JOURNAL_2026-06-25-pt89.md`, `GTO_BRAIN.md §9`, `TECH_DEBTS pt89`.

## ★ FUTURO (registar, sem fix agora) — `#BEELINK-DAEMONS-AUTOSTART`

Arranque automático dos daemons do robot no Beelink. **Estende/subsome o
`#HRC-ADAPTER-SCHEDULED-TASK`** (TECH_DEBTS, 🟢 LOW, que cobre **só o adapter**) — esta
visão é mais larga: **adapter + watcher + watchdog**.

- **O que já está feito:** o lado da **APP**. O Rui abre a queue na app e a app comanda o
  que o robot puxa (gate da fila pt68, multi-select, `GET /api/queue/hrc`). Esse fluxo
  funciona.
- **A dor (o que falta):** o arranque **no Beelink** é todo manual e frágil — arrancar o
  adapter à mão (`arranca_adapter.bat` / `venv\python hrc_adapter.py`), ligar o watcher à
  mão (`hrc_watcher.exe`), e o PATH/env que não persiste entre reinícios (visto nesta
  sessão: o Claude Code do Beelink e o `setx` na janela errada). E os daemons **morrem em
  silêncio** sem ninguém os levantar.
- **Visão:** adapter + watcher arrancam **sozinhos** (no boot/logon do Beelink, ou num
  único atalho/serviço), para o Rui **só ligar o Beelink e abrir a queue na app** — zero
  comandos à mão.
- **Candidato técnico (confirmado read-only, faz sentido):** **Scheduled Task do Windows
  "ao logon"** para os dois. **Caveat-chave:** o **watcher precisa de sessão interactiva
  com desktop** (conduz o GUI do HRC por rato/Win32) → tem de ser **task ao logon a correr
  como `riand`**, **NÃO um Windows Service** (sem desktop). O **adapter é headless** (HTTP +
  filesystem) e podia ser serviço, mas por simplicidade vai como task ao logon ao lado do
  watcher. Cadeia: Beelink liga → **auto-logon** `riand` → task(s) arrancam adapter +
  watcher → o `ensure_hrc` do watcher abre o HRC. O env (`HRC_WATCHER_API_KEY`) viaja na
  task (ou no `.bat`), matando a fragilidade do `setx`.
- **Watchdog (incluir):** relançar um daemon que **morra**. (a) "restart-on-failure" nativo
  da Scheduled Task apanha o fim do processo; (b) uma 2ª task em intervalo curto que
  **verifica liveness** (processo vivo?) e relança — apanha também o caso de morte
  silenciosa. ⚠️ **Distinto** do `pt84` hang-watchdog INTERNO do watcher (esse trata o HRC
  pendurado/OOM **dentro** do watcher; não relança o **processo** watcher se este morre).
- **Custo grosseiro:** **BAIXO-MÉD.** Config (schtasks/XML do Task Scheduler), **não código**
  nos daemons; + config de **auto-logon** (registo/netplwiz — nota de segurança: sem gate de
  password numa máquina dedicada, aceitável); + watchdog (pequeno script/2ª task). A maior
  parte é **operacional no Beelink** + 1 validação (reiniciar → ambos sobem → queue funciona).
- **NÃO implementar agora — só registado.** Instruções base do adapter já em
  `tools/hrc_adapter/README.md`; o `tools/appmaster/RunAll.bat` (bat-mestre) é ponto de
  partida para o "único atalho".

## ★ pt85–pt86 (22-23 Jun) — re-corrida das trees Winamax contaminadas

Contexto: `#DERIVE-MAX-PLAYERS-WINAMAX-COLON-BLIND` ✅ fechado (`b7c3b08`,
deployed) — ver `JOURNAL_2026-06-23-pt85-pt86.md` + `TECH_DEBTS_INVENTARIO.md`.
O fix corrige a **geração** (mãos WN novas já saem com `max_players` certo,
provado read-only sem robot). Falta **re-correr o que já está contaminado**.

1. **Re-correr as 7 trees Winamax contaminadas** (quando o Rui mandar, com o
   **robot livre**). Sequência: **apagar SÓ os `hrc_jobs` destas 7** (NUNCA a
   tabela `hands`) → re-exportar (já com `max_players` certo) → re-correr no
   Beelink. **Lista dos 7 `hand_id`:**
   `WN-4850168930850832386-8-1781543237` (GRAVITY, max 2→3),
   `WN-4850168930850832391-177-1781554111` (2→6),
   `WN-4778368858757005322-248-1781557719` (2→5),
   `WN-4778368858757005442-9-1781564008` (2→6),
   `WN-4778368858757005442-14-1781564568` (2→5),
   `WN-4853541992006680581-17-1781626609` (2→6),
   `WN-4853547261931552780-74-1781630020` (…780-74, 2→4).
   **EXCLUIR `WN-4853541992006680581-53-1781629653`** (já correta — SB-vs-BB
   genuíno, max=2 certo, **não contaminada**). As **GG (17 done) ficam como
   estão** (têm dois-pontos, nunca foram afetadas).

2. **Validação à vista da página de verificação HRC** (pendente anterior,
   continua) — só retoma **DEPOIS** de as 7 estarem re-corridas com max certo (a
   árvore navegável da GRAVITY só fica "boa" então: o flat-call do SB passa a ter
   o nó do BB). A **decisão do flat-call na UI** (deixar a opção CALL sem ▸ vs
   pôr uma nota tipo "→ vai a flop, multiway não modelado") fica para quando a
   árvore estiver boa.

## ★ pt80 (18 Jun) — equity model FT/MTT

- **Onde o Rui vê o alarme de validação do equity model** (`#EQUITY-MODEL-FT-VS-MTT-VALIDATION`).
  A validação `validate_equity_model_vs_table_ss` (a SS de mesa do IT valida o modelo
  que a tag decidiu) já corre e regista o conflito em **dois sítios**: `logger.warning`
  (`[equity-validation] ALARME …`) + `manifest.hands_included[*].equity_validation`
  (None ou `{kind, equity_model, players_left, seats_at_table, looks_ft}`). **Falta
  decidir ONDE o Rui o vê** — coluna/badge no painel `/hrc`, no Estudo, ou um painel
  próprio. **Pode mexer em schema/UX → desenhar COM o Rui** (não decidir sozinho).
  Tipos de alarme: `ft_tag_but_multi_table` (tag FT mas várias mesas),
  `mtt_tag_but_single_table` (tag MTT mas todos numa mesa). Hoje: 0 conflitos reais
  (scan 91 mãos com SS de mesa). Ver `JOURNAL_2026-06-18-pt80.md`.

## ★ pt78 (18 Jun) — HRC pacote vazio / payouts Winamax (lobby SS)

Contexto completo em `docs/JOURNAL_2026-06-18-pt78.md` (arco: pacote HRC vazio →
payouts Winamax → upload de lobby SS).

1. ✅ **RESOLVIDO (pt81) — `#WN-LOBBY-NO-AUTO-RETRY`.** As mãos WN entram pelo **.bat do
   HM3 (`import_hm3`)**, que — ao contrário do `import_.py` — **não** re-corria
   `reconcile_lobby_logs` → os lobbys ficavam `tm_not_found` mesmo depois de as mãos
   chegarem. **Fix:** `import_hm3` (hm3.py) passa a disparar o mesmo gatilho fire-and-forget
   `reconcile_lobby_logs()` (o relink de SS de mesa órfãs já lá estava) → caminho HM3 igual
   ao `import_`/`tournament_summaries`. Ver `JOURNAL_2026-06-18-pt81.md`.

2. **Avisar à entrada quando um torneio entra SEM payout (não-pronto p/ HRC).** Hoje
   descobre-se só por **pacote vazio**. Inclui resolver o **mismatch `include_no_payout`**:
   o `POST /hrc/release` valida com `include_no_payout=True` (`queue.py:186`) → liberta;
   o `GET /api/queue/hrc` puxa com `include_no_payout=False` (`queue.py:96→124`) → dropa
   em `missing_payouts`. Resultado: **libertada mas não puxável**. Decidir comportamento
   canónico (bloquear release sem payout, ou sinalizar "à espera de payout" no painel/gate).

3. ✅ **FEITO (pt81) — religação a sério do lote 16-Jun.** Reconcile **scoped** (novo param
   `message_ids` no `POST /api/lobbys/reconcile`) corrido a sério sobre os **14** lobbys WN
   tm_not_found do lote: **12 escritos** (7 torneios, source `reconcile_lobby_vision:`),
   **2 still** (LATE REGISTRATION misread + ZENITH 15-Jun sem mãos), precedência OK
   (0 manual/backoffice sobrescrito), 4 GG intactos. Ver `JOURNAL_2026-06-18-pt81.md`.

4. **`tm_not_found` por resolver.** Casos a triar: **2 GG Bounty Hunters**, **ZENITH 15-Jun**,
   **William Harding** (este possível **misread da Vision** no nome do torneio). Re-Vision
   ou desambiguação manual.

5. **`limpa_scratch.bat`: `arquivo\` access denied** (snag operacional, POR RESOLVER) — ao
   mover `arquivo\` para o backup. Provável permissão `riand`↔`Administrator` ou handles
   abertos. A tentar: correr como `Administrator` / fechar HRC+watcher antes / `robocopy
   /MOVE` com retry. → `tools/hrc_adapter/limpa_scratch.bat`.

## ★ pt75 (18 Jun) — operacional

- **Cobertura de HH (Março/Junho) do backoffice.** A desanon por `position_v3` está pronta e
  a lane gold (`GOLD_DIR`→`/api/screenshots`) também, mas as gold images da Documents só
  desanonimizam quando a **HH correspondente** existir na app. As HH de Março e de 16-Jun **não
  estão importadas** (vivem no backoffice do Rui). **Ordem recomendada:** importar a HH primeiro,
  depois correr a gold lane → `position_v3` no match directo (a ordem inversa também dá
  `position_v3` via re-link, mas precisa na mesma da HH). Operacional, não código.

## ★ Fila de arranque da pt73 (fecho pt72, 14 Jun)

**Contexto fechado em pt72 (não repetir):** o **replayer-image GG morreu** (SPA Angular
sem og:image, todas as idades — `#REPLAYER-OGIMAGE-DEAD-SPA`); screenshot/headless
**descartado** (pesado/frágil/ToS incerto). Desanon GG = **só table-SS do IT**. 3 features
shipped (`70a2919` botão Sincronizar histórico, `6b8d09c` janela de datas appimport,
`f539cef` Dashboard nome-clicável). Detalhe: `JOURNAL_2026-06-14-pt72.md`.

Para a pt73:
1. **★ Classificador de tags por PASTA do IT** — **AUTORIZADO** (Rui, pt72). Tabela:
   `ICM`→`icm`, `ICM PKO`→`icm-pko`, `PKO Pos`→`pos-pko`, `NPKO Pos`→**`pos-nko`**
   (canónica existente — o Rui propôs `pos-npko` mas órfão de 21 mãos `pos-nko`;
   recomendado `pos-nko`; aguarda 1 linha de confirmação da grafia). FT auto em todas
   as famílias (`len(seats)==players_left`; fail-safe sem `-ft` se incerto;
   `pos-pko-ft` unifica com `pos pko FT` existente — sem órfão). Construção:
   (a) appimport itera **subpastas** de `it\` + injecta tag; (b) `folder_tag` no
   `/api/table-ss/upload` → aplica a `discord_tags` da mão casada (como `capture_triage.tag`)
   + guarda no log p/ reconcile; (c) `ALLOWED_TRIAGE_TAGS` += `pos-nko` + variantes `-ft`;
   (d) FT `-ft` prudente. Diff ao Web antes do push. Ver `JOURNAL pt72 §E/§F`.
2. **Concluir o Discord de maio 15-31** (`#DISCORD-MAIO-15-31-PENDENTE`) — sync até 31-mai +
   processar o sem-replayer; GG-só-replayer ficam anónimas até haver table-SS.
3. **★ VALIDAR o `-ft` automático nas primeiras FT reais** (pedido do Web, pt72) — a regra
   `len(seats_ocupados)==players_left → +"-ft"` está LIVE mas **nunca foi vista numa mão FT
   real** (no lote das 64 GG, 0 eram FT). Quando aparecer a 1ª captura de mesa final
   (`it\…` com bancos==restantes), confirmar que a tag sai `…-ft` correcta (ex. `icm-pko-ft`)
   e que a contagem de bancos ignora vazios. Fail-safe activo (incerto → sem sufixo). Se a
   Vision contar bancos a mais/menos, rever o `_ft_applies`. → `table_ss.py:_ft_applies`.

### Ajuste pt73 ao classificador (14 Jun) — ✅ FEITO (diff ao Web; falta correr `--ao-vivo`)

- **Tabela alargada** (`IT_FOLDER_TAGS`): + `ICM PKO FT`→`icm-pko-ft`, `PKO Pos FT`→`pos-pko-ft`,
  `SpeedRacer`→`speed-racer`, `Nota`→`nota` (4 faltavam → 34 capturas entravam SEM tag).
  `ALLOWED_TRIAGE_TAGS` += `speed-racer`, `speed-racer-ft`.
- **FT dupla, prioridade MANUAL > AUTO**: pasta já com `-ft` = FT confirmado (não re-verifica,
  não duplica sufixo); pasta base = `-ft` AUTO via Vision. `_folder_tag_ft_source` devolve
  `'manual'`/`'auto'`/`None`.
- **✅ Distinguir `-ft` MANUAL vs AUTO na app** (aprovado pelo Rui, pt73): coluna nova
  `hands.folder_ft_source` (`manual`/`auto`/NULL; `ensure_capture_triage_column`); escrita no
  table-SS (`_apply_folder_tag_to_hand`) e na triagem manual (tag `-ft` clicada = manual). Badge
  **âmbar "auto"** ao lado da tag `-ft` no `HandRow`; filtro **"-ft auto"** na Estudo
  (`list_hands`/`tag-groups` param `folder_ft_source`) para o Rui rever as adivinhadas.
- **✅ `Nota` sem formato/pré-pós — RESOLVIDO** (decisão do Rui, pt73): a tag `nota` sozinha
  basta (→ Vilões, regra C). Sem família de formato nem fase. Questão fechada.

### ✅ RE-IMPORT do 14 Jun — RECUPERAÇÃO CONCLUÍDA (verificado 16 Jun, pt73)

No `--ao-vivo` de 14 Jun a **Vision falhou 100%** (166 capturas `vision_failed`, 39 lobbys
"transitório"). **Causa confirmada** (teste directo à API com a chave de prod): Anthropic
**`400 invalid_request_error: "Your credit balance is too low"`** — saldo a zero. **NÃO é o
deploy** `a894703` (ilibado: 8 capturas tiveram `success` antes do saldo acabar; serviço
saudável, migração `folder_ft_source` correu no boot; rollback não resolveria). O
classificador de pastas funcionou (tags certas em todas as subpastas).
- **Acção do Rui:** ✅ feito — créditos carregados na conta Anthropic.
- **Retrato (verificado read-only, 15 Jun):** **120 capturas de 14 Jun**, todas `vision_failed`,
  `attempt_count=1`, **com `folder_tag` (120/120) + `img_b64` (120/120) + `original_filename`**
  guardados no `table_ss_processing_log`. **0 mãos desanon** (Vision falhou → sem match → tag não
  propagou a `hands.discord_tags`). As 1495 HH GG de 14 Jun estão na BD. **Nada perdido.**
  ⚠️ **Correcção:** os ficheiros **FORAM movidos para `done\`** (não "ficaram nas pastas" — eu
  tinha dito mal); `attempt_count=1` ⟹ nunca reprocessados (o re-import pós-créditos não lhes
  tocou, já estavam em `done\`).
- **✅ Recuperação 14 Jun CONCLUÍDA (verificado 16 Jun):** **120/120** capturas em `success`,
  `img_b64` guardado. Preview `GET /api/table-ss/reprocess-failed` = **0 eligible** → **nada a
  reprocessar**. Créditos já carregados. A ferramenta de reprocesso server-side existe (re-corre a
  Vision sobre o `img_b64` guardado → match HH → `folder_tag` → desanon; idempotente, `file_hash`
  PK; sem re-feed de `done\`) mas **não foi preciso disparar** — as 120 já tinham passado a `success`.
- **Snapshot verificado (`table_ss_processing_log`, 16 Jun):** **262 linhas** — **261 success, 1
  no_match_to_hand (12 Jun), 0 vision_failed**. Por dia: 05/1, 08/15, 09/36, 11/36, 12/4 (+1
  no_match), 13/3, **14/120**, 15/46 — todas `success`.
- **Observabilidade (✅ pt73, commit a):** `extract_table_ss_json`/`extract_lobby_payout_json`
  propagam o erro REAL da Anthropic para `reason_detail` (ex. "credit balance too low") em vez
  do genérico "devolveu None" — o próximo caso é óbvio no `/import-health` sem ir à API.

### Discord ReadTimeout no mesmo import — `#SYNC-ENDPOINTS-SYNCHRONOUS-TIMEOUT` (pré-existente)

O Discord sync deu **ReadTimeout (300s)** no mesmo import. É **separado** da Vision e
**pré-existente** (pt68, `#SYNC-ENDPOINTS-SYNCHRONOUS-TIMEOUT`): endpoint síncrono a estoirar
o limite num lote grande. Não tem a ver com o crédito Anthropic nem com o deploy de hoje.
Backlog: tornar os endpoints de import assíncronos (job + polling) — fora do âmbito da pt73.

### 🟥→✅ 502 do servidor (15 Jun) — replayer GG morto a prender o event loop — FIX pt73

Após o re-import (com créditos), a app deu **502** (containers "Online", mas o worker único do
uvicorn **bloqueado**). Causa real (watchdog dumpou a stack do event loop 3×, fundo em
`httpcore/_sync/ssl.recv`): `process_replayer_links` é `async` mas chamava
`_extract_gg_replayer_image` **síncrono no event loop**, 1× por entry replayer GG pendente —
cada um um fetch a `gg.gl→pokercraft` que **falha sempre** (SPA morto, `#REPLAYER-OGIMAGE-DEAD-SPA`).
Em lote (14 Jun), centenas a fio congelaram o worker. **Não era OOM nem crash-loop; não era o
deploy.** Rui reiniciou → estável.
- **✅ FIX (pt73, commit b):** flag `REPLAYER_IMAGE_DISCOVERY` (env, **default OFF**) +
  short-circuit em `_extract_gg_replayer_image` (zero rede); a chamada em `process_replayer_links`
  passa a `asyncio.to_thread` (nunca no event loop) + early-return quando off; `preview` reporta
  `pending_extract=0` (botão "Sincronizar histórico" não entra em loop). Fecha o lado **replayer**
  do `#SYNC-ENDPOINTS-SYNCHRONOUS-TIMEOUT`; o refactor async geral dos endpoints de import fica
  backlog. Reversível por `REPLAYER_IMAGE_DISCOVERY=1` se a GG repuser og:image.

### 🟡 BUG appimport — `_post_table_ss` move para `done\` mesmo em `vision_failed` (registar, corrigir depois)

`tools/appimport/app_import.py:_post_table_ss` trata **qualquer HTTP 200 como sucesso** e o
appimport move o ficheiro para `done\` — mas o endpoint responde 200 mesmo em `vision_failed`.
Resultado: capturas que **não** foram desanon foram movidas (e o `done\it\` é **achatado**, perde
a subpasta = a tag). Foi isto que assustou o Rui no 14 Jun. **Correcção (não agora):** o MESA deve
imitar o LOBBY — em falha **não mover** (deixar nas pastas para retry), distinguindo `success` de
`vision_failed`/`json_invalid`/`no_match` na resposta. Ver `_post_lobby` (devolve `retry` e não move).

---

## ★ Feito em pt71 (13 Jun) — desanonimização por table-SS

**FECHADO (não repetir):** pipeline de desanonimização por SS de mesa em **6 estágios**
(deployed) + **votação cross-mão por torneio** (validada por forense: hash-fixo-por-torneio,
0 violações cross-torneio) + **64 mãos GG renascidas** com nomes reais (confirmação visual
do Rui) na fila `/marcadas-por-captura` + lightbox + guarda epistémica na Saúde do Import.
Commits `79677fe`…`9442729`. Detalhe: `JOURNAL_2026-06-13-pt71.md`.

Follow-ups LOW (não-bloqueantes): `#TABLE-SS-DEANON-VILLAIN-NOTES-STALE`,
`#TABLE-SS-DEANON-SINGLETON-UNVERIFIED`, `#PLAYED-AT-COARSE-GRANULARITY` (TECH_DEBTS pt71).

## ★ Fila de arranque da pt71 (fecho pt70) — HRC (não tocado nesta sessão)

**Fechado em pt70 (não repetir):** LEI §18 deployada LIVE (`7e7a68e`, SUCCESS) + `WN-…663`
→ `SIZES_OPEN_SB=[2.5, ALLIN]` confirmado a olho; `watcher-pt70` (exe `315CC2B5…D50C`)
**instalado no Beelink + smoke dirigida PASSOU** (escada validada no rung 2 na
`GG-6041753261`, transições limpas no rung 0, zero deadlock).

Genuinamente para a pt71:
1. **1º lote real disparado no gate** (`POST /trigger?count=N`) com o exe pt70 a correr.
2. **`#HRC-NODE-OFFSET-IMPLICIT-LINES`** — modelar o ALLIN implícito (regra 25 BB confirmada).
3. **Política CI/tempo da 2ª run** (`#HRC-2ND-RUN-CI-TIME-DISCREPANCY`).
4. **Mistério do chord SWT** (observação) — porque é que o chord `Ctrl+W,M` falha pós-fecho
   de aba mas nunca em cold start (o pt70 contorna com a escada; a causa-raiz fica por
   caracterizar — binding contextual SWT?).
5. **`#SECOND-RUN-NOOP-SILENT-DONE`** — 2ª run que degrada para no-op sem sinalizar.
6. **Max=2 da WN por auditar.**
7. **Etapa 2 do re-teste** (sessões dos dias 5 + 8 + 9).
8. **★ Futura encomenda — "Mestre único" de import (sem código nesta fase):** um
   duplo-clique = HM3 + appimport ao-vivo (com confirmação) + Discord sync + rematch +
   abrir a Saúde do Import. O **Intuitive Tables passa a gravar direto em `Batmen\it`** por
   definição própria (config da app, sem código). Ver `REGISTO_CONCEITO` (linha pt70).

Backlog: 413 definitivo (interino 200 MB), `#MYSTERY-KO-DUAL-SUPPORT`.

---

**Última actualização:** 11 Junho 2026 (**pt68 FECHADO**). Wipe total + Etapa 1 (sessão dia 4, 6 canos validados, ~5044 mãos, 123/127 órfãos); 502 do `/api/import` = timeout síncrono com import COMPLETO (4710 mãos 4-9 Jun verificadas); incidente do watcher (degradação progressiva por acumulação de abas, confirmada na fonte; 3 done VERDES na mini-auditoria); **★ Saúde do Import v1** (`/import-health`); **★ Gate da fila v1** (fila fechada + disparo manual/lote); **★ exe watcher pt68** (3 fixes: fechar aba Ctrl+F4+Don't Save, reiniciar/5+health-check, log-em-ficheiro) — **Release publicada+validada, instalação no Beelink PENDENTE**; **★ multi-select "Enviar ao HRC" backend LIVE** (frontend = 1º da próxima). Journal: `docs/JOURNAL_2026-06-11-pt68.md`. Antes: pt67 (pipeline certificado).
**Propósito:** lista priorizada do que atacar a seguir. Distinta do
`TECH_DEBTS_INVENTARIO.md` (que é o registo histórico exaustivo, com
estado de cada debt) — aqui é só a **fila de trabalho**, ordenada.

> Manutenção: quando um item for feito, mover para o journal/tech debts e
> remover daqui. Quando aparecer um item novo, colocar na categoria certa.

---

## ★ Fila de arranque da pt69 (ordem do Rui no fecho pt68)

1. **Frontend do multi-select "Enviar ao HRC"** (1º item) — backend **LIVE** à espera
   (`POST /api/queue/hrc/release` + `/states`). Estudo (`Hands.jsx` 2001 linhas + `HandRow`):
   checkboxes + "selecionar todas do torneio/grupo" + barra "Enviar N" + badges de estado +
   checkbox desabilitado nas não-exportáveis (com motivo).
2. **Instalar o exe pt68 no Beelink** (`irm` do `instala_pt68.bat`, Release `watcher-pt68`,
   SHA `222fc48d…3f57`) + **smoke do reinício-a-cada-5 e do fecho de abas** (Ctrl+F4 +
   Don't Save) + confirmar o log em `C:\hrc\watcher_logs\`.
3. **Etapa 2** = importar **dias 5 + 8 + 9** (re-teste com volume, à luz da Etapa 1).
4. **Fix `#HRC-NODE-OFFSET-IMPLICIT-LINES`** (gate da fila grande; regra 25 BB confirmada).
5. **Política CI/tempo da 2ª run** (`#HRC-2ND-RUN-CI-TIME-DISCREPANCY`) — **decisão de
   produto** do Rui (reiniciar a cada N? alvo de CI? tempo-limite?).
6. **4 órfãos Discord** (dias 5/8/9) sem match — investigar.
7. **2 lobbys com Vision de site trocado** — corrigir.
8. **Limpeza física do Beelink** (`C:\hrc\queue_hold\`, `stale_done`, Desktop riand) — as
   linhas dry-run + apagar já foram desenhadas no chat; correr quando o Rui puder.
9. **Mão do derail** (a seguir à `GG-6041861838`) — **forense opcional** (precisa do
   `state.json`/ordem de pick do Beelink).
10. **Gate por botão** (`#QUEUE-NO-SERVER-SIDE-GATE`) — ✅ **ENTREGUE pt68** (riscado).

---

## Alta prioridade (atacar a seguir)

> **★ FEATURE FUTURA (registar; desenho quando chegar a vez) — AVALIAÇÃO AUTOMÁTICA
> HERÓI vs HRC.** Ao receber o zip de estratégias, avaliar a decisão do herói: localizar
> na árvore o(s) nó(s) da linha real, ler a estratégia do solver para o **combo exacto**
> do herói (freq + EVs por ação) e comparar com a ação tomada → **veredicto** (em linha /
> mix / desvio) + **custo em EV** (ação tomada vs melhor). Output no Estudo + badge/filtro
> **"mãos onde desviei"**. **Questões para o desenho:** (1) mapear a acção real aos sizings
> da árvore (ex.: raise 2.2bb real vs linha 2.0 do solver); (2) herói com **múltiplos nós**
> de decisão na linha; (3) **onde guardar** o veredicto (coluna na mão? tabela própria?);
> (4) badge/filtro no Estudo. Constrói sobre a infra do **GTO Brain** (matching + navegação
> a nó). Reusa o zip que já entra em `hrc_jobs`/`hrc_sessions`.
>
> **★ ✅ ENTREGUE (pt68, `c10e303`) — GATE SERVER-SIDE DA FILA HRC COM DISPARO MANUAL**
> (`#QUEUE-NO-SERVER-SIDE-GATE`). Construído: tabela `hrc_queue_release` + filtro no GET +
> `POST /trigger?count=N` + `GET /gate` + página HRC Queue. ~~Desenho:~~ feito.
> A fila nasce FECHADA no servidor
> (`GET /api/queue/hrc` devolve vazio); só serve mãos após o Rui carregar em **"Disparar"**
> na página HRC Queue. **Modelo proposto:** tabela `hrc_queue_release` + filtro no GET (só
> mãos libertadas e não-done) + `POST /api/queue/hrc/trigger?count=N` + `GET …/gate` (estado:
> fechada/aberta/N em curso). **Auto-fecho** quando o lote é consumido. **Disparo:** "tudo"
> (v1) ou "lote de N" (v2). **Per-mão `…/hand/{id}` NÃO gated** (pedido explícito do Rui).
> **Zero alterações no adapter/Beelink** (o adapter já idle em vazio). **Esforço:** v1 ~1 dia
> (tabela+filtro+trigger+gate+botão "Disparar tudo"); v2 lote-de-N + histórico. Entra em
> vigor quando construído; a corrida de 11 Jun à noite mantém-se. Detalhe: `REGISTO_CONCEITO`.
>
> **★ pt67 IMPLEMENTADO (em buffer + Release `watcher-pt67`); falta a RE-SMOKE real
> (gate da fila).** 3 fixes em código (**916 PASSED** + 102 watcher + in-process smoke
> ALL OK; diffs validados pelo Web): **#HRC-MAX-PLAYERS-SPAN-NOT-PARTICIPANTS** (backend
> — span âncora→BB, **teto 6** [LEI `REGRAS_NEGOCIO §15`]; GG-6029013400 agora 5),
> **#HRC-RUN-WINDOW-DETECTION-BLIND** (watcher — vigia desde o Finish por hwnd, sem sleep
> cego), **#HRC-CI-SAFEGUARD-CHILD-CONTROLS** (watcher — "Target CI" nos child controls).
> + In-hand `\S+`→`.+?`. `.exe` **`a9554427`**.
>
> **Re-smoke pt67 = as MESMAS 2 mãos.** **DELETE dos 2 hrc_jobs (job 6,7) FEITO** → ambas
> voltaram a elegíveis (recalc da quarentena dessas 2). Beelink: instala_pt67 →
> `requeue_pt67.bat` (asset da Release, self-fetch do `requeue_state.py`) → adapter →
> watcher → packs novos (Max=5). **Critérios:** GG-6029013400 com **Max=5** + 1ª run
> DETECTADA (sem WARN "NUNCA vista"); GG-6039094225 regressão.
>
> **⚠️ FILA (~49) TRAVADA** até a re-smoke pt67 passar; depois lote(s) ao ritmo do Rui.
> **Quarentenas restantes:** `GG-6028190109` + `GG-6027751209` (recalc no 1º lote).
> Detalhe: `JOURNAL_2026-06-10-pt67.md` + `TECH_DEBTS_INVENTARIO.md` (pt67).

> **★ Quarentena de 2 resultados HRC (recalcular pós-pt66).** `GG-6028190109`
> (smoke pt64, corridas sobrepostas) e `GG-6027751209` (STALE, postado no arranque
> do adapter a 9 Jun). **Invalidar = re-POSTar pós-pt66** (o `upsert_hrc_job_result`
> sobrescreve por `hand_db_id`); não é preciso mexer na BD. Não estão visíveis em
> nenhuma UI hoje (`hrc_jobs` ≠ `/hrc-sessions`). Suspeito a investigar:
> `players_left = 3179` numa mesa GG (escala ICM). Detalhe: `TECH_DEBTS_INVENTARIO.md`
> (pt62–pt64).

> **★ pt58 — RE-IMPORT de scope ABRIL é o PRÓXIMO GRANDE PASSO operacional.**
> O re-import end-to-end **já foi feito** (pt50, Fases 1+2) mas só com a **janela
> de 3 dias** das HH (HH3dias.zip + TS3dias.zip). Falta o **scope de Abril**:
> 1. Importar as HH GG de Abril para **fechar os placeholders Discord/lobby de
>    Abril** (a Fase 3 confirmou que os replayer de Abril ficam placeholders por
>    não terem mão importada — esperado, mas resolúvel) e os `no_match` do
>    table-SS que caem **fora da janela 30/Mai+** (28 rows = gaps reais de import,
>    não bug de site/nome).
> 2. **Convenção de fuso já é Lisboa-naive** (pt51) — GG/PS gravam verbatim, sem
>    matemática DST. **A "validação de Inverno" da rota UTC dissolveu-se** (já não
>    convertemos GG/PS). Nada a validar do lado do fuso no re-import de Abril.
> 3. **Reavaliar o table-SS** com Abril importado: `#TABLE-SS-VISION-SITE-MISCLASS`
>    ✅ (pt49), site agora **determinístico pelo filename** (pt56). Suspeitos reais
>    que sobram: **WPN/PS time-only** (`#WPN-PS-TABLE-SS-TIME-ONLY-MATCH`),
>    **multi-tabling GG** (`#TABLE-SS-GG-MULTITABLING-MATCH` MED).

> **CoinPoker — adiado (o Rui joga, adição diferida).** Quando se fizer = **pacote
> completo**: `_FILENAME_SITE_MAP` (token do filename), nicks de hero, fonte de
> import das mãos, e pool de matching. Hoje cai no fallback + log (`_site_from_filename`
> devolve `None` para o token `CoinPoker`).

> **Sessão 2026-06-02 — planeado, NÃO aplicado (ver `docs/PLAN_2026-06-02-table-ss-gg-match.md`):**
> Match SS de mesa ↔ mão GG em multi-tabling. Investigação read-only completa.
> Achados: GG falha sobretudo por **import em falta** (68/99 SS sem mão na janela) + ~9 que o
> matcher devia apanhar (usa o resolver de nomes frágil em vez de nome-directo+fingerprint);
> nomes GG **fiéis** (prefixos de série a manter), `#NNN` é só da Winamax (já aparado, garantido
> preservado); TZ OK; 2 SS Winamax mal classificados como GG pelo Vision.
> **Próxima sessão (por ordem):** 1) fix `_resolve_match` (nome-directo por-site + impressão
> digital stack/blinds; GG sem limpeza; chokepoint que serve upload+relink) + testes; 2) importar
> as HH GG em falta (depois do fix, p/ o relink ligar); 3) abrir `#TABLE-SS-VISION-SITE-MISCLASS`.
> Constantes fixadas: `_FINGERPRINT_STACK_TOL=0.20`, blinds exacto, NÃO usar hero_position.
> **⚠️ Actualização pt49:** `#TABLE-SS-VISION-SITE-MISCLASS` já **FEITO** (`ef82a0d`/`41d83d3`);
> e o "TZ OK" acima estava **errado** — o GG tinha o bug de fuso `#GG-PLAYED-AT-LOCAL-NOT-UTC`
> (✅ pt49) a falsear a janela ±5min. Re-medir tudo **pós-reimport** (ver bloco ★ pt49 no topo).

> **Foco pt42e (por ordem):**
> 1. **Smoke real Beelink pt42d** (CRITICAL pré-commit). Sequência:
>    - Rui corre backend DEV LOCAL (`uvicorn` em `:8000`).
>    - Descarrega zip WN PKO pós-pt42d local.
>    - Valida `payouts.json` no zip: APENAS `{name, folders, structures}`;
>      `structures[0].name == "<Name>  #<tn>"`; `bountyType="PKO"`;
>      `progressiveFactor=0.5`.
>    - Copia para o Beelink: `.exe` novo (SHA cdfc7247...3262) +
>      `payouts_helpers.py`.
>    - Importa no HRC → confirma Instant=50% (não ICM puro).
>    - Corre robot Beelink (1ª + 2ª run) com hints em meta.json.
> 2. **Commit + push pt42d** (após smoke OK).
> 3. **`#LOBBY-SYNC-PAGINATION-LIMIT` (🟡 MED)** — paginação Discord.
> 4. **`#MYSTERY-KO-DUAL-SUPPORT` (🟡 MED)** — pré/pós-ITM.
> 5. **`#SMOKE-HARNESS-WAIT-FOR-FINISH-MOCK-MISSING` (🟢 LOW, novo pt42d)**.
> 6. **`#OPEN-COUNT-DRIFT-HRC-NODE-OFFSET-LATENT` (🟢 LOW)**.
> 7. **`#POSITION-LABELS-PYTHON-JS-DRIFT` (🟢 LOW, pt42b)**.
> 8. **`#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START` (🟡 MED)**.
>
> ✅ **Guarda mantida:** `DISCORD_LOBBY_AUTO=true`.
> **Fechados pt42d:** `#WN-BOUNTY-NULL-IN-HRC-PIPELINE` v2 ✅ (pt42c v1
> revertido em T2; pipeline v2 final com payouts HRC-native + meta hints).
> Suite 730→734 PASSED. .exe recompilado.
> **Pendente:** smoke real Beelink + commit/push.
> **Fechados pt42c:** `#WN-BOUNTY-NULL-IN-HRC-PIPELINE` v1 (parcial — Seat
> lines conversion subsequentemente revertida em pt42d).
> **Fechados pt42b:** `#HRC-BETTING-SCRIPT-IMPROVEMENTS` ✅ (3-bet IP por
> posição).
> **Fechados pt42:** `#HRC-BETTING-SCRIPT-IMPROVEMENTS` ✅ (1ª parte).
> **Fechados pt41:** `#HERO-BOUNTY-FROM-TS-DERIVATION` ✅ (`a942ac7`);
> `#LOBBY-ANCHOR-PRESTART-REGRESSION` ✅ + `#RESOLVER-TIER12-WINDOW-NO-START` ✅ (`6409b19`).
> **Fechados antes:** `#HRC-PER-HAND-DOWNLOAD` ✅ (`dfc13a5`, pt40);
> `#RESOLVER-TIER0-STRICT-EQUALITY` ✅ + `#TABLE-SS-RESOLVER-COLLISION` ✅ (pt39).

1. **`#PIPELINE-ROBUSTNESS-SMOKE-BATTERY` — porta de entrada da Fase 2 do
   GTO Brain.** Validar o pipeline ponta-a-ponta nas **4 combinações site ×
   formato**: (1) GG NKO Vanilla, (2) PokerStars PKO, (3) Winamax PKO,
   (4) PokerStars NKO Vanilla. Cada smoke = mão marcada na app → adapter
   pull → watcher → adapter push → `.zip` em `hrc_jobs` com dezenas de MB /
   milhares de nós. Ponto de partida validado: pt35 GG PKO 50%
   (`GG-5944816316`, Complete Export 44 MB). Só depois das 4 baterem se
   arranca a Fase 2 (auto-import `.zip` → `gto_trees`/`gto_nodes`). Ver
   `docs/GTO_BRAIN.md §7` e `docs/TECH_DEBTS_INVENTARIO.md`.

   > **SUPERSEDED (pt35):** o antigo item "validar o `.zip` pt34 v1
   > (~23 000 nós) vs Save As manual" foi tornado obsoleto pelo smoke real
   > pt35. O mecanismo de export mudou de Selected-Subtree/Save-As para
   > **Complete Export** (44 MB, ciclo funcional ponta-a-ponta), pelo que a
   > comparação célula-a-célula contra o Save As manual deixou de fazer
   > sentido.
   >
   > **pt36 — blocker removido:** `#HRC-RUN-2-ALWAYS-DISPATCH` ✅ resolvido
   > (backend). Toda mão que entra no zip tem agora `aggressor_real_action`
   > não-None → o gate da 2ª run no watcher passa sempre. A smoke battery
   > deixa de ter o risco de mãos exportadas com 1 run só; mãos limp/walk
   > passam a refinar a raiz da Strategy Table na 2ª run. (Detalhe +
   > `#PARSER-SEATS-FAILURES` em `docs/TECH_DEBTS_INVENTARIO.md` pt36.)

2. **`#HRC-BOUNTY-HARDCODED-50PCT` — RESOLVIDO em pt66 (em buffer; pendente
   build + re-smoke).** O robot metia sempre `Bounty Mode PKO 50%` (via
   `select_bounty_mode` legacy, que corria **depois** do import da estrutura e a
   **esmagava**, só em KO). **Fix pt66:** remover `select_bounty_mode` + o gate
   `is_ko_tournament` → é o **HRC** que põe o modo a partir da estrutura
   importada (`payouts.json`); **não** se constrói mapa→dropdown.
   **⚠️ Correcção factual (3ª vez — a cópia stale aqui voltou a infetar):
   NÃO existe `progressiveFactor=0.25` no pipeline HRC.** Os factores vêm do
   **`LOBBY_RATIO_LOOKUP`** (`backend/app/services/lobby_vision.py`, por nome do
   torneio) — **fonte única**: `0.75` monster, `0.50` bounty
   hunters/builder/knockout/[bounty], `0.40` super ko, `0.33` mystery (`KO`),
   `0.0` resto. (Os `0.25`/`0.33` doutras notas são constantes do `ire.py` —
   coisa **diferente**.) Já corrigido no TECH_DEBTS em `135be97` (22 Mai); esta
   era a cópia stale que sobreviveu. Ver `TECH_DEBTS_INVENTARIO.md` (pt66).

3. **`#HRC-REDUNDANT-SECOND-RUN-OLD-CONFIGS` ✅ RESOLVIDO em pt66** (código +
   exe `9ea51ce4` na Release `watcher-pt66`; pendente re-smoke real). Removido o
   `start_calculation` do `setup_hand` → a 1ª run é lançada pelo Finish e vai-se
   direto a navigate → Selected Subtree (exatamente 2 runs, sem prune). Ver o
   bloco ★ pt66 acima + `TECH_DEBTS_INVENTARIO.md` (pt66).

4. **Uniformização de tags Discord ↔ HM3.** Urgente — fragmentação visual
   no Estudo (o mesmo conceito aparece com nomes diferentes consoante a
   fonte). 3 opções já levantadas: renomear canais, dict de aliases
   hardcoded, ou UI admin central de tags. Decisão de produto pendente.

7. **`#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START` (🔴 HIGH, aberto pt37
   como `#START-TIME-TIMEZONE-INCONSISTENCY`, re-rotulado pt39).** **NÃO é bug de
   TZ** (re-diagnose pt39, read-only). `tournament_summaries.start_time` =
   arranque agendado; `tournaments_meta.start_time` = `MIN(played_at)` = 1ª mão
   importada (horas adiantada quando há late-reg / import parcial). O diff é 0
   quando a 1ª hand é Level1 e cresce com níveis tardios — semântica, não
   relógio. **Já não bloqueia os outros** (não há TZ a corrigir); mas continua a
   contaminar qualquer janela ancorada em `meta.start_time`. Ver
   `TECH_DEBTS_INVENTARIO.md` (secção pt39).

9. **`#HRC-MTT-STACKS-PAGE-SKIPPED-ON-NULL-PLAYERS-LEFT` (🔴 HIGH, aberto pt38; pipeline construído pt38).**
   **Endereçado** pelo **pipeline SS de mesa** construído em pt38 (Fases A+B +
   trigger re-link + fix mapeamento Vision): captura via Intuitive Tables →
   Vision lê `players_left` **por mão** → `_resolve_players_left` usa-o
   (prioridade granular, antes do fallback lobby). **Residual a fechar:**
   - **Fase C** (cliente automático `.bat-like`) **pendente** → até lá o upload
     é **manual** em `/table-ss`.
   - **Captura:** a SS tem de incluir o painel "Rank:"
     (`#TABLE-SS-VISION-CAPTURE-GAP`), senão `players_left` vem null —
     Rui configurar o Intuitive Tables.
   - **Fiabilidade do linking depende do resolver**
     (`#TABLE-SS-PIPELINE-DEPENDENCIES`, `#TABLE-SS-RESOLVER-COLLISION`):
     multi-tabling não é 100% fiável enquanto o resolver não estabilizar (TIER0
     ✅ pt39, TIER12 ✅ pt41; resta `#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START`,
     item 7). Ver `docs/JOURNAL_2026-05-24-pt38.md` e `TECH_DEBTS_INVENTARIO.md` (pt38).

---

## GTO Brain — roadmap (depois da smoke battery)

Plano completo em `docs/GTO_BRAIN.md §7`. Resumo da fila:

- **Fase 1 — ✅ fechada (pt35).** Watcher exporta Complete Export; ciclo
  `app → adapter → watcher → adapter → app` validado (`GG-5944816316`, 44 MB).
- **Fase 2 — auto-import `.zip` → `gto_trees`/`gto_nodes`.** Estender
  `POST /api/queue/hrc/results` para, depois de gravar em `hrc_jobs`, chamar
  `parse_hrc_zip()` + insert em `gto_trees`/`gto_nodes`, derivando metadados
  automaticamente (format, num_players, hero_position, stack, phase) — sem
  form manual. **Gated por `#PIPELINE-ROBUSTNESS-SMOKE-BATTERY`** (ver Alta
  prioridade). Tech debts: `#GTO-IMPORT-AUTOMATICO-AUSENTE` (HIGH),
  `#GTO-METADADOS-DERIVACAO-AUSENTE` (LOW).
- **Fase 3 — UI rica + tab FIELD.** Navegação interactiva multi-spot (não só
  o nó do Hero), grelha 13×13 com pesos/EVs, e construção do lado FIELD
  (schema `field_stats_preflop` + worker de agregação + `/api/field/match` +
  tab FIELD no replayer). Tech debts: `#GTO-NAVIGATE-SO-HERO-NODE` (MED),
  `#FIELD-PIPELINE-AUSENTE` (MED), `#GTO-RANGE-VISUAL-VALIDACAO` (LOW).

---

## Médio prazo

10. **`#CI-TARGET-INITIAL-NOT-CALIBRATED` ✅ DISSOLVIDO em pt66.** Já não há set
   do CI no main UI: o watcher deixou de escrever o CI (default do popup = 10.0);
   `set_ci_target_initial/refine` + `_set_ci_target_common` + `CI_TARGET_FIELD_*`
   removidos. Salvaguarda só-leitura `_ci_target_readback_warn`. Ver bloco ★ pt66.

11. **`#WIZARD-FINISH-FALSE-POSITIVE-STATE-CHECK`.** `verify_wizard_finished`
   (state check WARN-only pós-Finish, pt29-v1) verifica **cedo demais** — o
   wizard ainda está visível no instante da verificação, gera WARN espúrio,
   mas a 1ª run efectivamente arranca. Adicionar um pequeno settle/poll
   antes de verificar, ou retirar o WARN. Não-bloqueante.

12. **`#CURSOR-ANOMALY-POST-SAVE-AS`.** Após o Save As, o cursor da Strategy
   Table cai na 2ª linha (EP). **Refinado pt64: é DETERMINÍSTICO** — o Rui
   confirma "sempre o 2º nó" na fase de guardar estratégias (já não é anomalia
   de origem desconhecida; há padrão reproduzível). Não bloqueia o flow, mas
   investigar (pode afectar uma futura 3ª run ou navegação encadeada).

13. **`#PARSER-SEATS-FAILURES` (🟡 MED, aberto pt36).** `build_queue_zip`
   passou a skipar mãos cujo `derive_seats_in_preflop_order` devolve `[]`
   (sem button / <2 seats) com `reason="no_seats_at_table"`. Desde
   `#HRC-RUN-2-ALWAYS-DISPATCH`, uma falha do parser de seats custa a **mão
   inteira** à biblioteca (antes só a 2ª run). Robustecer
   `derive_seats_in_preflop_order` contra edge cases cross-site (PS/GG/WN/WPN;
   ex.: nicks com espaços, `#DERIVE-MAX-PLAYERS-HERO-REGEX-GG`). Detalhe em
   `docs/TECH_DEBTS_INVENTARIO.md` (secção pt36).

14. **`#LOBBYS-RETRIGGER-NOT-DISCOVERABLE` (🟡 MED UX, aberto pt37).** O botão
   "Sincronizar Lobbys" + Avançado/`tm_not_found` vive só na página Discord,
   fácil de não notar; não há aviso em Dashboard/Torneios quando há candidatos
   `tm_not_found` pendentes. O utilizador importa TS+HH e não sabe que precisa
   de re-disparar os lobbys para fechar o ciclo. Fix: badge/link na
   Dashboard/Torneios, ou auto-retrigger pós-import. Ver
   `TECH_DEBTS_INVENTARIO.md` (pt37).

14b. **`#WPN-PS-TABLE-SS-TIME-ONLY-MATCH` (🟡 MED, aberto pt50).** WPN/PS não estão
   em `_NAME_RELIABLE_SITES` → o table-SS casa-os **só por tempo** (nomes WPN =
   garantia, PS = NULL, não validáveis). Superfície de falso-match em multi-tabling
   WPN/PS na janela. Mitigado pelo site determinístico (filename, pt56). Reavaliar
   se aparecerem falsos matches reais. Ver `TECH_DEBTS_INVENTARIO.md` (pt50–pt58).

15. **`#BUBBLE-FACTOR-PER-PLAYER` (FEATURE FUTURA — estudo de viabilidade feito,
   NÃO implementar sem OK).** Mostrar um **bubble factor por jogador, ajustado a
   bounty**, ao lado de cada jogador na vista da mão.
   - **Âmbito:** **só as mãos que vão ao HRC**, onde o `players_left` **já é exacto**
     via o mecanismo que alimenta o watcher (`_resolve_players_left` / a SS de
     `players_left` associada à mão). **NÃO estimar `players_left`** — usar o exacto
     dessas SS. *(Corrige a conclusão do estudo: o "furo de players_left" NÃO se
     aplica a estas mãos — só apareceria se quiséssemos BF em qualquer mão.)*
   - **Motor:** **próprio**, ICM **Malmuth-Harville** (mesa ≤9 exacta + resto do
     campo colapsado em stacks médios; ~ms/mão, on-demand). O **HRC NÃO serve como
     fonte primária** — só dá BF **pós-processamento** e cobre ~0 mãos (`hrc_jobs`
     vazio); fica como **cruzamento v2**: parsear `bubbleFactors` (matriz NxN) +
     `preHandEquity` do `equity.json` do HRC quando a mão já passou pelo robot
     (formato confirmado em `services/hrc_import.py`; hoje só se extrai o `meta.json`).
   - **Bounty (PKO):** reutilizar a matemática do **`ire.py`** (`ko_units`,
     `constant = KOP_fraction × instant_fraction`, coroas `bounty_value_usd`) para o
     **termo de bounty**; combina (multiplicativo no risk premium) com o termo
     **ICM-regular** do motor próprio. Já temos metade (o lado bounty).
   - **Dados já presentes por mão:** stacks (apa), coroas (`bounty_value_usd`),
     escada de prémios completa (`tournament_payouts.payouts_json.structures[0].prizes`,
     ex.: 912 ranks), field size (`tournament_summaries.total_players`), split
     `buy_in_entry`/`buy_in_bounty`, `starting_stack`. (Não falta nada para as mãos
     do âmbito.)
   - **Esforço (do estudo):** motor ICM **~2-3 dias** + termo bounty **+1-2** +
     híbrido HRC (parse `equity.json` no ingest do robot) **+1-2**.

16. **`#CONTEXT-IMAGE-MKO-BOUNTY-AVG` (FEATURE FUTURA — NÃO implementar sem OK).**
   Aproveitar **imagens de contexto não-reconhecidas** (lobbys + Intuitive Tables)
   que hoje caem em `no_match_to_hand`/`vision_failed`/ignoradas e **perdem-se** —
   tratar as que são contexto útil.
   - **Caso-bandeira: Mystery KO.** Foto dos **KOs restantes** numa mão → obter o
     **valor MÉDIO do bounty restante** → alimentar o **HRC em KO mode** para essa
     mão (o MKO é não-progressivo, `instant_fraction=1.0`; a média é o input que
     falta para modelar o bounty).
   - **Extracção POR SALA** (a média pode ou não vir já calculada — mesmo padrão
     por-sala que o `ire.py` tem para GG vs Winamax):
     - **PokerStars, Winamax:** já mostram a média → Vision lê o número directo.
     - **WPN, GG:** NÃO calculam → Vision extrai o **breakdown** dos bounties
       restantes (nº × valor por tier) e calcula a média (total restante ÷ nº de
       bounties).
   - **Modelo:** irmão do **table-SS** (`context → players_left`); aqui
     `context → média bounty MKO → HRC KO mode`. **Mesma família HRC** do bubble
     factor (`#BUBBLE-FACTOR-PER-PLAYER`) e do IRE.
   - **A confirmar ao implementar:** como a imagem se prende à mão (timestamp, à la
     table-SS); **nova categoria de imagem** na pipeline (hoje só lobby / table-SS /
     manual / replayer); **formato do breakdown** em WPN/GG. Nota: as imagens do
     table-SS **são guardadas** (`img_b64`; `#TABLE-SS-IMAGE-NOT-STORED` ✅ resolvido
     16 Jun) → re-Vision retroactiva **é** possível para esse caminho.

---

## Baixo prazo / qualidade

15b. **`#TABLE-SS-IMAGE-NOT-STORED` — ✅ RESOLVIDO (16 Jun, pt73).** **Era falso já:**
   o `table_ss_processing_log` **guarda** a imagem em `img_b64` (coluna `table_ss.py:194`;
   escrita no upload). Validado ponta-a-ponta na recuperação 14 Jun: **120/120** com
   `img_b64` + re-Vision a partir do guardado a funcionar (`/reprocess-failed`). **A
   re-Vision retroactiva é possível** — sem re-fornecer o ficheiro. Âmbito: caminho
   **table-SS** (o screenshot/replayer guarda `img_b64` em `entries.raw_json`, separado).
   Reforça o princípio de hoje (a imagem é a outra metade — `REGISTO_CONCEITO 2026-06-16`),
   já satisfeito aqui. Detalhe: entrada `#TABLE-SS-IMAGE-NOT-STORED` no `TECH_DEBTS_INVENTARIO.md`.

15c. **🟢 BAIXA (tracking, pt73) — 1 captura `no_match_to_hand` (12 Jun).** site/tn
   casados mas **sem mão correspondente** na BD. Leitura provável (**não verificada**):
   HH ainda não reimportado (reimport por fases) ou órfão. **Revisitar quando a fase do
   HH chegar**; **não** é `vision_failed` (fora do âmbito da recuperação de Vision).


15. **Vision parser improvements** — tolerância ao prefixo TM, heurística do
   BB stack, prompt GTO mais forte.
17. **Filtros derivados no Estudo.**
18. **Dashboard — colunas adicionais.**
19. **Winamax replayer — URL da Vision.**
20. **`_upload_screenshot_to_storage`** — limpeza do stub.
21. **Discord entry status** — cosmético.
22. **Discord page — dual time filters.**
23. **Teste de regressão `/ss-without-match`** (pt48) — não há teste pytest para o
   endpoint; o dedupe por TM só está verificado por simulação ad-hoc. Adicionar: 2
   uploads manuais **sem TM** por casar → **ambos** aparecem (não colapsam por
   `NULL=NULL`); N replayers do **mesmo** TM → **1** linha. Cobre o `COALESCE(tm,
   'e'||entry_id)` do `56025af`.

---

## ★ Lane — Importador automático de replayer GG (ressuscitar a desanon) — **FIX-PRIMEIRO**

Lane nova (registada pt73, 16 Jun). **Não ligar a torneira antes do fix** — ver ordem abaixo.

**O quê:** um **importador automático** (irmão do `bat` HM3 / `appimport` / `appmaster`) que
lê imagens do **replayer GG** de uma pasta e as mete pelo **caminho de screenshot-por-nome**
(`screenshot.py:_parse_filename` + `mtt._match_screenshot`) → **ressuscita a desanon GG** agora
que o `og:image` morreu (pt72, `#REPLAYER-OGIMAGE-DEAD-SPA`).

**Porquê vale a pena:** a imagem do replayer é a **MELHOR fonte de desanon** — traz **SB/BB +
botão do dealer + Herói**, ou seja os **três critérios da âncora P2** (`DESANON_ANATOMIA §3.2.1`).
Melhor que o table-SS para alinhamento.

- **Persistir a imagem** — é a **outra metade do registo da mão** (tags + nicks); perdê-la =
  perder ambos para sempre. O table-SS já guarda `img_b64`; esta lane tem de garantir o mesmo.
- **P1 (qual é a mão)** = por **hand-id do nome** (o número TM imediatamente antes do timestamp),
  determinístico — decisão pt73 (`DESANON_ANATOMIA §2`).
- **P2 (quem senta onde)** = âncora SB+BB + botão (invariante) + Herói — `DESANON_ANATOMIA §3.2.1`.

**⚠️ ORDEM OBRIGATÓRIA — fix-primeiro-depois-acordar.** Antes de alimentar **mãos reais** por
este caminho:
1. **Corrigir o debt do nome** `#GG-DOWNLOAD-IMG-FILENAME-TIME-AND-BLINDS-UNRELIABLE` — tirar a
   **hora-de-download** e as **blinds** do nome do `_match_screenshot` (desempate) **e** do
   **`played_at`-fallback** (`screenshot.py:1565`). O único sinal fiável do nome é o **TM**.
2. **Corrigir a doutrina** — para estas imagens, a **Vision é a fonte das blinds**; o nome só
   dá o TM (reconciliar `CLAUDE.md:174` / `MAPA_ACOPLAMENTO §file_meta` / `VERIFICACAO_PIPELINES:516`).
3. **Só depois ligar a torneira** (apontar o importador a mãos reais).

> Nota: o **scan pt73** mostrou **0 mãos contaminadas hoje** (a superfície de screenshot-por-nome
> está vazia post-wipe + replayer morto). O caminho está **latente**, não activo — é exactamente
> por isso que se corrige **antes** de o reactivar, e não depois. → `#GG-DOWNLOAD-IMG-FILENAME-TIME-AND-BLINDS-UNRELIABLE`.

---

## #HRC-REIMPORT-REDEANON-CASADAS — 🔴 PRÉ-REQUISITO DO WIPE (subiu de prioridade em 3 Jul)

> **⚠️ Re-priorizado (3 Jul 2026).** Deixou de ser "melhoria futura, NÃO agora" (pt93). Com a
> decisão de **apagar + reimportar** todos os dados (ver `APA_INDEXACAO_E_COLAPSO.md` e o banner
> ★★ no topo deste ficheiro), este passa a ser **bloqueador do reimport**: sem ele, o reimport
> **parte a desanon de TODAS as mãos GG com captura já casada** (não só de 1 mão pontual). O
> "acidente 1 vez" descrito abaixo torna-se a regra no dia do wipe. **Fix a fazer ANTES do
> reimport:** o `import_` (e o `import_hm3`) re-dispararem a desanon por table-SS para mãos com
> SS **casada** (não só as órfãs `no_match_to_hand`).

Um **re-import de HH** repõe `all_players_actions` cru + esvazia `player_names.anon_map`
**sem re-disparar a desanon por table-SS**, porque o re-link só re-corre a desanon de SS
**órfãs** (`no_match_to_hand`), não de SS **já casadas**. Resultado: uma mão GG que já estava
desanonimizada volta a ficar com hashes (display) e, se for **PKO**, com **bounty achatado no
solve HRC** (a injecção casa por nome → miss → todos no base). Aconteceu **1 vez** (GG-6113994321,
por causa dos wipes/re-imports pt68/pt92). **Fix futuro:** o `import_` re-disparar a desanon para
mãos com table-SS já casada (não só órfãs). Diferido por decisão do Rui (pt93) — não empilhar nas
3 frentes em curso (gravação/âncora/bounty). O acidente actual resolve-se com **re-run** da desanon
da própria mão. Cross-ref: `DESANON_ANATOMIA`, `#HRC-ANCHOR-RAISE-AFTER-HERO-FOLD`.

---

## Cross-references

- `docs/TECH_DEBTS_INVENTARIO.md` — estado detalhado de cada `#TECH-DEBT`.
- `docs/GTO_BRAIN.md` — visão e roadmap do GTO Brain (3 fases).
- `docs/JOURNAL_2026-05-22-pt35.md` — sessão que fechou a Fase 1 do GTO Brain.
- `docs/JOURNAL_2026-05-22-pt30-pt34.md` — contexto da sessão que fechou a
  cadeia da 2ª run.
