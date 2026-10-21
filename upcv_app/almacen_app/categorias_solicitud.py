"""Tipos de solicitud y etiquetas reales del catálogo, sin modificar sus registros."""
import unicodedata

from .models import Categoria

CATEGORIAS_POR_TIPO = {
    'bienes': frozenset(('bien', 'bienes')),
    'suministros': frozenset(('suministro', 'suministros')),
    'insumos': frozenset(('insumo', 'insumos')),
}
MENSAJE_TIPOS = 'Debe seleccionar al menos un tipo de solicitud: Bienes, Suministros o Insumos.'
MENSAJE_JUSTIFICACION = 'Debe ingresar una justificación para crear la solicitud.'


def tipo_categoria(nombre):
    normalizado = ''.join(c for c in unicodedata.normalize('NFKD', nombre or '')
                          if not unicodedata.combining(c)).strip().casefold()
    return next((tipo for tipo, nombres in CATEGORIAS_POR_TIPO.items() if normalizado in nombres), None)


def filtrar_por_tipos(articulos, tipos):
    seleccionados = set(tipos or ()) & CATEGORIAS_POR_TIPO.keys()
    if not seleccionados:
        return articulos.none()
    ids = [categoria.pk for categoria in Categoria.objects.only('id', 'nombre')
           if tipo_categoria(categoria.nombre) in seleccionados]
    return articulos.filter(categoria_id__in=ids)
