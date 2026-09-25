#!/usr/bin/env python3
"""Coleta vendas e custos pelas APIs e gera o CSV normalizado da rotina.

    python coletar_api.py --de 2026-08-01 --ate 2026-08-31 \
        --credenciais "~/Desktop/Segundo Celebro/credenciais-api.env" \
        --saida "99 - Anexos/Desempenho/2026-08" [--canais ml,shopee,amazon,tiktok]

Gera na pasta de saída:
    vendas.csv   — uma linha por pedido-item, no formato de referencias/formato-entrada.md
    custos.csv   — custo unitário em reais, do Lexos, já com a regra de unidade
    coleta.log   — o que cada conector trouxe, o que falhou e por quê
    bruto/       — respostas cruas das APIs (para conferir mapeamento)

Só biblioteca padrão. Tokens de atualização renovados são gravados de volta no
arquivo de credenciais (o do Mercado Livre e o da Shopee são de uso único).
Nenhuma credencial é impressa na tela ou gravada fora do arquivo de credenciais.
"""
import argparse
import csv
import datetime as dt
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TZ = dt.timezone(dt.timedelta(hours=-3))  # horário de Brasília
COLUNAS = ["canal", "conta", "pedido", "data", "sku", "titulo", "unidades",
           "receita_bruta", "comissao", "taxa_servico", "afiliados",
           "frete_vendedor", "frete_recebido", "devolucao", "ads", "status"]


# --------------------------------------------------------------- utilidades

class Credenciais:
    """Arquivo KEY=VALUE. Regrava só as chaves alteradas, preservando o resto."""

    def __init__(self, caminho):
        self.caminho = os.path.expanduser(caminho)
        self.v = {}
        if os.path.exists(self.caminho):
            with open(self.caminho, encoding="utf-8") as f:
                for linha in f:
                    linha = linha.strip()
                    if linha and not linha.startswith("#") and "=" in linha:
                        k, val = linha.split("=", 1)
                        self.v[k.strip()] = val.strip().strip('"')

    def get(self, k, padrao=None):
        return self.v.get(k) or os.environ.get(k) or padrao

    def tem(self, *ks):
        return all(self.get(k) for k in ks)

    def gravar(self, k, valor):
        self.v[k] = valor
        linhas, achou = [], False
        if os.path.exists(self.caminho):
            with open(self.caminho, encoding="utf-8") as f:
                linhas = f.read().splitlines()
        for i, linha in enumerate(linhas):
            if linha.split("=", 1)[0].strip() == k:
                linhas[i], achou = f"{k}={valor}", True
        if not achou:
            linhas.append(f"{k}={valor}")
        with open(self.caminho, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")


class Log:
    def __init__(self, pasta):
        self.f = open(os.path.join(pasta, "coleta.log"), "a", encoding="utf-8")

    def __call__(self, msg):
        linha = f"[{dt.datetime.now():%H:%M:%S}] {msg}"
        print(linha, file=sys.stderr)
        self.f.write(linha + "\n")
        self.f.flush()


def http(metodo, url, params=None, headers=None, corpo=None, form=None,
         tentativas=4):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    dados, hdr = None, dict(headers or {})
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        hdr.setdefault("Content-Type", "application/json")
    elif form is not None:
        dados = urllib.parse.urlencode(form).encode()
        hdr.setdefault("Content-Type", "application/x-www-form-urlencoded")
    espera = 2
    for n in range(tentativas):
        req = urllib.request.Request(url, data=dados, headers=hdr, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                txt = r.read().decode("utf-8")
                return json.loads(txt) if txt else {}
        except urllib.error.HTTPError as e:
            corpo_erro = e.read().decode("utf-8", "replace")[:500]
            if e.code in (429, 500, 502, 503, 504) and n < tentativas - 1:
                time.sleep(espera)
                espera *= 2
                continue
            raise RuntimeError(f"HTTP {e.code} em {url.split('?')[0]}: {corpo_erro}")
        except urllib.error.URLError as e:
            if n < tentativas - 1:
                time.sleep(espera)
                espera *= 2
                continue
            raise RuntimeError(f"Sem conexão com {url.split('?')[0]}: {e.reason}")


def f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def ratear(total, pesos):
    """Divide um valor do pedido entre os itens, proporcional ao peso."""
    s = sum(pesos)
    if not s:
        return [total / len(pesos)] * len(pesos) if pesos else []
    return [total * p / s for p in pesos]


def salvar_bruto(pasta, nome, dados):
    os.makedirs(os.path.join(pasta, "bruto"), exist_ok=True)
    with open(os.path.join(pasta, "bruto", nome), "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=1)


def linha(**kw):
    return {c: kw.get(c, "") for c in COLUNAS}


# ------------------------------------------------------------ Mercado Livre

class MercadoLivre:
    """API oficial. Uma conta por prefixo: ML_CRGFESTAS_*, ML_CRGFESTAS2_*...

    Chaves: ML_CONTAS=CRGFESTAS,CRGFESTAS2  ML_CLIENT_ID  ML_CLIENT_SECRET
            ML_<CONTA>_REFRESH_TOKEN
    """
    BASE = "https://api.mercadolibre.com"

    def __init__(self, cred, log, pasta):
        self.cred, self.log, self.pasta = cred, log, pasta

    def token(self, conta):
        r = http("POST", f"{self.BASE}/oauth/token", form={
            "grant_type": "refresh_token",
            "client_id": self.cred.get("ML_CLIENT_ID"),
            "client_secret": self.cred.get("ML_CLIENT_SECRET"),
            "refresh_token": self.cred.get(f"ML_{conta}_REFRESH_TOKEN")})
        # o refresh token do ML é de uso único: grava o novo imediatamente
        self.cred.gravar(f"ML_{conta}_REFRESH_TOKEN", r["refresh_token"])
        return r["access_token"]

    def coletar(self, de, ate):
        contas = [c.strip() for c in (self.cred.get("ML_CONTAS") or "").split(",") if c.strip()]
        if not contas:
            self.log("Mercado Livre: ML_CONTAS vazio — não obtido")
        linhas = []
        for conta in contas:
            if not self.cred.tem("ML_CLIENT_ID", "ML_CLIENT_SECRET",
                                 f"ML_{conta}_REFRESH_TOKEN"):
                self.log(f"Mercado Livre {conta}: credenciais ausentes — não obtido")
                continue
            try:
                linhas += self._conta(conta, de, ate)
            except Exception as e:  # um conector falhar não derruba os outros
                self.log(f"Mercado Livre {conta}: FALHOU — {e}")
        return linhas

    def _conta(self, conta, de, ate):
        h = {"Authorization": f"Bearer {self.token(conta)}"}
        uid = http("GET", f"{self.BASE}/users/me", headers=h)["id"]
        pedidos, offset = [], 0
        while True:
            r = http("GET", f"{self.BASE}/orders/search", headers=h, params={
                "seller": uid, "sort": "date_asc", "offset": offset, "limit": 50,
                "order.date_created.from": de.strftime("%Y-%m-%dT00:00:00.000-03:00"),
                "order.date_created.to": ate.strftime("%Y-%m-%dT23:59:59.999-03:00")})
            pedidos += r.get("results", [])
            offset += 50
            if offset >= r.get("paging", {}).get("total", 0):
                break
        salvar_bruto(self.pasta, f"ml-{conta}-pedidos.json", pedidos)

        linhas, envios_vistos = [], set()
        for p in pedidos:
            status = "cancelado" if p.get("status") == "cancelled" else p.get("status", "")
            itens = p.get("order_items", [])
            envio = (p.get("shipping") or {}).get("id")
            frete = 0.0
            # pedidos de um mesmo carrinho dividem o envio: conta uma vez só
            if envio and envio not in envios_vistos and status != "cancelado":
                envios_vistos.add(envio)
                try:
                    c = http("GET", f"{self.BASE}/shipments/{envio}/costs",
                             headers={**h, "x-format-new": "true"})
                    frete = sum(f(s.get("cost")) for s in c.get("senders", [])
                                if str(s.get("user_id")) == str(uid))
                except Exception as e:
                    self.log(f"ML {conta}: custo do envio {envio} não obtido — {e}")
            pesos = [f(i.get("unit_price")) * f(i.get("quantity")) for i in itens]
            fretes = ratear(frete, pesos)
            reemb = 0.0
            if p.get("mediations") or "refunded" in (p.get("tags") or []):
                reemb = f(p.get("total_amount"))
            reembs = ratear(reemb, pesos)
            for i, it, fr, rb in zip(range(len(itens)), itens, fretes, reembs):
                item = it.get("item", {})
                qtd = f(it.get("quantity"))
                # sale_fee vem por unidade na API de pedidos
                linhas.append(linha(
                    canal="Mercado Livre", conta=conta, pedido=p.get("id"),
                    data=(p.get("date_created") or "")[:10],
                    sku=item.get("seller_sku") or item.get("seller_custom_field") or item.get("id"),
                    titulo=item.get("title", ""), unidades=qtd,
                    receita_bruta=round(f(it.get("unit_price")) * qtd, 2),
                    comissao=round(f(it.get("sale_fee")) * qtd, 2),
                    frete_vendedor=round(fr, 2), devolucao=round(rb, 2), status=status))
        self.log(f"Mercado Livre {conta}: {len(pedidos)} pedidos, {len(linhas)} itens")
        return linhas


# ------------------------------------------------------------------ Shopee

class Shopee:
    """Shopee Open Platform v2.

    Chaves: SHOPEE_PARTNER_ID  SHOPEE_PARTNER_KEY  SHOPEE_CONTAS=SHOPEE1,SHOPEE2
            SHOPEE_<CONTA>_SHOP_ID  SHOPEE_<CONTA>_REFRESH_TOKEN
    """
    BASE = "https://partner.shopeemobile.com"

    def __init__(self, cred, log, pasta):
        self.cred, self.log, self.pasta = cred, log, pasta

    def _assinar(self, caminho, ts, token="", shop_id=""):
        base = f"{self.cred.get('SHOPEE_PARTNER_ID')}{caminho}{ts}{token}{shop_id}"
        return hmac.new(self.cred.get("SHOPEE_PARTNER_KEY").encode(), base.encode(),
                        hashlib.sha256).hexdigest()

    def token(self, conta, shop_id):
        caminho, ts = "/api/v2/auth/access_token/get", int(time.time())
        r = http("POST", self.BASE + caminho, params={
            "partner_id": self.cred.get("SHOPEE_PARTNER_ID"), "timestamp": ts,
            "sign": self._assinar(caminho, ts)}, corpo={
            "refresh_token": self.cred.get(f"SHOPEE_{conta}_REFRESH_TOKEN"),
            "partner_id": int(self.cred.get("SHOPEE_PARTNER_ID")),
            "shop_id": int(shop_id)})
        if r.get("error"):
            raise RuntimeError(f"token: {r.get('error')} {r.get('message')}")
        self.cred.gravar(f"SHOPEE_{conta}_REFRESH_TOKEN", r["refresh_token"])
        return r["access_token"]

    def _get(self, caminho, token, shop_id, params):
        ts = int(time.time())
        r = http("GET", self.BASE + caminho, params={
            "partner_id": self.cred.get("SHOPEE_PARTNER_ID"), "timestamp": ts,
            "access_token": token, "shop_id": shop_id,
            "sign": self._assinar(caminho, ts, token, shop_id), **params})
        if r.get("error"):
            raise RuntimeError(f"{caminho}: {r.get('error')} {r.get('message')}")
        return r.get("response", {})

    def coletar(self, de, ate):
        contas = [c.strip() for c in (self.cred.get("SHOPEE_CONTAS") or "").split(",") if c.strip()]
        if not contas:
            self.log("Shopee: SHOPEE_CONTAS vazio — não obtido")
        linhas = []
        for conta in contas:
            if not self.cred.tem("SHOPEE_PARTNER_ID", "SHOPEE_PARTNER_KEY",
                                 f"SHOPEE_{conta}_SHOP_ID", f"SHOPEE_{conta}_REFRESH_TOKEN"):
                self.log(f"Shopee {conta}: credenciais ausentes — não obtido")
                continue
            try:
                linhas += self._conta(conta, de, ate)
            except Exception as e:
                self.log(f"Shopee {conta}: FALHOU — {e}")
        return linhas

    def _conta(self, conta, de, ate):
        shop_id = self.cred.get(f"SHOPEE_{conta}_SHOP_ID")
        tok = self.token(conta, shop_id)
        inicio = int(dt.datetime.combine(de, dt.time(0), TZ).timestamp())
        fim = int(dt.datetime.combine(ate, dt.time(23, 59, 59), TZ).timestamp())
        pedidos = []
        janela = 15 * 86400 - 1  # a API aceita no máximo 15 dias por consulta
        t = inicio
        while t <= fim:
            cursor = ""
            while True:
                r = self._get("/api/v2/order/get_order_list", tok, shop_id, {
                    "time_range_field": "create_time", "time_from": t,
                    "time_to": min(t + janela, fim), "page_size": 100, "cursor": cursor,
                    "response_optional_fields": "order_status"})
                pedidos += r.get("order_list", [])
                if not r.get("more"):
                    break
                cursor = r.get("next_cursor", "")
            t += janela + 1

        linhas, sem_repasse, brutos = [], 0, []
        for p in pedidos:
            sn = p["order_sn"]
            if p.get("order_status") in ("CANCELLED", "IN_CANCEL"):
                continue
            try:
                inc = self._get("/api/v2/payment/get_escrow_detail", tok, shop_id,
                                {"order_sn": sn}).get("order_income", {})
            except Exception:
                sem_repasse += 1  # pedido ainda não liquidado: sem taxa final
                continue
            brutos.append({"order_sn": sn, "order_income": inc})
            itens = inc.get("items", [])
            if not itens:
                continue
            # receita do ponto de vista do vendedor: desconto bancado pela Shopee
            # volta para o vendedor; o bancado pelo vendedor sai da receita
            receita = (f(inc.get("original_price")) - f(inc.get("seller_discount"))
                       - f(inc.get("voucher_from_seller")))
            pesos = [f(i.get("discounted_price")) or f(i.get("original_price")) for i in itens]
            campos = {
                "receita_bruta": receita,
                "comissao": f(inc.get("commission_fee")),
                "taxa_servico": f(inc.get("service_fee")) + f(inc.get("seller_transaction_fee")),
                "afiliados": f(inc.get("order_ams_commission_fee")),
                "frete_vendedor": f(inc.get("actual_shipping_fee")) + f(inc.get("reverse_shipping_fee")),
                "frete_recebido": f(inc.get("buyer_paid_shipping_fee")) + f(inc.get("shopee_shipping_rebate")),
                "devolucao": f(inc.get("seller_return_refund")) if f(inc.get("seller_return_refund")) > 0 else 0.0,
            }
            rateado = {k: ratear(v, pesos) for k, v in campos.items()}
            for n, it in enumerate(itens):
                linhas.append(linha(
                    canal="Shopee", conta=conta, pedido=sn,
                    data=dt.datetime.fromtimestamp(p.get("create_time", inicio), TZ).date().isoformat()
                    if p.get("create_time") else "",
                    sku=it.get("model_sku") or it.get("item_sku") or it.get("item_id"),
                    titulo=it.get("item_name", ""), unidades=f(it.get("quantity_purchased")),
                    **{k: round(v[n], 2) for k, v in rateado.items()}))
        salvar_bruto(self.pasta, f"shopee-{conta}-repasses.json", brutos)
        self.log(f"Shopee {conta}: {len(pedidos)} pedidos, {len(linhas)} itens, "
                 f"{sem_repasse} ainda sem repasse (fora da MC)")
        return linhas


# ------------------------------------------------------------------ Amazon

class Amazon:
    """Selling Partner API — Finances (eventos financeiros por data de lançamento).

    Chaves: AMZ_CLIENT_ID  AMZ_CLIENT_SECRET  AMZ_REFRESH_TOKEN  [AMZ_CONTA=Amazon]
    """
    BASE = "https://sellingpartnerapi-na.amazon.com"  # Brasil fica na região NA

    def __init__(self, cred, log, pasta):
        self.cred, self.log, self.pasta = cred, log, pasta

    def coletar(self, de, ate):
        if not self.cred.tem("AMZ_CLIENT_ID", "AMZ_CLIENT_SECRET", "AMZ_REFRESH_TOKEN"):
            self.log("Amazon: credenciais ausentes — não obtido")
            return []
        try:
            return self._coletar(de, ate)
        except Exception as e:
            self.log(f"Amazon: FALHOU — {e}")
            return []

    def _coletar(self, de, ate):
        conta = self.cred.get("AMZ_CONTA", "Amazon")
        tok = http("POST", "https://api.amazon.com/auth/o2/token", form={
            "grant_type": "refresh_token",
            "refresh_token": self.cred.get("AMZ_REFRESH_TOKEN"),
            "client_id": self.cred.get("AMZ_CLIENT_ID"),
            "client_secret": self.cred.get("AMZ_CLIENT_SECRET")})["access_token"]
        h = {"x-amz-access-token": tok}
        fim = min(dt.datetime.combine(ate, dt.time(23, 59, 59), TZ),
                  dt.datetime.now(TZ) - dt.timedelta(minutes=5))
        params = {"PostedAfter": dt.datetime.combine(de, dt.time(0), TZ).isoformat(),
                  "PostedBefore": fim.isoformat(), "MaxResultsPerPage": 100}
        eventos = {"ShipmentEventList": [], "RefundEventList": [],
                   "ProductAdsPaymentEventList": []}
        while True:
            r = http("GET", f"{self.BASE}/finances/v0/financialEvents", headers=h,
                     params=params).get("payload", {})
            fe = r.get("FinancialEvents", {})
            for k in eventos:
                eventos[k] += fe.get(k, []) or []
            if not r.get("NextToken"):
                break
            params = {"NextToken": r["NextToken"]}
            time.sleep(2.1)  # limite da API: 0,5 requisição por segundo
        salvar_bruto(self.pasta, "amazon-eventos.json", eventos)

        def soma(lista, campo_valor, tipos=None, excluir=None):
            t = 0.0
            for x in lista or []:
                tipo = x.get("ChargeType") or x.get("FeeType") or ""
                if tipos and tipo not in tipos:
                    continue
                if excluir and tipo in excluir:
                    continue
                t += f((x.get(campo_valor) or {}).get("CurrencyAmount"))
            return t

        linhas = []
        for ev in eventos["ShipmentEventList"]:
            if ev.get("MarketplaceName") and "br" not in ev["MarketplaceName"].lower():
                continue
            for it in ev.get("ShipmentItemList", []):
                ch, fe_ = it.get("ItemChargeList"), it.get("ItemFeeList")
                promo = sum(f((p.get("PromotionAmount") or {}).get("CurrencyAmount"))
                            for p in it.get("PromotionList", []) or [])
                fba = ("FBAPerUnitFulfillmentFee", "FBAPerOrderFulfillmentFee",
                       "FBAWeightBasedFee", "ShippingChargeback", "ShippingHB")
                linhas.append(linha(
                    canal="Amazon", conta=conta, pedido=ev.get("AmazonOrderId"),
                    data=(ev.get("PostedDate") or "")[:10], sku=it.get("SellerSKU"),
                    titulo=it.get("SellerSKU"), unidades=f(it.get("QuantityShipped")),
                    receita_bruta=round(soma(ch, "ChargeAmount", ("Principal",)) + promo, 2),
                    frete_recebido=round(soma(ch, "ChargeAmount", ("ShippingCharge",)), 2),
                    # taxas vêm negativas na API
                    comissao=round(-soma(fe_, "FeeAmount", ("Commission",)), 2),
                    frete_vendedor=round(-soma(fe_, "FeeAmount", fba), 2),
                    taxa_servico=round(-soma(fe_, "FeeAmount", excluir=("Commission",) + fba), 2)))
        for ev in eventos["RefundEventList"]:
            for it in ev.get("ShipmentItemAdjustmentList", []) or []:
                valor = -soma(it.get("ItemChargeAdjustmentList"), "ChargeAmount", ("Principal",))
                taxa_dev = soma(it.get("ItemFeeAdjustmentList"), "FeeAmount", ("Commission",))
                linhas.append(linha(
                    canal="Amazon", conta=conta, pedido=ev.get("AmazonOrderId"),
                    data=(ev.get("PostedDate") or "")[:10], sku=it.get("SellerSKU"),
                    titulo=it.get("SellerSKU"), unidades=0, receita_bruta=0,
                    # comissão estornada pela Amazon abate a perda
                    devolucao=round(valor - taxa_dev, 2), status="devolucao"))
        ads = -sum(f((e.get("transactionValue") or {}).get("CurrencyAmount"))
                   for e in eventos["ProductAdsPaymentEventList"])
        if ads:
            linhas.append(linha(canal="Amazon", conta=conta, pedido="ADS", sku="ADS",
                                titulo="Sponsored Products", unidades=0, receita_bruta=0,
                                ads=round(abs(ads), 2)))
        self.log(f"Amazon: {len(eventos['ShipmentEventList'])} envios, "
                 f"{len(eventos['RefundEventList'])} reembolsos, ads R$ {abs(ads):.2f} "
                 "(data de lançamento financeiro, não de pedido)")
        return linhas


# -------------------------------------------------------------- TikTok Shop

class TikTok:
    """TikTok Shop Partner API (versão 202309). BETA: validar no primeiro uso.

    Chaves: TIKTOK_APP_KEY  TIKTOK_APP_SECRET  TIKTOK_REFRESH_TOKEN  [TIKTOK_CONTA]
    """
    BASE = "https://open-api.tiktokglobalshop.com"

    def __init__(self, cred, log, pasta):
        self.cred, self.log, self.pasta = cred, log, pasta

    def _assinar(self, caminho, params, corpo):
        segredo = self.cred.get("TIKTOK_APP_SECRET")
        base = caminho + "".join(f"{k}{params[k]}" for k in sorted(params)
                                 if k not in ("sign", "access_token"))
        if corpo is not None:
            base += json.dumps(corpo, separators=(",", ":"))
        base = segredo + base + segredo
        return hmac.new(segredo.encode(), base.encode(), hashlib.sha256).hexdigest()

    def _req(self, metodo, caminho, tok, params=None, corpo=None, cipher=None):
        p = {"app_key": self.cred.get("TIKTOK_APP_KEY"), "timestamp": int(time.time()),
             **(params or {})}
        if cipher:
            p["shop_cipher"] = cipher
        p["sign"] = self._assinar(caminho, p, corpo)
        r = http(metodo, self.BASE + caminho, params=p, corpo=corpo,
                 headers={"x-tts-access-token": tok})
        if r.get("code") not in (0, None):
            raise RuntimeError(f"{caminho}: {r.get('code')} {r.get('message')}")
        return r.get("data", {})

    def coletar(self, de, ate):
        if not self.cred.tem("TIKTOK_APP_KEY", "TIKTOK_APP_SECRET", "TIKTOK_REFRESH_TOKEN"):
            self.log("TikTok Shop: credenciais ausentes — não obtido")
            return []
        try:
            return self._coletar(de, ate)
        except Exception as e:
            self.log(f"TikTok Shop: FALHOU — {e}")
            return []

    def _coletar(self, de, ate):
        conta = self.cred.get("TIKTOK_CONTA", "TikTok")
        r = http("GET", "https://auth.tiktok-shops.com/api/v2/token/refresh", params={
            "app_key": self.cred.get("TIKTOK_APP_KEY"),
            "app_secret": self.cred.get("TIKTOK_APP_SECRET"),
            "refresh_token": self.cred.get("TIKTOK_REFRESH_TOKEN"),
            "grant_type": "refresh_token"}).get("data", {})
        tok = r["access_token"]
        if r.get("refresh_token"):
            self.cred.gravar("TIKTOK_REFRESH_TOKEN", r["refresh_token"])
        lojas = self._req("GET", "/authorization/202309/shops", tok).get("shops", [])
        if not lojas:
            raise RuntimeError("nenhuma loja autorizada")
        cipher = lojas[0]["cipher"]

        pedidos, pagina = [], ""
        corpo = {"create_time_ge": int(dt.datetime.combine(de, dt.time(0), TZ).timestamp()),
                 "create_time_lt": int(dt.datetime.combine(ate + dt.timedelta(days=1),
                                                           dt.time(0), TZ).timestamp())}
        while True:
            params = {"page_size": 100}
            if pagina:
                params["page_token"] = pagina
            d = self._req("POST", "/order/202309/orders/search", tok, params, corpo, cipher)
            pedidos += d.get("orders", [])
            pagina = d.get("next_page_token")
            if not pagina:
                break

        linhas, extratos, sem_extrato = [], [], 0
        for p in pedidos:
            status = "cancelado" if p.get("status") == "CANCELLED" else p.get("status", "")
            # line_items vêm uma linha por unidade: agrupa por SKU
            grupos = {}
            for li in p.get("line_items", []):
                k = li.get("seller_sku") or li.get("sku_id")
                g = grupos.setdefault(k, {"titulo": li.get("product_name", ""), "q": 0, "v": 0.0})
                g["q"] += 1
                g["v"] += f(li.get("sale_price"))
            taxas = {}
            if status != "cancelado":
                try:
                    st = self._req("GET", f"/finance/202309/orders/{p['id']}/statement_transactions",
                                   tok, cipher=cipher)
                    extratos.append({"pedido": p["id"], "extrato": st})
                    taxas = self._taxas(st)
                except Exception:
                    sem_extrato += 1
            pesos = [g["v"] for g in grupos.values()]
            rateado = {k: ratear(v, pesos) for k, v in taxas.items()}
            for n, (sku, g) in enumerate(grupos.items()):
                linhas.append(linha(
                    canal="TikTok Shop", conta=conta, pedido=p.get("id"),
                    data=dt.datetime.fromtimestamp(p.get("create_time", 0), TZ).date().isoformat(),
                    sku=sku, titulo=g["titulo"], unidades=g["q"], receita_bruta=round(g["v"], 2),
                    status=status if taxas or status == "cancelado" else "sem_extrato",
                    **{k: round(v[n], 2) for k, v in rateado.items()}))
        salvar_bruto(self.pasta, "tiktok-extratos.json", extratos)
        self.log(f"TikTok Shop: {len(pedidos)} pedidos, {len(linhas)} itens, "
                 f"{sem_extrato} sem extrato ainda — CONFIRA o mapeamento em bruto/tiktok-extratos.json")
        return linhas

    @staticmethod
    def _taxas(st):
        """Soma as taxas do extrato. Nomes de campo conferidos na doc 202309;
        procura em qualquer nível para tolerar mudança de estrutura."""
        mapa = {"platform_commission_amount": "comissao",
                "transaction_fee_amount": "taxa_servico",
                "referral_fee_amount": "comissao",
                "affiliate_commission_amount": "afiliados",
                "affiliate_partner_commission_amount": "afiliados",
                "shipping_cost_amount": "frete_vendedor",
                "actual_shipping_fee_amount": "frete_vendedor",
                "customer_paid_shipping_fee_amount": "frete_recebido"}
        tot = {v: 0.0 for v in set(mapa.values())}

        def andar(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in mapa and not isinstance(v, (dict, list)):
                        tot[mapa[k]] += abs(f(v))
                    else:
                        andar(v)
            elif isinstance(o, list):
                for x in o:
                    andar(x)
        andar(st)
        return tot


# ------------------------------------------------------------------- Lexos

class Lexos:
    """Custo por SKU. Chave no arquivo apontado por LEXOS_CHAVE_ARQUIVO."""
    BASE = "https://lexosapi.azure-api.net"
    LOJA_PRINCIPAL, LOJAS_REF = "21310", ("21410", "21263")

    def __init__(self, cred, log):
        self.log = log
        arq = os.path.expanduser(cred.get("LEXOS_CHAVE_ARQUIVO", "") or "")
        self.chave = cred.get("LEXOS_CHAVE") or (
            open(arq, encoding="utf-8").read().strip() if arq and os.path.exists(arq) else "")

    def custos(self, linhas):
        if not self.chave:
            self.log("Lexos: chave ausente — custos.csv não gerado")
            return {}
        preco_obs = {}  # preço praticado: receita ÷ unidades, por SKU
        for l in linhas:
            if l["sku"] and f(l["unidades"]) > 0 and f(l["receita_bruta"]) > 0:
                a = preco_obs.setdefault(l["sku"], [0.0, 0.0])
                a[0] += f(l["receita_bruta"])
                a[1] += f(l["unidades"])
        custos, sem = {}, []
        for sku, (rec, un) in preco_obs.items():
            try:
                d = http("GET", f"{self.BASE}/Catalogo/ObterProdutoSku",
                         params={"sku": sku}, headers={"Chave": self.chave})
            except Exception:
                sem.append(sku)
                continue
            c = self.regra_unidade(d, rec / un)
            if c is None:
                sem.append(sku)
            else:
                custos[sku] = c
        self.log(f"Lexos: custo confirmado para {len(custos)} SKUs, "
                 f"{len(sem)} sem custo (regra de unidade não fechou ou SKU não achado)")
        return custos

    @classmethod
    def regra_unidade(cls, produto, preco_obs):
        """Regra centavos × reais do dre-mensal-crg. Devolve None se não fechar."""
        if isinstance(produto, list):
            produto = produto[0] if produto else {}
        est = {str(e.get("LojaId")): f(e.get("Custo")) for e in produto.get("Estoques", []) or []}
        principal = est.get(cls.LOJA_PRINCIPAL) or next((v for v in est.values() if v > 0), 0)
        if principal <= 0:
            return None
        # 1) outra loja tem o mesmo custo em reais: 21310 ≈ 100 × ref → centavos
        for ref in cls.LOJAS_REF:
            r = est.get(ref, 0)
            if r > 0:
                if 80 <= principal / r <= 120:
                    return round(principal / 100, 2)
                if 0.8 <= principal / r <= 1.25:
                    return round(principal, 2)
        # 2) compara com o preço praticado no marketplace
        ok_reais = 0.08 <= principal / preco_obs <= 0.75
        ok_cent = 0.08 <= (principal / 100) / preco_obs <= 0.75
        if ok_reais and not ok_cent:
            return round(principal, 2)
        if ok_cent and not ok_reais:
            return round(principal / 100, 2)
        return None  # 3) nenhum teste fecha: sem custo, nunca chute


# -------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--de", required=True, type=dt.date.fromisoformat)
    ap.add_argument("--ate", required=True, type=dt.date.fromisoformat)
    ap.add_argument("--credenciais", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--canais", default="ml,shopee,amazon,tiktok")
    ap.add_argument("--sem-custo", action="store_true", help="não consulta o Lexos")
    a = ap.parse_args()

    os.makedirs(a.saida, exist_ok=True)
    log = Log(a.saida)
    cred = Credenciais(a.credenciais)
    conectores = {"ml": MercadoLivre, "shopee": Shopee, "amazon": Amazon, "tiktok": TikTok}
    log(f"Coleta de {a.de} a {a.ate} — canais: {a.canais}")
    linhas = []
    for c in a.canais.split(","):
        c = c.strip()
        if c in conectores:
            args = (cred, log, a.saida)
            linhas += conectores[c](*args).coletar(a.de, a.ate)
    log("Shein: sem conector de API — complete pelo relatório de repasse")

    with open(os.path.join(a.saida, "vendas.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(linhas)
    log(f"vendas.csv: {len(linhas)} linhas")

    if not a.sem_custo:
        custos = Lexos(cred, log).custos(linhas)
        if custos:
            with open(os.path.join(a.saida, "custos.csv"), "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["sku", "custo_unit"])
                for sku, c in sorted(custos.items()):
                    w.writerow([sku, f"{c:.2f}"])


if __name__ == "__main__":
    main()
