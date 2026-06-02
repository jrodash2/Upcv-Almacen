from django import template

register = template.Library()


@register.simple_tag
def estado_badge_class(estado):
    estado = str(estado or "").lower().strip()

    mapa = {
        "pendiente": "estado-pendiente",

        "en_proceso": "estado-en-proceso",
        "proceso": "estado-en-proceso",
        "en proceso": "estado-en-proceso",
        "enviado": "estado-en-proceso",
        "parcial": "estado-en-proceso",

        "aprobado": "estado-aprobado",
        "aprobada": "estado-aprobado",
        "confirmado": "estado-aprobado",

        "convertido": "estado-convertida",
        "convertida": "estado-convertida",

        "despachado": "estado-despachado",
        "despachada": "estado-despachado",

        "finalizado": "estado-finalizado",
        "finalizada": "estado-finalizado",

        "entregado": "estado-entregado",
        "entregada": "estado-entregado",

        "rechazado": "estado-rechazado",
        "rechazada": "estado-rechazado",

        "anulado": "estado-rechazado",
        "anulada": "estado-rechazado",

        "cancelado": "estado-rechazado",
        "cancelada": "estado-rechazado",

        "borrador": "estado-borrador",
    }

    return mapa.get(estado, "estado-default")
