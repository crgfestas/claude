#!/usr/bin/env python3
"""Margem de contribuição por loja/conta e por SKU — CRG Festas.

Entrada: CSV normalizado (uma linha por pedido-item ou por SKU agregado),
montado a partir dos relatórios de cada marketplace. Ver
referencias/formato-entrada.md.

Uso:
    python margem_contribuicao.py vendas.csv [--anterior vendas_mes_anterior.csv]
        [--custos custos.csv] [--mc-alvo 30] [--mc-minima 15] [--saida pasta/]

Só biblioteca padrão. Não faz correção de unidade do Lexos: o custo que entra
aqui já tem de estar em reais por unidade vendida.
"""
import argparse
import csv
import os
import sys
from collections import defaultdict

CAMPOS_VALOR = [
    "unidades", "receita_bruta", "comissao", "taxa_servico", "afiliados",
    "frete_vendedor", "frete_recebido", "ads", "devolucao", "imposto",
]
# CMV fora desta faixa é erro de unidade que passou (regra do dre-mensal-crg)
CMV_MIN, CMV_MAX = 0.08, 0.75


def num(v):
    if v is None:
        return 0.0
    s = str(v).strip().replace("R$", "").replace(" ", "")
    if not s:
        return 0.0
    if "," in s:  # formato brasileiro 1.234,56
        s = s.replace(".", "").replace(",", ".")
    return float(s)


def ler_custos(caminho):
    custos = {}
    if not caminho:
        return custos
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            sku = (r.get("sku") or "").strip()
            if sku and (r.get("custo_unit") or "").strip():
                custos[sku] = num(r["custo_unit"])
    return custos


def ler_vendas(caminho, custos):
    linhas = []
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            status = (r.get("status") or "").strip().lower()
            if status in ("cancelado", "cancelada"):
                continue
            item = {k: num(r.get(k)) for k in CAMPOS_VALOR}
            item["canal"] = (r.get("canal") or "").strip() or "sem canal"
            item["conta"] = (r.get("conta") or "").strip() or item["canal"]
            item["pedido"] = (r.get("pedido") or "").strip()
            item["sku"] = (r.get("sku") or "").strip()
            item["titulo"] = (r.get("titulo") or "").strip()
            cu = (r.get("custo_unit") or "").strip()
            item["custo_unit"] = num(cu) if cu else custos.get(item["sku"])
            linhas.append(item)
    return linhas


def novo_acum():
    a = defaultdict(float)
    a["pedidos"] = set()
    return a


def acumular(a, it, custo_ok):
    a["pedidos"].add(it["pedido"] or id(it))
    for k in CAMPOS_VALOR:
        a[k] += it[k]
    a["taxa"] += it["comissao"] + it["taxa_servico"] + it["afiliados"]
    a["frete_liq"] += it["frete_vendedor"] - it["frete_recebido"]
    if custo_ok:
        a["receita_c_custo"] += it["receita_bruta"]
        a["cmv"] += it["custo_unit"] * it["unidades"]
        # MC só é calculada sobre a parte da receita que tem custo confiável
        a["taxa_c_custo"] += it["comissao"] + it["taxa_servico"] + it["afiliados"]
        a["frete_c_custo"] += it["frete_vendedor"] - it["frete_recebido"]
        a["dev_c_custo"] += it["devolucao"]


def custo_valido(it):
    cu = it["custo_unit"]
    if cu is None or cu <= 0 or it["unidades"] <= 0 or it["receita_bruta"] <= 0:
        return False, cu is not None and cu > 0
    pct = cu * it["unidades"] / it["receita_bruta"]
    return CMV_MIN <= pct <= CMV_MAX, True


def indicadores(a, alvo=0.30):
    rb = a["receita_bruta"]
    rc = a["receita_c_custo"]
    ped = len(a["pedidos"])
    mc = rc - a["cmv"] - a["taxa_c_custo"] - a["frete_c_custo"] - a["dev_c_custo"]
    # ads e imposto são do canal inteiro: rateados pela cobertura de custo
    cob = rc / rb if rb else 0.0
    mc_pos = mc - (a["ads"] + a["imposto"]) * cob
    return {
        "receita_bruta": rb,
        "pedidos": ped,
        "unidades": a["unidades"],
        "ticket": rb / ped if ped else 0.0,
        "taxa_pct": a["taxa"] / rb if rb else 0.0,
        "frete_pct": a["frete_liq"] / rb if rb else 0.0,
        "dev_pct": a["devolucao"] / rb if rb else 0.0,
        "ads": a["ads"],
        "acos": a["ads"] / rb if rb else 0.0,
        "cobertura": cob,
        "cmv_pct": a["cmv"] / rc if rc else None,
        "mc": mc if rc else None,
        "mc_pct": mc / rc if rc else None,
        "mc_pos": mc_pos if rc else None,
        "mc_pos_pct": mc_pos / rc if rc else None,
        # quanto falta (R$) para a MC pós-ads chegar na meta, sobre a receita com custo
        "gap_alvo": (alvo * rc - mc_pos) if rc else None,
        "preco_alvo_fator": preco_alvo_fator(a, alvo),
    }


def preco_alvo_fator(a, alvo):
    """Fator a aplicar no preço médio para a MC chegar na meta.

    Taxas do canal e ads escalam com o preço (percentuais); CMV, frete e
    devolução ficam fixos por unidade. p' = fixos / (1 − taxa% − ads% − alvo).
    """
    rc = a["receita_c_custo"]
    if not rc:
        return None
    var_pct = (a["taxa_c_custo"] / rc) + (a["ads"] + a["imposto"]) / a["receita_bruta"]
    fixos = a["cmv"] + a["frete_c_custo"] + a["dev_c_custo"]
    den = 1 - var_pct - alvo
    if den <= 0:
        return float("inf")  # meta inviável no canal com essas taxas
    return (fixos / den) / rc


def veredito(i, alvo, minima):
    m = i["mc_pos_pct"]
    if m is None:
        return "⚪ sem custo"
    if m >= alvo:
        return "🟢 na meta"
    if m >= minima:
        return "🟡 abaixo da meta"
    return "🔴 estancar"


def ajuste(fator):
    if fator is None:
        return "—"
    if fator == float("inf"):
        return "inviável"
    return ("+" if fator >= 1 else "") + pct(fator - 1)


def brl(v):
    if v is None:
        return "—"
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-R$ " if v < 0 else "R$ ") + s


def pct(v):
    return "—" if v is None else f"{v * 100:.1f}%".replace(".", ",")


def var(atual, ant):
    if ant in (None, 0) or atual is None:
        return "—"
    return pct((atual - ant) / abs(ant))


def processar(linhas):
    por_conta = defaultdict(novo_acum)
    por_canal = defaultdict(novo_acum)
    por_sku = defaultdict(novo_acum)
    total = novo_acum()
    suspeitos, sem_custo = {}, {}
    for it in linhas:
        ok, tinha = custo_valido(it)
        chave_sku = (it["canal"], it["sku"] or it["titulo"])
        if not ok and it["receita_bruta"] > 0:
            destino = suspeitos if tinha else sem_custo
            d = destino.setdefault(chave_sku, [it["titulo"], 0.0])
            d[1] += it["receita_bruta"]
        for acc in (por_conta[(it["canal"], it["conta"])], por_canal[it["canal"]],
                    total):
            acumular(acc, it, ok)
        acumular(por_sku[chave_sku], it, ok)
        por_sku[chave_sku]["titulo"] = it["titulo"]
    return por_conta, por_canal, por_sku, total, suspeitos, sem_custo


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("vendas")
    p.add_argument("--anterior")
    p.add_argument("--custos")
    p.add_argument("--mc-alvo", type=float, default=30.0,
                   help="MC%% ideal (meta), padrão 30")
    p.add_argument("--mc-minima", type=float, default=15.0,
                   help="abaixo disto a loja/SKU é 🔴 estancar, padrão 15")
    p.add_argument("--saida", default=".")
    args = p.parse_args()

    alvo, minima = args.mc_alvo / 100, args.mc_minima / 100
    custos = ler_custos(args.custos)
    linhas = ler_vendas(args.vendas, custos)
    if not linhas:
        sys.exit("Nenhuma linha de venda lida.")
    por_conta, por_canal, por_sku, total, suspeitos, sem_custo = processar(linhas)

    ant_canal = {}
    if args.anterior:
        _, pc_ant, _, _, _, _ = processar(ler_vendas(args.anterior, custos))
        ant_canal = {c: indicadores(a, alvo) for c, a in pc_ant.items()}

    out = []
    out.append("## Desempenho e margem por conta\n")
    out.append("| Canal | Conta | Receita bruta | Pedidos | Ticket | Taxa canal | "
               "Frete líq. | Devol. | CMV | **MC** | **MC %** | Ads (ACOS) | "
               f"MC pós-ads/imp. | Falta p/ {args.mc_alvo:.0f}% | Preço p/ meta | "
               "Cobertura custo | Veredito |")
    out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for (canal, conta), a in sorted(por_conta.items(),
                                    key=lambda x: -x[1]["receita_bruta"]):
        i = indicadores(a, alvo)
        out.append(
            f"| {canal} | {conta} | {brl(i['receita_bruta'])} | {i['pedidos']} | "
            f"{brl(i['ticket'])} | {pct(i['taxa_pct'])} | {pct(i['frete_pct'])} | "
            f"{pct(i['dev_pct'])} | {pct(i['cmv_pct'])} | {brl(i['mc'])} | "
            f"**{pct(i['mc_pct'])}** | {brl(i['ads'])} ({pct(i['acos'])}) | "
            f"{pct(i['mc_pos_pct'])} | {brl(max(i['gap_alvo'], 0) if i['gap_alvo'] is not None else None)} | "
            f"{ajuste(i['preco_alvo_fator'])} | {pct(i['cobertura'])} | {veredito(i, alvo, minima)} |")
    it = indicadores(total, alvo)
    out.append(
        f"| **Total** | | **{brl(it['receita_bruta'])}** | {it['pedidos']} | "
        f"{brl(it['ticket'])} | {pct(it['taxa_pct'])} | {pct(it['frete_pct'])} | "
        f"{pct(it['dev_pct'])} | {pct(it['cmv_pct'])} | **{brl(it['mc'])}** | "
        f"**{pct(it['mc_pct'])}** | {brl(it['ads'])} ({pct(it['acos'])}) | "
        f"{pct(it['mc_pos_pct'])} | {brl(max(it['gap_alvo'], 0) if it['gap_alvo'] is not None else None)} | "
        f"{ajuste(it['preco_alvo_fator'])} | {pct(it['cobertura'])} | {veredito(it, alvo, minima)} |")
    out.append("\n_MC = receita − CMV − taxa do canal − frete líquido − devoluções, "
               "calculada só sobre a receita com custo confiável (coluna Cobertura). "
               f"Meta: MC pós-ads ≥ {args.mc_alvo:.0f}%. \"Preço p/ meta\" = ajuste no "
               "preço médio para chegar na meta, com taxas e ads proporcionais ao preço "
               "e CMV/frete fixos — estimativa; preço de SKU se decide na precificação._\n")

    if ant_canal:
        out.append("## Comparativo por canal com o período anterior\n")
        out.append("| Canal | Receita | Var. | Pedidos | Var. | Ticket | Var. | "
                   "MC % | MC % anterior |")
        out.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for canal, a in sorted(por_canal.items(), key=lambda x: -x[1]["receita_bruta"]):
            i, j = indicadores(a, alvo), ant_canal.get(canal)
            out.append(
                f"| {canal} | {brl(i['receita_bruta'])} | "
                f"{var(i['receita_bruta'], j and j['receita_bruta'])} | {i['pedidos']} | "
                f"{var(i['pedidos'], j and j['pedidos'])} | {brl(i['ticket'])} | "
                f"{var(i['ticket'], j and j['ticket'])} | {pct(i['mc_pct'])} | "
                f"{pct(j and j['mc_pct'])} |")
        out.append("")

    skus = []
    for (canal, sku), a in por_sku.items():
        i = indicadores(a, alvo)
        if i["mc"] is not None:
            skus.append((canal, sku, a["titulo"], i))
    abaixo = [s for s in skus if s[3]["mc_pos_pct"] < alvo]
    abaixo.sort(key=lambda s: s[3]["mc"])
    top = sorted(skus, key=lambda s: -s[3]["mc"])[:10]

    def tabela_sku(titulo, lista):
        out.append(f"## {titulo}\n")
        if not lista:
            out.append("Nenhum.\n")
            return
        out.append("| Canal | SKU | Produto | Receita | Unid. | Preço médio | CMV % | "
                   "Taxa % | MC | MC % | Preço p/ meta | Ajuste |")
        out.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for canal, sku, tit, i in lista:
            pm = i["receita_bruta"] / i["unidades"] if i["unidades"] else None
            fat = i["preco_alvo_fator"]
            pa = pm * fat if pm and fat not in (None, float("inf")) else None
            out.append(f"| {canal} | {sku} | {tit[:50]} | {brl(i['receita_bruta'])} | "
                       f"{i['unidades']:.0f} | {brl(pm)} | {pct(i['cmv_pct'])} | "
                       f"{pct(i['taxa_pct'])} | {brl(i['mc'])} | {pct(i['mc_pct'])} | "
                       f"{brl(pa) if fat != float('inf') else 'inviável'} | {ajuste(fat)} |")
        out.append("")

    tabela_sku("Top 10 SKUs por margem de contribuição (R$)", top)
    tabela_sku(f"SKUs abaixo da meta de MC {args.mc_alvo:.0f}% — piores primeiro",
               abaixo[:25])

    for titulo, dic in (("SKUs sem custo (fora da MC)", sem_custo),
                        ("SKUs com custo suspeito — CMV fora de 8–75%, provável "
                         "erro de unidade (fora da MC)", suspeitos)):
        if dic:
            rec = sum(v[1] for v in dic.values())
            out.append(f"## {titulo}\n")
            out.append(f"{len(dic)} SKUs, {brl(rec)} de receita.\n")
            out.append("| Canal | SKU | Produto | Receita |")
            out.append("|---|---|---|---:|")
            for (canal, sku), (tit, r) in sorted(dic.items(), key=lambda x: -x[1][1])[:15]:
                out.append(f"| {canal} | {sku} | {tit[:50]} | {brl(r)} |")
            out.append("")

    os.makedirs(args.saida, exist_ok=True)
    md = os.path.join(args.saida, "margem_contribuicao.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    csv_sku = os.path.join(args.saida, "margem_por_sku.csv")
    with open(csv_sku, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["canal", "sku", "titulo", "receita_bruta", "unidades", "cmv_pct",
                    "taxa_pct", "frete_pct", "mc", "mc_pct", "mc_pos_pct",
                    "fator_preco_meta"])
        for canal, sku, tit, i in sorted(skus, key=lambda s: s[3]["mc"]):
            w.writerow([canal, sku, tit, f"{i['receita_bruta']:.2f}",
                        f"{i['unidades']:.0f}", f"{i['cmv_pct']:.4f}",
                        f"{i['taxa_pct']:.4f}", f"{i['frete_pct']:.4f}",
                        f"{i['mc']:.2f}", f"{i['mc_pct']:.4f}", f"{i['mc_pos_pct']:.4f}",
                        "inviavel" if i["preco_alvo_fator"] == float("inf")
                        else f"{i['preco_alvo_fator']:.4f}"])
    print("\n".join(out))
    print(f"\nGravado: {md} e {csv_sku}", file=sys.stderr)


if __name__ == "__main__":
    main()
