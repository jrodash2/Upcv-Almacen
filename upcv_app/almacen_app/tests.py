from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from .form import Form1hForm
from .models import Dependencia, Programa
from .templatetags.moneda_filters import fecha_corta, quetzales


class Form1hFormTests(TestCase):
    def test_preselecciona_primera_dependencia_y_programa_activos(self):
        primera_dependencia = Dependencia.objects.create(nombre="Primera")
        Dependencia.objects.create(nombre="Segunda")
        primera_programa = Programa.objects.create(nombre="Primero")
        Programa.objects.create(nombre="Segundo")

        formulario = Form1hForm()

        self.assertEqual(
            formulario.fields["dependencia"].initial, primera_dependencia
        )
        self.assertEqual(formulario.fields["programa"].initial, primera_programa)

    def test_excluye_opciones_inactivas(self):
        Dependencia.objects.create(nombre="Inactiva", activo=False)
        dependencia_activa = Dependencia.objects.create(nombre="Activa")
        Programa.objects.create(nombre="Inactivo", activo=False)
        programa_activo = Programa.objects.create(nombre="Activo")

        formulario = Form1hForm()

        self.assertEqual(
            list(formulario.fields["dependencia"].queryset), [dependencia_activa]
        )
        self.assertEqual(
            list(formulario.fields["programa"].queryset), [programa_activo]
        )

    def test_respeta_valores_iniciales_existentes(self):
        primera_dependencia = Dependencia.objects.create(nombre="Primera")
        dependencia_inicial = Dependencia.objects.create(nombre="Inicial")
        primer_programa = Programa.objects.create(nombre="Primero")
        programa_inicial = Programa.objects.create(nombre="Inicial")

        formulario = Form1hForm(
            initial={
                "dependencia": dependencia_inicial,
                "programa": programa_inicial,
            }
        )

        self.assertEqual(formulario.initial["dependencia"], dependencia_inicial)
        self.assertEqual(formulario.initial["programa"], programa_inicial)
        self.assertNotEqual(
            formulario.initial["dependencia"], primera_dependencia
        )
        self.assertNotEqual(formulario.initial["programa"], primer_programa)


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
