"""Saldos por fuente. No repara ni reescribe históricos o contadores heredados."""
from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum

from .models import (
    AsignacionDetalleFactura, Departamento, DetalleRequerimiento,
    DetalleSolicitudRequerimiento, DivisionArticuloUbicacion, DivisionUbicacion,
)

ZERO = Decimal('0')
ACTIVOS = ('pendiente', 'enviado', 'parcial')


def bloquear_departamento(departamento):
    """Orden único: departamento, directas por PK, ubicaciones por PK, cabecera.

    Solo tablas base en FOR UPDATE; jamás joins opcionales.
    """
    Departamento.objects.select_for_update().get(pk=departamento.pk)
    list(AsignacionDetalleFactura.objects.select_for_update().filter(destino=departamento).order_by('pk'))
    list(DivisionArticuloUbicacion.objects.select_for_update().filter(ubicacion=departamento).order_by('pk'))


def fuentes_departamento(departamento):
    if not departamento:
        return []
    directas = list(AsignacionDetalleFactura.objects.filter(destino=departamento)
                    .select_related('articulo__categoria').order_by('pk'))
    divisiones = list(DivisionArticuloUbicacion.objects.filter(ubicacion=departamento)
                     .select_related('division_articulo__articulo__categoria', 'division_articulo__division')
                     .order_by('pk'))
    membresias = set(DivisionUbicacion.objects.filter(ubicacion=departamento, activa=True)
                     .values_list('division_id', flat=True))
    # Incluye consumos históricos de divisiones inactivas: no se vuelven consumo directo.
    consumido_division = defaultdict(Decimal)
    for source in divisiones:
        consumido_division[source.division_articulo.articulo_id] += source.cantidad_consumida
    despachado = dict(DetalleRequerimiento.objects.filter(requerimiento__departamento=departamento)
                     .values('articulo_id').annotate(total=Sum('cantidad_despachada'))
                     .values_list('articulo_id', 'total'))
    reservas_exactas = defaultdict(Decimal)
    consumos_exactos = defaultdict(Decimal)
    reservas_heredadas = defaultdict(Decimal)
    detalles = DetalleSolicitudRequerimiento.objects.filter(
        solicitud__departamento=departamento, division_articulo_ubicacion__isnull=True,
    ).select_related('solicitud__requerimiento', 'detalle_requerimiento')
    for detalle in detalles:
        solicitud = detalle.solicitud
        consumido = Decimal(detalle.detalle_requerimiento.cantidad_despachada if detalle.detalle_requerimiento_id else 0)
        if detalle.asignacion_directa_id:
            consumos_exactos[detalle.asignacion_directa_id] += consumido
        reserva = ZERO
        if solicitud.estado == 'pendiente':
            reserva = Decimal(detalle.cantidad)
        elif solicitud.estado == 'convertida' and solicitud.requerimiento_id and solicitud.requerimiento.estado in ACTIVOS:
            if not detalle.detalle_requerimiento_id:
                # Los detalles antiguos no tenían vínculo: solo inferir si es inequívoco.
                candidatos = solicitud.requerimiento.detalles.filter(articulo_id=detalle.articulo_id)
                if candidatos.count() == 1:
                    consumido = Decimal(candidatos.first().cantidad_despachada)
            reserva = max(ZERO, Decimal(detalle.cantidad) - consumido)
        if detalle.asignacion_directa_id:
            reservas_exactas[detalle.asignacion_directa_id] += reserva
        else:
            reservas_heredadas[detalle.articulo_id] += reserva
    # Requerimientos directos anteriores/sin solicitud: una sola reserva por pendiente.
    for detalle in DetalleRequerimiento.objects.filter(
        requerimiento__departamento=departamento, requerimiento__estado__in=ACTIVOS,
        requerimiento__solicitudes_origen__isnull=True,
    ):
        reservas_heredadas[detalle.articulo_id] += max(ZERO, Decimal(detalle.cantidad - detalle.cantidad_despachada))
    consumo_heredado = defaultdict(Decimal)
    for articulo_id, total in despachado.items():
        exacto = sum((consumos_exactos[x.pk] for x in directas if x.articulo_id == articulo_id), ZERO)
        consumo_heredado[articulo_id] = max(ZERO, Decimal(total or 0) - consumido_division[articulo_id] - exacto)
    fuentes = []
    for source in directas:
        articulo = source.articulo
        asignado = Decimal(source.cantidad_asignada)
        consumido = consumos_exactos[source.pk]
        legado = min(max(ZERO, asignado - consumido), consumo_heredado[articulo.pk])
        consumido += legado
        consumo_heredado[articulo.pk] -= legado
        reservado = reservas_exactas[source.pk]
        legado_reserva = min(max(ZERO, asignado - consumido - reservado), reservas_heredadas[articulo.pk])
        reservado += legado_reserva
        reservas_heredadas[articulo.pk] -= legado_reserva
        fuentes.append(_fila(source, articulo, departamento, f'D:{source.pk}', 'Directo', None,
                             asignado, reservado, consumido))
    # Si faltan datos históricos, bloquear el artículo y señalar revisión; no ocultar déficit.
    for fila in fuentes:
        articulo_id = fila['articulo'].pk
        if reservas_heredadas[articulo_id] > 0 or consumo_heredado[articulo_id] > 0:
            fila['requiere_revision'] = True
            fila['disponible'] = ZERO
    for source in divisiones:
        da = source.division_articulo
        if not (source.activo and da.activo and da.division.activa and da.division_id in membresias):
            continue
        fuentes.append(_fila(source, da.articulo, departamento, f'V:{source.pk}', 'División', da.division.nombre,
                             source.cantidad_asignada, source.cantidad_reservada, source.cantidad_consumida))
    return fuentes


def _fila(source, articulo, departamento, key, origen, division, asignado, reservado, consumido):
    saldo = asignado - reservado - consumido
    return dict(fuente=key, asignacion=source, articulo=articulo, departamento=departamento,
                origen=origen, division=division, cantidad_asignada=asignado,
                reservado=reservado, consumido=consumido, disponible=max(ZERO, saldo),
                requiere_revision=saldo < 0, fecha=source.fecha_asignacion,
                descripcion=getattr(source, 'descripcion', ''), transferible=origen == 'Directo')


def totales_departamento(departamento):
    totales = defaultdict(Decimal)
    for fila in fuentes_departamento(departamento):
        totales[fila['articulo'].pk] += fila['disponible']
    return dict(totales)


def validar_y_reservar(departamento, formularios):
    """Invocar bajo atomic y bloquear_departamento; revalidar contra el saldo actual."""
    fuentes = {fila['fuente']: fila for fila in fuentes_departamento(departamento)}
    acumulado = defaultdict(Decimal)
    detalles = []
    for form in formularios:
        if not form.cleaned_data or form.cleaned_data.get('DELETE'):
            continue
        detalle = form.save(commit=False)
        key = form.cleaned_data.get('origen')
        source = fuentes.get(key)
        if not source or source['articulo'].pk != detalle.articulo_id:
            raise ValidationError('La fuente seleccionada no pertenece al artículo y departamento autorizados.')
        acumulado[key] += Decimal(detalle.cantidad)
        if acumulado[key] > source['disponible']:
            raise ValidationError(mensaje_saldo(source, acumulado[key]))
        detalle.asignacion_directa = source['asignacion'] if key.startswith('D:') else None
        detalle.division_articulo_ubicacion = source['asignacion'] if key.startswith('V:') else None
        detalles.append(detalle)
    for key, cantidad in acumulado.items():
        if key.startswith('V:'):
            source = fuentes[key]['asignacion']
            source.cantidad_reservada += cantidad
            source.save(update_fields=['cantidad_reservada', 'fecha_actualizacion'])
    return detalles


def mensaje_saldo(fila, cantidad):
    articulo = fila['articulo']
    origen = 'asignación directa' if fila['origen'] == 'Directo' else f"división {fila['division']}"
    return (f"El artículo {articulo.codigo} - {articulo.nombre} tiene {fila['disponible']:g} unidades "
            f"disponibles en {origen} (asignación {fila['asignacion'].pk}). La cantidad solicitada es {cantidad:g}.")


def liberar_reservas_division(solicitud):
    """Cabecera ya bloqueada; usar solo una vez al cambiar a estado terminal."""
    for detalle in solicitud.detalles.select_related('detalle_requerimiento'):
        if not detalle.division_articulo_ubicacion_id:
            continue
        consumido = detalle.detalle_requerimiento.cantidad_despachada if detalle.detalle_requerimiento_id else 0
        restante = max(ZERO, Decimal(detalle.cantidad - consumido))
        source = DivisionArticuloUbicacion.objects.get(pk=detalle.division_articulo_ubicacion_id)
        if source.cantidad_reservada < restante:
            raise ValidationError('La reserva histórica de división requiere revisión; no se modificaron saldos.')
        source.cantidad_reservada -= restante
        source.save(update_fields=['cantidad_reservada', 'fecha_actualizacion'])


def saldo_global_sin_asignar(ingresado, directo, divisiones):
    return Decimal(ingresado) - Decimal(directo) - Decimal(divisiones)


def resumen_global_articulo(articulo):
    """Separar el presupuesto sin asignar de la disponibilidad ya asignada."""
    from .models import DetalleFactura, DivisionArticulo
    ingresado = Decimal(DetalleFactura.objects.filter(articulo=articulo, form1h__estado='confirmado')
                        .aggregate(total=Sum('cantidad'))['total'] or 0)
    directo = Decimal(AsignacionDetalleFactura.objects.filter(articulo=articulo)
                      .aggregate(total=Sum('cantidad_asignada'))['total'] or 0)
    divisiones = DivisionArticulo.objects.filter(articulo=articulo, activo=True)
    asignado_divisiones = divisiones.aggregate(total=Sum('cantidad_asignada'))['total'] or ZERO
    reservado_directo = consumido_directo = ZERO
    deptos = Departamento.objects.filter(asignaciondetallefactura__articulo=articulo).distinct()
    for departamento in deptos:
        for fila in fuentes_departamento(departamento):
            if fila['articulo'].pk == articulo.pk and fila['origen'] == 'Directo':
                reservado_directo += fila['reservado']
                consumido_directo += fila['consumido']
    ubicaciones = DivisionArticuloUbicacion.objects.filter(division_articulo__articulo=articulo, activo=True)
    reservado_division = ubicaciones.aggregate(total=Sum('cantidad_reservada'))['total'] or ZERO
    consumido_division = ubicaciones.aggregate(total=Sum('cantidad_consumida'))['total'] or ZERO
    sin_asignar = saldo_global_sin_asignar(ingresado, directo, asignado_divisiones)
    return dict(total_ingresado=ingresado, asignado_directo=directo, asignado_divisiones=asignado_divisiones,
                reservado=reservado_directo + reservado_division,
                consumido=consumido_directo + consumido_division,
                disponible_para_division=max(ZERO, sin_asignar), requiere_revision=sin_asignar < 0)
