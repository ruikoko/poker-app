# Onboarding prompt — sessão pt19 (sucessora de pt18)

Cola este prompt no início de uma nova sessão Claude Web ou Claude Code para retomar o trabalho da FASE A pipeline lobbys.

---

## Para a sessão Claude (lê na ordem indicada)

És o **Claude novo** desta sessão (pt19). A sessão anterior (pt18, 9 Maio 2026) deixou o pipeline FASE A C1-C3 deployed em prod mas com 3 gaps no `tm_resolver` que bloqueiam upserts reais. O teu trabalho é arrancar **commit A** primeiro.

### Documentos obrigatórios (ler na ordem)

1. **`CLAUDE.md`** — secções:
   - "FASE 1 — HRC Export Queue" (deployed 8 Mai)
   - "FASE A — Pipeline lobbys via Discord" (deployed parcial 9 Mai)
   - "Variáveis de ambiente FASE A"
   - "Última sessão fechada: pt18"

2. **`docs/JOURNAL_2026-05-09-pt18.md`** (sessão imediatamente anterior — leitura completa)
   - Resumo executivo
   - Bloco 6 (validação real 5 SSs) — explicação dos gaps G1/G2/G3
   - Pendências carry-over: lista A/B/C/E/D/F

3. **`docs/TECH_DEBTS_INVENTARIO.md`** — secção "Estado actual (9 Maio 2026 — pós-pt18, ...)" tem tudo o que precisas:
   - Lista de commits cronológicos em prod
   - Tabela dos gaps
   - Tech debts pendentes ordenados por prioridade

4. **`docs/PAPEIS_E_RESPONSABILIDADES.md`** — papel do Rui, do Claude Web, do Claude Code.

5. **`docs/REGRAS_NEGOCIO.md`** — regras duras + secção §6 ("Regras DURAS — o que a app NUNCA pode fazer").

(Total: ~15 min de leitura. Não saltar — pt18 cometeu erros que estavam documentados em sessões anteriores.)

### Estado actual da FASE A em prod

- **Backend:** `poker-app-production-34a7.up.railway.app` (commit `0a1241b` em main).
- **Pipeline:** SS no `#lobbys` → bot Discord → Vision Anthropic Claude Sonnet 4.6 → JSON parse → `tm_resolver` → ❌ falha aqui.
- **Validado funcional:**
  - Vision API call (HTTP 200, MIME magic-number detection).
  - JSON parse + validate.
  - Verbose `[lobby] FAIL <razão>` logs em todos os paths.
- **Gaps a resolver (commit A primeiro):**
  - **G2** — Vision lê nome diferente do BD (ex: `Bounty Hunters Hyper Special $108` vs BD `Bounty Hunters **Sunday** Hyper Special $108`).
  - **G1** — `tournaments_meta` Winamax/PS = 0 rows.
  - **G3** — `start_time_iso` ausente + nome muito comum (`Daily Hyper $80` corre todos os dias).

### Primeiro objectivo da sessão pt19

**Arrancar commit A: fuzzy / token-set match em `tm_resolver.resolve_tournament_number`.**

Spec resumido:
- Em `services/tm_resolver.py`, substituir o ILIKE `%name%` simples por **token-set match**: separar o nome (Vision) em tokens word, exigir que cada token esteja presente no `tournament_name` do BD (case-insens, ordem irrelevante).
- Implementação SQL possível: `tournament_name ILIKE ALL (ARRAY['%token1%', '%token2%', ...])`. Ou adoptar `tsvector @@ plainto_tsquery` (FTS Postgres).
- Manter o filtro start_time ±2h se Vision conseguiu ler.
- Devolver `(tn, [])` se 1 match único; `(None, candidates)` se 0 ou 2+.

**Antes de tocar em código:**
1. Lê `services/tm_resolver.py` actual (~80 linhas).
2. Lê `tests/test_tm_resolver.py` (~100 linhas, 6 tests com mock `query`).
3. Apresenta buffer + diff antes do write (workflow buffered-diff que o Rui pediu — registado em memory).
4. Aguarda OK do Rui.
5. Após OK: write + pytest (esperado 59/59 ainda passam, +N tests novos para token match).
6. Commit + push + auto-deploy.
7. Pede ao Rui para repostar SSs no `#lobbys` para validação.

**Workflow:** buffer-diff em fases → aprovação → disco → diff → commit. Rui é estrito sobre isto.

### Coisas a NÃO fazer

- ❌ Não tocar no `extract_lobby_payout_json` nem no prompt Vision sem aprovação explícita.
- ❌ Não mexer em commits A→B→C→E em paralelo. Commit A primeiro, smoke test, depois B, etc.
- ❌ Não remover instrumentation `[debug-msg-lobby]` ou `[lobby] FAIL ...` antes de pipeline estável (pt18 deixou propositadamente).
- ❌ Não fazer commit sem permissão explícita do Rui.
- ❌ Não imprimir secrets em probes (lição aprendida em pt18 — `OPENAI_API_KEY` foi exposta acidentalmente quando o probe matchou o pattern; corrigido com `Select-String -Pattern "ANTHROPIC|CLAUDE" -NotMatch` em probes futuros).

### Comandos úteis para diagnose pt19

```powershell
# Capturar logs Railway
railway logs --service "poker-app" 2>&1 | Select-Object -Last 200 | Out-File <file>

# Filtrar logs lobby
grep -E "lobby|FAIL|override|Anthropic|HTTP/1.1 [24]" <file>

# Confirmar env vars (sem expor valores)
railway variables -s poker-app --kv 2>&1 | Select-String -Pattern "^DISCORD_LOBBY|^ANTHROPIC|^OPENAI"

# SELECT tournament_payouts via Vision
SELECT site, tournament_number, source, uploaded_at,
       payouts_json->'structures'->0->>'name' AS name
  FROM tournament_payouts
 WHERE source LIKE 'discord_lobby_vision:%'
 ORDER BY uploaded_at DESC LIMIT 5;
```

### Memória existente que ajuda

- Workflow buffered-diff: buffer → diff → aprovação → disco → diff → commit, em fases.
- "Quando Rui diz 'já te disse isto', ouvir e documentar" — repetição = trigger para escrever em CLAUDE.md.
- "Apresentar opções em PT-PT corrente antes do código" — para decisões, prosa pt-pt primeiro; tradução técnica depois.

---

**Boa sessão. Primeira pergunta ao Rui depois de leres tudo:**

> Li CLAUDE.md, JOURNAL pt18, TECH_DEBTS, PAPEIS, REGRAS. Estado FASE A entendido — gaps G1/G2/G3 identificados, plano A→B→C→E. Vou arrancar commit A (fuzzy/token-set match em tm_resolver). Preferes que apresente buffer da abordagem token-set ILIKE ALL ou da via FTS `tsvector @@ plainto_tsquery`? Ambas têm trade-offs (simples-mas-permissiva vs robusta-mas-mais-código). Posso comparar lado-a-lado se quiseres.
