from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .form import Form1hForm, ReversionMovimientoForm
from .models import (
    Articulo,
    Dependencia,
    DetalleFactura,
    Kardex,
    Programa,
    ReversionMovimiento,
    Serie,
    form1h,
)
from .templatetags.moneda_filters import fecha_corta, quetzales
from .views import _procesar_movimientos_kardex


class Form1hFormTests(TestCase):
    def test_preselecciona_primera_dependencia_y_programa_disponibles(self):
        primera_dependencia = Dependencia.objects.create(
            nombre="Primera", activo=False
        )
        Dependencia.objects.create(nombre="Segunda")
        primera_programa = Programa.objects.create(nombre="Primero", activo=False)
        Programa.objects.create(nombre="Segundo")

        formulario = Form1hForm()

        self.assertEqual(
            formulario.fields["dependencia"].initial, primera_dependencia
        )
        self.assertEqual(formulario.fields["programa"].initial, primera_programa)

    def test_muestra_todas_las_opciones_disponibles(self):
        dependencia_inactiva = Dependencia.objects.create(
            nombre="Inactiva", activo=False
        )
        dependencia_activa = Dependencia.objects.create(nombre="Activa")
        programa_inactivo = Programa.objects.create(nombre="Inactivo", activo=False)
        programa_activo = Programa.objects.create(nombre="Activo")

        formulario = Form1hForm()

        self.assertEqual(
            list(formulario.fields["dependencia"].queryset),
            [dependencia_inactiva, dependencia_activa],
        )
        self.assertEqual(
            list(formulario.fields["programa"].queryset),
            [programa_inactivo, programa_activo],
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


class Form1hFormTests(TestCase):
    def test_preselecciona_primera_dependencia_y_programa_disponibles(self):
        primera_dependencia = Dependencia.objects.create(
            nombre="Primera", activo=False
        )
        Dependencia.objects.create(nombre="Segunda")
        primera_programa = Programa.objects.create(nombre="Primero", activo=False)
        Programa.objects.create(nombre="Segundo")

        formulario = Form1hForm()

        self.assertEqual(
            formulario.fields["dependencia"].initial, primera_dependencia
        )
        self.assertEqual(formulario.fields["programa"].initial, primera_programa)

    def test_muestra_todas_las_opciones_disponibles(self):
        dependencia_inactiva = Dependencia.objects.create(
            nombre="Inactiva", activo=False
        )
        dependencia_activa = Dependencia.objects.create(nombre="Activa")
        programa_inactivo = Programa.objects.create(nombre="Inactivo", activo=False)
        programa_activo = Programa.objects.create(nombre="Activo")

        formulario = Form1hForm()

        self.assertEqual(
            list(formulario.fields["dependencia"].queryset),
            [dependencia_inactiva, dependencia_activa],
        )
        self.assertEqual(
            list(formulario.fields["programa"].queryset),
            [programa_inactivo, programa_activo],
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


class ReversionMovimientoFormTests(SimpleTestCase):
    def test_justificacion_es_obligatoria_y_requiere_diez_caracteres(self):
        formulario_vacio = ReversionMovimientoForm(data={"justificacion": ""})
        formulario_corto = ReversionMovimientoForm(data={"justificacion": "corto"})

        self.assertFalse(formulario_vacio.is_valid())
        self.assertIn(
            "Debe ingresar una justificación para realizar la reversión.",
            formulario_vacio.errors["justificacion"],
        )
        self.assertFalse(formulario_corto.is_valid())
        self.assertIn(
            "La justificación debe tener al menos 10 caracteres.",
            formulario_corto.errors["justificacion"],
        )


class ReversionesViewsTests(TestCase):
    def setUp(self):
        administradores = Group.objects.create(name="Administrador")
        self.administrador = User.objects.create_user(
            username="admin_reversion", password="secreto"
        )
        self.administrador.groups.add(administradores)
        self.gestor = User.objects.create_user(username="gestor", password="secreto")
        self.gestor.groups.add(Group.objects.create(name="Gestor"))
        self.articulo = Articulo.objects.create(codigo="REV-001", nombre="Prueba")

    def test_administrador_revierte_ingreso_y_no_puede_repetirlo(self):
        original = Kardex.objects.create(
            articulo=self.articulo, tipo_movimiento="INGRESO", cantidad=10
        )
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            reverse("almacen:crear_reversion", args=[original.id]),
            {"justificacion": "Corrección administrativa"},
        )

        reversion = ReversionMovimiento.objects.get(movimiento_original=original)
        original.refresh_from_db()
        self.assertRedirects(
            respuesta, reverse("almacen:detalle_reversion", args=[reversion.id])
        )
        self.assertEqual(original.estado, "revertido")
        self.assertEqual(reversion.movimiento_reversion.tipo_movimiento, "SALIDA")
        self.assertEqual(reversion.movimiento_reversion.estado, "reversion")
        self.assertEqual(reversion.movimiento_reversion.saldo_actual, 0)

        respuesta_repetida = self.client.post(
            reverse("almacen:crear_reversion", args=[original.id]),
            {"justificacion": "Segundo intento inválido"},
        )
        self.assertContains(respuesta_repetida, "Este movimiento ya fue revertido.")
        self.assertEqual(ReversionMovimiento.objects.count(), 1)

    def test_reversion_de_salida_genera_ingreso(self):
        Kardex.objects.create(
            articulo=self.articulo, tipo_movimiento="INGRESO", cantidad=10
        )
        salida = Kardex.objects.create(
            articulo=self.articulo, tipo_movimiento="SALIDA", cantidad=4
        )
        self.client.force_login(self.administrador)

        self.client.post(
            reverse("almacen:crear_reversion", args=[salida.id]),
            {"justificacion": "Salida registrada por error"},
        )

        reversion = ReversionMovimiento.objects.get(movimiento_original=salida)
        self.assertEqual(reversion.movimiento_reversion.tipo_movimiento, "INGRESO")
        self.assertEqual(reversion.movimiento_reversion.saldo_actual, 10)

    def test_no_revierte_ingreso_sin_existencia_suficiente(self):
        ingreso = Kardex.objects.create(
            articulo=self.articulo, tipo_movimiento="INGRESO", cantidad=10
        )
        Kardex.objects.create(
            articulo=self.articulo, tipo_movimiento="SALIDA", cantidad=6
        )
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            reverse("almacen:crear_reversion", args=[ingreso.id]),
            {"justificacion": "Intento sin existencia suficiente"},
        )

        self.assertContains(
            respuesta,
            "No se puede revertir este ingreso porque la existencia actual del artículo no es suficiente.",
        )
        self.assertFalse(ReversionMovimiento.objects.exists())
        ingreso.refresh_from_db()
        self.assertEqual(ingreso.estado, "activo")

    def test_gestor_no_accede_a_reversiones(self):
        self.client.force_login(self.gestor)

        respuesta = self.client.get(reverse("almacen:reversiones_historial"))

        self.assertRedirects(respuesta, reverse("almacen:acceso_denegado"))


class CalculoKardexConReversionesTests(TestCase):
    def setUp(self):
        self.articulo = Articulo.objects.create(codigo="TAPE", nombre='Cinta 2"')
        Serie.objects.create(
            serie="F", numero_inicial=1, numero_final=100, activo=True
        )
        formulario = form1h.objects.create(numero_factura="FACT-REV-1")
        self.detalle = DetalleFactura.objects.create(
            form1h=formulario,
            articulo=self.articulo,
            cantidad=226,
            precio_unitario=Decimal("12.10"),
            precio_total=Decimal("2734.60"),
            id_linea=1,
            renglon=100,
        )

    def test_reversion_de_salida_cuadra_filas_y_totales(self):
        Kardex.objects.create(
            articulo=self.articulo,
            tipo_movimiento="INGRESO",
            cantidad=226,
            fuente_factura=self.detalle,
        )
        salida = Kardex.objects.create(
            articulo=self.articulo, tipo_movimiento="SALIDA", cantidad=2
        )
        movimiento_reversion = Kardex.objects.create(
            articulo=self.articulo,
            tipo_movimiento="INGRESO",
            cantidad=2,
            estado="reversion",
            movimiento_revertido=salida,
        )
        ReversionMovimiento.objects.create(
            movimiento_original=salida,
            movimiento_reversion=movimiento_reversion,
            tipo_reversion="SALIDA",
            articulo=self.articulo,
            cantidad=2,
            justificacion="Salida registrada por error",
            realizado_por=User.objects.create_user(username="auditor"),
        )

        movimientos, totales = _procesar_movimientos_kardex(self.articulo)

        self.assertEqual(movimientos[0].saldo_calculado, 226)
        self.assertEqual(movimientos[0].saldo_costo_total, Decimal("2734.60"))
        self.assertEqual(movimientos[1].saldo_calculado, 224)
        self.assertEqual(movimientos[1].precio_unitario, Decimal("12.10"))
        self.assertEqual(movimientos[1].saldo_costo_total, Decimal("2710.40"))
        self.assertEqual(movimientos[2].saldo_calculado, 226)
        self.assertEqual(movimientos[2].precio_unitario, Decimal("12.10"))
        self.assertEqual(movimientos[2].precio_total, Decimal("24.20"))
        self.assertEqual(movimientos[2].saldo_costo_total, Decimal("2734.60"))
        self.assertEqual(totales["total_ingresos"], 228)
        self.assertEqual(totales["total_costo_ingresos"], Decimal("2758.80"))
        self.assertEqual(totales["total_salidas"], 2)
        self.assertEqual(totales["total_costo_salidas"], Decimal("24.20"))
        self.assertEqual(totales["saldo_final_unidades"], 226)
        self.assertEqual(totales["saldo_final_costo"], Decimal("2734.60"))

    def test_reversion_de_ingreso_conserva_costo_original(self):
        ingreso = Kardex.objects.create(
            articulo=self.articulo,
            tipo_movimiento="INGRESO",
            cantidad=10,
            fuente_factura=self.detalle,
        )
        movimiento_reversion = Kardex.objects.create(
            articulo=self.articulo,
            tipo_movimiento="SALIDA",
            cantidad=10,
            estado="reversion",
            movimiento_revertido=ingreso,
        )
        ReversionMovimiento.objects.create(
            movimiento_original=ingreso,
            movimiento_reversion=movimiento_reversion,
            tipo_reversion="INGRESO",
            articulo=self.articulo,
            cantidad=10,
            justificacion="Ingreso registrado por error",
            realizado_por=User.objects.create_user(username="auditor_ingreso"),
        )

        movimientos, totales = _procesar_movimientos_kardex(self.articulo)

        self.assertEqual(movimientos[1].precio_unitario, Decimal("12.10"))
        self.assertEqual(movimientos[1].precio_total, Decimal("121.00"))
        self.assertEqual(totales["saldo_final_unidades"], 0)
        self.assertEqual(totales["saldo_final_costo"], Decimal("0.00"))

    def test_kardex_sin_reversion_mantiene_saldo_secuencial(self):
        Kardex.objects.create(
            articulo=self.articulo,
            tipo_movimiento="INGRESO",
            cantidad=226,
            fuente_factura=self.detalle,
        )
        Kardex.objects.create(
            articulo=self.articulo, tipo_movimiento="SALIDA", cantidad=2
        )

        movimientos, totales = _procesar_movimientos_kardex(self.articulo)

        self.assertEqual(movimientos[-1].saldo_calculado, 224)
        self.assertEqual(movimientos[-1].saldo_costo_total, Decimal("2710.40"))
        self.assertEqual(totales["saldo_final_unidades"], 224)
        self.assertEqual(totales["saldo_final_costo"], Decimal("2710.40"))
