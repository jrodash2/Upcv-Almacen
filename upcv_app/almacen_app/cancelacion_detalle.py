"""Cancelación individual con reserva exacta y auditoría, sin borrar históricos."""
import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .disponibilidad import ACTIVOS, bloquear_departamento, fuentes_departamento
from .models import (Articulo, DetalleRequerimiento, DetalleSolicitudRequerimiento,
    DivisionArticuloUbicacion, Kardex, Requerimiento)

logger = logging.getLogger(__name__)


@transaction.atomic
def cancelar_detalle_pendiente(pk, usuario, motivo, requerimiento_id=None):
    """El llamador valida grupos; aquí se revalida identidad y origen bajo bloqueo."""
    from .models import UsuarioDepartamento
    from django.core.exceptions import PermissionDenied
    detalle = DetalleRequerimiento.objects.get(pk=pk)
    req = detalle.requerimiento
    if requerimiento_id is not None and str(req.pk) != str(requerimiento_id):
        raise DetalleRequerimiento.DoesNotExist
    admin = usuario.is_superuser or usuario.groups.filter(name__in=['Administrador', 'Almacen']).exists()
    if not admin and not UsuarioDepartamento.objects.filter(usuario=usuario, departamento=req.departamento).exists():
        raise PermissionDenied('No tiene permiso para eliminar este detalle.')
    motivo = motivo.strip()
    if not 3 <= len(motivo) <= 500:
        raise ValidationError('Ingrese un motivo de eliminación de entre 3 y 500 caracteres.')
    # Mismo orden que despacho/liberación: artículo, departamento, fuentes, cabecera.
    Articulo.objects.select_for_update().get(pk=detalle.articulo_id)
    bloquear_departamento(req.departamento)
    req = Requerimiento.objects.select_for_update().get(pk=req.pk)
    detalle = DetalleRequerimiento.objects.select_for_update().get(pk=pk)
    if req.estado != 'pendiente' or detalle.estado != 'pendiente' or detalle.cantidad_despachada:
        raise ValidationError('Solo se pueden eliminar detalles pendientes sin unidades despachadas de un requerimiento pendiente.')
    if Kardex.objects.filter(fuente_despacho=detalle).exists():
        raise ValidationError('El detalle tiene movimientos en Kardex; no se puede eliminar su historial.')
    origen = DetalleSolicitudRequerimiento.objects.select_for_update().filter(detalle_requerimiento=detalle).first()
    if origen:
        solicitud = origen.solicitud
        if (solicitud.requerimiento_id != req.pk or solicitud.departamento_id != req.departamento_id
                or solicitud.estado != 'convertida' or origen.articulo_id != detalle.articulo_id
                or origen.cantidad != detalle.cantidad
                or bool(origen.asignacion_directa_id) == bool(origen.division_articulo_ubicacion_id)):
            raise ValidationError('La reserva o el origen del detalle es ambiguo; requiere revisión. No se modificaron saldos.')
        key = f'V:{origen.division_articulo_ubicacion_id}' if origen.division_articulo_ubicacion_id else f'D:{origen.asignacion_directa_id}'
        fila = next((f for f in fuentes_departamento(req.departamento) if f['fuente'] == key), None)
        if not fila or fila['articulo'].pk != detalle.articulo_id or fila['requiere_revision']:
            raise ValidationError('La fuente original requiere revisión; no se modificaron saldos.')
        if origen.division_articulo_ubicacion_id:
            source = DivisionArticuloUbicacion.objects.get(pk=origen.division_articulo_ubicacion_id)
            # No liberar la reserva de otra fila ante un contador histórico incoherente.
            esperado = Decimal('0')
            for ds in source.detalles_solicitud.select_related('solicitud__requerimiento', 'detalle_requerimiento'):
                dr = ds.detalle_requerimiento if ds.detalle_requerimiento_id else None
                if dr and dr.cancelado_en:
                    continue
                if ds.solicitud.estado == 'pendiente':
                    esperado += ds.cantidad
                elif (ds.solicitud.estado == 'convertida' and ds.solicitud.requerimiento_id
                        and ds.solicitud.requerimiento.estado in ACTIVOS):
                    if dr is None:
                        raise ValidationError('Hay reservas históricas sin vínculo exacto en la fuente; requiere revisión.')
                    esperado += max(0, ds.cantidad - dr.cantidad_despachada)
            if source.cantidad_reservada != esperado or source.cantidad_reservada < detalle.cantidad:
                raise ValidationError('La reserva de división es inconsistente; requiere revisión. No se modificaron saldos.')
            source.cantidad_reservada -= detalle.cantidad
            source.save(update_fields=['cantidad_reservada', 'fecha_actualizacion'])
        elif fila['reservado'] < detalle.cantidad:
            raise ValidationError('La reserva directa es inconsistente; no se modificaron saldos.')
    else:
        if req.solicitudes_origen.exists():
            raise ValidationError('El detalle histórico no tiene un vínculo de origen exacto; requiere revisión.')
        directas = [f for f in fuentes_departamento(req.departamento)
                    if f['origen'] == 'Directo' and f['articulo'].pk == detalle.articulo_id]
        if not directas or any(f['requiere_revision'] for f in directas):
            raise ValidationError('La reserva directa histórica requiere revisión; no se modificaron saldos.')
    detalle.cancelado_en = timezone.now()
    detalle.cancelado_por = usuario
    detalle.motivo_cancelacion = motivo
    detalle.save(update_fields=['cancelado_en', 'cancelado_por', 'motivo_cancelacion'])
    return detalle
