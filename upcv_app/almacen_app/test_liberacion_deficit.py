"""Regresión con los saldos de la auditoría IIS de 675, sin tocar producción."""
from django.core.exceptions import ValidationError
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .disponibilidad import resumen_global_articulo
from .form import AsignacionDetalleFacturaForm
from .liberacion_division import estado_liberacion
from .models import (AsignacionDetalleFactura, DetalleRequerimiento,
    DetalleSolicitudRequerimiento, SolicitudRequerimiento, Requerimiento,
    LiberacionStockDivision)
from .test_liberacion_division import EscenarioLiberacion
from .views import construir_stock_list_administrador


class EscenarioDeficit(EscenarioLiberacion):
    def setUp(self):
        EscenarioLiberacion.setUp(self)
        self.ingreso(1720)
        self.da.refresh_from_db()
        self.u = self.ubicacion(620)
        self.directa = AsignacionDetalleFactura.objects.create(articulo=self.art,
            destino=self.dept, cantidad_asignada=620)
        req = Requerimiento.objects.create(departamento=self.dept,
            creado_por=self.user, estado='despachado')
        det = DetalleRequerimiento.objects.create(requerimiento=req, articulo=self.art,
            cantidad=620, cantidad_despachada=620, estado='despachado')
        sol = SolicitudRequerimiento.objects.create(departamento=self.dept,
            usuario_solicitante=self.user, estado='convertida', requerimiento=req)
        DetalleSolicitudRequerimiento.objects.create(solicitud=sol, articulo=self.art,
            cantidad=620, asignacion_directa=self.directa, detalle_requerimiento=det)


class LiberacionDeficitTests(EscenarioDeficit, TestCase):
    def test_exceso_global_no_bloquea_reducir_compromiso_no_distribuido(self):
        antes = resumen_global_articulo(self.art)
        self.assertEqual(antes['existencia_fisica'], 1200)
        self.assertEqual(antes['comprometido_divisiones'], 1820)
        self.assertEqual(antes['comprometido_directo'], 0)
        self.assertEqual(antes['saldo_sin_asignar'], -620)
        estado = estado_liberacion(self.da)
        self.assertEqual(estado['maximo_liberable'], 1200)
        self.assertIn('620', estado['advertencia'])
        self.assertEqual(estado['disponible_general_al_liberar_maximo'], 580)

    def test_liberar_1200_preserva_620_ubicacion_y_habilita_580_directos(self):
        snapshot = self.snapshot()
        registro, creado = self.liberar(1200)
        self.assertTrue(creado)
        self.assertEqual(registro.cantidad, 1200)
        self.assertEqual(self.snapshot(), snapshot)
        despues = resumen_global_articulo(self.art)
        self.assertEqual(despues['existencia_fisica'], 1200)
        self.assertEqual(despues['liberado_divisiones'], 1200)
        self.assertEqual(despues['comprometido_divisiones'], 620)
        self.assertEqual(despues['disponible_para_division'], 580)
        self.assertFalse(despues['requiere_revision'])
        fila = construir_stock_list_administrador()[0]
        self.assertEqual(fila['divisiones'], 'División A (620)')
        self.assertEqual(fila['disponible'], 580)
        item = self.client.get(reverse('almacen:buscar_articulos'),
            {'q':'675','asignacion_directa':'1'}).json()[0]
        self.assertEqual(float(item['existencias']['disponible_para_division']), 580)
        data = {'articulo':self.art.pk,'destino':self.dept.pk,'cantidad_asignada':581}
        self.assertFalse(AsignacionDetalleFacturaForm(data).is_valid())
        data['cantidad_asignada']=580
        form=AsignacionDetalleFacturaForm(data)
        self.assertTrue(form.is_valid(),form.errors)
        form.save()
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'],0)
        self.u.refresh_from_db()
        self.assertEqual(self.u.cantidad_asignada,620)
        self.assertEqual(self.u.cantidad_reservada,0)
        self.assertEqual(self.u.cantidad_consumida,0)

    def test_liberacion_parcial_reduce_deficit_sin_habilitar_saldo_ficticio(self):
        self.liberar(500)
        parcial=resumen_global_articulo(self.art)
        self.assertEqual(parcial['saldo_sin_asignar'],-120)
        self.assertEqual(parcial['disponible_para_division'],0)
        self.assertTrue(parcial['requiere_revision'])
        self.assertEqual(estado_liberacion(self.da)['maximo_liberable'],700)
        self.liberar(700)
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'],580)
        self.assertEqual(LiberacionStockDivision.objects.count(),2)

    def test_no_puede_liberar_las_620_comprometidas_a_ubicacion(self):
        self.liberar(1200)
        with self.assertRaises(ValidationError):
            self.liberar(1)
        self.assertEqual(self.da.total_liberado,1200)

    def test_liberacion_no_supera_fisico_y_audita_el_presupuesto_local(self):
        # Fixture de exceso histórico mayor que la existencia física.
        type(self.da).objects.filter(pk=self.da.pk).update(cantidad_asignada=3000)
        self.da.refresh_from_db()
        estado=estado_liberacion(self.da)
        self.assertEqual(estado['disponible_division'],2380)
        self.assertEqual(estado['maximo_liberable'],1200)
        with self.assertRaises(ValidationError):
            self.liberar(1201)
        registro,_=self.liberar(1200)
        self.assertEqual((registro.disponible_antes,registro.disponible_despues),(2380,1180))
        self.assertEqual(registro.tipo,'parcial')
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'],0)

    def test_mensaje_de_exito_informa_saldo_real_y_no_promete_1200_disponibles(self):
        from uuid import uuid4
        response=self.client.post(self.url,{'cantidad':1200,'justificacion':'Liberación solicitada',
            'operacion':uuid4()},follow=True)
        self.assertContains(response,'Se liberaron 1,200 unidades.')
        self.assertContains(response,'Disponible general para nuevas asignaciones: 580.')
        self.assertContains(response,'Compromiso vigente en divisiones: 620.')
        self.assertEqual(self.da.total_liberado,1200)

    def test_retirar_todo_exige_devolver_ubicacion_y_liberar_remanente_explicitamente(self):
        self.liberar(1200)
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'],580)
        response=self.client.post(reverse('almacen:desasignar_articulo_ubicacion',args=[self.u.pk]),
            {'cantidad_desasignar':620})
        self.assertEqual(response.status_code,302)
        self.u.refresh_from_db()
        self.assertEqual(self.u.cantidad_asignada,0)
        self.assertFalse(self.u.activo)
        # La desasignación devuelve cobertura a la división, no al almacén.
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'],580)
        self.liberar(620)
        resumen=resumen_global_articulo(self.art)
        self.assertEqual(resumen['existencia_fisica'],1200)
        self.assertEqual(resumen['comprometido_divisiones'],0)
        self.assertEqual(resumen['disponible_para_division'],1200)
        self.assertEqual(LiberacionStockDivision.objects.count(),2)
        self.da.refresh_from_db()
        self.assertEqual(self.da.cantidad_asignada,1820)
        self.directa.refresh_from_db()
        self.assertEqual(self.directa.cantidad_asignada,620)

    def test_reserva_sin_origen_verificable_sigue_bloqueando(self):
        sol=SolicitudRequerimiento.objects.create(departamento=self.dept,usuario_solicitante=self.user)
        DetalleSolicitudRequerimiento.objects.create(solicitud=sol,articulo=self.art,cantidad=1)
        self.assertEqual(estado_liberacion(self.da)['maximo_liberable'],0)
        with self.assertRaises(ValidationError):
            self.liberar(1200)
        self.assertEqual(self.da.total_liberado,0)


class LiberacionDeficitConcurrenciaTests(EscenarioDeficit, TransactionTestCase):
    def test_dos_liberaciones_sobre_deficit_respetan_cobertura_de_ubicacion(self):
        barrera=Barrier(2)
        def liberar(_):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                try:
                    self.liberar(700)
                    return 'registrada'
                except ValidationError:
                    return 'rechazada'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados=list(executor.map(liberar,range(2)))
        self.assertCountEqual(resultados,['registrada','rechazada'])
        self.assertEqual(self.da.total_liberado,700)
        self.assertEqual(self.da.disponible_division,500)
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'],80)
        self.u.refresh_from_db()
        self.assertEqual(self.u.cantidad_asignada,620)
