"""Regression coverage for active/deleted rows in new requests."""
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .models import (
    Articulo, AsignacionDetalleFactura, Categoria, Departamento,
    DivisionAlmacen, DivisionArticulo, DivisionArticuloUbicacion,
    DivisionUbicacion, SolicitudRequerimiento, UsuarioDepartamento,
)


class SolicitudFilasTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='gestor_filas')
        self.user.groups.add(Group.objects.get_or_create(name='Gestor')[0])
        self.dept = Departamento.objects.create(id_departamento='FILAS', nombre='Filas')
        UsuarioDepartamento.objects.create(usuario=self.user, departamento=self.dept)
        categoria = Categoria.objects.create(nombre='Suministros')
        self.a = Articulo.objects.create(codigo='FILA-A', nombre='Artículo A', categoria=categoria)
        self.b = Articulo.objects.create(codigo='FILA-B', nombre='Artículo B', categoria=categoria)
        AsignacionDetalleFactura.objects.bulk_create([
            AsignacionDetalleFactura(articulo=a, destino=self.dept, cantidad_asignada=9)
            for a in [self.a, self.b]
        ])
        self.client.force_login(self.user)
        self.url = reverse('almacen:crear_solicitud_requerimiento')

    def post(self, rows, **overrides):
        data = {
            'departamento': self.dept.pk, 'tipos_solicitud': ['suministros'],
            'detalles-TOTAL_FORMS': len(rows), 'detalles-INITIAL_FORMS': 0,
            'detalles-MIN_NUM_FORMS': 0, 'detalles-MAX_NUM_FORMS': 1000,
        }
        for i, (articulo, cantidad, deleted) in enumerate(rows):
            data.update({f'detalles-{i}-articulo': articulo.pk,
                         f'detalles-{i}-cantidad': cantidad})
            if deleted:
                data[f'detalles-{i}-DELETE'] = 'on'
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_only_remaining_article_is_saved(self):
        self.assertEqual(self.post([(self.a, 1, False)]).status_code, 302)
        self.assertEqual(list(SolicitudRequerimiento.objects.get().detalles.values_list(
            'articulo_id', 'cantidad')), [(self.a.pk, 1)])

    def test_deleted_invalid_row_is_ignored(self):
        self.assertEqual(self.post([(self.a, 1, False), (self.b, 999, True)]).status_code, 302)
        self.assertEqual(SolicitudRequerimiento.objects.get().detalles.count(), 1)

    def test_delete_and_readd_has_no_duplicate(self):
        self.assertEqual(self.post([(self.a, 1, False), (self.b, 2, True),
                                   (self.b, 2, False)]).status_code, 302)
        self.assertEqual(SolicitudRequerimiento.objects.get().detalles.count(), 2)

    def test_repeated_article_totals(self):
        for quantities, valid in [([5, 3], True), ([5, 5], False)]:
            with self.subTest(quantities=quantities):
                response = self.post([(self.a, q, False) for q in quantities])
                self.assertEqual(response.status_code, 302 if valid else 200)
                self.assertEqual(SolicitudRequerimiento.objects.count(), int(valid))
                SolicitudRequerimiento.objects.all().delete()

    def test_deleted_quantity_is_not_in_total(self):
        self.assertEqual(self.post([(self.a, 5, False), (self.a, 5, True)]).status_code, 302)

    def test_invalid_quantities_and_empty_request_save_nothing(self):
        for rows in [[], [(self.a, 0, False)], [(self.a, -1, False)],
                     [(self.a, 10, False)], [(self.a, 1, False), (self.b, '', False)]]:
            with self.subTest(rows=rows):
                self.assertEqual(self.post(rows).status_code, 200)
                self.assertFalse(SolicitudRequerimiento.objects.exists())

    def test_deleted_rows_not_rendered_on_invalid_post_or_get(self):
        response = self.post([(self.a, 0, False), (self.b, 2, True)])
        self.assertNotContains(response, 'name="detalles-1-articulo"')
        response = self.client.get(self.url)
        self.assertEqual(len(response.context['formset'].forms), 1)
        self.assertFalse(SolicitudRequerimiento.objects.exists())

    def division_source(self):
        AsignacionDetalleFactura.objects.all().delete()
        division = DivisionAlmacen.objects.create(nombre='División Filas')
        DivisionUbicacion.objects.create(division=division, ubicacion=self.dept)
        # Isolate source/reservation tests from unrelated inventory intake fixtures.
        source = DivisionArticulo(division=division, articulo=self.a, cantidad_asignada=20)
        DivisionArticulo.objects.bulk_create([source])
        return DivisionArticuloUbicacion.objects.create(
            division_articulo=source, ubicacion=self.dept,
            cantidad_asignada=14, cantidad_reservada=2, cantidad_consumida=3)

    def test_division_reserves_only_active_quantities(self):
        source = self.division_source()
        self.assertEqual(self.post([(self.a, 5, False), (self.a, 3, False),
                                   (self.a, 99, True)]).status_code, 302)
        source.refresh_from_db()
        self.assertEqual(source.cantidad_reservada, Decimal('10'))
        self.assertEqual(source.cantidad_consumida, Decimal('3'))
        self.assertEqual(source.disponible_ubicacion, Decimal('1'))
        self.assertEqual(set(SolicitudRequerimiento.objects.get().detalles.values_list(
            'division_articulo_ubicacion_id', flat=True)), {source.pk})

    def test_division_overdraw_saves_nothing_and_preserves_reserves(self):
        source = self.division_source()
        self.assertEqual(self.post([(self.a, 5, False), (self.a, 5, False)]).status_code, 200)
        self.assertFalse(SolicitudRequerimiento.objects.exists())
        source.refresh_from_db()
        self.assertEqual(source.cantidad_reservada, Decimal('2'))
