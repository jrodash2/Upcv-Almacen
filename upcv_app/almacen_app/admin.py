from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Proveedor, Departamento, Categoria, Ubicacion, UnidadDeMedida, Articulo, Ingreso, Kardex, Asignacion, Movimiento, FraseMotivacional

# Registrar Proveedor
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'direccion', 'telefono', 'email', 'nit', 'fecha_creacion', 'fecha_actualizacion')
    search_fields = ('nombre', 'nit', 'email')
    list_filter = ('fecha_creacion', 'fecha_actualizacion')

admin.site.register(Proveedor, ProveedorAdmin)

# Crea una clase que personaliza la vista en el admin
class FraseMotivacionalAdmin(admin.ModelAdmin):
    list_display = ('frase', 'personaje')  # Qué campos mostrar en la lista
    search_fields = ('frase', 'personaje')  # Habilitar búsqueda por estos campos
    ordering = ('personaje',)  # Ordenar por el campo 'personaje'

# Registra el modelo con la clase personalizada
admin.site.register(FraseMotivacional, FraseMotivacionalAdmin)

# Registrar Departamento
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('id_departamento', 'nombre', 'descripcion', 'fecha_creacion', 'fecha_actualizacion')
    search_fields = ('nombre', 'id_departamento')
    list_filter = ('fecha_creacion', 'fecha_actualizacion')

admin.site.register(Departamento, DepartamentoAdmin)

# Registrar Categoria
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'fecha_creacion', 'fecha_actualizacion')
    search_fields = ('nombre',)
    list_filter = ('fecha_creacion', 'fecha_actualizacion')

admin.site.register(Categoria, CategoriaAdmin)

# Registrar Ubicacion
class UbicacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'fecha_creacion', 'fecha_actualizacion', 'activo')
    search_fields = ('nombre',)
    list_filter = ('fecha_creacion', 'fecha_actualizacion')

admin.site.register(Ubicacion, UbicacionAdmin)

# Registrar UnidadDeMedida
class UnidadDeMedidaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'simbolo')
    search_fields = ('nombre', 'simbolo')

admin.site.register(UnidadDeMedida, UnidadDeMedidaAdmin)

# Registrar Articulo
class ArticuloAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'stock', 'precio', 'estado', 'proveedor', 'categoria', 'unidad_medida', 'ubicacion')
    search_fields = ('codigo', 'nombre')
    list_filter = ('estado', 'proveedor', 'categoria')
    list_editable = ('estado', 'stock')

admin.site.register(Articulo, ArticuloAdmin)

# Registrar Ingreso
class IngresoAdmin(admin.ModelAdmin):
    list_display = ('articulo', 'cantidad', 'fecha_ingreso', 'numero_factura', 'fecha_factura', 'precio_total_ingreso', 'fecha_creacion', 'fecha_actualizacion')
    search_fields = ('numero_factura',)
    list_filter = ('fecha_ingreso', 'fecha_factura', 'proveedor')

admin.site.register(Ingreso, IngresoAdmin)

# Registrar Kardex
class KardexAdmin(admin.ModelAdmin):
    list_display = ('articulo', 'tipo_movimiento', 'cantidad', 'fecha', 'observacion')
    search_fields = ('articulo__nombre',)
    list_filter = ('tipo_movimiento', 'fecha')

admin.site.register(Kardex, KardexAdmin)

# Registrar Asignacion
class AsignacionAdmin(admin.ModelAdmin):
    list_display = ('articulo', 'cantidad', 'destino', 'fecha_asignacion')
    search_fields = ('articulo__nombre', 'destino__nombre')
    list_filter = ('fecha_asignacion', 'destino')

admin.site.register(Asignacion, AsignacionAdmin)

# Registrar Movimiento
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ('articulo', 'tipo_movimiento', 'cantidad', 'fecha_movimiento', 'usuario', 'observacion')
    search_fields = ('articulo__nombre', 'usuario__username')
    list_filter = ('tipo_movimiento', 'fecha_movimiento', 'usuario')

admin.site.register(Movimiento, MovimientoAdmin)
