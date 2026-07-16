# CANON_BOUNTIES — DEGRAUS (valores possíveis de coroa)

> **Anexo do `CANON_BOUNTIES.md` (LEI).** Tabela dos **valores POSSÍVEIS de coroa** até
> ~3 KOs, por formato. Construída pelo Rui (16 Jul 2026). É a régua física do detetor
> fora-de-grelha e do critério de exclusão dos conflitos.
>
> A **coroa fresca (inicial) = B = `buy_in_bounty ÷ 2`** (metade do bounty do buy-in — o KO
> instantâneo). Cada KO acrescenta metade da coroa da vítima → a coroa só **sobe**, em
> **degraus** (não é contínua). Uma leitura que **não cai num degrau** do torneio é suspeita.

## Degraus (múltiplos de B)

- **Simples** (múltiplos «limpos» de B): `1 · 1.5 · 1.75 · 1.875 · 2 · 2.25 · 2.5 · 2.75 · 3 · 3.5`
- **De SPLIT** (raros, marcados `°`): `1.25 · 1.625 · 1.8125 · 2.125 · 2.375 · 2.625 · 2.875 · 3.25`

## Tabela em dólares — pelos B confirmados do Rui

Colunas = o multiplicador × B (as `°` são degraus de split). Uma coroa lida deve bater
**exatamente** uma destas casas do **seu** torneio.

| B (=bounty÷2) | 1.25° | 1.5 | 1.625° | 1.75 | 1.875 | 2 | 2.125° | 2.25 | 2.5 | 2.75 | 3 | 3.5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **$5** ($21.60) | 6.25° | 7.50 | 8.13° | 8.75 | 9.38 | 10 | 10.63° | 11.25 | 12.50 | 13.75 | 15 | 17.50 |
| **$7.50** ($32) | 9.38° | 11.25 | 12.19° | 13.13 | 14.06 | 15 | 15.94° | 16.88 | 18.75 | 20.63 | 22.50 | 26.25 |
| **$10** ($44) | 12.50° | 15 | 16.25° | 17.50 | 18.75 | 20 | 21.25° | 22.50 | 25 | 27.50 | 30 | 35 |
| **$12.50** ($54) | 15.63° | 18.75 | 20.31° | 21.88 | 23.44 | 25 | 26.56° | 28.13 | 31.25 | 34.38 | 37.50 | 43.75 |
| **$20** ($88) | 25° | 30 | 32.50° | 35 | 37.50 | 40 | 42.50° | 45 | 50 | 55 | 60 | 70 |
| **$25** ($108) | 31.25° | 37.50 | 40.63° | 43.75 | 46.88 | 50 | 53.13° | 56.25 | 62.50 | 68.75 | 75 | 87.50 |
| **$35** ($150) | 43.75° | 52.50 | 56.88° | 61.25 | 65.63 | 70 | 74.38° | 78.75 | 87.50 | 96.25 | 105 | 122.50 |
| **$50** ($215) | 62.50° | 75 | 81.25° | 87.50 | 93.75 | 100 | 106.25° | 112.50 | 125 | 137.50 | 150 | 175 |
| **$125** ($525) | 156.25° | 187.50 | 203.13° | 218.75 | 234.38 | 250 | 265.63° | 281.25 | 312.50 | 343.75 | 375 | 437.50 |

*(A coluna «B» mostra o chão do torneio = `buy_in_bounty ÷ 2`; entre parênteses, o buy-in
total confirmado pelo Rui. A coroa **fresca = B = 1×** — não vem na tabela porque é o próprio
chão; a tabela lista os degraus **acima** dele.)*

## Notas obrigatórias (LEI)

1. **Os `°` (split) são RAROS** — cara de «pote dividido na HH». A **grelha do detetor NÃO os
   inclui** (decisão do Rui): o detetor fora-de-grelha só valida os degraus **simples**; um
   valor que só bate num `°` fica **sinalizado** e o **olho do Rui arbitra** (não se rejeita
   nem se auto-resolve com base num split).

2. **A tabela só descodifica SABENDO O TORNEIO.** Os valores **colidem entre formatos** — o
   mesmo número é degraus diferentes conforme o B. Ex.: **$25 = 1.25B° do $88** (B=$20) **E
   B (fresca) do $108** (B=$25). Ler uma coroa sem saber o torneio não diz nada; a base
   (`buy_in_bounty` do TS) é obrigatória para interpretar.

3. **Acima de ~3 KOs os degraus adensam-se** e a régua perde poder (as casas ficam tão juntas
   que quase qualquer valor «bate» numa). Vale como **bisturi nos 2 primeiros KOs**; em fase
   funda (coroas grandes, muitos KOs) a grelha deixa de discriminar — aí manda a trajetória
   (não-desce) e o olho.

---

Cross-ref: `CANON_BOUNTIES.md` (LEI, a física das coroas), `crown_recovery._on_halves_grid`
(a grelha no código — só degraus simples), `gg_health._crossing_conflicts` (exclusão por
pertença à grelha), `LICOES.md` (fósseis-chama; a grelha apanha a chama fora-de-grelha).
