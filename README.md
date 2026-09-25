# CRG Festas — rotinas de marketplace

## `skills/desempenho-lojas-crg`

Rotina mensal de desempenho das lojas no **Mercado Livre, Shopee, Amazon, Shein e TikTok Shop**:

1. saúde de cada conta (reputação, atrasos, cancelamentos, devoluções) contra a rodada anterior;
2. margem de contribuição por loja/conta e por SKU, com o CMV do Lexos, contra a **meta de 30%** (quanto falta em R$ e ajuste de preço estimado);
3. até 3 ideias de melhoria por loja, cada uma presa a um número da rodada.

Grava a nota em `02 - Áreas/Financeiro/Desempenho das lojas/` no cofre Segundo Cérebro.

| Arquivo | Para quê |
|---|---|
| `SKILL.md` | a rotina (instruções para o Claude) |
| `scripts/coletar_api.py` | puxa vendas e taxas pelas APIs (ML, Shopee, Amazon, TikTok Shop) e o custo pelo Lexos |
| `scripts/teste_coletar_api.py` | testes offline dos conectores (`python3 -m unittest teste_coletar_api`) |
| `referencias/credenciais-modelo.env` | modelo do arquivo de credenciais — preenchido, fica fora do Git e do cofre |
| `scripts/margem_contribuicao.py` | calcula MC por conta e por SKU a partir de um CSV normalizado — só biblioteca padrão |
| `referencias/formato-entrada.md` | colunas do CSV e de qual relatório de cada canal elas vêm |
| `referencias/alavancas-por-canal.md` | cardápio de ideias de melhoria, cada uma com o gatilho numérico |
| `exemplo/` | dados fictícios para testar o script |

Teste rápido:

```
cd skills/desempenho-lojas-crg/exemplo
python3 ../scripts/margem_contribuicao.py vendas-exemplo.csv --custos custos-exemplo.csv \
    --anterior vendas-anterior-exemplo.csv --saida saida
```

Para instalar: compacte a pasta `skills/desempenho-lojas-crg` em `.zip` e envie em claude.ai → Configurações → Capacidades → Skills. Para rodar todo mês, crie uma tarefa agendada no Cowork para o dia 21 com o texto "rode o desempenho das lojas do mês passado".
