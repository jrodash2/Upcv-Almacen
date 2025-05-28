from django.contrib import admin
from .models import (
    Proveedor, Departamento, Categoria, Ubicacion, UnidadDeMedida, 
    Articulo, Kardex, AsignacionDetalleFactura, Movimiento, FraseMotivacional, 
    Serie, form1h, DetalleFactura, Dependencia, Programa
)


# Configuración para el modelo Dependencia
class DependenciaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'activo', 'fecha_creacion', 'fecha_actualizacion')
    search_fields = ('nombre', 'descripcion')
    list_filter = ('activo', 'fecha_creacion', 'fecha_actualizacion')
    # Registrar los modelos en el administrador
admin.site.register(Dependencia, DependenciaAdmin)

# Configuración para el modelo Programa
class ProgramaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'activo', 'fecha_creacion', 'fecha_actualizacion')
    search_fields = ('nombre', 'descripcion')
    list_filter = ('activo', 'fecha_creacion', 'fecha_actualizacion')


admin.site.register(Programa, ProgramaAdmin)

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
    list_display = ( 'nombre','categoria', 'unidad_medida', 'ubicacion')
    search_fields = ( 'nombre',)
    list_filter = ('categoria',)


admin.site.register(Articulo, ArticuloAdmin)

# Registrar Serie
class SerieAdmin(admin.ModelAdmin):
    list_display = ('serie', 'numero_inicial', 'numero_final', 'numero_actual', 'activo')
    search_fields = ('serie',)
    list_filter = ('activo',)

admin.site.register(Serie, SerieAdmin)

# Registrar Kardex
class KardexAdmin(admin.ModelAdmin):
    list_display = ('articulo', 'tipo_movimiento', 'cantidad', 'fecha', 'observacion')
    search_fields = ('articulo__nombre',)
    list_filter = ('tipo_movimiento', 'fecha')
 
admin.site.register(Kardex, KardexAdmin)

# Registrar AsignacionDetalleFactura
class AsignacionDetalleFacturaAdmin(admin.ModelAdmin):
    list_display = ('get_articulo', 'cantidad_asignada', 'destino', 'fecha_asignacion')
    search_fields = ('detalle__articulo__nombre', 'destino__nombre')
    list_filter = ('fecha_asignacion', 'destino')

    def get_articulo(self, obj):
        return obj.detalle.articulo.nombre
    get_articulo.short_description = 'Artículo'

admin.site.register(AsignacionDetalleFactura, AsignacionDetalleFacturaAdmin)

# Registrar Movimiento
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ('articulo', 'tipo_movimiento', 'cantidad', 'fecha_movimiento', 'usuario', 'observacion')
    search_fields = ('articulo__nombre', 'usuario__username')
    list_filter = ('tipo_movimiento', 'fecha_movimiento', 'usuario')

admin.site.register(Movimiento, MovimientoAdmin)

# Registrar DetalleFactura
class DetalleFacturaInline(admin.TabularInline):
    model = DetalleFactura
    extra = 1  # Número de detalles de factura a mostrar como formularios vacíos al principio

# Registrar form1h
class form1hAdmin(admin.ModelAdmin):
    list_display = ('numero_factura', 'proveedor', 'fecha_factura', 'fecha_creacion', 'fecha_actualizacion')
    search_fields = ('numero_factura', 'proveedor__nombre')
    list_filter = ('fecha_creacion', 'fecha_actualizacion', 'proveedor')
    inlines = [DetalleFacturaInline]  # Agrega los detalles de la factura en el formulario de form1h

admin.site.register(form1h, form1hAdmin)
