from django import template

register = template.Library()


@register.simple_tag
def estado_badge_class(estado):
    estado = str(estado or "").lower().strip()

    mapa = {
        "pendiente": "badge badge-light-warning estado-pendiente",

        "en_proceso": "badge badge-light-info estado-en-proceso",
        "proceso": "badge badge-light-info estado-en-proceso",
        "en proceso": "badge badge-light-info estado-en-proceso",
        "enviado": "badge badge-light-info estado-en-proceso",
        "parcial": "badge badge-light-info estado-en-proceso",

        "aprobado": "badge badge-light-primary estado-aprobado",
        "aprobada": "badge badge-light-primary estado-aprobado",
        "confirmado": "badge badge-light-primary estado-aprobado",

        "convertido": "badge badge-light-success estado-convertida",
        "convertida": "badge badge-light-success estado-convertida",

        "despachado": "badge badge-light-success estado-despachado",
        "despachada": "badge badge-light-success estado-despachado",

        "finalizado": "badge badge-light-success estado-finalizado",
        "finalizada": "badge badge-light-success estado-finalizado",

        "entregado": "badge badge-light-success estado-entregado",
        "entregada": "badge badge-light-success estado-entregado",

        "rechazado": "badge badge-light-danger estado-rechazado",
        "rechazada": "badge badge-light-danger estado-rechazado",

        "anulado": "badge badge-light-danger estado-rechazado",
        "anulada": "badge badge-light-danger estado-rechazado",

        "cancelado": "badge badge-light-danger estado-rechazado",
        "cancelada": "badge badge-light-danger estado-rechazado",

        "borrador": "badge badge-light-secondary estado-borrador",
    }

    return mapa.get(estado, "badge badge-light-secondary estado-default")
