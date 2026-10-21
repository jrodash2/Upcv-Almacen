from itertools import combinations

from django.test import TestCase
from django.urls import reverse

from . import test_solicitud_filas as fixtures
from .form import SolicitudRequerimientoForm, DetalleSolicitudRequerimientoFormSet
from .categorias_solicitud import MENSAJE_JUSTIFICACION, MENSAJE_TIPOS, tipo_categoria
from .models import (Articulo, AsignacionDetalleFactura, Categoria, SolicitudRequerimiento,
                     DetalleSolicitudRequerimiento, DivisionAlmacen, DivisionArticulo,
                     DivisionArticuloUbicacion, DivisionUbicacion)
from .views import obtener_stock_disponible_por_departamento


class CategoriasSolicitudTests(TestCase):
    post = fixtures.SolicitudFilasTests.post

    def setUp(self):
        fixtures.SolicitudFilasTests.setUp(self)
        self.a.nombre = 'Masking tape 2"'
        self.a.save()
        self.a.categoria.nombre = 'Suministro'
        self.a.categoria.save()
        self.b.categoria = Categoria.objects.create(nombre='  BiEnEs  ')
        self.b.save()
        self.insumo = Articulo.objects.create(codigo='INS-1', nombre='Insumo',
            categoria=Categoria.objects.create(nombre='INSUMO'))
        self.no_permitido = Articulo.objects.create(codigo='OTRO', nombre='Otro',
            categoria=Categoria.objects.create(nombre='Otros bienes especiales'))
        AsignacionDetalleFactura.objects.bulk_create([
            AsignacionDetalleFactura(articulo=a, destino=self.dept, cantidad_asignada=9)
            for a in (self.insumo, self.no_permitido)])
        self.por_tipo = {'suministros': self.a, 'bienes': self.b, 'insumos': self.insumo}
        self.api = reverse('almacen:articulos_asignados', args=[self.dept.pk])

    def fuentes_division(self, reservado=0, consumido=0):
        division = DivisionAlmacen.objects.create(nombre='Categorías')
        DivisionUbicacion.objects.create(division=division, ubicacion=self.dept)
        padre = DivisionArticulo(division=division, articulo=self.a, cantidad_asignada=20)
        DivisionArticulo.objects.bulk_create([padre])
        return DivisionArticuloUbicacion.objects.create(division_articulo=padre, ubicacion=self.dept,
            cantidad_asignada=2, cantidad_reservada=reservado, cantidad_consumida=consumido)

    def test_todas_las_combinaciones_api_y_widget_son_union_exacta(self):
        tipos = list(self.por_tipo)
        antes = list(AsignacionDetalleFactura.objects.order_by('pk').values_list('pk', 'cantidad_asignada'))
        for cantidad in range(4):
            for seleccion in combinations(tipos, cantidad):
                with self.subTest(tipos=seleccion):
                    response = self.client.get(self.api, {'contexto': 'solicitud', 'tipos_solicitud': list(seleccion)})
                    self.assertEqual(response.status_code, 200)
                    esperados = {self.por_tipo[tipo].pk for tipo in seleccion}
                    self.assertEqual({a['id'] for a in response.json()['articulos']}, esperados)
                    fs = DetalleSolicitudRequerimientoFormSet(queryset=DetalleSolicitudRequerimiento.objects.none(),
                        departamento=self.dept, stock_disponible=obtener_stock_disponible_por_departamento(self.dept),
                        tipos_solicitud=list(seleccion), prefix='detalles')
                    self.assertEqual({pk for pk, _ in fs.empty_form.fields['articulo'].choices if pk}, esperados)
        self.assertEqual(antes, list(AsignacionDetalleFactura.objects.order_by('pk').values_list('pk', 'cantidad_asignada')))
        self.assertFalse(SolicitudRequerimiento.objects.exists())

    def test_singular_plural_y_mayusculas_tienen_mapeo_explicito(self):
        for nombre, tipo in [('Bien', 'bienes'), (' BIENES ', 'bienes'), ('Suministro', 'suministros'),
                             ('Suministros', 'suministros'), ('insumo', 'insumos'), ('INSUMOS', 'insumos')]:
            self.assertEqual(tipo_categoria(nombre), tipo)
        self.assertIsNone(tipo_categoria('Otros bienes especiales'))
        self.assertIsNone(tipo_categoria(''))

    def test_post_manipulado_muestra_categoria_real_y_no_reserva(self):
        response = self.post([(self.a, 1, False)], tipos_solicitud=['bienes'], HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 400)
        error = ' '.join(response.json()['errors'])
        self.assertIn(self.a.nombre, error)
        self.assertIn('Suministro', error)
        self.assertIn('no corresponde', error)
        self.assertFalse(SolicitudRequerimiento.objects.exists())

    def test_justificacion_vacia_o_solo_espacios_es_rechazada(self):
        for justificacion in ['', '   ', '\t\n']:
            with self.subTest(justificacion=repr(justificacion)):
                response = self.post([(self.a, 1, False)], justificacion=justificacion, HTTP_ACCEPT='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertIn(MENSAJE_JUSTIFICACION, ' '.join(response.json()['errors']))
        self.assertFalse(SolicitudRequerimiento.objects.exists())

    def test_sin_tipos_se_rechaza_con_mensaje_especifico(self):
        response = self.post([(self.a, 1, False)], tipos_solicitud=[], HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(MENSAJE_TIPOS, ' '.join(response.json()['errors']))
        self.assertFalse(SolicitudRequerimiento.objects.exists())

    def test_justificacion_minima_sin_longitud_adicional_y_se_recorta(self):
        response = self.post([(self.a, 1, False)], justificacion=' x ', HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(SolicitudRequerimiento.objects.get().justificacion, 'x')

    def test_solicitud_valida_multicategoria_se_guarda(self):
        response = self.post([(self.a, 1, False), (self.b, 2, False)],
            tipos_solicitud=['bienes', 'suministros'], HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        solicitud = SolicitudRequerimiento.objects.get()
        self.assertEqual(set(solicitud.get_tipos_list()), {'bienes', 'suministros'})
        self.assertEqual(solicitud.detalles.count(), 2)

    def test_directo_disponible_se_conserva_con_division_agotada(self):
        source = self.fuentes_division(reservado=1, consumido=1)
        response = self.client.get(self.api, {'contexto': 'solicitud', 'tipos_solicitud': ['suministros']})
        item = response.json()['articulos'][0]
        self.assertEqual(item['id'], self.a.pk)
        self.assertEqual({f['origen'] for f in item['fuentes']}, {'Directo', 'División'})
        directo = AsignacionDetalleFactura.objects.get(articulo=self.a)
        response = self.post([(self.a, 1, False)], HTTP_ACCEPT='application/json',
                             **{'detalles-0-origen': f'D:{directo.pk}'})
        self.assertEqual(response.status_code, 201)
        source.refresh_from_db()
        self.assertEqual((source.cantidad_reservada, source.cantidad_consumida), (1, 1))

    def test_division_se_filtra_y_reserva_sin_cambiar_sus_reglas(self):
        source = self.fuentes_division()
        for tipos, esperado in [(['bienes'], False), (['suministros'], True)]:
            data = self.client.get(self.api, {'contexto': 'solicitud', 'tipos_solicitud': tipos}).json()['articulos']
            self.assertEqual(any(a['id'] == self.a.pk for a in data), esperado)
        response = self.post([(self.a, 1, False)], HTTP_ACCEPT='application/json',
                             **{'detalles-0-origen': f'V:{source.pk}'})
        self.assertEqual(response.status_code, 201)
        source.refresh_from_db()
        self.assertEqual((source.cantidad_reservada, source.cantidad_consumida), (1, 0))

    def test_tipo_desconocido_no_amplia_el_catalogo(self):
        response = self.client.get(self.api, {'contexto': 'solicitud', 'tipos_solicitud': ['otro']})
        self.assertEqual(response.json()['articulos'], [])
        response = self.post([(self.a, 1, False)], tipos_solicitud=['otro'], HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 400)

    def test_api_generica_de_transferencias_sigue_disponible_sin_filtro(self):
        data = self.client.get(self.api).json()['articulos']
        self.assertEqual({a['id'] for a in data}, {self.a.pk, self.b.pk, self.insumo.pk, self.no_permitido.pk})

    def test_get_sin_tipos_no_ofrece_articulos_y_justificacion_required(self):
        response = self.client.get(self.url)
        self.assertEqual(list(response.context['formset'].empty_form.fields['articulo'].choices), [('', '---------')])
        self.assertTrue(response.context['form'].fields['justificacion'].required)
        self.assertContains(response, 'id="id_justificacion"')
        self.assertEqual(response.context['articulos_data'], [])

    def test_consulta_de_solicitud_historica_no_modifica_datos(self):
        solicitud = SolicitudRequerimiento.objects.create(departamento=self.dept, usuario_solicitante=self.user,
            justificacion='', tipos_solicitud='suministros')
        DetalleSolicitudRequerimiento.objects.create(solicitud=solicitud, articulo=self.a, cantidad=1)
        form = SolicitudRequerimientoForm(instance=solicitud, usuario=self.user)
        self.assertEqual(form.fields['tipos_solicitud'].initial, ['suministros'])
        self.assertEqual(self.client.get(reverse('almacen:detalle_solicitud_requerimiento', args=[solicitud.pk])).status_code, 200)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.justificacion, '')
        self.assertEqual(solicitud.detalles.count(), 1)
