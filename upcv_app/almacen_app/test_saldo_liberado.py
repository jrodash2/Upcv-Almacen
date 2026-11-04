"""Distinguir liberaciones registradas, compromisos vigentes e inconsistencias."""
import json
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .disponibilidad import resumen_global_articulo
from .models import (AsignacionDetalleFactura, DetalleSolicitudRequerimiento,
    SolicitudRequerimiento)
from .test_liberacion_division import EscenarioLiberacion
from .views import construir_stock_list_administrador


class SaldoLiberadoTests(EscenarioLiberacion, TestCase):
    def test_stock_no_presenta_historico_como_compromiso_de_division(self):
        self.liberar(100)
        fila = construir_stock_list_administrador()[0]
        self.assertEqual(fila['divisiones'], 'Sin compromiso vigente')
        self.assertIn('División A (100)', fila['divisiones_historicas'])
        self.assertEqual(fila['comprometido_divisiones'], 0)
        self.assertEqual(fila['liberado_divisiones'], 100)
        self.assertEqual(fila['disponible'], 100)

    def test_liberacion_parcial_muestra_el_compromiso_restante(self):
        self.liberar(40)
        fila = construir_stock_list_administrador()[0]
        self.assertEqual(fila['divisiones'], 'División A (60)')
        self.assertIn('División A (100)', fila['divisiones_historicas'])

    def test_revision_explica_por_que_el_saldo_no_es_asignable(self):
        self.liberar(100)
        AsignacionDetalleFactura.objects.bulk_create([AsignacionDetalleFactura(
            articulo=self.art, destino=self.dept, cantidad_asignada=10)])
        solicitud = SolicitudRequerimiento.objects.create(
            departamento=self.dept, usuario_solicitante=self.user)
        DetalleSolicitudRequerimiento.objects.create(solicitud=solicitud, articulo=self.art, cantidad=20)
        resumen = resumen_global_articulo(self.art)
        self.assertTrue(resumen['requiere_revision'])
        self.assertEqual(resumen['liberado_divisiones'], 100)
        self.assertEqual(resumen['saldo_sin_asignar'], 90)
        self.assertEqual(resumen['disponible_para_division'], 0)
        self.assertTrue(any('Destino' in motivo for motivo in resumen['motivos_revision']))
        response = self.client.get(reverse('almacen:buscar_articulos'), {'q':'675','asignacion_directa':'1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response.json()[0]['existencias']['motivos_revision'], resumen['motivos_revision'])



class AuditoriaSaldoLiberadoTests(EscenarioLiberacion, TransactionTestCase):
    def test_auditoria_por_codigo_muestra_liberaciones_y_no_modifica_datos(self):
        self.liberar(40)
        antes = self.snapshot()
        output = StringIO()
        call_command('auditar_articulo_1h', codigo='675', resumen=True, stdout=output)
        datos = json.loads(output.getvalue())
        self.assertEqual(datos['articulo'], 9876)
        self.assertEqual(datos['codigo'], '675')
        self.assertEqual(Decimal(datos['resumen']['liberado_divisiones']), 40)
        self.assertEqual(Decimal(datos['resumen']['disponible_para_division']), 40)
        self.assertEqual(len(datos['liberaciones_division']), 1)
        self.assertEqual(self.snapshot(), antes)
