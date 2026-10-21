from django import template
from almacen_app.formatos_cantidades import cantidad_formato

register = template.Library()
register.filter('cantidad_formato', cantidad_formato)
