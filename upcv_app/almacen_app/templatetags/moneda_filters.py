from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django import template
from django.utils import timezone


register = template.Library()


@register.filter
def quetzales(value):
    """Presenta un valor monetario con el formato Q1,234.56."""
    try:
        number = Decimal(value or 0)
    except (InvalidOperation, TypeError, ValueError):
        number = Decimal("0.00")
    return f"Q{number:,.2f}"


@register.filter
def fecha_corta(value):
    """Presenta objetos date/datetime con el formato corto dd/mm/yyyy."""
    if not value:
        return ""
    try:
        if isinstance(value, str):
            value = date.fromisoformat(value[:10])
        if isinstance(value, datetime):
            if timezone.is_aware(value):
                value = timezone.localtime(value)
            value = value.date()
        return value.strftime("%d/%m/%Y")
    except (AttributeError, TypeError, ValueError):
        return value
