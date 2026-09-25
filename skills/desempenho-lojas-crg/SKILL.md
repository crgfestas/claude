---
name: "desempenho-lojas-crg"
description: "Rotina de desempenho das lojas da CRG Festas no Mercado Livre, Shopee, Amazon, Shein e TikTok Shop — saúde de cada conta, faturamento e comparação com o período anterior, margem de contribuição por loja e por SKU (com o CMV real do Lexos) e ideias de melhoria específicas de cada loja, gravado no cofre Segundo Cérebro. Use quando o usuário pedir o desempenho das lojas, \"como estão as contas\", margem de contribuição por canal, qual loja dá mais lucro, ideias para melhorar as lojas, ou quando a tarefa agendada de desempenho disparar."
---

# Desempenho das lojas — CRG Festas

Uma vez por mês (e sob demanda), olhar **cada loja** dos cinco marketplaces e responder três perguntas:

1. **A conta está saudável?** Reputação, atrasos, cancelamentos, devoluções, faturamento contra o período anterior.
2. **Quanto sobra de cada venda?** Margem de contribuição por loja e por SKU.
3. **O que fazer em cada loja?** No máximo 3 ideias por loja, cada uma presa a um número desta rodada.

Lojas cobertas: **Mercado Livre** (CRGFESTAS, CRGFESTAS2, ML Full), **Shopee** (conta 1 e conta 2 / Full Shopee), **Amazon** (FBA e FBM), **Shein**, **TikTok Shop**. Magalu e loja física ficam de fora — estão no `dre-mensal-crg`.

> **Relação com as outras skills.** O `dre-mensal-crg` fecha o resultado da empresa inteira (estrutura, impostos, dívida). Esta aqui para na **margem de contribuição** e olha loja a loja e SKU a SKU para decidir ação. Ideia de preço de SKU específico → encaminhe para `precificacao`. Anúncio fraco → `kit-anuncio-mercado-livre`. As regras de relatório e de custo do Lexos são as mesmas do DRE: **leia a seção de armadilhas do `dre-mensal-crg` antes de começar.**

## Antes de começar

1. O cofre fica em `Desktop\Segundo Celebro\Segundo Celebro`. Sem a pasta conectada, avise e pare.
2. Leia `CLAUDE.md`, `Contexto - CRG Festas.md`, o DRE mais recente em `02 - Áreas/Financeiro/` e a rodada anterior desta rotina em `02 - Áreas/Financeiro/Desempenho das lojas/`.
3. Peça acesso a `~/Downloads` (relatórios baixados) e a `~/Desktop/Segundo Celebro` (chave do Lexos).
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

1. **Baixe os relatórios financeiros** de cada loja (tabela em `referencias/formato-entrada.md`). Só relatório com taxa por pedido serve para MC; painel de GMV serve só para a parte 1.
2. **Monte um CSV normalizado** por período — `99 - Anexos/Desempenho/AAAA-MM/vendas.csv` — no formato de `referencias/formato-entrada.md`. Uma linha por pedido-item.
3. **Custo:** reaproveite `99 - Anexos/DRE/CMV medido por SKU - Lexos.csv` e o cache `99 - Anexos/DRE/_cache/catalogo-lexos.json`. SKU que não estiver lá: API do Lexos, casamento por nome com `fuzz.ratio` ≥ 90, **regra de unidade centavos × reais**. Sem teste que feche → sem custo. Grave em `custos.csv` (`sku,custo_unit`).
4. **Rode o script:**

   ```
   python scripts/margem_contribuicao.py vendas.csv --custos custos.csv \
       --anterior ../AAAA-MM-anterior/vendas.csv --mc-minima <mínimo do cofre> \
       --saida 99 - Anexos/Desempenho/AAAA-MM/
   ```

   Ele gera `margem_contribuicao.md` (tabelas prontas para a nota) e `margem_por_sku.csv`. A MC mínima vem do cofre; se não houver registro, use 15% e diga que é padrão.
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
tags: [financeiro, marketplace, desempenho]
---
# Desempenho das lojas — mês/AAAA

## Resumo
| Loja | Conta | Receita | Var. mês ant. | Saúde | MC % | MC pós-ads % | Veredito |
<!-- veredito: 🟢 crescer · 🟡 ajustar · 🔴 estancar -->

## Saúde das contas
| Loja | Conta | Indicador | Agora | Anterior | Situação |

## Margem de contribuição por conta
<!-- tabela do margem_contribuicao.md -->

## Comparativo com o mês anterior

## SKUs que mais geram margem
## SKUs abaixo da MC mínima
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
- **Nunca altere preço, anúncio, campanha de ads ou comissão de afiliado.** Esta rotina recomenda; quem executa é o Leandro.
- Valores de painel são brutos — antes de taxa, frete e imposto. Diga isso sempre que mostrar faturamento de painel.
- Nunca exponha a chave da API do Lexos no chat nem em arquivo do cofre.
- Nunca apague nota do Leandro — no máximo mova para `04 - Arquivo/`.
- Diga de qual relatório veio cada número.

# Ao final

Responda em até 8 linhas: receita total das cinco lojas, a loja com maior e a com menor MC pós-ads (com o %), a conta com saúde em risco (se houver), a ideia de maior ganho estimado, lojas que ficaram sem relatório, e onde ficou a nota.
