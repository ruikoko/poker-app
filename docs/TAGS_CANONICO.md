# TAGS_CANONICO — a lista canónica de tags de estudo (FONTE DE VERDADE)

**Sítio canónico** do vocabulário de tags de estudo da app (GG + HM3). Se vais
mexer em tags — vocabulário, normalização, incompatibilidades, pastas do IT,
gates que lêem tags — **lê isto primeiro**. Fonte no código:
`backend/app/services/tags_canonical.py` (a rede de reconhecimento unificada +
normalização na escrita, `4884f82`).

> **Estado (1 Jul 2026, pt97):** vocabulário fechado e validado pelo Rui;
> fonte única LIVE; as 2 regras de incompatibilidade estão **definidas aqui mas
> ainda NÃO enforçadas no código** (a app deixa coexistir; a secção "Saúde GG"
> só as SINALIZA — grupo "conflito de tags"). Enforcement = trabalho futuro.

---

## 1. O vocabulário REAL (não o teórico)

GG e HM3 **convergem no mesmo vocabulário pequeno**. Descoberta-chave: nas mãos
**Winamax** o Rui usa **as mesmas tags da GG** (`pos-pko`, `icm-pko`, …), **não**
os literais teóricos do HM3. Das ~54 `HM3_REAL_TAGS` só **3** têm mãos (`nota`,
`Timetell`, `For Review`); as outras **51 estão adormecidas** (aceites, mas
escondidas da UI até terem mãos — não se apagam).

O vocabulário é **(TIPO DE SPOT) × (FASE)** + `nota` + resíduos:

| Eixo | Membros canónicos |
|---|---|
| **TIPO DE SPOT** | `icm` · `icm-pko` · `pos-pko` · `pos-nko` · `speed-racer` *(só-GG)* |
| **FASE** | `base` (sem sufixo) **ou** `-ft` (mesa final) → `icm-ft`, `icm-pko-ft`, `pos-pko-ft`, `pos-nko-ft`, `speed-racer-ft` |
| **Transversal** | `nota` (`nota++` → `nota`; **`nota ex` é DISTINTO** — só agrupa visualmente com nota, NÃO se funde) |
| **Resíduos** | `Timetell`, `For Review` (HM3 legado, poucas mãos) |

**Forma canónica gravada = minúsculas com hífen** (`icm-pko-ft`). A GG já grava
assim; o HM3 tinha grafias tortas (`icm pko ft`, `pos pko FT`) — **backfilladas**
para a forma canónica em pt97.

## 2. Significados (do Rui — corrige suposições antigas)

- **`pos-nko`** = **PÓS-flop, Non-KO, torneio VANILLA** (sem bounty). ⚠️ **NÃO é
  "PKO posição"** — corrige qualquer texto que diga o contrário.
- **`pos-pko`** = pós-flop, torneio **PKO**.
- **`icm`** = ICM vanilla (não-PKO).
- **`icm-pko`** = ICM em torneio PKO.
- **`speed-racer`** = **tipo de torneio** (hyper-PKO da GG; não existe na Winamax).
- **`nota`** = marcação de vilão/observação (dispara Vilões; transversal, sem fase).

**Uma mão PODE ter 2 tipos de spot legítimos** — ex.: `icm-pko` + `pos-pko` =
defende a BB pré-flop **e** joga o pós-flop na mesma mão. Não é conflito.

## 3. As 2 REGRAS DE INCOMPATIBILIDADE (seladas pelo Rui)

Uma mão **não pode** ter, ao mesmo tempo:

- **R1 — FORMATO:** uma tag **PKO** `{icm-pko, pos-pko, speed-racer, +ft}` **e**
  uma tag **não-PKO** `{icm, pos-nko, +ft}`. *(Um torneio é PKO **ou** vanilla —
  não os dois.)*
- **R2 — FASE:** uma tag **base** e a **sua própria `-ft`** (ex.: `icm` + `icm-ft`,
  ou `pos-pko` + `pos-pko-ft`). *(A mesa é normal **ou** final.)*

**Neutras** (casam com tudo, nunca geram conflito): `nota`, `Timetell`,
`For Review`.

*(As regras vêm da semântica: TIPO DE SPOT pode acumular; FORMATO e FASE são
propriedades do torneio/momento e são exclusivas.)*

## 4. Normalização e reconhecimento (a rede unificada)

`canonicalize_tag(raw)` (em `tags_canonical.py`) resolve **qualquer forma
reconhecida** → canónica, e **preserva inalterado** o que não reconhece (51
adormecidas, `nota ex`, custom, resíduos). A rede absorve as 4 antigas:

- **`normalize_tag_key`** — minúsculas + hífen→espaço + colapsa espaços.
- **`IT_FOLDER_TAGS`** — nome da subpasta do IT → canónica (inclui a ordem
  invertida `PKO Pos`→`pos-pko`).
- **`hm3_tag_aliases`** — `GTw`→`pos-nko`, `nota++`→`nota`.
- **`tag_family_key`** — `nota ex`→`nota` (SÓ agrupamento; o literal fica).

**Normaliza na ESCRITA** nos 3 pontos de entrada (import HM3, 1-clique da
triagem, folder_tag do IT) + no PATCH da mão (TagEditor). A leitura continua
normalizada também (dados antigos).

## 5. Pastas do IT (o Rui cria; a app aprende)

Na GG a tag entra pela **subpasta do Intuitive Tables** onde o print cai (a
subpasta É a tag). Pastas do Rui (1 Jul 2026): `ICM`, `ICM PKO`, `PKO Pos`,
**`NKO Pos`** (era `NPKO Pos`), `SpeedRacer`, `Nota`, `ICM FT`, `ICM PKO FT`,
`PKO Pos FT` (**a criar:** `NKO Pos FT`, `Speed Racer FT`). Renomear uma pasta
do lado do Rui exige a app **aprender o nome novo** — agora resolvido pela fonte
única (basta o nome normalizar para uma forma reconhecida; nomes antigos
mantidos para não perder histórico).

## 6. Gates que LÊEM tags (não mexer sem cuidado — lêem NORMALIZADO)

Estes decidem por tag e **não** são tocados pela canónica (lêem normalizado; as
canónicas normalizam para as mesmas chaves de sempre):

- **Elegibilidade HRC** (`hrc_queue.select_andar1`, basket `DEFAULT_TAGS`).
- **Gate WPN** (`WPN_ALLOWED_TAGS = {ICM, ICM FT}`).
- **Equity model HRC** (`queue_export._derive_equity_model` — token `ft` → FT/FGS).
- **IRE** (`ire._has_ko_tag` — substring `ko` ou `speed racer`).
- **Vilões / Estudo** (`villain_rules` A/C/nota; gate de Estudo nota-only).

---
**Cross-refs:** `MAPA_ACOPLAMENTO §2` (`hm3_tags`/`discord_tags`) ·
`REGRAS_NEGOCIO` (fluxo de tagging) · `DESANON_ANATOMIA` (acoplamento tag↔captura) ·
`JOURNAL_2026-07-01-pt97.md`.
