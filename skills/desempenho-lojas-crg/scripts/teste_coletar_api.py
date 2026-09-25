"""Testes offline dos conectores: respostas simuladas no formato das APIs."""
import datetime as dt
import os
import tempfile
import unittest
from unittest import mock

import coletar_api as c

DE, ATE = dt.date(2026, 8, 1), dt.date(2026, 8, 31)


def cred(**kv):
    arq = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
    arq.write("\n".join(f"{k}={v}" for k, v in kv.items()))
    arq.close()
    return c.Credenciais(arq.name)


class Falso:
    """Substitui c.http: devolve a resposta da primeira rota contida na URL."""
    def __init__(self, rotas):
        self.rotas, self.chamadas = rotas, []

    def __call__(self, metodo, url, **kw):
        self.chamadas.append((metodo, url, kw))
        for trecho, resp in self.rotas:
            if trecho in url:
                return resp(kw) if callable(resp) else resp
        raise RuntimeError("rota não simulada: " + url)


class TesteML(unittest.TestCase):
    def test_pedido_vira_linhas_e_token_regravado(self):
        cr = cred(ML_CONTAS="CRGFESTAS", ML_CLIENT_ID="1", ML_CLIENT_SECRET="s",
                  ML_CRGFESTAS_REFRESH_TOKEN="velho")
        falso = Falso([
            ("/oauth/token", {"access_token": "a", "refresh_token": "novo"}),
            ("/users/me", {"id": 135206778}),
            ("/orders/search", {"paging": {"total": 2}, "results": [
                {"id": 1, "status": "paid", "date_created": "2026-08-03T10:00:00-03:00",
                 "shipping": {"id": 9}, "order_items": [
                     {"item": {"id": "MLB1", "title": "Kit 300", "seller_sku": "KIT300"},
                      "quantity": 2, "unit_price": 89.9, "sale_fee": 12.59}]},
                {"id": 2, "status": "cancelled", "shipping": {"id": 10}, "order_items": [
                    {"item": {"title": "Balão"}, "quantity": 1, "unit_price": 19.9, "sale_fee": 3}]}]}),
            ("/shipments/9/costs", {"senders": [{"user_id": 135206778, "cost": 22.9}]}),
        ])
        with tempfile.TemporaryDirectory() as d, mock.patch.object(c, "http", falso):
            linhas = c.MercadoLivre(cr, lambda m: None, d).coletar(DE, ATE)
        l = linhas[0]
        self.assertEqual((l["sku"], l["receita_bruta"], l["comissao"], l["frete_vendedor"]),
                         ("KIT300", 179.8, 25.18, 22.9))
        self.assertEqual(linhas[1]["status"], "cancelado")
        self.assertEqual(c.Credenciais(cr.caminho).get("ML_CRGFESTAS_REFRESH_TOKEN"), "novo")


class TesteShopee(unittest.TestCase):
    def test_repasse_rateado_por_item(self):
        cr = cred(SHOPEE_PARTNER_ID="10", SHOPEE_PARTNER_KEY="k", SHOPEE_CONTAS="SHOPEE1",
                  SHOPEE_SHOPEE1_SHOP_ID="55", SHOPEE_SHOPEE1_REFRESH_TOKEN="r")
        falso = Falso([
            ("/auth/access_token/get", {"access_token": "a", "refresh_token": "r2"}),
            ("/order/get_order_list", lambda kw: {"response": {"more": False, "order_list": [
                {"order_sn": "X1", "order_status": "COMPLETED"},
                {"order_sn": "X2", "order_status": "CANCELLED"}]
                if kw["params"]["time_from"] == int(dt.datetime(2026, 8, 1, tzinfo=c.TZ).timestamp())
                else []}}),
            ("/payment/get_escrow_detail", {"response": {"order_income": {
                "original_price": 120, "seller_discount": 20, "voucher_from_seller": 0,
                "commission_fee": 14, "service_fee": 6, "seller_transaction_fee": 0,
                "order_ams_commission_fee": 5, "actual_shipping_fee": 20,
                "buyer_paid_shipping_fee": 5, "shopee_shipping_rebate": 15,
                "items": [
                    {"item_name": "Kit", "model_sku": "KIT300", "quantity_purchased": 1,
                     "discounted_price": 75},
                    {"item_name": "Vela", "item_sku": "VELA10", "quantity_purchased": 5,
                     "discounted_price": 25}]}}}),
        ])
        with tempfile.TemporaryDirectory() as d, mock.patch.object(c, "http", falso):
            linhas = c.Shopee(cr, lambda m: None, d).coletar(DE, ATE)
        self.assertEqual(len(linhas), 2)  # cancelado fica de fora
        kit, vela = linhas
        self.assertEqual((kit["receita_bruta"], kit["comissao"], kit["afiliados"]), (75.0, 10.5, 3.75))
        self.assertEqual((vela["receita_bruta"], vela["unidades"]), (25.0, 5.0))
        # janelas de 15 dias: agosto inteiro = 3 consultas
        self.assertEqual(sum("/order/get_order_list" in u for _, u, _ in falso.chamadas), 3)

    def test_assinatura_hmac(self):
        cr = cred(SHOPEE_PARTNER_ID="2001887", SHOPEE_PARTNER_KEY="chave")
        s = c.Shopee(cr, None, None)._assinar("/api/v2/shop/get_shop_info", 1655714431, "tok", "123")
        import hashlib, hmac
        esperado = hmac.new(b"chave", b"2001887/api/v2/shop/get_shop_info1655714431tok123",
                            hashlib.sha256).hexdigest()
        self.assertEqual(s, esperado)


class TesteAmazon(unittest.TestCase):
    def test_eventos_financeiros(self):
        cr = cred(AMZ_CLIENT_ID="i", AMZ_CLIENT_SECRET="s", AMZ_REFRESH_TOKEN="r")
        money = lambda v: {"CurrencyCode": "BRL", "CurrencyAmount": v}
        falso = Falso([
            ("api.amazon.com/auth", {"access_token": "a"}),
            ("/financialEvents", {"payload": {"FinancialEvents": {
                "ShipmentEventList": [{"AmazonOrderId": "701", "PostedDate": "2026-08-05T12:00:00Z",
                    "MarketplaceName": "Amazon.com.br", "ShipmentItemList": [{
                        "SellerSKU": "KIT300", "QuantityShipped": 2,
                        "ItemChargeList": [{"ChargeType": "Principal", "ChargeAmount": money(189.8)},
                                           {"ChargeType": "ShippingCharge", "ChargeAmount": money(0)}],
                        "ItemFeeList": [{"FeeType": "Commission", "FeeAmount": money(-22.78)},
                                        {"FeeType": "FBAPerUnitFulfillmentFee", "FeeAmount": money(-31.4)},
                                        {"FeeType": "FixedClosingFee", "FeeAmount": money(-2)}]}]}],
                "RefundEventList": [], "ProductAdsPaymentEventList": [
                    {"transactionValue": money(-12)}]}}}),
        ])
        with tempfile.TemporaryDirectory() as d, mock.patch.object(c, "http", falso):
            linhas = c.Amazon(cr, lambda m: None, d).coletar(DE, ATE)
        v, ads = linhas
        self.assertEqual((v["receita_bruta"], v["comissao"], v["frete_vendedor"], v["taxa_servico"]),
                         (189.8, 22.78, 31.4, 2.0))
        self.assertEqual(ads["ads"], 12.0)


class TesteLexos(unittest.TestCase):
    def test_regra_de_unidade(self):
        R = c.Lexos.regra_unidade
        centavos_por_loja = {"Estoques": [{"LojaId": 21310, "Custo": 3150}, {"LojaId": 21410, "Custo": 31.5}]}
        self.assertEqual(R(centavos_por_loja, 89.9), 31.5)
        self.assertEqual(R({"Estoques": [{"LojaId": 21310, "Custo": 3150}]}, 89.9), 31.5)
        self.assertEqual(R({"Estoques": [{"LojaId": 21310, "Custo": 31.5}]}, 89.9), 31.5)
        self.assertIsNone(R({"Estoques": [{"LojaId": 21310, "Custo": 0}]}, 89.9))
        # nenhum teste fecha → sem custo, nunca chute
        self.assertIsNone(R({"Estoques": [{"LojaId": 21310, "Custo": 5000}]}, 20.0))


if __name__ == "__main__":
    unittest.main()
