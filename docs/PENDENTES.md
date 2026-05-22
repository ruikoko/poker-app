# Pendentes — backlog vivo

**Última actualização:** 22 Maio 2026 (fim da sessão pt30-pt34).
**Propósito:** lista priorizada do que atacar a seguir. Distinta do
`TECH_DEBTS_INVENTARIO.md` (que é o registo histórico exaustivo, com
estado de cada debt) — aqui é só a **fila de trabalho**, ordenada.

> Manutenção: quando um item for feito, mover para o journal/tech debts e
> remover daqui. Quando aparecer um item novo, colocar na categoria certa.

---

## Alta prioridade (atacar a seguir)

1. **Validar o `.zip` exportado pelo robot pt34 v1 vs Save As manual.**
   O smoke pt34 v1 saiu com `~23 000 nós`. Confirmar que tem a árvore
   completa (~23 255 nós) e que bate, célula-a-célula, com o Save As manual
   da sessão anterior. É a validação formal do marco "2ª run automática =
   fluxo manual".

2. **`#HRC-BOUNTY-HARDCODED-50PCT`.** O robot mete sempre `Bounty Mode PKO
   50%` (via `select_bounty_mode` legacy). Fazer ler o `progressiveFactor`
   do `payouts.json` (já é data-driven: 0.5/0.33/0.25/0.0) ou o
   `tournament_format`, e seleccionar a opção correspondente no dropdown
   do HRC. Suporta PKO 25% e Mystery KO correctamente. Ver
   `TECH_DEBTS_INVENTARIO.md` e `WORKFLOW_OPERACIONAL.md` §4.2.

3. **Discord — 2ª entry para Tournament Markers duplicados.** Bug aberto há
   sessões: quando um TM aparece em 2 canais, o 2º canal não é adicionado a
   `discord_tags`, e a regra C de villain não dispara. Alta prioridade
   pré-sessão.

4. **Uniformização de tags Discord ↔ HM3.** Urgente — fragmentação visual
   no Estudo (o mesmo conceito aparece com nomes diferentes consoante a
   fonte). 3 opções já levantadas: renomear canais, dict de aliases
   hardcoded, ou UI admin central de tags. Decisão de produto pendente.

---

## Médio prazo

5. **`#CI-TARGET-INITIAL-NOT-CALIBRATED` (pt25e Bloco 2).** Calibrar a coord
   do campo CI Target inicial da 1ª run no main UI. Actualmente
   `CI_TARGET_FIELD_X/Y = 0` → `_set_ci_target_common` degrada para Enter
   (funciona, mas é menos limpo). Smoke devagar com o Rui para medir a
   coord.

6. **`#WIZARD-FINISH-FALSE-POSITIVE-STATE-CHECK`.** `verify_wizard_finished`
   (state check WARN-only pós-Finish, pt29-v1) verifica **cedo demais** — o
   wizard ainda está visível no instante da verificação, gera WARN espúrio,
   mas a 1ª run efectivamente arranca. Adicionar um pequeno settle/poll
   antes de verificar, ou retirar o WARN. Não-bloqueante.

7. **`#CURSOR-ANOMALY-POST-SAVE-AS`.** Após o Save As, o cursor da Strategy
   Table cai na 2ª linha (EP). Origem desconhecida. Não bloqueia o flow,
   mas investigar (pode afectar uma futura 3ª run ou navegação encadeada).

---

## Baixo prazo / qualidade

8. **Vision parser improvements** — tolerância ao prefixo TM, heurística do
   BB stack, prompt GTO mais forte.
9. **Gyazo pipeline** — tabela `hand_attachments` (anexos de imagem
   Discord ↔ mão; ver CLAUDE.md "Imagens de contexto Discord").
10. **Filtros derivados no Estudo.**
11. **Dashboard — colunas adicionais.**
12. **Winamax replayer — URL da Vision.**
13. **`_upload_screenshot_to_storage`** — limpeza do stub.
14. **Discord entry status** — cosmético.
15. **Discord page — dual time filters.**

---

## Cross-references

- `docs/TECH_DEBTS_INVENTARIO.md` — estado detalhado de cada `#TECH-DEBT`.
- `docs/JOURNAL_2026-05-22-pt30-pt34.md` — contexto da sessão que fechou a
  cadeia da 2ª run.
