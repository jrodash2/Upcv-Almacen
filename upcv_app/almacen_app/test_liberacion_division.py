"""Liberaciones con PostgreSQL, señales reales y bases temporales; sin ajustes históricos."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from .confirmacion_1h import confirmar_ingreso_form1h
from .disponibilidad import fuentes_departamento, resumen_global_articulo
from .form import AsignacionDetalleFacturaForm
from .liberacion_division import estado_liberacion, liberar_stock_division
from .models import (Articulo, AsignacionDetalleFactura, Categoria, Departamento,
    DetalleFactura, DetalleFacturaDivision, DetalleRequerimiento, DetalleSolicitudRequerimiento,
    DivisionAlmacen, DivisionArticulo, DivisionArticuloUbicacion, DivisionUbicacion,
    Kardex, LiberacionStockDivision, Requerimiento, Serie, SolicitudRequerimiento,
    UsuarioDepartamento, form1h)
from .views import construir_stock_list_administrador


class EscenarioLiberacion:
    def setUp(self):
        self.user = User.objects.create_user(username='admin_liberacion')
        self.user.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        self.client.force_login(self.user)
        self.art = Articulo.objects.create(pk=9876, codigo='675',
            nombre='Medalla 2.5" Dorada de metal incluye cinta',
            renglon_presupuestario='294', categoria=Categoria.objects.create(nombre='Suministro'))
        self.div = DivisionAlmacen.objects.create(nombre='División A')
        self.dept = Departamento.objects.create(id_departamento='LIB', nombre='Destino')
        UsuarioDepartamento.objects.create(usuario=self.user, departamento=self.dept)
        DivisionUbicacion.objects.create(division=self.div, ubicacion=self.dept)
        Serie.objects.create(serie='LIB', numero_inicial=1, numero_final=999, activo=True)
        self.ingreso(100)
        self.da = DivisionArticulo.objects.get(division=self.div, articulo=self.art)
        self.url = reverse('almacen:liberar_stock_division', args=[self.da.pk])
        self.detail = reverse('almacen:division_detail', args=[self.div.pk])

    def ingreso(self, cantidad):
        f = form1h.objects.create(numero_factura=f'LIB-{form1h.objects.count()}')
        d = DetalleFactura.objects.create(form1h=f, articulo=self.art, cantidad=cantidad,
            precio_unitario=Decimal('2'), id_linea=1, renglon=294)
        confirmar_ingreso_form1h(f.pk, [(d.pk, self.div.pk, str(cantidad))], self.user)
        return f, d

    def ubicacion(self, cantidad=30, reserva=0, consumo=0, dept=None):
        dept = dept or self.dept
        DivisionUbicacion.objects.get_or_create(division=self.div, ubicacion=dept)
        u = DivisionArticuloUbicacion.objects.create(division_articulo=self.da, ubicacion=dept,
            cantidad_asignada=cantidad, cantidad_reservada=reserva, cantidad_consumida=consumo)
        if consumo:
            req = Requerimiento.objects.create(departamento=dept, creado_por=self.user,
                estado='parcial' if reserva else 'despachado')
            d = DetalleRequerimiento.objects.create(requerimiento=req, articulo=self.art,
                cantidad=consumo+reserva, cantidad_despachada=consumo,
                estado='parcial' if reserva else 'despachado')
            sol = SolicitudRequerimiento.objects.create(departamento=dept, usuario_solicitante=self.user,
                estado='convertida', requerimiento=req)
            DetalleSolicitudRequerimiento.objects.create(solicitud=sol, articulo=self.art,
                cantidad=consumo+reserva, division_articulo_ubicacion=u, detalle_requerimiento=d)
        elif reserva:
            sol = SolicitudRequerimiento.objects.create(departamento=dept, usuario_solicitante=self.user)
            DetalleSolicitudRequerimiento.objects.create(solicitud=sol, articulo=self.art,
                cantidad=reserva, division_articulo_ubicacion=u)
        return u

    def liberar(self, cantidad, operacion=None):
        return liberar_stock_division(self.da.pk, cantidad, 'Redistribución administrativa', self.user, operacion or uuid4())

    def snapshot(self):
        return {m.__name__: list(m.objects.order_by('pk').values()) for m in [
            DetalleFactura, DetalleFacturaDivision, form1h, Kardex, DivisionArticulo,
            DivisionArticuloUbicacion, DetalleSolicitudRequerimiento, SolicitudRequerimiento,
            DetalleRequerimiento, Requerimiento, AsignacionDetalleFactura]}


class LiberacionDivisionTests(EscenarioLiberacion, TestCase):
    def test_total_conserva_asignacion_original_kardex_ingresos_y_procedencias(self):
        anterior = self.snapshot()
        registro, creado = self.liberar(100)
        self.assertTrue(creado)
        self.assertEqual(self.snapshot(), anterior)
        self.assertEqual(registro.tipo, 'total')
        self.assertEqual((registro.disponible_antes, registro.disponible_despues), (100, 0))
        self.assertEqual(registro.procedencias[0]['distribucion_id'], DetalleFacturaDivision.objects.get().pk)
        self.assertEqual(self.da.total_liberado, 100)
        self.assertEqual(self.da.compromiso_vigente, 0)
        self.assertEqual(resumen_global_articulo(self.art)['existencia_fisica'], 100)
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'], 100)

    def test_parcial_y_liberaciones_sucesivas(self):
        self.liberar(40)
        self.assertEqual(self.da.disponible_division, 60)
        self.liberar(60)
        self.assertEqual(self.da.total_liberado, 100)
        with self.assertRaises(ValidationError):
            self.liberar(1)
        self.assertEqual(LiberacionStockDivision.objects.count(), 2)

    def test_ubicacion_vigente_protege_30_y_permite_70_no_71(self):
        self.ubicacion(30)
        self.assertEqual(estado_liberacion(self.da)['maximo_liberable'], 70)
        with self.assertRaises(ValidationError):
            self.liberar(71)
        self.liberar(70)
        self.assertEqual(self.da.compromiso_vigente, 30)
        self.assertEqual(self.da.disponible_division, 0)

    def test_reserva_pendiente_no_se_libera_ni_se_descontabiliza_dos_veces(self):
        u = self.ubicacion(30, reserva=20)
        anterior = self.snapshot()
        self.assertEqual(estado_liberacion(self.da)['maximo_liberable'], 70)
        self.liberar(70)
        self.assertEqual(self.snapshot(), anterior)
        self.assertEqual(fuentes_departamento(self.dept)[0]['disponible'], 10)
        self.assertEqual(u.cantidad_reservada, 20)

    def test_varias_ubicaciones_incluidas_inactivas(self):
        self.ubicacion(30)
        dept = Departamento.objects.create(id_departamento='OTRA', nombre='Otra ubicación')
        u = self.ubicacion(20, dept=dept)
        u.activo = False
        u.save()
        self.assertEqual(estado_liberacion(self.da)['maximo_liberable'], 50)
        self.liberar(50)
        self.assertEqual(self.da.disponible_division, 0)

    def test_consumo_parcial_y_reserva_se_conservan(self):
        self.ubicacion(30, consumo=10, reserva=10)
        antes = self.snapshot()
        self.assertEqual(estado_liberacion(self.da)['maximo_liberable'], 70)
        self.liberar(70)
        globales = resumen_global_articulo(self.art)
        self.assertEqual(globales['existencia_fisica'], 90)
        self.assertEqual(globales['comprometido_divisiones'], 20)
        self.assertEqual(globales['reservado'], 10)
        self.assertEqual(globales['disponible_para_division'], 70)
        self.assertEqual(self.snapshot(), antes)

    def test_675_1820_menos_620_libera_1200_sin_cambiar_fisico(self):
        self.ingreso(1720)
        self.da.refresh_from_db()
        self.ubicacion(620, consumo=620)
        self.assertEqual(estado_liberacion(self.da)['maximo_liberable'], 1200)
        anterior = self.snapshot()
        self.liberar(1200)
        self.assertEqual(self.snapshot(), anterior)
        self.assertEqual(self.da.cantidad_asignada, 1820)
        self.assertEqual(self.da.compromiso_vigente, 0)
        self.assertEqual(self.da.disponible_division, 0)
        self.assertEqual(resumen_global_articulo(self.art)['existencia_fisica'], 1200)
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'], 1200)

    def test_exceso_global_permite_reducir_sin_modificar_compromisos_directos(self):
        self.ingreso(1720)
        self.da.refresh_from_db()
        self.ubicacion(620, consumo=620)
        AsignacionDetalleFactura.objects.bulk_create([AsignacionDetalleFactura(
            articulo=self.art, destino=self.dept, cantidad_asignada=620)])
        anterior = self.snapshot()
        estado = estado_liberacion(self.da)
        self.assertEqual(estado['maximo_liberable'], 1200)
        self.assertIn('exceso global', estado['advertencia'])
        self.liberar(1200)
        self.assertEqual(self.snapshot(), anterior)
        globales = resumen_global_articulo(self.art)
        self.assertEqual(globales['comprometido_directo'], 620)
        self.assertEqual(globales['disponible_para_division'], 580)

    def test_consumo_duplicado_directo_y_division_no_autoriza_liberacion(self):
        self.ubicacion(30, consumo=30)
        directa = AsignacionDetalleFactura(articulo=self.art, destino=self.dept, cantidad_asignada=30)
        AsignacionDetalleFactura.objects.bulk_create([directa])
        # Fixture histórico inconsistente: el despacho identifica origen directo,
        # pero también permanece contabilizado en el contador de la división.
        DetalleSolicitudRequerimiento.objects.update(
            division_articulo_ubicacion=None, asignacion_directa=directa)
        estado = estado_liberacion(self.da)
        self.assertEqual(estado['maximo_liberable'], 0)
        self.assertIn('más de un origen', estado['motivo'])
        with self.assertRaises(ValidationError):
            self.liberar(70)

    def test_consumo_sin_despacho_o_reserva_sin_contador_bloquean(self):
        u = self.ubicacion(30, reserva=10)
        DivisionArticuloUbicacion.objects.filter(pk=u.pk).update(cantidad_reservada=0)
        self.assertEqual(estado_liberacion(self.da)['maximo_liberable'], 0)
        with self.assertRaises(ValidationError):
            self.liberar(1)
        # Restaurar solo el fixture de prueba para aislar el segundo diagnóstico.
        DivisionArticuloUbicacion.objects.filter(pk=u.pk).update(cantidad_reservada=10, cantidad_consumida=5)
        self.assertIn('sin despachos', estado_liberacion(self.da)['motivo'])

    def test_solicitudes_y_requerimientos_sin_origen_se_reportan(self):
        sol = SolicitudRequerimiento.objects.create(departamento=self.dept, usuario_solicitante=self.user)
        detalle = DetalleSolicitudRequerimiento.objects.create(solicitud=sol, articulo=self.art, cantidad=10)
        self.assertIn('sin origen verificable', estado_liberacion(self.da)['motivo'])
        with self.assertRaises(ValidationError):
            self.liberar(1)
        detalle.delete()  # Solo el fixture temporal para aislar el otro caso.
        req = Requerimiento.objects.create(departamento=self.dept, creado_por=self.user, estado='pendiente')
        DetalleRequerimiento.objects.create(requerimiento=req, articulo=self.art, cantidad=10)
        self.assertEqual(estado_liberacion(self.da)['maximo_liberable'], 0)

    def test_sin_disponibilidad_boton_deshabilitado_y_post_rechazado(self):
        self.ubicacion(100)
        response = self.client.get(self.detail)
        self.assertContains(response, 'disabled>Liberar stock')
        self.assertNotContains(response, 'class="form-liberar-stock"')
        self.assertEqual(self.client.post(self.url, {'cantidad':100, 'justificacion':'Motivo', 'operacion':uuid4()}).status_code, 302)
        self.assertFalse(LiberacionStockDivision.objects.exists())

    def test_reintento_mismo_identificador_es_idempotente(self):
        operacion = uuid4()
        a, creado = self.liberar(40, operacion)
        b, creado = self.liberar(40, operacion)
        self.assertFalse(creado)
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(LiberacionStockDivision.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.liberar(10, operacion)

    def test_validaciones_cantidad_justificacion_e_identificador(self):
        for cantidad in [0, -1, 'NaN', 'Infinity', '1.001', '100000000000', '', 101]:
            with self.subTest(cantidad=cantidad), self.assertRaises(ValidationError):
                self.liberar(cantidad)
        for justificacion, operacion in [(' ',uuid4()),('Motivo','invalido')]:
            with self.assertRaises(ValidationError):
                liberar_stock_division(self.da.pk,1,justificacion,self.user,operacion)
        self.assertFalse(LiberacionStockDivision.objects.exists())

    def test_asignacion_directa_posterior_y_coexistencia(self):
        self.liberar(50)
        form = AsignacionDetalleFacturaForm({'articulo':self.art.pk,'destino':self.dept.pk,'cantidad_asignada':50})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        globales = resumen_global_articulo(self.art)
        self.assertEqual(globales['comprometido_directo'], 50)
        self.assertEqual(globales['comprometido_divisiones'], 50)
        self.assertEqual(globales['existencia_fisica'],100)
        self.assertEqual(globales['disponible_para_division'],0)
        # Aún puede liberar su remanente, sin tocar el compromiso directo.
        self.liberar(50)
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'],50)

    def test_reasignar_a_otra_division_y_reutilizar_la_original(self):
        self.liberar(50)
        otra = DivisionArticulo.objects.create(division=DivisionAlmacen.objects.create(nombre='B'),
            articulo=self.art,cantidad_asignada=30)
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'],20)
        self.da.cantidad_asignada += 20
        self.da.save()
        self.assertEqual(self.da.total_liberado,50)
        self.assertEqual(self.da.compromiso_vigente,70)
        self.assertEqual(otra.compromiso_vigente,30)
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'],0)

    def test_675_liberar_500_otra_division_300_deja_200_generales(self):
        self.ingreso(1720)
        self.da.refresh_from_db()
        self.ubicacion(620, consumo=620)
        self.liberar(500)
        otra = DivisionArticulo.objects.create(division=DivisionAlmacen.objects.create(nombre='División B'),
            articulo=self.art, cantidad_asignada=300)
        self.assertEqual(self.da.compromiso_vigente, 700)
        self.assertEqual(otra.compromiso_vigente, 300)
        globales = resumen_global_articulo(self.art)
        self.assertEqual(globales['existencia_fisica'], 1200)
        self.assertEqual(globales['disponible_para_division'], 200)

    def test_nuevo_1h_despues_de_liberacion_no_restaura_stock_liberado(self):
        self.liberar(100)
        self.ingreso(50)
        self.da.refresh_from_db()
        self.assertEqual(self.da.cantidad_asignada,150)
        self.assertEqual(self.da.total_liberado,100)
        self.assertEqual(self.da.compromiso_vigente,50)
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'],100)

    def test_capacidad_de_ubicacion_no_puede_reutilizar_unidades_liberadas(self):
        self.liberar(70)
        self.ubicacion(30)
        dept = Departamento.objects.create(id_departamento='OTRA',nombre='Otra')
        with self.assertRaises(ValidationError):
            self.ubicacion(1,dept=dept)
        self.assertEqual(estado_liberacion(self.da)['maximo_liberable'],0)

    def test_vistas_y_ajax_concuerdan(self):
        self.liberar(40)
        globales = resumen_global_articulo(self.art)
        stock = construir_stock_list_administrador()[0]
        self.assertEqual(stock['comprometido_divisiones'],60)
        self.assertEqual(stock['liberado_divisiones'],40)
        self.assertEqual(stock['disponible'],40)
        self.assertEqual(stock['existencia_fisica'],100)
        response = self.client.get(reverse('almacen:buscar_articulos'),{'q':'675','asignacion_directa':'1'})
        self.assertEqual(Decimal(response.json()[0]['existencias']['disponible_para_division']),40)
        self.assertEqual(globales['comprometido'],self.da.compromiso_vigente)
        for url in [self.detail,reverse('almacen:division_control'),reverse('almacen:ver_stock_formulario_1h')]:
            response = self.client.get(url)
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'Liberado')
        self.assertContains(self.client.get(self.detail),'Redistribución administrativa')
        control = self.client.get(reverse('almacen:division_control'))
        total = list(control.context['totales_division'])[0]
        self.assertEqual((total['historico'], total['liberado'], total['comprometido'], total['disponible']), (100,40,60,60))

    def test_solicitud_no_puede_usar_unidades_liberadas_de_la_division(self):
        u = self.ubicacion(30)
        self.liberar(70)
        self.user.groups.add(Group.objects.get_or_create(name='Gestor')[0])
        data = {'departamento':self.dept.pk, 'tipos_solicitud':['suministros'],
            'justificacion':'Solicitud de suministros para actividades del departamento.',
            'detalles-TOTAL_FORMS':1, 'detalles-INITIAL_FORMS':0,
            'detalles-MIN_NUM_FORMS':0, 'detalles-MAX_NUM_FORMS':1000,
            'detalles-0-articulo':self.art.pk,'detalles-0-origen':f'V:{u.pk}',
            'detalles-0-cantidad':31}
        url = reverse('almacen:crear_solicitud_requerimiento')
        response = self.client.post(url,data,HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,400)
        self.assertFalse(SolicitudRequerimiento.objects.exists())
        data['detalles-0-cantidad']=30
        response = self.client.post(url,data,HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,201)
        u.refresh_from_db()
        self.assertEqual(u.cantidad_reservada,30)
        self.assertEqual(self.da.total_liberado,70)
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'],70)

    def test_permisos_post_csrf_y_solo_lectura(self):
        self.assertEqual(self.client.get(self.url).status_code,405)
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.url,{}).status_code,403)
        self.user.groups.clear()
        self.user.groups.add(Group.objects.get_or_create(name='Almacen')[0])
        self.assertNotContains(self.client.get(self.detail),'class="form-liberar-stock"')
        self.assertEqual(self.client.post(self.url,{}).status_code,302)
        with self.assertRaises(PermissionDenied):
            self.liberar(1)
        self.assertFalse(LiberacionStockDivision.objects.exists())
        self.user.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        registro,_=self.liberar(1)
        with self.assertRaises(ValidationError):
            registro.save()
        with self.assertRaises(ValidationError):
            registro.delete()
        with self.assertRaises(ProtectedError):
            self.da.delete()

    def test_rollback_incluye_bitacora_si_falla_validacion_final(self):
        from . import liberacion_division as servicio
        original = servicio.resumen_global_articulo
        calls = [0]
        def fallo(articulo):
            calls[0] += 1
            result = original(articulo)
            if calls[0] == 2:
                result['existencia_fisica'] += 1
            return result
        anterior = self.snapshot()
        with patch.object(servicio,'resumen_global_articulo',side_effect=fallo):
            with self.assertRaises(ValidationError):
                self.liberar(40)
        self.assertFalse(LiberacionStockDivision.objects.exists())
        self.assertEqual(self.snapshot(),anterior)


class LiberacionConcurrenciaTests(EscenarioLiberacion, TransactionTestCase):
    def test_dos_administradores_no_liberan_las_mismas_unidades(self):
        barrera = Barrier(2)
        admin2=User.objects.create_user(username='admin2')
        admin2.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        def ejecutar(user):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                try:
                    liberar_stock_division(self.da.pk,70,'Concurrente',user,uuid4())
                    return 'ok'
                except ValidationError:
                    return 'saldo'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados=list(executor.map(ejecutar,[self.user,admin2]))
        self.assertCountEqual(resultados,['ok','saldo'])
        self.assertEqual(self.da.total_liberado,70)
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'],70)

    def test_dos_envios_mismo_identificador_no_duplican_bitacora(self):
        barrera = Barrier(2)
        operacion = uuid4()
        def ejecutar(_):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return liberar_stock_division(self.da.pk,70,'Concurrente',self.user,operacion)[1]
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(ejecutar,range(2)))
        self.assertCountEqual(resultados,[True,False])
        self.assertEqual(LiberacionStockDivision.objects.count(),1)
        self.assertEqual(self.da.total_liberado,70)

    def test_liberacion_y_autoasignacion_no_sobrecomprometen(self):
        gestor=User.objects.create_user(username='gestor_liberacion')
        gestor.groups.add(Group.objects.get_or_create(name='Gestor')[0])
        UsuarioDepartamento.objects.create(usuario=gestor,departamento=self.dept)
        barrera=Barrier(2)
        def ejecutar(accion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                if accion=='liberar':
                    try:
                        self.liberar(70)
                    except ValidationError:
                        pass
                else:
                    client=Client();client.force_login(gestor)
                    response=client.post(reverse('almacen:autoasignar_division_articulo',args=[self.da.pk]),{'cantidad':70})
                    self.assertEqual(response.status_code,302)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(ejecutar,['liberar','asignar']))
        distribuido=self.da.total_asignado_ubicaciones
        self.assertEqual(self.da.total_liberado+distribuido,70)
        self.assertGreaterEqual(self.da.disponible_division,0)
