from django import template

register = template.Library()

@register.filter
def dict_get(d, key):
    try:
        return d.get(key)
    except Exception:
        return ''


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def get_item(dictionary, key):
    try:
        return dictionary.get(str(key))  # key convertido a string, pues stock_dict tiene claves string
    except Exception:
        return 0

@register.filter
def cantidad_limpia(value):
    # Backward-compatible alias; presentation now preserves fractional precision.
    from almacen_app.formatos_cantidades import cantidad_formato
    return cantidad_formato(value)
