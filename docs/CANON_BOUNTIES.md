# CANON DOS BOUNTIES — a lei das coroas (ditado pelo Rui)

> **Estado: 🟡 RASCUNHO — à espera do carimbo do Rui.** Depois de carimbado, fica LEI:
> **nada sobre coroas se decide fora deste documento.** Como a lei dos sizings e a lei do
> selo, isto rege TODO o código que lê, deriva, grava ou mostra uma coroa ($ bounty).

## 0. A premissa (a frase que manda)

**A COROA É O BOUNTY.** A app só conhece **coroas** — o valor em $ que a **placa** mostra
na cabeça de cada jogador. É a única unidade da casa.

**BANIDO do vocabulário:** "bounty total", "instantâneo", "metade do total", conversões
de unidade. Não existem na app. Se um cálculo ou um texto precisa de "total" ou de uma
conversão, está errado — traduz para coroas antes. A placa é a verdade; a coroa é o número.

## 1. Exemplo fixo (para todos os números baterem)

**Speed Racer $108 · coroa inicial = $25.** Um jogador fresco (ainda sem KOs) tem a placa
a mostrar **$25**. É o ponto de partida de toda a aritmética abaixo.

## 2. As 6 regras

1. **Eliminar = ganhar a COROA da vítima** (vai para o bolso do matador — é o prémio).
2. **A coroa do matador SOBE METADE da coroa da vítima.** Elimina um fresco ($25) →
   a coroa dele sobe **$12.50** (`25 → 37.50 → …`).
3. **O VERDE mostra o incremento** = **coroa da vítima ÷ 2**. (Fresco $25 → verde $12.50.)
4. **★ A COROA DE QUEM MORREU = O VERDE × 2** (regra do Rui). É a recuperação: é assim que
   o painel preenche o **eliminado**, **por vítima**. (Verde $12.50 → coroa da vítima $25.)
5. **Multi-KO:** o **verde total = soma das coroas das vítimas ÷ 2**. → A **contraprova do
   card** compara com a **soma ÷ 2** (não com a soma inteira). *Caso do Rui: 2 frescos, verde
   total $25 → coroas $25 cada ✓* (`(25+25)/2 = 25`).
6. **KO dividido** (dois matadores partem uma vítima — raro): fica **registado como raridade**,
   **não** ajusta as regras acima.

## 3. A progressão (frescos $25, um KO de cada vez)

Cada KO de um **fresco** ($25) soma **$12.50** à coroa do matador:

```
 coroa do matador:   25.00  →  37.50  →  50.00  →  62.50  →  75.00  → …
 (cada passo = +12.50 = coroa da vítima fresca ÷ 2)
```

Se a vítima **não** é fresca (já acumulou), o passo é **a coroa DELA ÷ 2** — não $12.50 fixo.
O incremento é sempre **metade da coroa da vítima do momento** (regra 2/3).

## 4. O duplo-KO do Rui (multi-KO, regra 5)

Numa mão, o Hero elimina **dois** jogadores **frescos** (coroa $25 cada):

- coroa de cada vítima (o que se preenche, regra 4) = **$25** cada;
- **verde total na placa do matador** = `(25 + 25) / 2` = **$25** (regra 5);
- **contraprova:** soma das coroas ($50) **÷ 2** = **$25** = o verde total ✓.

O erro a evitar (corrigido pela regra 5): comparar o verde ($25) com a **soma inteira** ($50)
e achar que "não bate". Bate — o verde é sempre a soma **÷ 2**.

## 5. Onde isto já vive no código (para o próximo Claude não reabrir)

- **Regra 4** (coroa do eliminado = verde × 2): `eliminated_bounty.resolve_seat_bounty`
  (`GREEN_TO_CROWN_FACTOR = 2.0`) — chokepoint único; cobre a recuperação (Etapa 2 `/suggest`)
  e o scrub `green_ko` de ingest.
- **Regra 5** (multi-KO: verde total = soma ÷ 2): contraprova do card em
  `CrownRecovery.jsx` (Group1Card multi-KO).
- **Selo:** um valor de coroa validado pelo Rui é intocável (`LEI_SELO_COROAS_NOMES.md`).

**Manutenção:** mudou uma regra de coroa? Muda AQUI primeiro (com carimbo do Rui), depois o
código. Um doc de regras de coroa fora deste é dívida — funde-se aqui.
