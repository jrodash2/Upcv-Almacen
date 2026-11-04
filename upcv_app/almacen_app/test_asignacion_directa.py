"""Asignación directa: código comercial, AJAX, saldos y guardado sin tocar divisiones."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils.html import escape

from .disponibilidad import resumen_global_articulo
from .form import AsignacionDetalleFacturaForm
from .models import (Articulo, AsignacionDetalleFactura, Categoria, Departamento,
    DetalleFactura, DivisionAlmacen, DivisionArticulo, Kardex, Serie,
    UsuarioDepartamento, form1h)


class AsignacionDirectaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='asignador')
        self.user.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        self.client.force_login(self.user)
        self.dept = Departamento.objects.create(id_departamento='AD', nombre='Destino')
        UsuarioDepartamento.objects.create(usuario=self.user, departamento=self.dept)
        self.a = Articulo.objects.create(pk=9876, codigo='675',
            nombre='Medalla 2.5" Dorada de metal incluye cinta',
            categoria=Categoria.objects.create(nombre='Bien'), renglon_presupuestario='291')
        Serie.objects.create(serie='AD', numero_inicial=1, numero_final=100, activo=True)
        self.factura = form1h.objects.create(numero_factura='AD-1', estado='confirmado')
        DetalleFactura.objects.create(form1h=self.factura, articulo=self.a, cantidad=80,
            precio_unitario=Decimal('2'), id_linea=1, renglon=291)
        self.division = DivisionArticulo.objects.create(
            division=DivisionAlmacen.objects.create(nombre='División AD'),
            articulo=self.a, cantidad_asignada=30)
        self.url = reverse('almacen:crear_asignacion_detalle')
        self.busqueda = reverse('almacen:buscar_articulos')

    def data(self, cantidad):
        return {'articulo': self.a.pk, 'destino': self.dept.pk, 'cantidad_asignada': cantidad}

    def buscar(self, q='675'):
        return self.client.get(self.busqueda, {'q': q, 'asignacion_directa': '1'}).json()[0]

    def test_codigo_y_nombre_devuelven_identificador_interno_y_catalogo(self):
        for q in ['675', 'Medalla', 'incluye cinta']:
            with self.subTest(q=q):
                item = self.buscar(q)
                self.assertEqual(item['id'], 9876)
                self.assertEqual(item['codigo'], '675')
                self.assertEqual(item['nombre'], self.a.nombre)
                self.assertEqual(item['categoria'], 'Bien')
                self.assertEqual(item['renglon_presupuestario'], '291')

    def test_ajax_saldos_reales_y_descripcion_incluso_con_cero(self):
        item = self.buscar()
        self.assertEqual(Decimal(item['existencias']['existencia_fisica']), 80)
        self.assertEqual(Decimal(item['existencias']['disponible_para_division']), 50)
        self.division.cantidad_asignada = 80
        self.division.save()
        item = self.buscar()
        self.assertEqual(item['nombre'], self.a.nombre)
        self.assertEqual(Decimal(item['existencias']['disponible_para_division']), 0)
        response = self.client.post(self.url, self.data(1))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AsignacionDetalleFactura.objects.exists())

    def test_contrato_busqueda_compartida_sin_cambios(self):
        item = self.client.get(self.busqueda, {'q': '675'}).json()[0]
        self.assertEqual(set(item), {'id', 'codigo', 'nombre', 'text', 'categoria', 'renglon_presupuestario'})

    def test_existencias_conservan_permisos_de_asignacion(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.busqueda, {'q': '675'}).status_code, 200)
        self.assertEqual(self.client.get(self.busqueda, {'q': '675', 'asignacion_directa': '1'}).status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.user.groups.clear()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.busqueda, {'q': '675', 'asignacion_directa': '1'}).status_code, 403)

    def test_pagina_no_inyecta_decimal_como_javascript(self):
        html = self.client.get(self.url).content.decode()
        self.assertNotIn('Decimal(', html)
        self.assertIn('asignacion_directa.js', html)

    def test_cantidades_1_25_50_guardan_sin_alterar_historia_ni_divisiones(self):
        for cantidad in [1, 25, 50]:
            with self.subTest(cantidad=cantidad):
                # Cada cantidad usa el mismo saldo inicial sin modificar registros históricos.
                with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
                    form = AsignacionDetalleFacturaForm(self.data(cantidad))
                    self.assertTrue(form.is_valid(), form.errors)
                    with transaction.atomic():
                        before = list(Kardex.objects.values())
                        response = self.client.post(self.url, self.data(cantidad))
                        self.assertEqual(response.status_code, 302)
                        asignacion = AsignacionDetalleFactura.objects.get()
                        self.assertEqual(asignacion.cantidad_asignada, cantidad)
                        self.division.refresh_from_db()
                        self.assertEqual(self.division.cantidad_asignada, 30)
                        self.assertEqual(list(Kardex.objects.values()), before)
                        self.assertEqual(resumen_global_articulo(self.a)['disponible_para_division'], 50-cantidad)
                        self.assertContains(self.client.get(self.url), 'Última Asignación')
                        transaction.set_rollback(True)

    def test_rechaza_excesiva_cero_negativa_vacia_fraccion(self):
        for cantidad in [51, 0, -1, '', '1.5']:
            with self.subTest(cantidad=cantidad):
                response = self.client.post(self.url, self.data(cantidad))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
                self.assertFalse(AsignacionDetalleFactura.objects.exists())

    def test_preserva_asignaciones_anteriores_y_actualiza_stock_e_historial(self):
        form = AsignacionDetalleFacturaForm(self.data(10))
        self.assertTrue(form.is_valid(), form.errors)
        anterior = form.save()
        historial = AsignacionDetalleFactura.objects.filter(pk=anterior.pk).values().get()
        kardex = list(Kardex.objects.values())
        self.assertEqual(self.client.post(self.url, self.data(25)).status_code, 302)
        self.assertEqual(AsignacionDetalleFactura.objects.filter(pk=anterior.pk).values().get(), historial)
        self.assertEqual(list(Kardex.objects.values()), kardex)
        self.factura.refresh_from_db()
        self.division.refresh_from_db()
        self.assertEqual(self.factura.estado, 'confirmado')
        self.assertEqual(self.division.cantidad_asignada, 30)
        self.assertEqual(resumen_global_articulo(self.a)['existencia_fisica'], 80)
        self.assertEqual(resumen_global_articulo(self.a)['disponible_para_division'], 15)
        response = self.client.get(self.url)
        self.assertEqual(response.context['ultima_asignacion'].cantidad_asignada, 25)
        self.assertContains(response, escape(self.a.nombre))

    def test_revalida_saldo_al_guardar_formulario_ya_validado(self):
        form = AsignacionDetalleFacturaForm(self.data(50))
        self.assertTrue(form.is_valid(), form.errors)
        self.division.cantidad_asignada = 40
        self.division.save()
        with self.assertRaises(ValidationError):
            form.save()
        self.assertFalse(AsignacionDetalleFactura.objects.exists())

    def test_departamento_sin_usuario_no_impide_asignacion(self):
        UsuarioDepartamento.objects.all().delete()
        response = self.client.post(self.url, self.data(1))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AsignacionDetalleFactura.objects.get().cantidad_asignada, 1)


class AsignacionDirectaConcurrenciaTests(TransactionTestCase):
    setUp = AsignacionDirectaTests.setUp
    data = AsignacionDirectaTests.data

    def test_dos_directas_compiten_por_el_mismo_saldo(self):
        barrera = Barrier(2)
        def asignar():
            close_old_connections()
            try:
                form = AsignacionDetalleFacturaForm(self.data(40))
                valido = form.is_valid()
                barrera.wait(timeout=10)
                if not valido:
                    return 'invalid'
                try:
                    form.save()
                    return 'saved'
                except ValidationError:
                    return 'stock'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(lambda _: asignar(), range(2)))
        self.assertCountEqual(resultados, ['saved', 'stock'])
        self.assertEqual(AsignacionDetalleFactura.objects.get().cantidad_asignada, 40)
        self.assertEqual(resumen_global_articulo(self.a)['disponible_para_division'], 10)
        self.division.refresh_from_db()
        self.assertEqual(self.division.cantidad_asignada, 30)
