"""Reservas exactas, auditoría y operaciones posteriores a la cancelación."""
from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from . import test_eliminar_detalle_requerimiento as fixtures
from .models import (DetalleRequerimiento, DetalleSolicitudRequerimiento, Kardex,
                     Requerimiento, SolicitudRequerimiento)


class CancelacionIndividualTests(TestCase):
    setUp = fixtures.EliminarDetalleRequerimientoTests.setUp
    post = fixtures.EliminarDetalleRequerimientoTests.post
    crear = fixtures.EliminarDetalleRequerimientoTests.crear
    convertir = fixtures.EliminarDetalleRequerimientoTests.convertir
    division = fixtures.EliminarDetalleRequerimientoTests.division
    saldo = fixtures.EliminarDetalleRequerimientoTests.saldo
    eliminar = fixtures.EliminarDetalleRequerimientoTests.eliminar
    detalle = fixtures.EliminarDetalleRequerimientoTests.detalle

    def escenario(self):
        division = self.division()
        self.assertEqual(self.crear([(self.a, 3, False), (self.a, 2, False)],
            [f'D:{self.directa.pk}', f'V:{division.pk}']).status_code, 201)
        solicitud = SolicitudRequerimiento.objects.get()
        req = self.convertir(solicitud)
        return req, solicitud, division, [
            req.detalles.get(detalle_solicitud_origen__asignacion_directa=self.directa),
            req.detalles.get(detalle_solicitud_origen__division_articulo_ubicacion=division)]

    def test_misma_articulo_dos_origenes_anular_y_convertir_sin_duplicar(self):
        req, solicitud, source, (directo, division) = self.escenario()
        asignados = (self.directa.cantidad_asignada, source.cantidad_asignada, source.division_articulo.cantidad_asignada)
        kardex = list(Kardex.objects.values())
        self.assertEqual(self.eliminar(division).status_code, 200)
        self.assertEqual(self.saldo(f'D:{self.directa.pk}')['reservado'], 3)
        self.assertEqual(self.saldo(f'V:{source.pk}')['reservado'], 0)
        cancelado = DetalleRequerimiento.all_objects.get(pk=division.pk)
        self.assertIsNotNone(cancelado.cancelado_en)
        self.assertEqual(cancelado.cancelado_por, self.user)
        self.assertEqual(cancelado.cantidad, 2)
        self.assertEqual(cancelado.motivo_cancelacion, 'Detalle solicitado por error')
        self.assertEqual(cancelado.detalle_solicitud_origen.solicitud_id, solicitud.pk)
        self.assertEqual(self.eliminar(division).status_code, 404)
        self.client.post(reverse('almacen:convertir_solicitud_en_requerimiento', args=[solicitud.pk]))
        self.assertEqual(Requerimiento.objects.count(), 1)
        self.assertEqual(req.detalles.count(), 1)
        self.assertEqual(DetalleSolicitudRequerimiento.objects.count(), 2)
        page = self.client.get(reverse('almacen:detalle_requerimiento', args=[req.pk]))
        self.assertContains(page, 'Historial de detalles eliminados')
        self.assertContains(page, 'Detalle solicitado por error')
        for _ in range(2):
            self.client.post(reverse('almacen:anular_requerimiento', args=[req.pk]), {'motivo_anulacion': 'Ya no se necesita'})
        self.assertEqual(self.saldo(f'D:{self.directa.pk}')['reservado'], 0)
        self.assertEqual(self.saldo(f'V:{source.pk}')['reservado'], 0)
        source.refresh_from_db()
        self.directa.refresh_from_db()
        self.assertEqual((self.directa.cantidad_asignada, source.cantidad_asignada, source.division_articulo.cantidad_asignada), asignados)
        self.assertEqual(list(Kardex.objects.values()), kardex)

    def test_motivo_obligatorio(self):
        detalle = self.detalle()
        for motivo in ['', '  ', 'ab', 'x'*501]:
            self.assertEqual(self.eliminar(detalle, motivo=motivo).status_code, 400)
        self.assertTrue(DetalleRequerimiento.objects.filter(pk=detalle.pk).exists())

    def test_rollback_despues_de_liberar_division(self):
        req, solicitud, source, (_, detalle) = self.escenario()
        original = DetalleRequerimiento.save
        def falla(obj, *args, **kwargs):
            original(obj, *args, **kwargs)
            if obj.cancelado_en:
                raise RuntimeError('Fallo de auditoría de prueba')
        with patch.object(DetalleRequerimiento, 'save', falla), self.assertLogs(level='ERROR'):
            self.assertEqual(self.eliminar(detalle).status_code, 500)
        source.refresh_from_db()
        self.assertEqual(source.cantidad_reservada, 2)
        self.assertIsNone(DetalleRequerimiento.objects.get(pk=detalle.pk).cancelado_en)

    def test_origen_ambiguo_o_reserva_inconsistente_no_modifican(self):
        req, solicitud, source, (_, detalle) = self.escenario()
        ds = detalle.detalle_solicitud_origen
        for campo, valor in [('cantidad', 3), ('division_articulo_ubicacion_id', None), ('detalle_requerimiento_id', None)]:
            original = getattr(ds, campo)
            DetalleSolicitudRequerimiento.objects.filter(pk=ds.pk).update(**{campo:valor})
            self.assertEqual(self.eliminar(detalle).status_code, 400)
            DetalleSolicitudRequerimiento.objects.filter(pk=ds.pk).update(**{campo:original})
        type(source).objects.filter(pk=source.pk).update(cantidad_reservada=1)
        self.assertEqual(self.eliminar(detalle).status_code, 400)
        source.refresh_from_db()
        self.assertEqual(source.cantidad_reservada, 1)
        self.assertTrue(DetalleRequerimiento.objects.filter(pk=detalle.pk).exists())

    def test_ultima_fila_no_se_despacha_ni_recrea(self):
        detalle = self.detalle()
        req = detalle.requerimiento
        self.assertEqual(self.eliminar(detalle).status_code, 200)
        self.assertTrue(Requerimiento.objects.filter(pk=req.pk).exists())
        self.assertFalse(req.detalles.exists())
        req.estado='enviado'
        req.save()
        self.client.post(reverse('almacen:despachar_requerimiento', args=[req.pk]))
        req.refresh_from_db()
        self.assertEqual(req.estado, 'enviado')
        self.assertFalse(Kardex.objects.exists())

    def test_despacho_restante_no_incluye_cancelado(self):
        from .test_disponibilidad import FuentesDisponibilidadTests
        req, solicitud, source, (directo, division) = self.escenario()
        FuentesDisponibilidadTests.ingreso(self)
        self.assertEqual(self.eliminar(division).status_code, 200)
        req.estado='enviado'
        req.save()
        self.client.post(reverse('almacen:despachar_requerimiento', args=[req.pk]),
            {f'cantidades[{directo.pk}]': 3, f'cantidades[{division.pk}]': 2})
        req.refresh_from_db()
        self.assertEqual(req.estado, 'despachado')
        self.assertEqual(Kardex.objects.filter(tipo_movimiento='SALIDA').count(), 1)
        self.assertFalse(Kardex.objects.filter(fuente_despacho_id=division.pk).exists())
        self.assertEqual(DetalleRequerimiento.objects.get(pk=directo.pk).cantidad_despachada, 3)
        self.assertEqual(DetalleRequerimiento.all_objects.get(pk=division.pk).cantidad_despachada, 0)


from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections
from django.test import Client, TransactionTestCase


class CancelacionConcurrenteTests(TransactionTestCase):
    setUp = fixtures.EliminarDetalleRequerimientoTests.setUp
    post = fixtures.EliminarDetalleRequerimientoTests.post
    crear = fixtures.EliminarDetalleRequerimientoTests.crear
    convertir = fixtures.EliminarDetalleRequerimientoTests.convertir
    division = fixtures.EliminarDetalleRequerimientoTests.division
    escenario = CancelacionIndividualTests.escenario
    saldo = fixtures.EliminarDetalleRequerimientoTests.saldo

    def paralelo(self, operaciones):
        barrier = Barrier(len(operaciones))
        cookie = self.client.cookies['sessionid'].value
        def ejecutar(operacion):
            close_old_connections()
            try:
                client = Client()
                client.cookies['sessionid'] = cookie
                barrier.wait(timeout=10)
                return client.post(*operacion).status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=len(operaciones)) as pool:
            return list(pool.map(ejecutar, operaciones))

    def test_doble_cancelacion_libera_una_vez(self):
        req, solicitud, source, (_, detalle) = self.escenario()
        operacion = (reverse('almacen:eliminar_detalle_requerimiento', args=[detalle.pk]),
                     {'motivo': 'Duplicado por error', 'requerimiento_id': req.pk})
        self.assertEqual(sorted(self.paralelo([operacion, operacion])), [200, 404])
        source.refresh_from_db()
        self.assertEqual(source.cantidad_reservada, 0)
        self.assertEqual(req.detalles.count(), 1)
        self.assertEqual(DetalleRequerimiento.all_objects.filter(cancelado_en__isnull=False).count(), 1)

    def test_cancelacion_y_anulacion_no_restan_dos_veces(self):
        req, solicitud, source, (_, detalle) = self.escenario()
        resultados = self.paralelo([
            (reverse('almacen:eliminar_detalle_requerimiento', args=[detalle.pk]), {'motivo': 'Retirar fila'}),
            (reverse('almacen:anular_requerimiento', args=[req.pk]), {'motivo_anulacion': 'Ya no se necesita'})])
        self.assertIn(resultados[0], [200, 400])
        self.assertEqual(resultados[1], 302)
        source.refresh_from_db()
        self.assertEqual(source.cantidad_reservada, 0)
        self.assertEqual(self.saldo(f'D:{self.directa.pk}')['reservado'], 0)

    def test_cancelacion_y_conversion_repetida_no_recrean(self):
        req, solicitud, source, (_, detalle) = self.escenario()
        resultados = self.paralelo([
            (reverse('almacen:eliminar_detalle_requerimiento', args=[detalle.pk]), {'motivo': 'Retirar fila'}),
            (reverse('almacen:convertir_solicitud_en_requerimiento', args=[solicitud.pk]), {})])
        self.assertEqual(resultados, [200, 302])
        self.assertEqual(Requerimiento.objects.count(), 1)
        self.assertEqual(req.detalles.count(), 1)
        source.refresh_from_db()
        self.assertEqual(source.cantidad_reservada, 0)

    def test_despacho_concurrente_de_enviado_impide_cancelar(self):
        from .test_disponibilidad import FuentesDisponibilidadTests
        req, solicitud, source, (directo, division) = self.escenario()
        FuentesDisponibilidadTests.ingreso(self)
        req.estado='enviado'
        req.save()
        resultados = self.paralelo([
            (reverse('almacen:eliminar_detalle_requerimiento', args=[division.pk]), {'motivo': 'Retirar fila'}),
            (reverse('almacen:despachar_requerimiento', args=[req.pk]),
             {f'cantidades[{directo.pk}]': 3, f'cantidades[{division.pk}]': 2})])
        self.assertEqual(resultados, [400, 302])
        source.refresh_from_db()
        self.assertEqual((source.cantidad_reservada, source.cantidad_consumida), (0, 2))
        self.assertEqual(Kardex.objects.filter(tipo_movimiento='SALIDA').count(), 2)
