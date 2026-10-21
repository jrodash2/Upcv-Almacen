from django.test import TestCase

from . import test_categorias_solicitud as fixtures
from .models import AsignacionDetalleFactura, SolicitudRequerimiento


class ModalArticulosTests(TestCase):
    setUp = fixtures.CategoriasSolicitudTests.setUp
    post = fixtures.CategoriasSolicitudTests.post

    def test_modal_incluye_agotados_sin_cambiar_saldos(self):
        source = fixtures.CategoriasSolicitudTests.fuentes_division(self, reservado=1, consumido=1)
        AsignacionDetalleFactura.objects.filter(articulo=self.a).update(cantidad_asignada=0)
        params = {'contexto': 'solicitud', 'tipos_solicitud': ['suministros']}
        self.assertEqual(self.client.get(self.api, params).json()['articulos'], [])
        response = self.client.get(self.api, {**params, 'incluir_agotados': '1'})
        item = response.json()['articulos'][0]
        self.assertEqual(item['id'], self.a.pk)
        self.assertTrue(all(float(f['cantidad_disponible']) == 0 for f in item['fuentes']))
        response = self.post([(self.a, 1, False)], HTTP_ACCEPT='application/json',
                             **{'detalles-0-origen': f'V:{source.pk}'})
        self.assertEqual(response.status_code, 400)
        source.refresh_from_db()
        self.assertEqual((source.cantidad_reservada, source.cantidad_consumida),(1,1))
        self.assertFalse(SolicitudRequerimiento.objects.exists())

    def test_backend_no_acepta_cantidad_fraccionaria_en_solicitud(self):
        response = self.post([(self.a, '1.5', False)], HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SolicitudRequerimiento.objects.exists())

    def test_fuente_repetida_valida_suma_y_no_reserva_doble(self):
        source = AsignacionDetalleFactura.objects.get(articulo=self.a)
        response = self.post([(self.a, 5, False), (self.a, 5, False)], HTTP_ACCEPT='application/json',
            **{'detalles-0-origen':f'D:{source.pk}', 'detalles-1-origen':f'D:{source.pk}'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SolicitudRequerimiento.objects.exists())
