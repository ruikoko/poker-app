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
