"""Ingreso nuevo respaldado por un documento, separado de asignar stock existente.

No recibe existencias, incrementos acumulados ni opciones para saltar validaciones.
La única API es confirmar_ingreso_form1h; toda escritura pertenece a su transacción.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import models, transaction

from .models import (Articulo, DetalleFacturaDivision, DivisionAlmacen,
                     DivisionArticulo, Kardex, form1h)


@transaction.atomic
def confirmar_ingreso_form1h(formulario_id, filas, usuario):
    """Retorna False si ya se confirmó; un error revierte la operación completa.

    filas contiene (detalle_id, division_id, cantidad_a_distribuir). El ingreso
    autorizado se obtiene exclusivamente de los detalles bloqueados en la BD.
    """
    formulario = form1h.objects.select_for_update().get(pk=formulario_id)
    if formulario.estado == 'confirmado':
        return False
    if formulario.estado != 'borrador':
        raise ValidationError('Este Formulario 1H no se puede confirmar en su estado actual.')
    detalles = list(formulario.detalles.select_for_update().order_by('pk'))
    if not detalles:
        raise ValidationError('No puede confirmar un Formulario 1H sin detalles.')
    list(Articulo.objects.select_for_update().filter(
        pk__in={d.articulo_id for d in detalles}).order_by('pk'))
    por_id = {d.pk: d for d in detalles}
    distribucion = defaultdict(lambda: defaultdict(Decimal))
    for fila in filas:
        try:
            detalle_id, division_id, texto = fila
            detalle_id, division_id = int(detalle_id), int(division_id)
            cantidad = Decimal(texto)
        except (TypeError, ValueError, InvalidOperation):
            raise ValidationError('La distribución contiene filas inválidas o incompletas.')
        if (detalle_id not in por_id or not cantidad.is_finite() or cantidad <= 0
                or cantidad > por_id[detalle_id].cantidad):
            raise ValidationError('La distribución contiene detalles ajenos o cantidades inválidas.')
        distribucion[detalle_id][division_id] += cantidad
    divisiones_ids = {pk for fila in distribucion.values() for pk in fila}
    # La vigencia de las divisiones tampoco puede cambiar a mitad de la operación.
    divisiones = {d.pk: d for d in DivisionAlmacen.objects.select_for_update().filter(
        pk__in=divisiones_ids, activa=True).order_by('pk')}
    if set(divisiones) != divisiones_ids:
        raise ValidationError('Debe seleccionar divisiones activas y válidas.')

    incrementos = defaultdict(Decimal)
    registros = []
    for detalle in detalles:
        cantidades = distribucion.get(detalle.pk, {})
        if not cantidades or sum(cantidades.values(), Decimal('0')) != detalle.cantidad:
            raise ValidationError(f'La distribución del detalle {detalle.pk} debe sumar exactamente {detalle.cantidad}.')
        if detalle.asignaciones_division.exists():
            raise ValidationError('El borrador ya tiene una distribución histórica; requiere revisión.')
        ingresos = list(Kardex.objects.select_for_update().filter(
            fuente_factura=detalle, tipo_movimiento='INGRESO').order_by('pk'))
        if len(ingresos) != 1:
            raise ValidationError(f'El ingreso Kardex del detalle {detalle.pk} está ausente o duplicado; requiere revisión.')
        ingreso = ingresos[0]
        if (ingreso.cantidad != detalle.cantidad or ingreso.articulo_id != detalle.articulo_id
                or ingreso.estado != 'activo' or ingreso.movimiento_revertido_id
                or ingreso.fuente_asignacion_id or ingreso.fuente_despacho_id):
            raise ValidationError(f'El ingreso Kardex del detalle {detalle.pk} tiene cantidad, artículo o vínculos inconsistentes.')
        for division_id, cantidad in cantidades.items():
            registro = DetalleFacturaDivision(detalle_factura=detalle,
                division=divisiones[division_id], cantidad_asignada=cantidad, creado_por=usuario)
            registro.full_clean()
            registros.append(registro)
            incrementos[(detalle.articulo_id, division_id)] += cantidad

    # Una sola validación/escritura por artículo y división, aun con varias líneas.
    asignaciones = []
    for (articulo_id, division_id), cantidad in sorted(incrementos.items()):
        asignacion = DivisionArticulo.objects.select_for_update().filter(
            articulo_id=articulo_id, division_id=division_id).first()
        if asignacion is None:
            asignacion = DivisionArticulo(articulo_id=articulo_id,
                                          division_id=division_id, cantidad_asignada=0)
        asignacion.cantidad_asignada += cantidad
        asignacion.asignado_por = usuario
        asignacion.activo = True
        # Campos, clean estructural, unicidad y constraints. El límite de esta
        # operación ya se validó contra cada detalle, nunca contra el stock viejo.
        asignacion.full_clean()
        asignaciones.append(asignacion)

    formulario.estado = 'confirmado'
    formulario.save(update_fields=['estado', 'fecha_actualizacion'])
    for registro in registros:
        registro.save()
    for asignacion in asignaciones:
        # Persistencia exclusiva de este comando de dominio tras validar TODOS
        # los incrementos respaldados por registros creados aquí. No se expone un
        # save(skip_validation=True) reutilizable por otras rutas.
        models.Model.save(asignacion)
    return True
