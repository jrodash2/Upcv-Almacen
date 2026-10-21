"""Inspección de solo lectura; nunca elimina ni reconcilia reservas."""
import json
from django.core.management.base import BaseCommand, CommandError
from almacen_app.disponibilidad import fuentes_departamento, ACTIVOS
from almacen_app.models import Departamento, DetalleRequerimiento, DetalleSolicitudRequerimiento, DivisionArticuloUbicacion


class Command(BaseCommand):
    help = 'Audita saldos y documentos de un artículo/departamento sin modificar datos.'

    def add_arguments(self, parser):
        parser.add_argument('--departamento', type=int, required=True)
        parser.add_argument('--codigo', required=True)

    def handle(self, *args, **options):
        try:
            dept = Departamento.objects.get(pk=options['departamento'])
        except Departamento.DoesNotExist as exc:
            raise CommandError('Departamento inexistente.') from exc
        filas = [f for f in fuentes_departamento(dept) if f['articulo'].codigo == options['codigo']]
        datos = {'departamento': dept.pk, 'codigo': options['codigo'], 'fuentes': [
            {k: str(f[k]) for k in ['fuente', 'origen', 'division', 'cantidad_asignada', 'reservado',
                                    'consumido', 'disponible', 'requiere_revision']}
            for f in filas], 'solicitudes': list(DetalleSolicitudRequerimiento.objects.filter(
                solicitud__departamento=dept, articulo__codigo=options['codigo']).values(
                    'id', 'solicitud_id', 'solicitud__estado', 'solicitud__requerimiento_id',
                    'solicitud__requerimiento__estado', 'cantidad', 'asignacion_directa_id',
                    'division_articulo_ubicacion_id', 'detalle_requerimiento_id')),
            'despachos': list(DetalleRequerimiento.objects.filter(requerimiento__departamento=dept,
                articulo__codigo=options['codigo']).values('id', 'requerimiento_id', 'requerimiento__estado',
                                                         'cantidad', 'cantidad_despachada')),
            'contadores_division_incluidos_inactivos': list(DivisionArticuloUbicacion.objects.filter(
                ubicacion=dept, division_articulo__articulo__codigo=options['codigo']).values(
                    'id', 'activo', 'division_articulo_id', 'cantidad_asignada', 'cantidad_reservada', 'cantidad_consumida')),
        }
        comparacion = []
        for source in DivisionArticuloUbicacion.objects.filter(ubicacion=dept, division_articulo__articulo__codigo=options['codigo']):
            documentada = 0
            ambiguos = []
            for detalle in source.detalles_solicitud.select_related('solicitud__requerimiento', 'detalle_requerimiento'):
                solicitud = detalle.solicitud
                if solicitud.estado == 'pendiente':
                    documentada += detalle.cantidad
                elif solicitud.estado == 'convertida' and solicitud.requerimiento_id and solicitud.requerimiento.estado in ACTIVOS:
                    if detalle.detalle_requerimiento_id:
                        documentada += max(0, detalle.cantidad - detalle.detalle_requerimiento.cantidad_despachada)
                    else:
                        ambiguos.append(detalle.pk)
            comparacion.append({'asignacion_id': source.pk, 'reserva_contador': source.cantidad_reservada,
                                'reserva_activa_documentada': documentada,
                                'detalles_convertidos_sin_vinculo': ambiguos,
                                'diferencia_por_investigar': source.cantidad_reservada - documentada})
        datos['comparacion_reservas_division'] = comparacion
        self.stdout.write(json.dumps(datos, ensure_ascii=False, indent=2, default=str))
