from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal

from django.test import SimpleTestCase

from .templatetags.moneda_filters import fecha_corta, quetzales


class FormatoVisualTests(SimpleTestCase):
    def test_quetzales_usa_punto_decimal_y_coma_de_miles(self):
        casos = (
            (5, "Q5.00"),
            (50, "Q50.00"),
            (1250, "Q1,250.00"),
            (Decimal("15000.5"), "Q15,000.50"),
        )
        for valor, esperado in casos:
            with self.subTest(valor=valor):
                self.assertEqual(quetzales(valor), esperado)

    def test_quetzales_maneja_valores_vacios_o_invalidos(self):
        self.assertEqual(quetzales(None), "Q0.00")
        self.assertEqual(quetzales("no es un monto"), "Q0.00")

    def test_fecha_corta_acepta_fecha_datetime_e_iso(self):
        self.assertEqual(fecha_corta(date(2026, 9, 11)), "11/09/2026")
        self.assertEqual(
            fecha_corta(datetime(2026, 9, 11, 15, 30, tzinfo=datetime_timezone.utc)),
            "11/09/2026",
        )
        self.assertEqual(fecha_corta("2026-09-11"), "11/09/2026")

    def test_fecha_corta_conserva_valor_no_interpretable(self):
        self.assertEqual(fecha_corta(None), "")
        self.assertEqual(fecha_corta("sin fecha"), "sin fecha")
