# Formato de entrada do `margem_contribuicao.py`

Um CSV (UTF-8, separador vírgula) com **uma linha por pedido-item** — ou por SKU agregado no período, quando o relatório do canal não abre por pedido. Valores em reais, positivos. Aceita `1.234,56` ou `1234.56`.

| Coluna | Obrigatória | O que é |
|---|---|---|
| `canal` | sim | `Mercado Livre`, `Shopee`, `Amazon`, `Shein`, `TikTok Shop` — sempre escrito igual |
| `conta` | sim | `CRGFESTAS`, `CRGFESTAS2`, `ML Full`, `Shopee 1`, `Shopee 2`, `Amazon FBA`… |
| `pedido` | recomendada | id do pedido — é o que conta pedidos e ticket médio |
| `sku` | sim | SKU do Lexos (o mesmo usado no custo) |
| `titulo` | sim | título do anúncio |
| `unidades` | sim | quantidade vendida |
| `receita_bruta` | sim | preço pago pelo comprador pelo produto, **sem** o frete pago pelo comprador |
| `comissao` | sim | comissão/tarifa de venda do canal |
| `taxa_servico` | não | taxa fixa por item, taxa de serviço, taxa de transação |
| `afiliados` | não | comissão de afiliado / criador (Shopee, TikTok) |
| `frete_vendedor` | não | frete que o vendedor pagou (etiqueta, coparticipação, Full/FBA fulfillment) |
| `frete_recebido` | não | frete que o comprador pagou e foi repassado ao vendedor |
| `devolucao` | não | valor perdido com devolução/reembolso daquele item |
| `ads` | não | investimento em anúncio patrocinado **atribuído** àquele item/conta |
| `imposto` | não | imposto sobre a venda, se a nota já tiver alíquota |
| `status` | não | `cancelado` é descartado; qualquer outro valor entra |
| `custo_unit` | não | custo unitário **em reais**, já corrigido pela regra de unidade do Lexos |

Sem `custo_unit` na linha, o script procura o SKU no arquivo `--custos` (colunas `sku,custo_unit`).

Quando o ads só existe no total da conta (caso comum), coloque numa linha extra com `sku` = `ADS`, `receita_bruta` = 0 e o valor em `ads`. Ela entra no ACOS e na "MC pós-ads" da conta.

## De onde vem cada coluna, por canal

As fontes são as mesmas do `dre-mensal-crg` — leia as armadilhas de lá antes de montar.

| Canal | Relatório | Mapeamento |
|---|---|---|
| Shopee | Minha Renda → Pedidos Completos (`Income.lançado.br.*.xlsx`) | Linhas `Ver == 'Order'` para taxas e receita; `Ver == 'Sku'` para abrir por produto (rateie as taxas do pedido pela receita de cada SKU). Comissão → `comissao`, taxa de serviço → `taxa_servico`, afiliado → `afiliados`. |
| Mercado Livre | Faturamento → Conciliação → Por vendas | Tarifa de venda → `comissao`; custo fixo por unidade → `taxa_servico`; custo de envio → `frete_vendedor`. **Não use o extrato do Mercado Pago.** Mercado Ads vem do painel de Publicidade. |
| Amazon | Pagamentos → Todas as transações | Referral fee → `comissao`; FBA fulfillment fee → `frete_vendedor`; taxa de fechamento → `taxa_servico`. Sponsored Products vem do Campaign Manager. |
| Shein | Relatório de repasse / liquidação | Comissão → `comissao`. Se só houver o gráfico de GMV, o canal fica **sem MC** — registre "sem relatório de taxas". |
| TikTok Shop | Extrato financeiro (Finanças → Extratos) | Comissão da plataforma → `comissao`; taxa de transação → `taxa_servico`; comissão de afiliado/criador → `afiliados`; frete → `frete_vendedor`. Confira o campo Período: já vieram três cópias do mesmo mês. |
