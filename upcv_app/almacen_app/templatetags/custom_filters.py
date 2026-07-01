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
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return value
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}".rstrip('0').rstrip('.')


@register.filter
def quetzales(value):
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0
    return f"Q{number:,.2f}"
