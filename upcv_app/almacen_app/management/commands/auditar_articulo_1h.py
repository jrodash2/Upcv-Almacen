"""Diagnóstico reproducible de solo lectura antes de confirmar un ingreso."""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from almacen_app import models as m


class Command(BaseCommand):
    help = 'Documenta ingresos, Kardex y orígenes de consumo; no modifica datos.'

    def add_arguments(self, parser):
        parser.add_argument('--articulo', type=int, required=True)

    def handle(self, *args, **options):
        with transaction.atomic():
            # Un único snapshot y protección también contra escrituras accidentales.
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            articulo = m.Articulo.objects.filter(pk=options['articulo']).first()
            if articulo is None:
                raise CommandError('Artículo inexistente en esta base.')
            datos = {'articulo': articulo.pk, 'codigo': articulo.codigo,
                     'existencia_general': m.existencia_general_articulo(articulo)}
            from almacen_app.disponibilidad import resumen_global_articulo
            datos['resumen'] = resumen_global_articulo(articulo)
            from almacen_app.liberacion_division import estado_liberacion
            datos['liberacion_por_division'] = [dict(asignacion_id=a.pk, division_id=a.division_id,
                **estado_liberacion(a)) for a in m.DivisionArticulo.objects.filter(articulo=articulo)]
            consultas = {
                'liberaciones_division': m.LiberacionStockDivision.objects.filter(articulo=articulo).values(),
                'ingresos': m.DetalleFactura.objects.filter(articulo=articulo).values(
                    'id', 'form1h_id', 'form1h__estado', 'form1h__numero_serie', 'cantidad'),
                'kardex': m.Kardex.objects.filter(articulo=articulo).values(
                    'id', 'tipo_movimiento', 'cantidad', 'estado', 'movimiento_revertido_id',
                    'fuente_factura_id', 'fuente_factura__form1h_id',
                    'fuente_factura__form1h__estado', 'fuente_despacho_id',
                    'fuente_despacho__requerimiento_id'),
                'reversiones': m.ReversionMovimiento.objects.filter(articulo=articulo).values(),
                'directas': m.AsignacionDetalleFactura.objects.filter(articulo=articulo).values(),
                'divisiones': m.DivisionArticulo.objects.filter(articulo=articulo).values(),
                'ubicaciones': m.DivisionArticuloUbicacion.objects.filter(
                    division_articulo__articulo=articulo).values(),
                'distribuciones_1h': m.DetalleFacturaDivision.objects.filter(
                    detalle_factura__articulo=articulo).values(),
                'despachos': m.DetalleRequerimiento.objects.filter(articulo=articulo).values(),
                'origenes_solicitud': m.DetalleSolicitudRequerimiento.objects.filter(
                    articulo=articulo).values('id', 'solicitud_id', 'solicitud__estado',
                    'solicitud__requerimiento_id', 'cantidad', 'asignacion_directa_id',
                    'division_articulo_ubicacion_id', 'detalle_requerimiento_id'),
            }
            datos.update({nombre: list(qs.order_by('pk')) for nombre, qs in consultas.items()})
            self.stdout.write(json.dumps(datos, ensure_ascii=False, indent=2, default=str))
