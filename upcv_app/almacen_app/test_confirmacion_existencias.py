"""Regresiones con PostgreSQL y señales reales; ningún ajuste de inventario."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from io import StringIO
import json
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import close_old_connections, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from .disponibilidad import compromisos_articulo, fuentes_departamento, resumen_global_articulo
from .models import (Articulo, AsignacionDetalleFactura, Departamento, DetalleFactura,
    DetalleFacturaDivision, DetalleRequerimiento, DetalleSolicitudRequerimiento,
    DivisionAlmacen, DivisionArticulo, DivisionArticuloUbicacion, DivisionUbicacion,
    Kardex, Requerimiento, Serie, SolicitudRequerimiento, form1h, existencia_general_articulo)


class Escenario:
    def setUp(self):
        self.user = User.objects.create_user(username='confirmador')
        self.user.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        self.a = Articulo.objects.create(pk=675, codigo='675', nombre='Artículo 675')
        self.div = DivisionAlmacen.objects.create(nombre='División 3')
        self.dept = Departamento.objects.create(id_departamento='TEST', nombre='Departamento')
        DivisionUbicacion.objects.create(division=self.div, ubicacion=self.dept)
        Serie.objects.create(serie='T', numero_inicial=1, numero_final=100, activo=True)
        self.client.force_login(self.user)

    def ingreso(self, cantidad, estado='borrador'):
        form = form1h.objects.create(numero_factura=f'F-{form1h.objects.count()}', estado=estado)
        det = DetalleFactura.objects.create(form1h=form, articulo=self.a, cantidad=cantidad,
            precio_unitario=Decimal('2'), precio_total=Decimal(cantidad * 2), id_linea=1, renglon=243)
        return form, det

    def confirmar(self, form, det, distribucion=None, client=None):
        distribucion = distribucion or [(self.div, det.cantidad)]
        return (client or self.client).post(reverse('almacen:confirmar_form1h', args=[form.pk]), {
            'detalle_id': [str(det.pk)] * len(distribucion),
            'division_id': [str(d.pk) for d, _ in distribucion],
            'cantidad_asignada': [str(q) for _, q in distribucion]})

    def historico(self, consumido=620, reservado=0):
        form, det = self.ingreso(620, 'confirmado')
        da = DivisionArticulo.objects.create(division=self.div, articulo=self.a, cantidad_asignada=620)
        ubicacion = DivisionArticuloUbicacion.objects.create(division_articulo=da, ubicacion=self.dept,
            cantidad_asignada=620, cantidad_consumida=consumido, cantidad_reservada=reservado)
        req = Requerimiento.objects.create(departamento=self.dept, creado_por=self.user,
            estado='despachado' if consumido == 620 else 'parcial')
        detalle = DetalleRequerimiento.objects.create(requerimiento=req, articulo=self.a,
            cantidad=620, cantidad_despachada=consumido,
            estado='despachado' if consumido == 620 else 'parcial')
        # La señal solo registra el despacho al completarlo; esta prueba también
        # conserva el parcial sin fabricar un Kardex.
        sol = SolicitudRequerimiento.objects.create(departamento=self.dept, usuario_solicitante=self.user,
            estado='convertida', requerimiento=req)
        DetalleSolicitudRequerimiento.objects.create(solicitud=sol, articulo=self.a, cantidad=620,
            division_articulo_ubicacion=ubicacion, detalle_requerimiento=detalle)
        return da, ubicacion


class ConfirmacionExistenciasTests(Escenario, TestCase):
    def test_primer_y_segundo_ingreso_y_doble_confirmacion(self):
        for cantidad in [620, 1200]:
            form, det = self.ingreso(cantidad)
            before = Kardex.objects.count()
            self.assertEqual(self.confirmar(form, det).status_code, 302)
            self.confirmar(form, det)
            form.refresh_from_db()
            self.assertEqual(form.estado, 'confirmado')
            self.assertEqual(Kardex.objects.count(), before)
            self.assertEqual(det.asignaciones_division.count(), 1)
        self.assertEqual(DivisionArticulo.objects.get().cantidad_asignada, 1820)
        self.assertEqual(existencia_general_articulo(self.a), 1820)

    def test_620_consumidas_nuevo_ingreso_1200_no_resucita_consumos(self):
        da, source = self.historico()
        self.assertEqual(existencia_general_articulo(self.a), 0)
        self.assertEqual(source.disponible_ubicacion, 0)
        form, det = self.ingreso(1200)
        movimiento = Kardex.objects.get(fuente_factura=det)
        self.assertEqual(movimiento.cantidad, 1200)
        self.assertEqual(existencia_general_articulo(self.a), 0)
        self.confirmar(form, det)
        form.refresh_from_db(); da.refresh_from_db(); source.refresh_from_db()
        self.assertEqual(form.estado, 'confirmado')
        self.assertEqual(da.cantidad_asignada, 1820)
        self.assertEqual(source.cantidad_consumida, 620)
        self.assertEqual(source.disponible_ubicacion, 0)
        self.assertEqual(da.disponible_division, 1200)
        self.assertEqual(da.disponible_para_solicitud, 1200)
        self.assertEqual(existencia_general_articulo(self.a), 1200)
        self.assertEqual(compromisos_articulo(self.a)['comprometido'], 1200)
        self.assertEqual(Kardex.objects.filter(fuente_factura=det).count(), 1)
        self.assertEqual(resumen_global_articulo(self.a)['disponible_para_division'], 0)
        self.assertEqual(fuentes_departamento(self.dept)[0]['disponible'], 0)

    def test_parcial_y_reservas_siguen_comprometidos(self):
        da, source = self.historico(200, 420)
        self.assertEqual(existencia_general_articulo(self.a), 420)
        form, det = self.ingreso(1200)
        self.confirmar(form, det)
        da.refresh_from_db(); source.refresh_from_db()
        self.assertEqual(existencia_general_articulo(self.a), 1620)
        self.assertEqual(compromisos_articulo(self.a)['comprometido'], 1620)
        self.assertEqual(source.cantidad_reservada, 420)
        self.assertEqual(da.disponible_para_solicitud, 1200)
        da.cantidad_asignada += 1
        with self.assertRaises(ValidationError):
            da.save()

    def test_completar_parcial_no_descontar_dos_veces(self):
        da, source = self.historico(200, 420)
        form, det = self.ingreso(1200)
        self.confirmar(form, det)
        req = Requerimiento.objects.get()
        req.estado = 'enviado'; req.save()
        detalle = req.detalles.get()
        self.client.post(reverse('almacen:despachar_requerimiento', args=[req.pk]),
                         {f'cantidades[{detalle.pk}]': 620})
        detalle.refresh_from_db(); source.refresh_from_db()
        self.assertEqual(detalle.cantidad_despachada, 620)
        self.assertEqual(source.cantidad_consumida, 620)
        self.assertEqual(source.cantidad_reservada, 0)
        self.assertEqual(existencia_general_articulo(self.a), 1200)
        self.assertEqual(compromisos_articulo(self.a)['comprometido'], 1200)

    def test_desactivar_ubicacion_no_libera_su_consumo(self):
        da, source = self.historico()
        source.activo = False
        source.save()
        otro = Departamento.objects.create(id_departamento='OTRO', nombre='Otro')
        DivisionUbicacion.objects.create(division=self.div, ubicacion=otro)
        with self.assertRaises(ValidationError):
            DivisionArticuloUbicacion.objects.create(division_articulo=da, ubicacion=otro, cantidad_asignada=1)
        self.assertEqual(da.disponible_division, 0)

    def test_varias_divisiones_y_distribucion_exacta(self):
        segunda = DivisionAlmacen.objects.create(nombre='Segunda')
        form, det = self.ingreso(1200)
        self.confirmar(form, det, [(self.div, 500), (segunda, 699)])
        self.assertFalse(DetalleFacturaDivision.objects.exists())
        form.refresh_from_db(); self.assertEqual(form.estado, 'borrador')
        self.confirmar(form, det, [(self.div, 500), (segunda, 700)])
        self.assertEqual(list(DivisionArticulo.objects.order_by('division_id').values_list('cantidad_asignada', flat=True)), [500, 700])

    def test_consumo_sin_origen_no_libera_division_y_rollback(self):
        da, source = self.historico()
        # Historia inconsistente: la salida existe pero el contador de origen no
        # acredita consumo. No atribuirle una salida por coincidir la cantidad.
        DivisionArticuloUbicacion.objects.filter(pk=source.pk).update(cantidad_consumida=0)
        form, det = self.ingreso(1200)
        self.confirmar(form, det)
        form.refresh_from_db(); da.refresh_from_db()
        self.assertEqual(form.estado, 'borrador')
        self.assertEqual(da.cantidad_asignada, 620)
        self.assertFalse(det.asignaciones_division.exists())
        self.assertEqual(Kardex.objects.count(), 3)

    def test_directo_y_division_no_comparten_presupuesto(self):
        self.ingreso(100, 'confirmado')
        AsignacionDetalleFactura.objects.bulk_create([AsignacionDetalleFactura(
            articulo=self.a, destino=self.dept, cantidad_asignada=40)])
        DivisionArticulo.objects.create(division=self.div, articulo=self.a, cantidad_asignada=60)
        segunda = DivisionAlmacen.objects.create(nombre='Segunda')
        with self.assertRaises(ValidationError):
            DivisionArticulo.objects.create(division=segunda, articulo=self.a, cantidad_asignada=1)

    def test_kardex_y_libro_mayor_excluyen_borrador(self):
        from .views import _procesar_movimientos_kardex, _calcular_movimientos_valorizados
        form, det = self.ingreso(1200)
        self.assertEqual(_procesar_movimientos_kardex(self.a)[1]['total_ingresos'], 0)
        self.assertEqual(_calcular_movimientos_valorizados(self.a, None)['entradas_cantidad'], 0)
        self.confirmar(form, det)
        self.assertEqual(_procesar_movimientos_kardex(self.a)[1]['total_ingresos'], 1200)
        self.assertEqual(_calcular_movimientos_valorizados(self.a, None)['entradas_cantidad'], 1200)

    def test_stock_y_formulario_directo_respetan_divisiones(self):
        from .form import AsignacionDetalleFacturaForm
        from .views import construir_stock_list_administrador
        form, det = self.ingreso(100)
        self.confirmar(form, det)
        self.assertNotIn(self.a, AsignacionDetalleFacturaForm().fields['articulo'].queryset)
        fila = next(f for f in construir_stock_list_administrador() if f['articulo_id'] == self.a.pk)
        self.assertEqual(fila['disponible'], 0)

    def test_ingreso_duplicado_no_se_confirma_ni_repara(self):
        form, det = self.ingreso(1200)
        Kardex.objects.create(articulo=self.a, tipo_movimiento='INGRESO', cantidad=1200, fuente_factura=det)
        self.confirmar(form, det)
        form.refresh_from_db(); self.assertEqual(form.estado, 'borrador')
        self.assertEqual(Kardex.objects.count(), 2)
        self.assertFalse(DetalleFacturaDivision.objects.exists())

    def test_reversion_salida_no_se_resta_dos_veces(self):
        self.ingreso(100, 'confirmado')
        salida = Kardex.objects.create(articulo=self.a, tipo_movimiento='SALIDA', cantidad=40)
        Kardex.objects.create(articulo=self.a, tipo_movimiento='INGRESO', cantidad=40,
            estado='reversion', movimiento_revertido=salida)
        self.assertEqual(existencia_general_articulo(self.a), 100)

    def test_fallo_en_segunda_asignacion_revierte_todo(self):
        segunda = DivisionAlmacen.objects.create(nombre='Segunda')
        form, det = self.ingreso(1200)
        original = DivisionArticulo.clean
        def validar(instance):
            if instance.division_id == segunda.pk:
                raise ValidationError('Fallo deliberado')
            original(instance)
        with patch.object(DivisionArticulo, 'clean', validar):
            self.confirmar(form, det, [(self.div, 500), (segunda, 700)])
        form.refresh_from_db(); self.assertEqual(form.estado, 'borrador')
        self.assertFalse(DivisionArticulo.objects.exists())
        self.assertFalse(DetalleFacturaDivision.objects.exists())


class ConfirmacionConcurrenteTests(Escenario, TransactionTestCase):
    def test_diagnostico_solo_lectura(self):
        form, det = self.ingreso(1200)
        salida = StringIO()
        call_command('auditar_articulo_1h', articulo=675, stdout=salida)
        datos = json.loads(salida.getvalue())
        self.assertEqual(datos['kardex'][-1]['fuente_factura__form1h_id'], form.pk)
        self.assertEqual(datos['kardex'][-1]['fuente_factura__form1h__estado'], 'borrador')
        self.assertEqual(existencia_general_articulo(self.a), 0)

    def paralelo(self, trabajos):
        barrera = Barrier(2)
        def ejecutar(trabajo):
            close_old_connections()
            try:
                client = Client(); client.force_login(self.user)
                barrera.wait(timeout=15)
                return trabajo(client)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(ejecutar, trabajos))

    def test_dos_confirmaciones_del_mismo_documento(self):
        form, det = self.ingreso(1200)
        self.paralelo([lambda c: self.confirmar(form, det, client=c)] * 2)
        self.assertEqual(DetalleFacturaDivision.objects.count(), 1)
        self.assertEqual(DivisionArticulo.objects.get().cantidad_asignada, 1200)
        self.assertEqual(Kardex.objects.count(), 1)

    def test_dos_ingresos_del_mismo_articulo(self):
        f1, d1 = self.ingreso(620); f2, d2 = self.ingreso(1200)
        self.paralelo([lambda c: self.confirmar(f1, d1, client=c), lambda c: self.confirmar(f2, d2, client=c)])
        self.assertEqual(DetalleFacturaDivision.objects.count(), 2)
        self.assertEqual(DivisionArticulo.objects.get().cantidad_asignada, 1820)
        self.assertEqual(existencia_general_articulo(self.a), 1820)

    def test_sobreasignaciones_concurrentes(self):
        self.ingreso(100, 'confirmado')
        segunda = DivisionAlmacen.objects.create(nombre='Segunda')
        def asignar(division):
            try:
                DivisionArticulo.objects.create(division=division, articulo=self.a, cantidad_asignada=80)
                return True
            except ValidationError:
                return False
        resultados = self.paralelo([lambda c: asignar(self.div), lambda c: asignar(segunda)])
        self.assertEqual(sorted(resultados), [False, True])
        self.assertEqual(DivisionArticulo.objects.get().cantidad_asignada, 80)
