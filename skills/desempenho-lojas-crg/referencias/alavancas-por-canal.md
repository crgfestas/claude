# Alavancas de melhoria por canal

Cardápio para a seção "Ideias de melhoria". **Toda ideia tem de nascer de um número da rodada** — o gatilho da primeira coluna. Ideia sem gatilho não entra no relatório.

Tarifas, faixas de frete grátis e regras de programa mudam com frequência. Antes de citar um valor de regra (ex.: "a partir de R$ X o frete é grátis"), confirme na central do vendedor do canal ou diga que é a regra conhecida até a data da rodada.

## Transversais (valem para todas as lojas)

| Gatilho no número | Ideia |
|---|---|
| SKU com MC negativa ou abaixo da mínima em mais de uma loja | Problema é o produto, não o canal: rever custo de compra com fornecedor, trocar embalagem, ou descontinuar |
| SKU com MC boa num canal e ruim noutro | Preço por canal: subir no canal caro ou tirar o SKU de lá. Use `precificacao` para o preço |
| Ticket médio baixo e frete líquido acima de ~10% da receita | Kit/combo para subir o ticket (73% da receita Shopee já é kit — o formato funciona) |
| Muito SKU sem custo ou com custo suspeito | Antes de qualquer ideia de preço: corrigir o cadastro de custo no Lexos. Sem isso a margem é chute |
| Receita concentrada em poucos SKUs (top 5 > 50%) | Risco de ruptura: checar estoque e cobertura desses SKUs; ter segundo fornecedor |
| Devolução acima de 3% da receita num SKU | Ler motivo das devoluções: foto/descrição enganosa, avaria no envio, tamanho/quantidade mal explicada |
| ACOS acima da MC % antes de ads | O anúncio está pagando para vender com prejuízo: pausar ou reduzir lance nesse SKU |
| Mesma loja em dois CNPJs com MC muito diferente | Verificar se a diferença é regime tributário, nível de reputação ou mix — e concentrar volume onde a margem é maior |

## Mercado Livre (CRGFESTAS, CRGFESTAS2, ML Full)

| Gatilho | Ideia |
|---|---|
| Reputação abaixo de verde ou métrica de atraso/reclamação subindo | Prioridade 1: reputação derruba exposição e aumenta tarifa efetiva. Atacar a causa (atraso de postagem, cancelamento por falta de estoque) |
| Frete líquido alto em produto leve e de giro | Avaliar Full para os campeões — melhora prazo e posição, mas soma custo de armazenagem; comparar MC Full × Flex/Coleta |
| Anúncio clássico com MC folgada e conversão baixa | Testar Premium (parcelamento) nos campeões: tarifa maior, conversão maior; medir MC após 2 semanas |
| Perdendo a posição num campeão | Rodar `precificacao`; olhar `preco_para_ganhar` |
| Muitas perguntas repetidas no mesmo anúncio | Reescrever título/descrição/foto (skill `kit-anuncio-mercado-livre`) |
| Mercado Ads com ACOS alto | Separar campanhas por curva: Curva A com ROAS alvo, cauda longa com orçamento baixo |

## Shopee (Shopee 1 e Shopee 2)

| Gatilho | Ideia |
|---|---|
| Taxa total (comissão + serviço + afiliado) acima de ~36% (referência do DRE set/2026) | Checar se está pagando programa de frete grátis/cupom em SKU de ticket baixo onde ele não compensa |
| Afiliados com peso alto na taxa | Revisar a % oferecida por SKU: comissão de afiliado alta só em SKU com MC folgada |
| Ticket baixo com taxa fixa por item pesando | Kit/combo e "compre 2 leve 3" para diluir a taxa fixa |
| Envio atrasado / taxa de não cumprimento subindo | Risco de penalidade e perda de exposição: ajustar prazo de postagem ou estoque |
| Full Shopee com SKU parado | Retirar do Full o que não gira — armazenagem come margem |

## Amazon (Amazon FBA e FBM)

| Gatilho | Ideia |
|---|---|
| Buy Box perdida em SKU de giro | Preço e disponibilidade: conferir concorrente na mesma ASIN |
| FBA com taxa de armazenagem/estoque antigo | Liquidar ou retirar estoque parado antes da cobrança de longo prazo |
| Produto leve e barato com taxa de fulfillment alta | Avaliar FBM ou kit para subir o ticket |
| ODR / taxa de defeito ou atraso subindo | Saúde da conta primeiro — risco de suspensão |
| Sponsored Products com ACOS acima da MC % | Negativar termos amplos, concentrar em termos exatos que convertem |

## Shein

| Gatilho | Ideia |
|---|---|
| Canal sem relatório de taxas | Primeiro passo é conseguir o relatório de repasse — sem ele não há MC |
| GMV crescendo com poucos SKUs | Ampliar catálogo com o que já vende bem nos outros canais (kits de festa, temas) |
| Devolução alta | Público de moda devolve mais: descrição de quantidade/tamanho muito explícita, foto com escala |
| Prazo de envio fora do exigido | Ajustar estoque/antecedência — atraso pesa na avaliação da loja |

## TikTok Shop

| Gatilho | Ideia |
|---|---|
| Comissão de afiliado/criador pesando muito na taxa | Pagar comissão maior só em SKU com MC folgada; nos demais, amostra + comissão menor |
| GMV concentrado em poucos vídeos/criadores | Diversificar criadores e produzir vídeo próprio (tema de festa, unboxing de kit) |
| Live/vídeo com venda mas MC baixa | O produto de "gancho" pode dar MC baixa se puxar kit junto — medir MC do pedido, não do item |
| Pontuação da loja caindo (atraso, cancelamento) | Corrigir antes de investir em criador: loja penalizada perde alcance |
| Canal com MC boa e volume baixo | Canal para crescer: mais SKUs vencedores de Shopee/ML, campanhas de data comemorativa |
