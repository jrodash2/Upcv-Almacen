"""Reconocimiento de asignaciones espejo históricas, sin escribir ni crear salidas.

Solo un despacho directo completo, con salida Kardex vigente, un ingreso original
exclusivo de la división y una ubicación previa del mismo departamento. No se
reparte el consumo global entre divisiones ni se emparejan cantidades ambiguas.
"""
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from decimal import Decimal, InvalidOperation

from . import models as m

TIPO = 'consumo_historico_compartido'
ZERO = Decimal('0')


_lectura = ContextVar('lectura_consumos_historicos', default=None)


@contextmanager
def contexto_lectura():
    """Reutilizar consultas solo dentro de una lectura, nunca entre escrituras."""
    if _lectura.get() is not None:
        yield
        return
    token = _lectura.set({})
    try:
        yield
    finally:
        _lectura.reset(token)


def lectura_consumos(funcion):
    @wraps(funcion)
    def leer(*args, **kwargs):
        with contexto_lectura():
            return funcion(*args, **kwargs)
    return leer


def _vigente(movimiento):
    return (movimiento.estado == 'activo' and not movimiento.movimiento_revertido_id
            and not m.ReversionMovimiento.objects.filter(movimiento_original=movimiento).exists()
            and not movimiento.movimientos_reversion.exists())


def _validar(evidencia, ubicacion, persistida=False):
    try:
        directa = m.AsignacionDetalleFactura.objects.get(pk=evidencia['asignacion_directa_id'])
        salida = m.Kardex.objects.select_related('fuente_despacho__requerimiento').get(pk=evidencia['kardex_salida_id'])
        distribucion = m.DetalleFacturaDivision.objects.select_related('detalle_factura__form1h').get(pk=evidencia['distribucion_1h_id'])
        cantidad = Decimal(str(evidencia['cantidad']))
        extra = Decimal(str(evidencia['consumo_extra']))
    except (KeyError, ValueError, TypeError, InvalidOperation, m.AsignacionDetalleFactura.DoesNotExist,
            m.Kardex.DoesNotExist, m.DetalleFacturaDivision.DoesNotExist):
        return False
    da = ubicacion.division_articulo
    if (evidencia.get('ubicacion_id')!=ubicacion.pk or evidencia.get('asignacion_division_id')!=da.pk
            or evidencia.get('detalle_requerimiento_id')!=salida.fuente_despacho_id):
        return False
    if (not cantidad.is_finite() or not extra.is_finite() or cantidad <= 0
            or extra not in (ZERO, cantidad) or cantidad > directa.cantidad_asignada
            or (not persistida and (cantidad != directa.cantidad_asignada or ubicacion.cantidad_asignada < cantidad))):
        return False
    if persistida and extra == 0 and ubicacion.cantidad_consumida < cantidad:
        return False
    detalle = salida.fuente_despacho
    if (not detalle or salida.tipo_movimiento != 'SALIDA' or salida.cantidad != cantidad or not _vigente(salida)
            or salida.fuente_factura_id or salida.fuente_asignacion_id not in (None, directa.pk)
            or salida.articulo_id != da.articulo_id or directa.articulo_id != da.articulo_id
            or directa.destino_id != ubicacion.ubicacion_id
            or detalle.articulo_id != da.articulo_id or detalle.requerimiento.departamento_id != ubicacion.ubicacion_id
            or detalle.cantidad != cantidad or detalle.cantidad_despachada != cantidad
            or detalle.estado != 'despachado'
            or directa.fecha_asignacion > salida.fecha or ubicacion.fecha_asignacion > salida.fecha):
        return False
    origen = m.DetalleSolicitudRequerimiento.objects.filter(detalle_requerimiento=detalle,
        asignacion_directa=directa, division_articulo_ubicacion__isnull=True,
        articulo_id=da.articulo_id, solicitud__estado='convertida',
        solicitud__requerimiento_id=detalle.requerimiento_id,
        solicitud__departamento_id=ubicacion.ubicacion_id, cantidad=cantidad).first()
    if not origen:
        return False
    ingreso = distribucion.detalle_factura
    if (distribucion.division_id != da.division_id or ingreso.articulo_id != da.articulo_id
            or ingreso.form1h.estado != 'confirmado' or distribucion.cantidad_asignada != cantidad
            or ingreso.cantidad != cantidad or distribucion.fecha_creacion > directa.fecha_asignacion
            or ingreso.asignaciones_division.exclude(pk=distribucion.pk).exists()):
        return False
    entradas = list(m.Kardex.objects.filter(fuente_factura=ingreso,tipo_movimiento='INGRESO'))
    if len(entradas) != 1 or entradas[0].cantidad != cantidad or not _vigente(entradas[0]):
        return False
    entrada = entradas[0]
    if entrada.fecha > directa.fecha_asignacion:
        return False
    # Antes de esa asignación no debe haber otro lote que haga ambiguo el origen.
    if m.Kardex.objects.filter(articulo_id=da.articulo_id,tipo_movimiento='INGRESO',
            fecha__lte=directa.fecha_asignacion).exclude(pk=entrada.pk).exists():
        return False
    if not persistida:
        if directa.detalles_solicitud.exclude(pk=origen.pk).exists():
            return False
        # Los consumos posteriores, enlazados realmente a esta ubicación, siguen
        # viviendo en el contador original. Solo se añade el consumo que faltaba.
        despachado_ubicacion = sum((Decimal(d.detalle_requerimiento.cantidad_despachada)
            for d in ubicacion.detalles_solicitud.select_related('detalle_requerimiento')
            if d.detalle_requerimiento_id), ZERO)
        sin_origen = ubicacion.cantidad_consumida - despachado_ubicacion
        if sin_origen not in (ZERO, cantidad):
            return False
        if extra != (cantidad if sin_origen == 0 else ZERO):
            return False
    return True


def _reconocimientos_consumo(articulo_id):
    ubicaciones = list(m.DivisionArticuloUbicacion.objects.filter(
        division_articulo__articulo_id=articulo_id).select_related('division_articulo'))
    if not ubicaciones:
        return []
    por_id = {u.pk:u for u in ubicaciones}
    registros = list(m.LiberacionStockDivision.objects.filter(articulo_id=articulo_id)
                     .values('asignacion_id','procedencias'))
    divisiones_con_liberaciones = {r['asignacion_id'] for r in registros}
    confirmados = {}
    for registro in registros:
        for dato in registro['procedencias']:
            if not isinstance(dato,dict) or dato.get('tipo') != TIPO:
                continue
            ubicacion = por_id.get(dato.get('ubicacion_id'))
            if (ubicacion and registro['asignacion_id'] == ubicacion.division_articulo_id
                    and _validar(dato,ubicacion,persistida=True)):
                confirmados[(ubicacion.pk,dato['kardex_salida_id'])]=dato
    candidatos = []
    for ubicacion in ubicaciones:
        if ubicacion.division_articulo_id in divisiones_con_liberaciones:
            continue  # No reinterpretar liberaciones antiguas que carecen de enlace auditable.
        directas = m.AsignacionDetalleFactura.objects.filter(articulo_id=articulo_id,
            destino_id=ubicacion.ubicacion_id,cantidad_asignada__gt=0,
            cantidad_asignada__lte=ubicacion.cantidad_asignada)
        for directa in directas:
            origenes = list(directa.detalles_solicitud.select_related('detalle_requerimiento'))
            if len(origenes)!=1 or not origenes[0].detalle_requerimiento_id:
                continue
            salidas = list(m.Kardex.objects.filter(fuente_despacho_id=origenes[0].detalle_requerimiento_id,
                tipo_movimiento='SALIDA'))
            if len(salidas)!=1:
                continue
            distribuciones = m.DetalleFacturaDivision.objects.filter(division_id=ubicacion.division_articulo.division_id,
                detalle_factura__articulo_id=articulo_id,cantidad_asignada=directa.cantidad_asignada,
                fecha_creacion__lte=directa.fecha_asignacion)
            validos=[]
            for distribucion in distribuciones:
                consumo_enlazado = sum((Decimal(d.detalle_requerimiento.cantidad_despachada)
                    for d in ubicacion.detalles_solicitud.select_related('detalle_requerimiento')
                    if d.detalle_requerimiento_id),ZERO)
                base=ubicacion.cantidad_consumida-consumo_enlazado
                dato=dict(tipo=TIPO,ubicacion_id=ubicacion.pk,asignacion_division_id=ubicacion.division_articulo_id,
                    asignacion_directa_id=directa.pk,kardex_salida_id=salidas[0].pk,
                    detalle_requerimiento_id=origenes[0].detalle_requerimiento_id,
                    distribucion_1h_id=distribucion.pk,cantidad=str(directa.cantidad_asignada),
                    consumo_extra=str(directa.cantidad_asignada if base==0 else ZERO))
                if _validar(dato,ubicacion):
                    validos.append(dato)
            if len(validos)==1:
                candidatos.append(validos[0])
    # Una salida no se acredita a dos ubicaciones; tampoco se elige arbitrariamente
    # entre dos posibles despachos del mismo registro histórico.
    por_salida=Counter(c['kardex_salida_id'] for c in candidatos)
    por_ubicacion=Counter(c['ubicacion_id'] for c in candidatos)
    for dato in candidatos:
        key=(dato['ubicacion_id'],dato['kardex_salida_id'])
        if por_salida[dato['kardex_salida_id']]==1 and por_ubicacion[dato['ubicacion_id']]==1:
            confirmados.setdefault(key,dato)
    salidas_confirmadas=Counter(d['kardex_salida_id'] for d in confirmados.values())
    return [d for d in confirmados.values() if salidas_confirmadas[d['kardex_salida_id']]==1]


def reconocimientos_consumo(articulo_id):
    cache = _lectura.get()
    if cache is None:
        return _reconocimientos_consumo(articulo_id)
    if articulo_id not in cache:
        cache[articulo_id] = _reconocimientos_consumo(articulo_id)
    return cache[articulo_id]


def extra_ubicacion(ubicacion):
    if not ubicacion.pk:
        return ZERO
    return sum((Decimal(d['consumo_extra']) for d in reconocimientos_consumo(ubicacion.division_articulo.articulo_id)
                if d['ubicacion_id']==ubicacion.pk),ZERO)
