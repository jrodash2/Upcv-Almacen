from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User

# Modelo de Proveedor
class Proveedor(models.Model):
    nombre = models.CharField(max_length=255)
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    nit = models.CharField(max_length=50, unique=True, null=True, blank=True)  # NIT del proveedor
    fecha_creacion = models.DateTimeField(auto_now_add=True)  # Fecha de creación automática
    fecha_actualizacion = models.DateTimeField(auto_now=True)  # Fecha de actualización automática

    def __str__(self):
        return self.nombre


# Modelo de Departamento
class Departamento(models.Model):
    id_departamento = models.CharField(max_length=50, unique=True)  # ID personalizado del departamento
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)  # Fecha de creación automática
    fecha_actualizacion = models.DateTimeField(auto_now=True)  # Fecha de actualización automática

    def __str__(self):
        return self.nombre


# Modelo de Categoría
class Categoria(models.Model):
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)  # Fecha de creación automática
    fecha_actualizacion = models.DateTimeField(auto_now=True)  # Fecha de actualización automática

    def __str__(self):
        return self.nombre
    

class Ubicacion(models.Model):
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)  # Fecha de creación automática
    fecha_actualizacion = models.DateTimeField(auto_now=True)  # Fecha de actualización automática
    activo = models.BooleanField(default=True)  # Campo para determinar si la ubicación está activa

    def __str__(self):
        return self.nombre


# Modelo de Unidad de Medida
class UnidadDeMedida(models.Model):
    nombre = models.CharField(max_length=50)
    simbolo = models.CharField(max_length=10)

    def __str__(self):
        return f'{self.nombre} ({self.simbolo})'

class Articulo(models.Model):
    ESTADOS = [
        ('DISP', 'Disponible'),
        ('AGOT', 'Agotado'),
        ('REPO', 'En Reposición'),
        ('DESC', 'Descontinuado'),
    ]
    
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)
    unidad_medida = models.ForeignKey(UnidadDeMedida, on_delete=models.SET_NULL, null=True, blank=True)
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.SET_NULL, null=True, blank=True)
    estado = models.CharField(max_length=4, choices=ESTADOS, default='DISP')

    def __str__(self):
        return f'{self.nombre} ({self.codigo})'

class Ingreso(models.Model):
    articulo = models.ForeignKey(Articulo, related_name='ingresos', on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    fecha_ingreso = models.DateTimeField(auto_now_add=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    numero_factura = models.CharField(max_length=50, unique=True)  # Número de factura
    fecha_factura = models.DateTimeField(null=True, blank=True)  # Fecha de la factura
    numero_detalles_factura = models.PositiveIntegerField(default=1)  # Número de detalles (renglones)
    cantidad_renglon = models.PositiveIntegerField()  # Cantidad por renglón de factura
    precio_total_ingreso = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Total de ingreso calculado
    fecha_creacion = models.DateTimeField(auto_now_add=True)  # Fecha de creación
    fecha_actualizacion = models.DateTimeField(auto_now=True)  # Fecha de actualización

    def save(self, *args, **kwargs):
        # Calcular el precio total de ingreso automáticamente
        self.precio_total_ingreso = self.articulo.precio * self.cantidad
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Ingreso de {self.cantidad} unidades de {self.articulo.nombre} (Factura: {self.numero_factura})'


# Modelo de Kardex (Movimientos de Inventario)
class Kardex(models.Model):
    TIPO_MOVIMIENTO = [
        ('INGRESO', 'Ingreso'),
        ('SALIDA', 'Salida'),
    ]
    
    articulo = models.ForeignKey(Articulo, related_name='kardex', on_delete=models.CASCADE)
    tipo_movimiento = models.CharField(max_length=10, choices=TIPO_MOVIMIENTO)
    cantidad = models.PositiveIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)
    observacion = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.tipo_movimiento} de {self.cantidad} unidades de {self.articulo.nombre}'

# Modelo de Asignación (Asignación de artículos)
class Asignacion(models.Model):
    articulo = models.ForeignKey(Articulo, related_name='asignaciones', on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    destino = models.ForeignKey(Departamento, related_name='asignaciones', on_delete=models.CASCADE)
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    descripcion = models.TextField(blank=True, null=True)  # Descripción de la asignación
    id_ingreso = models.ForeignKey(Ingreso, related_name='asignaciones', on_delete=models.SET_NULL, null=True, blank=True)  # Relación con Ingreso

    def save(self, *args, **kwargs):
        # Verificar si hay suficiente stock antes de guardar
        if self.cantidad > self.articulo.stock:
            raise ValidationError(f"No hay suficiente stock de {self.articulo.nombre} para asignar.")
        
        # Reducir el stock del artículo al momento de la asignación
        self.articulo.stock -= self.cantidad
        self.articulo.save()

        super(Asignacion, self).save(*args, **kwargs)

    def __str__(self):
        return f'Asignación de {self.cantidad} unidades de {self.articulo.nombre} a {self.destino.nombre}'


# Modelo de Movimiento (Registra los movimientos internos, transferencias, etc.)
class Movimiento(models.Model):
    TIPO_MOVIMIENTO = [
        ('ENTRADA', 'Entrada'),
        ('SALIDA', 'Salida'),
        ('TRANSFERENCIA', 'Transferencia'),
    ]
    
    articulo = models.ForeignKey(Articulo, related_name='movimientos', on_delete=models.CASCADE)
    tipo_movimiento = models.CharField(max_length=13, choices=TIPO_MOVIMIENTO)
    cantidad = models.PositiveIntegerField()
    fecha_movimiento = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    observacion = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.tipo_movimiento} de {self.cantidad} unidades de {self.articulo.nombre}'

