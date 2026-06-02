from django import template

register = template.Library()


@register.simple_tag
def estado_badge_class(estado):
    estado = str(estado or '').lower()
    mapa = {
        'pendiente': 'estado-pendiente',
        'en_proceso': 'estado-en-proceso',
        'proceso': 'estado-proceso',
        'enviado': 'estado-en-proceso',
        'parcial': 'estado-en-proceso',
        'aprobado': 'estado-aprobado',
        'aprobada': 'estado-aprobado',
        'convertido': 'estado-convertido',
        'convertida': 'estado-convertida',
        'despachado': 'estado-despachado',
        'finalizado': 'estado-finalizado',
        'entregado': 'estado-entregado',
        'rechazado': 'estado-rechazado',
        'rechazada': 'estado-rechazado',
        'anulado': 'estado-anulado',
        'cancelado': 'estado-cancelado',
        'borrador': 'estado-borrador',
        'confirmado': 'estado-aprobado',
    }
    return mapa.get(estado, 'estado-default')
