from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from io import StringIO
import json

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from .disponibilidad import fuentes_departamento
from .models import (AsignacionDetalleFactura, Departamento, DetalleRequerimiento,
    DetalleSolicitudRequerimiento, DivisionAlmacen, DivisionArticulo,
    DivisionArticuloUbicacion, DivisionUbicacion, Requerimiento, SolicitudRequerimiento,
    Serie, form1h, DetalleFactura, Kardex)
from . import test_solicitud_filas as fixtures
from .views import construir_resumen_gestor_departamento, construir_stock_list_administrador


def preparar(self):
    fixtures.SolicitudFilasTests.setUp(self)
    AsignacionDetalleFactura.objects.filter(articulo=self.a).update(cantidad_asignada=10)
    self.directa = AsignacionDetalleFactura.objects.get(articulo=self.a)
    self.user.groups.add(Group.objects.get_or_create(name='Administrador')[0])


class FuentesDisponibilidadTests(TestCase):
    setUp = preparar
    post = fixtures.SolicitudFilasTests.post

    def division(self, cantidad=4, reservado=0, consumido=0):
        division = DivisionAlmacen.objects.create(nombre='Administración')
        DivisionUbicacion.objects.create(division=division, ubicacion=self.dept)
        source = DivisionArticulo(division=division, articulo=self.a, cantidad_asignada=20)
        DivisionArticulo.objects.bulk_create([source])
        return DivisionArticuloUbicacion.objects.create(division_articulo=source, ubicacion=self.dept,
            cantidad_asignada=cantidad, cantidad_reservada=reservado, cantidad_consumida=consumido)

    def crear(self, rows, sources):
        return self.post(rows, HTTP_ACCEPT='application/json',
                         **{f'detalles-{i}-origen': key for i, key in enumerate(sources)})

    def saldo(self, key):
        return next(f for f in fuentes_departamento(self.dept) if f['fuente'] == key)

    def convertir(self, solicitud):
        response = self.client.post(reverse('almacen:convertir_solicitud_en_requerimiento', args=[solicitud.pk]))
        self.assertEqual(response.status_code, 302)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'convertida')
        return solicitud.requerimiento

    def ingreso(self):
        Serie.objects.create(serie='SAL', numero_inicial=1, numero_final=100, activo=True)
        factura = form1h.objects.create(numero_factura='FUENTES', estado='confirmado')
        DetalleFactura.objects.create(form1h=factura, articulo=self.a, cantidad=30,
            precio_unitario=Decimal('1'), precio_total=Decimal('30'), id_linea=1, renglon=243)

    def test_a_solo_directo_reserva_y_deja_nueve(self):
        key = f'D:{self.directa.pk}'
        self.assertEqual(self.crear([(self.a, 1, False)], [key]).status_code, 201)
        detalle = SolicitudRequerimiento.objects.get().detalles.get()
        self.assertEqual(detalle.asignacion_directa, self.directa)
        self.assertIsNone(detalle.division_articulo_ubicacion_id)
        self.assertEqual(self.saldo(key)['reservado'], 1)
        self.assertEqual(self.saldo(key)['disponible'], 9)

    def test_b_division_agotada_rechaza_con_mensaje_preciso(self):
        division = self.division(2, 1, 1)
        response = self.crear([(self.a, 1, False)], [f'V:{division.pk}'])
        self.assertEqual(response.status_code, 400)
        errors = ' '.join(response.json()['errors'])
        for texto in ['FILA-A', 'Artículo A', 'Administración', 'disponibles']:
            self.assertIn(texto, errors)
        self.assertFalse(SolicitudRequerimiento.objects.exists())

    def test_c_directo_no_se_valida_como_division_y_explica_9_vs_10(self):
        division = self.division(2, 1, 1)
        req = Requerimiento.objects.create(departamento=self.dept, creado_por=self.user, estado='despachado')
        # Historical completed dispatch: no source link existed, but division counter records its consumption.
        DetalleRequerimiento.objects.bulk_create([DetalleRequerimiento(requerimiento=req, articulo=self.a,
            cantidad=1, cantidad_despachada=1, estado='despachado')])
        key = f'D:{self.directa.pk}'
        self.assertEqual(self.saldo(key)['disponible'], 10)
        self.assertEqual(self.crear([(self.a, 1, False)], [key]).status_code, 201)
        division.refresh_from_db()
        self.assertEqual((division.cantidad_reservada, division.cantidad_consumida), (1, 1))
        self.assertEqual(self.saldo(key)['disponible'], 9)

    def test_d_origenes_separados_se_guardan_con_trazabilidad(self):
        self.directa.cantidad_asignada = 6
        self.directa.save()
        division = self.division(4)
        response = self.crear([(self.a, 6, False), (self.a, 2, False)],
                              [f'D:{self.directa.pk}', f'V:{division.pk}'])
        self.assertEqual(response.status_code, 201, response.content)
        detalles = list(SolicitudRequerimiento.objects.get().detalles.order_by('pk'))
        self.assertEqual(detalles[0].asignacion_directa_id, self.directa.pk)
        self.assertEqual(detalles[1].division_articulo_ubicacion_id, division.pk)
        self.assertEqual([self.saldo(k)['disponible'] for k in [f'D:{self.directa.pk}', f'V:{division.pk}']], [0, 2])

    def test_e_solicitudes_sucesivas_no_sobrerreservan(self):
        key = f'D:{self.directa.pk}'
        self.assertEqual(self.crear([(self.a, 7, False)], [key]).status_code, 201)
        self.assertEqual(self.crear([(self.a, 4, False)], [key]).status_code, 400)
        self.assertEqual(SolicitudRequerimiento.objects.count(), 1)

    def test_f_fila_eliminada_no_reserva_su_fuente(self):
        division = self.division(4)
        response = self.crear([(self.a, 1, False), (self.a, 3, True)], [f'D:{self.directa.pk}', f'V:{division.pk}'])
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.saldo(f'V:{division.pk}')['reservado'], 0)
        self.assertEqual(SolicitudRequerimiento.objects.get().detalles.count(), 1)

    def test_g_rechazo_libera_una_vez_ambas_fuentes(self):
        division = self.division(4)
        self.crear([(self.a, 3, False), (self.a, 2, False)], [f'D:{self.directa.pk}', f'V:{division.pk}'])
        solicitud = SolicitudRequerimiento.objects.get()
        url = reverse('almacen:rechazar_solicitud_requerimiento', args=[solicitud.pk])
        for _ in range(2):
            self.client.post(url, {'motivo_rechazo': 'No se necesita'})
        self.assertEqual(self.saldo(f'D:{self.directa.pk}')['reservado'], 0)
        self.assertEqual(self.saldo(f'V:{division.pk}')['reservado'], 0)

    def test_h_conversion_despacho_no_duplica_reserva_ni_mezcla_fuentes(self):
        self.ingreso()
        division = self.division(4)
        self.crear([(self.a, 3, False), (self.a, 2, False)], [f'D:{self.directa.pk}', f'V:{division.pk}'])
        solicitud = SolicitudRequerimiento.objects.get()
        req = self.convertir(solicitud)
        self.client.post(reverse('almacen:convertir_solicitud_en_requerimiento', args=[solicitud.pk]))
        self.assertEqual(Requerimiento.objects.count(), 1)
        self.assertEqual(self.saldo(f'D:{self.directa.pk}')['reservado'], 3)
        self.assertEqual(self.saldo(f'V:{division.pk}')['reservado'], 2)
        req.estado = 'enviado'
        req.save()
        url = reverse('almacen:despachar_requerimiento', args=[req.pk])
        data = {f'cantidades[{d.pk}]': d.cantidad for d in req.detalles.all()}
        self.client.post(url, data)
        req.refresh_from_db()
        self.assertEqual(req.estado, 'despachado')
        self.assertEqual((self.saldo(f'D:{self.directa.pk}')['reservado'], self.saldo(f'D:{self.directa.pk}')['consumido']), (0, 3))
        self.assertEqual((self.saldo(f'V:{division.pk}')['reservado'], self.saldo(f'V:{division.pk}')['consumido']), (0, 2))
        self.client.post(url, data)
        self.assertEqual(Kardex.objects.filter(tipo_movimiento='SALIDA').count(), 2)
        self.assertEqual(self.saldo(f'V:{division.pk}')['consumido'], 2)

    def test_anulacion_de_convertida_libera_reservas(self):
        division = self.division(4)
        self.crear([(self.a, 3, False), (self.a, 2, False)], [f'D:{self.directa.pk}', f'V:{division.pk}'])
        req = self.convertir(SolicitudRequerimiento.objects.get())
        url = reverse('almacen:anular_requerimiento', args=[req.pk])
        for _ in range(2):
            self.client.post(url, {'motivo_anulacion': 'Error de solicitud'})
        self.assertEqual(self.saldo(f'D:{self.directa.pk}')['reservado'], 0)
        self.assertEqual(self.saldo(f'V:{division.pk}')['reservado'], 0)

    def test_i_api_resumen_y_admin_coinciden_sin_duplicar_distribuciones(self):
        self.ingreso()
        division = self.division(4)
        self.crear([(self.a, 3, False), (self.a, 2, False)], [f'D:{self.directa.pk}', f'V:{division.pk}'])
        response = self.client.get(reverse('almacen:articulos_asignados', args=[self.dept.pk]))
        item = next(a for a in response.json()['articulos'] if a['id'] == self.a.pk)
        self.assertEqual(sum(Decimal(f['cantidad_disponible']) for f in item['fuentes']), 9)
        resumen, filas = construir_resumen_gestor_departamento(self.dept)
        a = next(f for f in resumen if f['articulo_id'] == self.a.pk)
        self.assertEqual((a['disponible'], a['reservado']), (9, 5))
        admin = next(f for f in construir_stock_list_administrador() if f['articulo_id'] == self.a.pk)
        self.assertEqual(admin['reservado_total'], 5)
        # Parent division allocation 20 already contains the 4 distributed units.
        self.assertEqual(admin['asignado'], 30)
        self.assertEqual(admin['disponible'], 0)
        response = self.client.get(reverse('almacen:articulo_disponibilidad_json', args=[self.a.pk]))
        self.assertEqual(Decimal(response.json()['disponible_para_division']), admin['disponible'])
        self.assertEqual(Decimal(response.json()['reservado']), admin['reservado_total'])
        response = self.client.get(reverse('almacen:division_control'))
        ubicacion = next(x for x in response.context['asignaciones'] if x.pk == division.pk)
        self.assertEqual(ubicacion.disponible_ubicacion, 2)
        response = self.client.get(reverse('almacen:detalle_departamento', args=[self.dept.pk]))
        self.assertEqual(next(x for x in response.context['resumen_stock'] if x['articulo_id'] == self.a.pk)['disponible'], 9)
        response = self.client.get(reverse('almacen:mis_articulos_asignados'))
        self.assertEqual(sum(f['disponible'] for f in response.context['asignaciones'] if f['articulo'].pk == self.a.pk), 9)

    def test_fuente_ajena_o_de_otro_articulo_es_rechazada(self):
        otro = AsignacionDetalleFactura.objects.get(articulo=self.b)
        response = self.crear([(self.a, 1, False)], [f'D:{otro.pk}'])
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SolicitudRequerimiento.objects.exists())

    def test_origen_ambiguo_no_se_elige_automaticamente(self):
        self.division(4)
        self.assertEqual(self.post([(self.a, 1, False)]).status_code, 200)
        self.assertFalse(SolicitudRequerimiento.objects.exists())

    def test_membresia_inactiva_no_autoriza_nuevas_reservas(self):
        source = self.division(4)
        DivisionUbicacion.objects.update(activa=False)
        self.assertEqual(self.crear([(self.a, 1, False)], [f'V:{source.pk}']).status_code, 400)

    def test_error_posterior_revierte_toda_la_solicitud(self):
        from unittest.mock import patch
        from django.core.exceptions import ValidationError
        source = self.division(4)
        with patch.object(DetalleSolicitudRequerimiento, 'save', side_effect=ValidationError('Error guardando detalle')):
            response = self.crear([(self.a, 2, False)], [f'V:{source.pk}'])
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SolicitudRequerimiento.objects.exists())
        source.refresh_from_db()
        self.assertEqual(source.cantidad_reservada, 0)

    def test_auditoria_es_solo_lectura_y_conserva_reserva_no_identificada(self):
        source = self.division(2, 1, 1)
        out = StringIO()
        call_command('auditar_disponibilidad', departamento=self.dept.pk, codigo=self.a.codigo, stdout=out)
        data = json.loads(out.getvalue())
        self.assertEqual(len(data['contadores_division_incluidos_inactivos']), 1)
        source.refresh_from_db()
        self.assertEqual((source.cantidad_reservada, source.cantidad_consumida), (1, 1))
        self.assertFalse(SolicitudRequerimiento.objects.exists())

    def test_despacho_parcial_seguido_de_total_mueve_solo_la_diferencia(self):
        self.ingreso()
        source = self.division(4)
        self.crear([(self.a, 3, False)], [f'V:{source.pk}'])
        req = self.convertir(SolicitudRequerimiento.objects.get())
        detalle = req.detalles.get()
        url = reverse('almacen:despachar_requerimiento', args=[req.pk])
        for cantidad, esperado in [(1, (2, 1)), (1, (2, 1)), (3, (0, 3))]:
            req.estado = 'enviado'
            req.save()
            self.client.post(url, {f'cantidades[{detalle.pk}]': cantidad})
            source.refresh_from_db()
            self.assertEqual((source.cantidad_reservada, source.cantidad_consumida), esperado)
        self.assertEqual(Kardex.objects.filter(tipo_movimiento='SALIDA').count(), 1)

    def test_reserva_directa_historica_no_se_reescribe(self):
        solicitud = SolicitudRequerimiento.objects.create(departamento=self.dept, usuario_solicitante=self.user)
        detalle = DetalleSolicitudRequerimiento.objects.create(solicitud=solicitud, articulo=self.a, cantidad=2)
        fila = self.saldo(f'D:{self.directa.pk}')
        self.assertEqual((fila['reservado'], fila['disponible']), (2, 8))
        detalle.refresh_from_db()
        self.assertIsNone(detalle.asignacion_directa_id)

    def test_requerimiento_manual_reserva_directo_una_sola_vez(self):
        req = Requerimiento.objects.create(departamento=self.dept, creado_por=self.user)
        DetalleRequerimiento.objects.create(requerimiento=req, articulo=self.a, cantidad=4)
        fila = self.saldo(f'D:{self.directa.pk}')
        self.assertEqual((fila['reservado'], fila['disponible']), (4, 6))
        self.assertEqual(self.crear([(self.a, 7, False)], [f'D:{self.directa.pk}']).status_code, 400)

    def test_articulo_inactivo_no_puede_reservarse_ni_se_ofrece_en_api(self):
        self.a.activo = False
        self.a.save()
        response = self.crear([(self.a, 1, False)], [f'D:{self.directa.pk}'])
        self.assertEqual(response.status_code, 400)
        response = self.client.get(reverse('almacen:articulos_asignados', args=[self.dept.pk]))
        self.assertNotIn(self.a.pk, [x['id'] for x in response.json()['articulos']])
        self.assertFalse(SolicitudRequerimiento.objects.exists())


class ReservasConcurrentesTests(TransactionTestCase):
    setUp = preparar
    post = fixtures.SolicitudFilasTests.post

    def reservar_concurrentes(self, key):
        barrier = Barrier(2)
        cookie = self.client.cookies['sessionid'].value
        url = self.url
        data = {'departamento': self.dept.pk, 'tipos_solicitud': 'suministros',
                'detalles-TOTAL_FORMS': '1', 'detalles-INITIAL_FORMS': '0',
                'detalles-0-articulo': self.a.pk, 'detalles-0-cantidad': '7',
                'detalles-0-origen': key}
        def enviar(_):
            close_old_connections()
            try:
                client = Client()
                client.cookies['sessionid'] = cookie
                barrier.wait(timeout=10)
                return client.post(url, data, HTTP_ACCEPT='application/json').status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(enviar, range(2)))
        self.assertEqual(sorted(resultados), [201, 400])
        self.assertEqual(SolicitudRequerimiento.objects.count(), 1)
        fila = next(f for f in fuentes_departamento(self.dept) if f['fuente'] == key)
        self.assertEqual((fila['reservado'], fila['disponible']), (7, 3))

    def test_fuente_de_otro_departamento_no_autorizada(self):
        otro = Departamento.objects.create(id_departamento='OTRO', nombre='Otro')
        asignacion = AsignacionDetalleFactura(articulo=self.a, destino=otro, cantidad_asignada=10)
        AsignacionDetalleFactura.objects.bulk_create([asignacion])
        response = self.post([(self.a, 1, False)], HTTP_ACCEPT='application/json',
                             **{'detalles-0-origen': f'D:{asignacion.pk}'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SolicitudRequerimiento.objects.exists())

    def test_dos_solicitudes_directas_no_reservan_las_mismas_unidades(self):
        self.reservar_concurrentes(f'D:{self.directa.pk}')

    def test_dos_solicitudes_division_no_reservan_las_mismas_unidades(self):
        source = FuentesDisponibilidadTests.division(self, 10)
        self.reservar_concurrentes(f'V:{source.pk}')
