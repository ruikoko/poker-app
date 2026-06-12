# LIÇÕES — Problemas → Soluções → Êxitos

Registo **cumulativo, append-only**. Uma linha por lição: o **problema**, a **solução**,
e (quando aplicável) o **êxito**. Link ao journal da sessão. Acrescentar, nunca
substituir. Serve para não repetir erros e para reconhecer o que funcionou.

Formato: `- AAAA-MM-DD — **Problema:** … → **Solução:** … (→ journal)`

---

## 2026-06-10 (pt64–pt67) — → `docs/JOURNAL_2026-06-10-pt67.md` + `…-pt66.md`

- 2026-06-10 — **Problema:** run intermédia redundante no watcher (qualidade inconsistente). → **Solução:** removida — o Finish já lança a 1ª run → exatamente 2 runs.
- 2026-06-10 — **Problema:** watcher cego a runs curtas (`sleep(30)` engolia runs de ~4-5s). → **Solução:** vigília da janela de progresso **desde o Finish** por hwnd (sem heurísticas de tempo) → runs de 4s **VISTAS**.
- 2026-06-10 — **Problema:** CI escrito às cegas (e a salvaguarda lia o título, não o valor). → **Solução:** leitura do "Target CI" pelos **child controls** do dialog; watcher não escreve o CI.
- 2026-06-10 — **Problema:** Max Players contava participantes, não o span; e a re-smoke das 18:09 correu contra o backend **não deployado**. → **Solução:** lei do span âncora→BB (teto 6) **+ lição FLUXO §10** (fix de backend valida-se **deployado**, não com "push no fecho").
- 2026-06-10 — **Problema:** nó de navegação errado na 2ª run (off-by-one within-bucket). → **Solução:** convenção `offset_within_bucket` all-in-dependent (jam = nó ALLIN = último) + **desempate fotográfico** que **reescreveu a semântica** do Selected Subtree e **reativou a LEI B** (revelando que o veneno real é a **posição errada**, `#IMPLICIT-LINES`, não o within-bucket).
- 2026-06-10 — **Problema:** POST de resultado a dar 413 (zip 112 MB, medido pelo Rui). → **Solução:** diagnosticado como cap da **própria app** (50 MB), não edge (POST de 120 MB chega ao uvicorn) → cap a **200 MB** interino; `/hrc-sessions` como plano B.
- 2026-06-10 — **Problema:** `.bat` corrompido no Beelink (LF + acentos → cmd rebenta). → **Solução:** ASCII puro + CRLF + `.gitattributes` (`*.bat text eol=crlf`).
- 2026-06-10 — **Problema:** build Railway a falhar (mise sem binário pré-compilado p/ Python 3.13.14). → **Solução:** pin **Python 3.12** (`.python-version`) + `audioop-lts; python_version>="3.13"`.
- 2026-06-10 — **ÊXITO:** **1ª mão certificada ponta-a-ponta** (`#225`, `hrc_job 10`) — `app → adapter → watcher → 2 runs → resultado na BD`.
- 2026-06-10 — **ÊXITO:** deploy de binários por **GitHub Release de 1 clique** (SHA-check, 1 exe no Beelink) consolidado.
- 2026-06-10 — **ÊXITO:** **verificação visual do nó** promovida a **critério permanente** de toda a smoke de navegação (o que apanhou o off-by-one e desbloqueou a semântica).

## 2026-06-11 (pt68) — → `docs/JOURNAL_2026-06-11-pt68.md`

- 2026-06-11 — **Problema:** 502 "Application failed to respond" no `/api/import` parecia crash. → **Solução:** diagnosticar pela BD ANTES de re-tentar — as 4710 mãos estavam TODAS lá (import completo, **resposta perdida por timeout síncrono**, não memória/crash). Idempotente → re-try seguro mas desnecessário.
- 2026-06-11 — **Problema:** `Ctrl+W` para fechar a aba da mão no HRC. → **Solução (achado do Rui na fonte):** `Ctrl+W` é **chord de nova-mão** (Ctrl+W,E/M/H/S) — **NUNCA usar**; o fecho de aba é **`Ctrl+F4` + diálogo "Save Resource" → Don't Save** (Win32 BM_CLICK).
- 2026-06-11 — **Problema:** o watcher derailou de madrugada (avaria "súbita"?). → **Solução:** o padrão (setup-failed cold start → 3 OK → derail; ritmo 3→9 min) é **degradação PROGRESSIVA** por **acumulação de abas** (HRC não fecha a anterior — confirmado na fonte). Fix: fechar aba + reiniciar a cada N + health-check de cold start.
- 2026-06-11 — **Problema:** consola do watcher perdida → sem root-cause do incidente. → **Solução:** `#WATCHER-LOG-TO-FILE` subido a prioridade + entregue no exe pt68 (Tee → ficheiro com rotação). Esta noite provou o custo.
- 2026-06-11 — **Problema:** o Code andou a vasculhar o disco (Documents\Poker\GG…) à procura da GG. → **Solução (regra `FLUXO §11`):** só os paths listados; **a GG vem do BACKOFFICE do Rui** — pede-se, não se vasculha.
- 2026-06-11 — **Problema:** mtime das zips GG sugeria "sessão 04-05" (era 3-4 Jun). → **Solução:** espreitar o **conteúdo** (horas reais das mãos), não confiar no mtime.
- 2026-06-11 — **Problema:** `gh` ausente → "não consigo publicar a Release". → **Solução (correcção do Rui):** publicar pela **API REST do GitHub** com as mesmas credenciais do push (`git credential fill` → POST releases + upload assets). Validar: download anónimo 200 + SHA round-trip.
- 2026-06-11 — **Problema:** wipe irreversível. → **Solução:** backup logical **restore-verificado** ANTES (COPY → schema scratch → assert contagens) + cross-check de cobertura vs `information_schema` (zero gaps) + TRUNCATE atómico com assert-zero/rollback.
- 2026-06-11 — **ÊXITO:** **Saúde do Import v1** (`/import-health`) — instrumento de validação da própria Etapa 1.
- 2026-06-11 — **ÊXITO:** **Gate da fila v1** + **multi-select backend** (release forçado + states) — controlo de lotes do Rui sobre o robot.
- 2026-06-11 — **ÊXITO:** **exe watcher pt68** construído (swap_and_smoke ALL OK) + **Release publicada via API REST + validada** (SHA round-trip).
- 2026-06-12 — **PROBLEMA→SOLUÇÃO→ÊXITO:** deadlock "Activas" reincidente (mão 2 pós-fecho-de-aba) — o `open_wizard` OG assumia o wizard às cegas (`Wizard assumed`) quando o chord falhava → pipeline contra o vazio. Fix: wrapper `_open_wizard_confirmed` confirma via janela `Hand Setup` real + escada re-chord→restart→bail (cold start = único estado 100% fiável). Release `watcher-pt70` (`315CC2B5…`). → `JOURNAL_2026-06-11-pt69-pt70.md`.
- 2026-06-12 — **PROBLEMA→SOLUÇÃO→ÊXITO:** betting scripts com 3-bets fabricados sobre opens all-in (`2.3×shove`) + SB-shoves `8<eff≤25` sem size — destapados por auditoria visual + busca inversa (BD prod). Fix: LEI do Rui §18 (tabela open blinds, tabela 3-bet BB, B1 sobre all-in, ordem [size,ALLIN]). Validado contra as mãos reais + suite 935 verde. → `REGRAS_NEGOCIO §18`.
- 2026-06-12 — **LIÇÃO:** mudar `setup_hand` (open_wizard→wrapper) partiu 11 testes do watcher que só o **full-run** apanhou (o swap_and_smoke passou na mesma) — a confirmação autoritária nova exigia o mock no stub partilhado. Correr a suite completa antes de declarar verde, não só o harness.
