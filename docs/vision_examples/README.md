# Few-shot visual da leitura de coroas — contrato + protocolo de medição

**Estado: 🟡 instrumento pronto, à espera das 3 imagens do Rui + do A/B (números antes de adotar).**

Ideia (pergunta do Rui, confirmada): antes da imagem ALVO, mandar à Vision 1-2 **exemplos
anotados** que ensinam a distinguir a **coroa** (placard dourado $ em cima do avatar) da
**chama** (círculo laranja junto ao timer = VPIP %, a IGNORAR). Depois **medir** se a taxa de
"chama-lida-como-coroa" cai — e a que custo — **antes** de ligar em produção.

## As 3 imagens (dropa-as AQUI, com estes nomes exatos)

| ficheiro | o que é | legenda (caption) usada na chamada |
|---|---|---|
| `01_placard_isolado.png` | só o **placard dourado** $ recortado | "Isto é a COROA: o placard rectangular DOURADO com um valor em $ ($50, $75…) que fica DIRECTAMENTE por CIMA do avatar. É ISTO que vai em `bounty_usd`." |
| `02_jogador_completo.png` | **um jogador inteiro**, anotável (placard em cima + chama na avatar + timer) | "Neste jogador: o $ no placard em CIMA = COROA (bounty_usd). O círculo LARANJA na avatar junto ao timer (ex.: 27%) = CHAMA/VPIP — IGNORAR, NUNCA vai em bounty_usd." |
| `03_mesa_8.png` | a **mesa de 8** completa | "Mesa completa: cada jogador tem placard $ (coroa, em cima) e pode ter chama % (laranja, na avatar). Lê só o $ do placard por seat; nunca a %." |

> As legendas vivem em `captions.json` (já criado com o texto acima — edita à vontade).
> Formatos aceites: `.png`/`.jpg`. Recorta o mais **apertado** possível (menos pixéis = mais
> barato — ver custo). Se um exemplo não existir, a chamada usa só os que existem (1 chega).

## Como o few-shot injecta (código)

`extract_table_ss_json(image_bytes, ..., examples=[...])` — quando `examples` é dado, o `content`
da mensagem fica: `[caption1, img1, caption2, img2, …, "Agora lê a imagem ALVO:", img_alvo, PROMPT]`.
Sem `examples` (default `None`) → comportamento ATUAL, byte-idêntico. **Nada muda em produção até
ligarmos** (o worker normal chama sem `examples`).

## Custo extra por chamada (calculado)

Tokens de imagem ≈ `w×h/750` (ref. do código: imagem 1280px ≈ **1229 tok**). Sonnet 4.6 input = **$3/1M**.

| exemplo | tamanho típico | ~tokens | ~custo |
|---|---|---|---|
| placard isolado (~200×80) | pequeno | ~25 | ~$0.0001 |
| jogador completo (~300×400) | médio | ~160 | ~$0.0005 |
| mesa de 8 (~1280) | grande | ~1229 | ~$0.0037 |
| legendas (3×~50 tok) | — | ~150 | ~$0.0005 |

- **2 exemplos pequenos (placard + jogador) + legendas ≈ +~335 tok ≈ +$0.001/chamada** (+7% sobre os ~$0.014 atuais).
- **+ a mesa de 8 ≈ +$0.0037** → **~$0.005/chamada no total** (+36%).
- **A/B de 20 leituras × 2 (com/sem) ≈ ~$0.66.** Negligível — decide-se pelos números de qualidade, não pelo custo.

## Protocolo A/B (o que corro quando as imagens cá estiverem)

1. Amostra: **20 capturas** table-SS reais (variadas: mesas cheias, PKO com coroas altas).
2. Para cada: corre a Vision **SEM** exemplos e **COM** exemplos (via `POST /api/table-ss/crown-ab`, dry-run, sem escrever).
3. **Métrica principal — taxa de chama-como-coroa:** nº de seats cujo `bounty_usd` sai um valor
   compatível com uma **%** (inteiro pequeno tipo 16/27/43) e/ou **< base÷2** (impossível para coroa fresca).
4. **Métrica de acordo:** onde há verdade selada (mãos que o Rui carimbou), % de seats que batem certo.
5. Reporto: taxa chama-como-coroa (com vs sem), acordo com a verdade, e o custo real medido. **Decides tu** se adota.
