"""Formato exclusivamente visual; no redondea ni modifica las cantidades."""
from decimal import Decimal, InvalidOperation


def cantidad_formato(value):
    if value is None or value == '':
        return '0'
    try:
        numero = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value
    if not numero.is_finite():
        return value
    if not numero:
        return '0'
    texto = format(numero, ',f')
    return texto.rstrip('0').rstrip('.') if '.' in texto else texto


def formato_excel_cantidad(value):
    """Solo la máscara de celda: conservar el valor numérico y toda su fracción."""
    try:
        numero = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return 'General'
    if not numero.is_finite():
        return 'General'
    fraccion = format(numero, 'f').partition('.')[2].rstrip('0')
    return '#,##0' + ('.' + '#' * len(fraccion) if fraccion else '')
