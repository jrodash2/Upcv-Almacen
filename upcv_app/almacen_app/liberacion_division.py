"""Liberar compromisos administrativos, conservando asignaciones e ingresos históricos."""
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum

from .disponibilidad import ACTIVOS, fuentes_departamento, resumen_global_articulo
from .models import (Articulo, Departamento, DetalleFacturaDivision, DetalleRequerimiento,
    DetalleSolicitudRequerimiento, DivisionArticulo, DivisionArticuloUbicacion,
    DivisionUbicacion, LiberacionStockDivision)

ZERO = Decimal('0')


def estado_liberacion(asignacion):
    """U incluye el consumo histórico: se conserva su cobertura una sola vez.

    A=asignación acumulada, L=liberado, U=distribuido acumulado a ubicaciones.
    C=consumido (incluido en U), R=reservado (incluido en U-C).
    Compromiso vigente=A-L-C. Máximo sin compromisos de ubicación=A-L-U.
    No se resta C ni R otra vez del máximo: ambos ya están protegidos por U.
    Ante inconsistencias se bloquea, nunca se reconstruyen/ajustan históricos.
    """
    ubicaciones = list(asignacion.asignaciones_ubicacion.all())  # también inactivas
    liberado = Decimal(asignacion.total_liberado)
    distribuido = sum((u.cantidad_asignada for u in ubicaciones), ZERO)
    reservado = sum((u.cantidad_reservada for u in ubicaciones), ZERO)
    consumido = sum((u.cantidad_consumida for u in ubicaciones), ZERO)
    vigente = asignacion.cantidad_asignada - liberado
    motivos = []
    if vigente < distribuido or distribuido < consumido + reservado:
        motivos.append('Las distribuciones o liberaciones históricas exceden la asignación; requiere revisión.')
    for ubicacion in ubicaciones:
        if min(ubicacion.cantidad_asignada, ubicacion.cantidad_consumida, ubicacion.cantidad_reservada) < 0:
            motivos.append('Existen contadores negativos en una ubicación; requiere revisión.')
        if ubicacion.cantidad_consumida + ubicacion.cantidad_reservada > ubicacion.cantidad_asignada:
            motivos.append('Una ubicación tiene reservas o consumos superiores a su asignación.')
        esperado_reservado = esperado_consumido = ZERO
        detalles = DetalleSolicitudRequerimiento.objects.filter(
            division_articulo_ubicacion=ubicacion).select_related('solicitud__requerimiento', 'detalle_requerimiento')
        for detalle in detalles:
            sol = detalle.solicitud
            despacho = detalle.detalle_requerimiento
            if (detalle.articulo_id != asignacion.articulo_id or sol.departamento_id != ubicacion.ubicacion_id
                    or (despacho and (despacho.articulo_id != asignacion.articulo_id
                        or despacho.requerimiento.departamento_id != ubicacion.ubicacion_id
                        or despacho.requerimiento_id != sol.requerimiento_id))):
                motivos.append('Un origen de solicitud no corresponde al artículo o ubicación; requiere revisión.')
            gastado = Decimal(despacho.cantidad_despachada) if despacho else ZERO
            esperado_consumido += gastado
            if sol.estado == 'pendiente':
                esperado_reservado += detalle.cantidad
            elif sol.estado == 'convertida' and sol.requerimiento_id and sol.requerimiento.estado in ACTIVOS:
                if not despacho:
                    motivos.append('Un requerimiento vigente no tiene origen de despacho verificable.')
                esperado_reservado += max(ZERO, Decimal(detalle.cantidad) - gastado)
        if esperado_reservado > ubicacion.cantidad_reservada or esperado_consumido > ubicacion.cantidad_consumida:
            motivos.append('Las solicitudes o despachos exceden los contadores de su ubicación; requiere revisión.')
        # Consumos antiguos sin enlace exacto solo se aceptan si hay despachos
        # reales suficientes en ese departamento; jamás se inventa una salida.
        consumo_depto = DivisionArticuloUbicacion.objects.filter(
            division_articulo__articulo_id=asignacion.articulo_id,
            ubicacion_id=ubicacion.ubicacion_id).aggregate(total=Sum('cantidad_consumida'))['total'] or ZERO
        despacho_depto = DetalleRequerimiento.objects.filter(
            articulo_id=asignacion.articulo_id,
            requerimiento__departamento_id=ubicacion.ubicacion_id).aggregate(total=Sum('cantidad_despachada'))['total'] or ZERO
        if consumo_depto > despacho_depto:
            motivos.append('Hay consumo de división sin despachos suficientes que lo respalden.')
        consumo_directo = sum((f['consumido'] for f in fuentes_departamento(ubicacion.ubicacion)
                               if f['origen'] == 'Directo' and f['articulo'].pk == asignacion.articulo_id), ZERO)
        if consumo_depto + consumo_directo > despacho_depto:
            motivos.append('Un despacho figura consumido en más de un origen; requiere revisión.')
    deptos = set(DivisionUbicacion.objects.filter(division_id=asignacion.division_id).values_list('ubicacion_id', flat=True))
    deptos.update(u.ubicacion_id for u in ubicaciones)
    sin_origen = DetalleSolicitudRequerimiento.objects.filter(
        articulo_id=asignacion.articulo_id, solicitud__departamento_id__in=deptos,
        asignacion_directa__isnull=True, division_articulo_ubicacion__isnull=True).filter(
            Q(solicitud__estado='pendiente') | Q(solicitud__estado='convertida', solicitud__requerimiento__estado__in=ACTIVOS))
    heredados = DetalleRequerimiento.objects.filter(articulo_id=asignacion.articulo_id,
        requerimiento__departamento_id__in=deptos, requerimiento__estado__in=ACTIVOS,
        requerimiento__solicitudes_origen__isnull=True, cantidad__gt=F('cantidad_despachada'))
    if sin_origen.exists() or heredados.exists():
        motivos.append('Hay solicitudes o requerimientos vigentes sin origen verificable; requiere revisión.')
    globales = resumen_global_articulo(asignacion.articulo)
    if globales['requiere_revision']:
        motivos.append('El inventario general tiene compromisos históricos inconsistentes; requiere revisión.')
    libre = max(ZERO, vigente - distribuido)
    if not libre and not motivos:
        motivos.append('Sin stock liberable: las unidades están distribuidas a ubicaciones o ya fueron liberadas.')
    return dict(asignado=asignacion.cantidad_asignada, liberado=liberado,
                distribuido=distribuido, reservado=reservado, consumido=consumido,
                compromiso_vigente=vigente-consumido, disponible_division=libre,
                maximo_liberable=ZERO if motivos else libre,
                motivo=' '.join(dict.fromkeys(motivos)), globales=globales)


@transaction.atomic
def liberar_stock_division(asignacion_id, cantidad, justificacion, usuario, operacion):
    from .form import LiberarStockDivisionForm
    if not usuario.is_authenticated or not (usuario.is_superuser or usuario.groups.filter(name='Administrador').exists()):
        raise PermissionDenied('Solo el Administrador puede liberar stock.')
    form = LiberarStockDivisionForm(dict(cantidad=cantidad, justificacion=justificacion, operacion=operacion))
    if not form.is_valid():
        raise ValidationError([str(error) for errores in form.errors.values() for error in errores])
    cantidad, justificacion, operacion = (form.cleaned_data[k] for k in ('cantidad', 'justificacion', 'operacion'))
    referencia = DivisionArticulo.objects.get(pk=asignacion_id)
    # Orden: artículo -> departamentos por PK -> asignación -> ubicaciones por PK.
    # Autoasignar toma primero el artículo; solicitudes/reservas conservan su
    # orden departamento -> ubicación. Nunca se bloquea un JOIN opcional.
    Articulo.objects.select_for_update().get(pk=referencia.articulo_id)
    deptos = set(DivisionArticuloUbicacion.objects.filter(division_articulo=referencia).values_list('ubicacion_id', flat=True))
    deptos.update(DivisionUbicacion.objects.filter(division_id=referencia.division_id).values_list('ubicacion_id', flat=True))
    list(Departamento.objects.select_for_update().filter(pk__in=deptos).order_by('pk'))
    asignacion = DivisionArticulo.objects.select_for_update().get(pk=asignacion_id)
    list(DivisionArticuloUbicacion.objects.select_for_update().filter(division_articulo=asignacion).order_by('pk'))
    anterior = LiberacionStockDivision.objects.filter(operacion=operacion).first()
    if anterior:
        if (anterior.asignacion_id != asignacion.pk or anterior.usuario_id != usuario.pk
                or anterior.cantidad != cantidad or anterior.justificacion != justificacion):
            raise ValidationError('El identificador ya corresponde a otra operación.')
        return anterior, False
    estado = estado_liberacion(asignacion)
    if cantidad > estado['maximo_liberable']:
        raise ValidationError(estado['motivo'] or 'La cantidad supera el máximo realmente liberable.')
    procedencias = [dict(distribucion_id=d.pk, detalle_factura_id=d.detalle_factura_id,
                        formulario_id=d.detalle_factura.form1h_id, cantidad=str(d.cantidad_asignada))
                   for d in DetalleFacturaDivision.objects.filter(
                       division_id=asignacion.division_id, detalle_factura__articulo_id=asignacion.articulo_id)
                   .select_related('detalle_factura').order_by('pk')]
    registro = LiberacionStockDivision(asignacion=asignacion, division_id=asignacion.division_id,
        articulo_id=asignacion.articulo_id, cantidad=cantidad, justificacion=justificacion,
        usuario=usuario, operacion=operacion, procedencias=procedencias,
        disponible_antes=estado['maximo_liberable'], disponible_despues=estado['maximo_liberable']-cantidad,
        tipo='total' if cantidad == estado['maximo_liberable'] else 'parcial')
    registro.full_clean()
    registro.save()
    # Ningún save/update de la asignación original, las ubicaciones ni Kardex.
    despues = resumen_global_articulo(asignacion.articulo)
    if (despues['existencia_fisica'] != estado['globales']['existencia_fisica']
            or despues['disponible_para_division'] != estado['globales']['disponible_para_division'] + cantidad):
        raise ValidationError('Los saldos cambiaron durante la operación; no se liberó stock. Intente nuevamente.')
    return registro, True
