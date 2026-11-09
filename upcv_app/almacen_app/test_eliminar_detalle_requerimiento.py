"""Eliminación segura y errores explícitos, sin reescribir fuentes reservadas."""
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from . import test_disponibilidad as fixtures
from .models import (DetalleRequerimiento, DetalleSolicitudRequerimiento, Kardex,
                     Requerimiento, SolicitudRequerimiento)


class EliminarDetalleRequerimientoTests(TestCase):
    def setUp(self):
        fixtures.preparar(self)
        self.user.groups.remove(Group.objects.get(name="Gestor"))
    post = fixtures.FuentesDisponibilidadTests.post
    def crear(self, rows, sources):
        grupo = Group.objects.get(name="Gestor")
        self.user.groups.add(grupo)
        try:
            return fixtures.FuentesDisponibilidadTests.crear(self, rows, sources)
        finally:
            self.user.groups.remove(grupo)
    convertir = fixtures.FuentesDisponibilidadTests.convertir
    saldo = fixtures.FuentesDisponibilidadTests.saldo
    division = fixtures.FuentesDisponibilidadTests.division

    def detalle(self, **kwargs):
        req = Requerimiento.objects.create(departamento=self.dept, creado_por=self.user)
        return DetalleRequerimiento.objects.create(requerimiento=req, articulo=self.a, cantidad=3, **kwargs)

    def eliminar(self, detalle, **data):
        return self.client.post(reverse('almacen:eliminar_detalle_requerimiento', args=[detalle.pk]), data)

    def test_pendiente_libera_reserva_directa_implicita_una_vez(self):
        detalle = self.detalle()
        otro = DetalleRequerimiento.objects.create(requerimiento=detalle.requerimiento, articulo=self.a, cantidad=2)
        key = f'D:{self.directa.pk}'
        self.assertEqual(self.saldo(key)['reservado'], 5)
        kardex = list(Kardex.objects.values())
        response = self.eliminar(detalle, requerimiento_id=detalle.requerimiento_id)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {'success': True})
        self.assertEqual(self.saldo(key)['reservado'], 2)
        self.assertEqual(self.eliminar(detalle).status_code, 404)
        self.assertEqual(self.saldo(key)['reservado'], 2)
        self.assertTrue(DetalleRequerimiento.objects.filter(pk=otro.pk).exists())
        self.directa.refresh_from_db()
        self.assertEqual(self.directa.cantidad_asignada, 10)
        self.assertEqual(list(Kardex.objects.values()), kardex)

    def test_origen_convertido_directo_o_division_se_conserva_y_explica(self):
        division = self.division()
        self.assertEqual(self.crear([(self.a, 3, False), (self.a, 2, False)],
            [f'D:{self.directa.pk}', f'V:{division.pk}']).status_code, 201)
        req = self.convertir(SolicitudRequerimiento.objects.get())
        origenes = list(DetalleSolicitudRequerimiento.objects.order_by('pk').values())
        for detalle in req.detalles.all():
            response = self.eliminar(detalle)
            self.assertEqual(response.status_code, 400)
            self.assertIn('Anule el requerimiento', response.json()['error'])
        self.assertEqual(req.detalles.count(), 2)
        self.assertEqual(self.saldo(f'D:{self.directa.pk}')['reservado'], 3)
        self.assertEqual(self.saldo(f'V:{division.pk}')['reservado'], 2)
        self.assertEqual(list(DetalleSolicitudRequerimiento.objects.order_by('pk').values()), origenes)

    def test_no_elimina_estados_no_permitidos(self):
        detalle = self.detalle()
        for estado in ['enviado', 'parcial', 'despachado', 'rechazado']:
            detalle.requerimiento.estado = estado
            detalle.requerimiento.save()
            response = self.eliminar(detalle)
            self.assertEqual(response.status_code, 400, estado)
            self.assertTrue(DetalleRequerimiento.objects.filter(pk=detalle.pk).exists())

    def test_no_elimina_despacho(self):
        detalle = self.detalle(cantidad_despachada=1)
        self.assertEqual(self.eliminar(detalle).status_code, 400)
        self.assertTrue(DetalleRequerimiento.objects.filter(pk=detalle.pk).exists())

    def test_no_desvincula_kardex_aunque_contador_este_en_cero(self):
        detalle = self.detalle()
        Kardex.objects.bulk_create([Kardex(articulo=self.a, tipo_movimiento='SALIDA', cantidad=1,
            fuente_despacho=detalle)])
        antes = list(Kardex.objects.values())
        self.assertEqual(self.eliminar(detalle).status_code, 400)
        self.assertEqual(list(Kardex.objects.values()), antes)

    def test_detalle_de_otro_requerimiento(self):
        detalle = self.detalle()
        self.assertEqual(self.eliminar(detalle, requerimiento_id=detalle.requerimiento_id + 1).status_code, 404)
        self.assertTrue(DetalleRequerimiento.objects.filter(pk=detalle.pk).exists())

    def test_departamento_ajeno(self):
        detalle = self.detalle()
        user = User.objects.create_user(username='otro_departamento')
        user.groups.add(Group.objects.get_or_create(name='Departamento')[0])
        self.client.force_login(user)
        self.assertEqual(self.eliminar(detalle).status_code, 403)
        self.assertTrue(DetalleRequerimiento.objects.filter(pk=detalle.pk).exists())

    def test_sin_permiso_y_gestor_no_eliminan(self):
        detalle = self.detalle()
        for grupo in [None, 'Gestor']:
            self.user.groups.clear()
            if grupo:
                self.user.groups.add(Group.objects.get_or_create(name=grupo)[0])
            self.assertNotEqual(self.eliminar(detalle).status_code, 200)
            self.assertTrue(DetalleRequerimiento.objects.filter(pk=detalle.pk).exists())

    def test_csrf_y_get(self):
        detalle = self.detalle()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        url = reverse('almacen:eliminar_detalle_requerimiento', args=[detalle.pk])
        self.assertEqual(client.post(url).status_code, 403)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertTrue(DetalleRequerimiento.objects.filter(pk=detalle.pk).exists())

    def test_rollback_si_falla_despues_de_borrar(self):
        detalle = self.detalle()
        original = DetalleRequerimiento.delete
        def falla(instance, *args, **kwargs):
            original(instance, *args, **kwargs)
            raise RuntimeError('Fallo simulado, no exponer al cliente')
        with patch.object(DetalleRequerimiento, 'delete', falla):
            with self.assertLogs(level='ERROR'):
                response = self.eliminar(detalle)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('Fallo simulado', response.content.decode())
        self.assertTrue(DetalleRequerimiento.objects.filter(pk=detalle.pk).exists())
        self.assertEqual(self.saldo(f'D:{self.directa.pk}')['reservado'], 3)

    def test_agregar_y_editar_detalle_directo_conservan_saldos(self):
        detalle = self.detalle()
        response = self.client.post(reverse('almacen:detalle_requerimiento', args=[detalle.requerimiento_id]),
            {'articulo': self.a.pk, 'cantidad': 2, 'observaciones': 'Otra fila'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(detalle.requerimiento.detalles.count(), 2)
        response = self.client.post(reverse('almacen:editar_detalle_requerimiento'),
            {'detalle_id': detalle.pk, 'articulo': self.a.pk, 'cantidad': 4, 'observaciones': 'Editada'})
        self.assertEqual(response.status_code, 302)
        detalle.refresh_from_db()
        self.assertEqual((detalle.cantidad, detalle.observacion), (4, 'Editada'))
        self.assertEqual(self.saldo(f'D:{self.directa.pk}')['reservado'], 6)
        self.assertEqual(self.eliminar(detalle).status_code, 200)
        self.assertEqual(self.saldo(f'D:{self.directa.pk}')['reservado'], 2)

    def test_anonimo_no_elimina(self):
        detalle = self.detalle()
        self.client.logout()
        response = self.eliminar(detalle)
        self.assertEqual(response.status_code, 302)
        self.assertIn('?next=', response.url)
        self.assertTrue(DetalleRequerimiento.objects.filter(pk=detalle.pk).exists())
