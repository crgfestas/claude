---
name: "desempenho-lojas-crg"
description: "Rotina de desempenho das lojas da CRG Festas no Mercado Livre, Shopee, Amazon, Shein e TikTok Shop — saúde de cada conta, faturamento e comparação com o período anterior, margem de contribuição por loja e por SKU (com o CMV real do Lexos) e ideias de melhoria específicas de cada loja, gravado no cofre Segundo Cérebro. Use quando o usuário pedir o desempenho das lojas, \"como estão as contas\", margem de contribuição por canal, qual loja dá mais lucro, ideias para melhorar as lojas, ou quando a tarefa agendada de desempenho disparar."
---

# Desempenho das lojas — CRG Festas

Uma vez por mês (e sob demanda), olhar **cada loja** dos cinco marketplaces e responder três perguntas:

1. **A conta está saudável?** Reputação, atrasos, cancelamentos, devoluções, faturamento contra o período anterior.
2. **Quanto sobra de cada venda?** Margem de contribuição por loja e por SKU.
3. **O que fazer em cada loja?** No máximo 3 ideias por loja, cada uma presa a um número desta rodada.

**Meta: margem de contribuição ideal de 30%** (MC pós-ads). Veredito por loja e por SKU:
🟢 **na meta** (≥ 30%) · 🟡 **abaixo da meta** (15–30%) · 🔴 **estancar** (< 15% ou negativa).

Lojas cobertas: **Mercado Livre** (CRGFESTAS, CRGFESTAS2, ML Full), **Shopee** (conta 1 e conta 2 / Full Shopee), **Amazon** (FBA e FBM), **Shein**, **TikTok Shop**. Magalu e loja física ficam de fora — estão no `dre-mensal-crg`.

> **Relação com as outras skills.** O `dre-mensal-crg` fecha o resultado da empresa inteira (estrutura, impostos, dívida). Esta aqui para na **margem de contribuição** e olha loja a loja e SKU a SKU para decidir ação. Ideia de preço de SKU específico → encaminhe para `precificacao`. Anúncio fraco → `kit-anuncio-mercado-livre`. As regras de relatório e de custo do Lexos são as mesmas do DRE: **leia a seção de armadilhas do `dre-mensal-crg` antes de começar.**

## Antes de começar

1. O cofre fica em `Desktop\Segundo Celebro\Segundo Celebro`. Sem a pasta conectada, avise e pare.
2. Leia `CLAUDE.md`, `Contexto - CRG Festas.md`, o DRE mais recente em `02 - Áreas/Financeiro/` e a rodada anterior desta rotina em `02 - Áreas/Financeiro/Desempenho das lojas/`.
3. Peça acesso a `~/Desktop/Segundo Celebro` (chave do Lexos e `credenciais-api.env`) e a `~/Downloads` (relatórios, só para o que a API não cobrir).
4. Defina o período. Padrão: **mês fechado anterior**, rodando **a partir do dia 20** (antes disso a conciliação da Shopee vem truncada). Pedido fora dessa janela = **prévia**: use os painéis de GMV, marque a nota como `prévia` e não calcule MC de canal com repasse incompleto.
5. Arquivos da rodada em `99 - Anexos/Desempenho/AAAA-MM/`. Crie a pasta se não existir.

---

# 1. Saúde de cada conta

Uma linha por conta. O que não puder ser obtido vira **"não obtido"** — nunca zero, nunca estimado.

| Loja | Onde olhar | Indicadores |
|---|---|---|
| Mercado Livre | ferramentas `minha_conta`, `resumo_vendas` (dias=30), `listar_meus_anuncios`; para CRGFESTAS2 e Full, painel da conta | cor da reputação, % reclamações, % atrasos, % cancelamentos, anúncios pausados/com saúde baixa, estoque zerado em item de giro |
| Shopee | Central do Vendedor → **Saúde da conta** e **Dados de negócio** | taxa de não cumprimento, envio atrasado, avaliação da loja, pontos de penalidade, visitantes, conversão |
| Amazon | Seller Central → **Saúde da conta** e **Relatórios de negócios** | ODR, taxa de envio atrasado, taxa de cancelamento, % Buy Box, sessões, conversão, estoque FBA parado |
| Shein | Painel do vendedor → desempenho da loja | nota da loja, pontualidade de envio, devolução, GMV |
| TikTok Shop | Painel → **Saúde da loja** e Visão geral | pontuação da loja, violações, GMV por origem (vídeo / live / vitrine / afiliado) |

Compare com a última medição registrada. **A mudança é o que interessa** — número isolado não diz nada. Sem rodada anterior, esta é a linha de base: diga isso.

⚠️ A conta CRGFESTAS é ~10% da operação. Nunca chame o número de uma conta de "faturamento da CRG Festas".

---

# 2. Margem de contribuição

## Definição (a mesma do DRE)

```
Receita bruta (produto, sem o frete pago pelo comprador)
(–) CMV                        custo do Lexos, corrigido pela regra de unidade
(–) Taxa do canal              comissão + taxa de serviço/fixa + afiliados
(–) Frete líquido              frete pago pelo vendedor − frete repassado
(–) Devoluções
= Margem de contribuição (MC)
(–) Ads do canal e imposto sobre venda
= MC pós-ads                    ← a que decide se vale investir mais na loja
```

## Passo a passo

1. **Colete pela API** — é o caminho padrão:

   ```
   python scripts/coletar_api.py --de AAAA-MM-01 --ate AAAA-MM-último \
       --credenciais "~/Desktop/Segundo Celebro/credenciais-api.env" \
       --saida "99 - Anexos/Desempenho/AAAA-MM"
   ```

   | Canal | API | O que traz |
   |---|---|---|
   | Mercado Livre | API oficial (`/orders/search`, `/shipments/{id}/costs`) | pedido, SKU, preço, tarifa de venda, frete do vendedor — todas as contas em `ML_CONTAS` |
   | Shopee | Open Platform v2 (`get_order_list`, `get_escrow_detail`) | repasse por pedido: comissão, taxa de serviço, afiliado, frete; pedido ainda não liquidado fica fora da MC e é contado no log |
   | Amazon | SP-API Finances (`financialEvents`) | venda, comissão, FBA, reembolsos e Sponsored Products — **por data de lançamento financeiro** |
   | TikTok Shop | Partner API 202309 (pedidos + `statement_transactions`) | **beta**: na primeira rodada confira `bruto/tiktok-extratos.json` contra o extrato do painel |
   | Shein | não tem API aberta ao vendedor | relatório de repasse, acrescentado ao `vendas.csv` à mão |
   | Custo | API do Lexos (`/Catalogo/ObterProdutoSku`) | custo com a regra de unidade centavos × reais já aplicada → `custos.csv` |

   Leia `coleta.log`. Canal com "credenciais ausentes" ou "FALHOU" → **não obtido** na nota; aí, e só aí, caia para o relatório exportado (`referencias/formato-entrada.md`). O modelo das credenciais está em `referencias/credenciais-modelo.env`. **Nunca mostre o conteúdo desse arquivo.**

   Se a sessão tiver as ferramentas do Mercado Livre (`resumo_vendas`, `minha_conta`, `listar_meus_anuncios`), use-as para a parte 1 (saúde) e para conferir o faturamento que o coletor trouxe.
2. **Ads que a API não trouxe** (Mercado Ads, Shopee Ads, TikTok Ads): acrescente uma linha `sku=ADS` por conta no `vendas.csv` com o valor do painel.
3. **Custo que o Lexos não confirmou:** tente `99 - Anexos/DRE/CMV medido por SKU - Lexos.csv`. Sem teste que feche → sem custo.
4. **Rode o cálculo:**

   ```
   python scripts/margem_contribuicao.py vendas.csv --custos custos.csv \
       --anterior ../AAAA-MM-anterior/vendas.csv --mc-alvo 30 --mc-minima 15 \
       --saida "99 - Anexos/Desempenho/AAAA-MM"
   ```

   Gera `margem_contribuicao.md` e `margem_por_sku.csv`, com, por loja e por SKU: MC pós-ads, **quanto falta em R$ para 30%**, **ajuste de preço estimado para chegar em 30%** e o veredito.
5. **Confira antes de acreditar:**
   - **Cobertura de custo** abaixo de 70% da receita numa loja → a MC daquela loja é indicativa; diga isso na tabela.
   - CMV da loja muito fora de 35–40% (referência medida set/2026) → desconfie do cruzamento de custo antes do número.
   - Taxa da Shopee muito longe de ~36% e do ML de ~38% (DRE set/2026) → confira o mapeamento das colunas.
   - Receita por loja contra o Lexos no mesmo período: divergência acima de 3% vira alerta na nota.

O script descarta automaticamente SKU com CMV fora de 8–75% (erro de unidade) e lista esses SKUs à parte. **Não force esses SKUs de volta** — corrija o custo ou deixe fora.

---

# 3. Ideias de melhoria por loja

Use o cardápio de `referencias/alavancas-por-canal.md`. Regras:

- **No máximo 3 ideias por loja**, em ordem de impacto em R$ de margem.
- **Cada ideia cita o número que a disparou** (ex.: "MC pós-ads de 4% com ACOS de 18% no SKU X"). Ideia genérica ("melhorar fotos") sem gatilho não entra.
- Estime o ganho quando der: "se a taxa de afiliado desse SKU cair de 15% para 8%, a MC sobe ~R$ 1.200/mês". Diga que é estimativa.
- Loja 🟡 ou 🔴: a primeira ideia diz **como fechar o "Falta p/ 30%"** — somando alavancas (taxa, frete, ads, kit, preço) até cobrir o valor. Aumento de preço acima de ~10% num SKU raramente é viável sozinho: diga isso e combine com outra alavanca.
- Saúde da conta em risco (reputação caindo, penalidade, ODR alto) vem **antes** de qualquer ideia de margem naquela loja.
- Loja com MC pós-ads negativa → ideia nº 1 é estancar (pausar ads no SKU, subir preço, tirar SKU do canal).

---

# 4. Gravar

**Nota:** `02 - Áreas/Financeiro/Desempenho das lojas/Desempenho AAAA-MM.md`

```markdown
---
tipo: desempenho-lojas
periodo: AAAA-MM
status: fechado | prévia
atualizado: AAAA-MM-DD
lojas_com_mc: []
lojas_sem_relatorio: []
mc_alvo: 30
tags: [financeiro, marketplace, desempenho]
---
# Desempenho das lojas — mês/AAAA

## Resumo
| Loja | Conta | Receita | Var. mês ant. | Saúde | MC % | MC pós-ads % | Falta p/ 30% | Veredito |
<!-- veredito: 🟢 na meta (≥30%) · 🟡 abaixo da meta (15–30%) · 🔴 estancar (<15%) -->

## Saúde das contas
| Loja | Conta | Indicador | Agora | Anterior | Situação |

## Margem de contribuição por conta
<!-- tabela do margem_contribuicao.md -->

## Comparativo com o mês anterior

## SKUs que mais geram margem
## SKUs abaixo da meta de 30% (com preço para a meta)
## SKUs sem custo ou com custo suspeito

## Ideias de melhoria
### Mercado Livre
### Shopee
### Amazon
### Shein
### TikTok Shop
<!-- até 3 por loja: gatilho → ação → ganho estimado -->

## Premissas e ressalvas
<!-- período, relatórios usados, cobertura de custo, o que ficou "não obtido" -->

## Leitura
<!-- até 5 linhas: qual loja sustenta a empresa, qual queima margem, o que mudou -->
```

**Também:**
- Salve `vendas.csv`, `custos.csv`, `margem_contribuicao.md` e `margem_por_sku.csv` em `99 - Anexos/Desempenho/AAAA-MM/`.
- Registre a nova medição de saúde de cada conta no histórico da nota da conta (ex.: `02 - Áreas/Mercado Livre/Conta CRGFESTAS.md`); crie a nota da conta se não existir.
- Loja com MC pós-ads negativa ou saúde em risco vira nota em `01 - Projetos/` com `#projeto/ativo`, linkada na rodada.
- SKU abaixo da MC mínima em loja de ML → liste na próxima rodada de `precificacao`.

# Regras invioláveis

- **Nunca invente número.** Loja sem relatório é "não enviado"/"não obtido", nunca zero.
- **Nunca use custo cru do Lexos** sem a regra de unidade; nunca baixe o corte de 90 no casamento de nome.
- **Nunca altere preço, anúncio, campanha de ads ou comissão de afiliado.** As APIs são usadas só para leitura. Esta rotina recomenda; quem executa é o Leandro.
- Nunca exiba nem copie para a nota o conteúdo de `credenciais-api.env`.
- Valores de painel são brutos — antes de taxa, frete e imposto. Diga isso sempre que mostrar faturamento de painel.
- Nunca exponha a chave da API do Lexos no chat nem em arquivo do cofre.
- Nunca apague nota do Leandro — no máximo mova para `04 - Arquivo/`.
- Diga de qual relatório veio cada número.

# Ao final

Responda em até 8 linhas: receita total das cinco lojas, a MC pós-ads total contra a meta de 30% (e quanto falta em R$), a loja com maior e a com menor MC pós-ads (com o %), a conta com saúde em risco (se houver), a ideia de maior ganho estimado, lojas que ficaram sem relatório, e onde ficou a nota.
