"""Cruce temporal y de orígenes del reporte completo de IIS, no solo sus totales."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth.models import Group,User
from django.core.exceptions import ValidationError
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections
from django.test import Client,TestCase,TransactionTestCase
from django.urls import reverse

from .consumo_historico_division import reconocimientos_consumo,TIPO
from .disponibilidad import fuentes_departamento,resumen_global_articulo
from .form import AsignacionDetalleFacturaForm
from .liberacion_division import estado_liberacion
from .models import (Articulo,Categoria,Departamento,DivisionAlmacen,DivisionArticulo,
    DivisionUbicacion,DivisionArticuloUbicacion,AsignacionDetalleFactura,UsuarioDepartamento,
    Serie,Requerimiento,DetalleRequerimiento,SolicitudRequerimiento,DetalleSolicitudRequerimiento,
    Kardex,LiberacionStockDivision)
from .test_liberacion_division import EscenarioLiberacion
from .views import construir_stock_list_administrador


class EscenarioEspejo(EscenarioLiberacion):
    def setUp(self):
        self.user=User.objects.create_user(username='admin_espejo')
        self.user.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        self.client.force_login(self.user)
        self.art=Articulo.objects.create(pk=9876,codigo='675',nombre='Medalla 2.5" Dorada de metal incluye cinta',
            categoria=Categoria.objects.create(nombre='Suministro'),renglon_presupuestario='294')
        self.div=DivisionAlmacen.objects.create(nombre='División histórica')
        self.dept=Departamento.objects.create(id_departamento='ESCUELAS',nombre='Sección de Escuelas Seguras')
        UsuarioDepartamento.objects.create(usuario=self.user,departamento=self.dept)
        DivisionUbicacion.objects.create(division=self.div,ubicacion=self.dept)
        Serie.objects.create(serie='H',numero_inicial=1,numero_final=999,activo=True)
        self.primer_form,self.primer_det=self.ingreso(620)
        self.da=DivisionArticulo.objects.get(articulo=self.art,division=self.div)
        self.directa=AsignacionDetalleFactura.objects.create(articulo=self.art,destino=self.dept,cantidad_asignada=620)
        self.u=self.ubicacion(620)
        self.req=Requerimiento.objects.create(departamento=self.dept,creado_por=self.user,estado='despachado')
        self.despacho=DetalleRequerimiento.objects.create(requerimiento=self.req,articulo=self.art,
            cantidad=620,cantidad_despachada=620,estado='despachado')
        sol=SolicitudRequerimiento.objects.create(departamento=self.dept,usuario_solicitante=self.user,
            estado='convertida',requerimiento=self.req)
        self.origen=DetalleSolicitudRequerimiento.objects.create(solicitud=sol,articulo=self.art,cantidad=620,
            asignacion_directa=self.directa,detalle_requerimiento=self.despacho)
        self.salida=Kardex.objects.get(fuente_despacho=self.despacho)
        self.segundo_form,self.segundo_det=self.ingreso(1200)
        self.da.refresh_from_db()
        self.url=reverse('almacen:liberar_stock_division',args=[self.da.pk])
        self.detail=reverse('almacen:division_detail',args=[self.div.pk])


class ConsumoHistoricoDivisionTests(EscenarioEspejo,TestCase):
    def test_reconoce_620_sin_escribir_contadores_ni_duplicar_salida(self):
        antes=self.snapshot()
        evidencia=reconocimientos_consumo(self.art.pk)
        self.assertEqual(len(evidencia),1)
        self.assertEqual(evidencia[0]['kardex_salida_id'],self.salida.pk)
        self.assertEqual(Decimal(evidencia[0]['consumo_extra']),620)
        self.assertEqual(self.u.cantidad_consumida,0)
        self.assertEqual(self.u.cantidad_consumida_efectiva,620)
        self.assertEqual(self.u.disponible_ubicacion,0)
        self.assertEqual(self.da.total_consumido,620)
        self.assertEqual(self.da.compromiso_vigente,1200)
        resumen=resumen_global_articulo(self.art)
        self.assertEqual(resumen['existencia_fisica'],1200)
        self.assertEqual(resumen['comprometido_directo'],0)
        self.assertEqual(resumen['comprometido_divisiones'],1200)
        self.assertEqual(resumen['consumido'],620)
        self.assertEqual(resumen['consumo_historico_compartido'],620)
        self.assertFalse(resumen['requiere_revision'])
        self.assertEqual(self.snapshot(),antes)

    def test_liberar_1200_deja_1200_asignables_y_traza_el_kardex_original(self):
        antes=self.snapshot()
        self.assertEqual(estado_liberacion(self.da)['consumido'],620)
        registro,_=self.liberar(1200)
        self.assertEqual(self.snapshot(),antes)
        self.assertTrue(any(d.get('tipo')==TIPO and d['kardex_salida_id']==self.salida.pk for d in registro.procedencias))
        resumen=resumen_global_articulo(self.art)
        self.assertEqual(resumen['comprometido_divisiones'],0)
        self.assertEqual(resumen['consumido'],620)
        self.assertEqual(resumen['disponible_para_division'],1200)
        fila=construir_stock_list_administrador()[0]
        self.assertEqual(fila['comprometido_divisiones'],0)
        self.assertEqual(fila['consumido_total'],620)
        self.assertEqual(fila['disponible'],1200)
        self.assertEqual(fila['divisiones'],'Sin compromiso vigente')
        form=AsignacionDetalleFacturaForm({'articulo':self.art.pk,'destino':self.dept.pk,'cantidad_asignada':1200})
        self.assertTrue(form.is_valid(),form.errors)
        form.save()
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'],0)
        self.assertEqual(Kardex.objects.filter(tipo_movimiento='SALIDA').count(),1)

    def test_no_permite_desasignar_ni_solicitar_las_620_ya_despachadas(self):
        fuentes=fuentes_departamento(self.dept)
        division=next(f for f in fuentes if f['origen']=='División')
        self.assertEqual(division['consumido'],620)
        self.assertEqual(division['disponible'],0)
        response=self.client.post(reverse('almacen:desasignar_articulo_ubicacion',args=[self.u.pk]),{'cantidad_desasignar':620})
        self.assertEqual(response.status_code,302)
        self.u.refresh_from_db()
        self.assertEqual(self.u.cantidad_asignada,620)
        self.u.cantidad_reservada=1
        with self.assertRaises(ValidationError):
            self.u.full_clean()

    def test_no_atribuye_consumo_a_otra_ubicacion_o_fecha_posterior(self):
        DivisionArticuloUbicacion.objects.filter(pk=self.u.pk).update(fecha_asignacion=self.salida.fecha+timedelta(seconds=1))
        self.assertEqual(reconocimientos_consumo(self.art.pk),[])
        DivisionArticuloUbicacion.objects.filter(pk=self.u.pk).update(fecha_asignacion=self.directa.fecha_asignacion)
        otro=Departamento.objects.create(id_departamento='DISTINTO',nombre='Otro departamento')
        DivisionArticuloUbicacion.objects.filter(pk=self.u.pk).update(ubicacion=otro)
        self.assertEqual(reconocimientos_consumo(self.art.pk),[])

    def test_salida_ausente_incompleta_o_revertida_no_se_utiliza(self):
        for cambios in [{'cantidad':619},{'estado':'revertido'},{'tipo_movimiento':'INGRESO'}]:
            with self.subTest(cambios=cambios):
                Kardex.objects.filter(pk=self.salida.pk).update(**cambios)
                self.assertEqual(reconocimientos_consumo(self.art.pk),[])
                Kardex.objects.filter(pk=self.salida.pk).update(cantidad=620,estado='activo',tipo_movimiento='SALIDA')

    def test_no_elige_entre_dos_ubicaciones_posibles(self):
        otra=DivisionAlmacen.objects.create(nombre='Otra división')
        # Mismo ingreso repartido a dos divisiones: no es una procedencia exclusiva.
        from .models import DetalleFacturaDivision
        nueva=DivisionArticulo(division=otra,articulo=self.art,cantidad_asignada=620)
        DivisionArticulo.objects.bulk_create([nueva])
        DivisionUbicacion.objects.create(division=otra,ubicacion=self.dept)
        u=DivisionArticuloUbicacion(division_articulo=nueva,ubicacion=self.dept,cantidad_asignada=620)
        DivisionArticuloUbicacion.objects.bulk_create([u])
        DetalleFacturaDivision.objects.create(detalle_factura=self.primer_det,division=otra,cantidad_asignada=620)
        self.assertEqual(reconocimientos_consumo(self.art.pk),[])

    def test_nuevo_ingreso_y_nuevo_consumo_no_resucitan_el_historico(self):
        self.liberar(1200)
        self.ingreso(100)
        self.da.refresh_from_db()
        self.u.cantidad_asignada+=100
        self.u.save()
        self.assertEqual(self.u.disponible_ubicacion,100)
        # Consumo posterior real en origen de división: el contador solo guarda el nuevo.
        req=Requerimiento.objects.create(departamento=self.dept,creado_por=self.user,estado='despachado')
        detalle=DetalleRequerimiento.objects.create(requerimiento=req,articulo=self.art,
            cantidad=30,cantidad_despachada=30,estado='despachado')
        sol=SolicitudRequerimiento.objects.create(departamento=self.dept,usuario_solicitante=self.user,
            estado='convertida',requerimiento=req)
        DetalleSolicitudRequerimiento.objects.create(solicitud=sol,articulo=self.art,cantidad=30,
            division_articulo_ubicacion=self.u,detalle_requerimiento=detalle)
        self.u.cantidad_consumida=30
        self.u.save()
        self.assertEqual(self.u.cantidad_consumida_efectiva,650)
        self.assertEqual(self.u.disponible_ubicacion,70)
        self.assertEqual(self.da.total_consumido,650)
        self.assertEqual(len(reconocimientos_consumo(self.art.pk)),1)
        self.assertEqual(resumen_global_articulo(self.art)['consumido'],650)

    def test_sin_prueba_del_ingreso_exclusivo_no_infere_consumo(self):
        from .models import DetalleFacturaDivision
        DetalleFacturaDivision.objects.filter(detalle_factura=self.primer_det).delete()
        self.assertEqual(reconocimientos_consumo(self.art.pk),[])
        self.assertTrue(resumen_global_articulo(self.art)['requiere_revision'])

    def test_consumo_ya_registrado_no_se_suma_otra_vez(self):
        DivisionArticuloUbicacion.objects.filter(pk=self.u.pk).update(cantidad_consumida=620)
        self.u.refresh_from_db()
        evidencia=reconocimientos_consumo(self.art.pk)
        self.assertEqual(len(evidencia),1)
        self.assertEqual(Decimal(evidencia[0]['consumo_extra']),0)
        self.assertEqual(self.u.cantidad_consumida_efectiva,620)
        self.assertEqual(resumen_global_articulo(self.art)['consumido'],620)
        self.liberar(1200)
        self.assertEqual(resumen_global_articulo(self.art)['disponible_para_division'],1200)

    def test_dos_liberaciones_no_duplican_la_evidencia_ni_el_consumo(self):
        self.liberar(500)
        self.liberar(700)
        self.assertEqual(LiberacionStockDivision.objects.count(),2)
        self.assertEqual(len(reconocimientos_consumo(self.art.pk)),1)
        self.assertEqual(self.u.cantidad_consumida_efectiva,620)
        resumen=resumen_global_articulo(self.art)
        self.assertEqual(resumen['consumido'],620)
        self.assertEqual(resumen['disponible_para_division'],1200)

    def test_linea_totalmente_despachada_en_requerimiento_parcial_se_reconoce(self):
        Requerimiento.objects.filter(pk=self.req.pk).update(estado='parcial')
        self.assertEqual(self.u.cantidad_consumida_efectiva,620)
        self.assertEqual(resumen_global_articulo(self.art)['comprometido_divisiones'],1200)

    def test_cache_de_lectura_no_conserva_consumo_tras_cambio_del_kardex(self):
        from .consumo_historico_division import contexto_lectura
        with contexto_lectura():
            self.assertEqual(len(reconocimientos_consumo(self.art.pk)),1)
            self.assertEqual(len(reconocimientos_consumo(self.art.pk)),1)
        Kardex.objects.filter(pk=self.salida.pk).update(estado='revertido')
        self.assertEqual(reconocimientos_consumo(self.art.pk),[])

    def test_resumen_y_api_departamento_no_duplican_las_620_despachadas(self):
        from .views import construir_resumen_gestor_departamento
        resumen,_=construir_resumen_gestor_departamento(self.dept)
        self.assertEqual(resumen[0]['asignado_historico'],1240)
        self.assertEqual(resumen[0]['asignado'],620)
        self.assertEqual(resumen[0]['despachado'],620)
        self.assertEqual(resumen[0]['disponible'],0)
        response=self.client.get(reverse('almacen:articulos_asignados',args=[self.dept.pk]))
        self.assertEqual(response.status_code,200)
        self.assertEqual(Decimal(response.json()['articulos'][0]['cantidad_asignada']),620)
        self.assertEqual(Decimal(response.json()['articulos'][0]['cantidad_disponible']),0)

    def test_liberacion_fallida_no_persiste_evidencia(self):
        from . import liberacion_division
        original=liberacion_division.resumen_global_articulo
        contador=[0]
        def romper(a):
            contador[0]+=1
            valor=original(a)
            if contador[0]==2:
                valor['existencia_fisica']+=1
            return valor
        with patch.object(liberacion_division,'resumen_global_articulo',side_effect=romper):
            with self.assertRaises(ValidationError):
                self.liberar(1200)
        self.assertFalse(LiberacionStockDivision.objects.exists())


class ConsumoHistoricoConcurrenciaTests(EscenarioEspejo,TransactionTestCase):
    def test_liberacion_y_despacho_concurrentes_conservan_unica_salida_historica(self):
        self.u.cantidad_asignada+=30
        self.u.cantidad_reservada=30
        self.u.save()
        req=Requerimiento.objects.create(departamento=self.dept,creado_por=self.user,estado='enviado')
        det=DetalleRequerimiento.objects.create(requerimiento=req,articulo=self.art,cantidad=30)
        sol=SolicitudRequerimiento.objects.create(departamento=self.dept,usuario_solicitante=self.user,
            estado='convertida',requerimiento=req)
        DetalleSolicitudRequerimiento.objects.create(solicitud=sol,articulo=self.art,cantidad=30,
            division_articulo_ubicacion=self.u,detalle_requerimiento=det)
        barrera=Barrier(2)
        def ejecutar(accion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                if accion=='liberar':
                    self.liberar(1170)
                else:
                    client=Client();client.force_login(self.user)
                    response=client.post(reverse('almacen:despachar_requerimiento',args=[req.pk]),
                        {f'cantidades[{det.pk}]':30})
                    self.assertEqual(response.status_code,302)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(ejecutar,['liberar','despachar']))
        self.u.refresh_from_db();req.refresh_from_db()
        self.assertEqual(req.estado,'despachado')
        self.assertEqual(self.u.cantidad_consumida,30)
        self.assertEqual(self.u.cantidad_consumida_efectiva,650)
        self.assertEqual(self.u.cantidad_reservada,0)
        self.assertEqual(Kardex.objects.filter(tipo_movimiento='SALIDA').count(),2)
        resumen=resumen_global_articulo(self.art)
        self.assertEqual(resumen['consumido'],650)
        self.assertEqual(resumen['existencia_fisica'],1170)
        self.assertEqual(resumen['disponible_para_division'],1170)
