from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import pre_save
from django.dispatch import receiver

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

    nombre = models.CharField(max_length=255)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)
    unidad_medida = models.ForeignKey(UnidadDeMedida, on_delete=models.SET_NULL, null=True, blank=True)
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.SET_NULL, null=True, blank=True)


    def __str__(self):
        return f'{self.nombre} ({self.categoria})'

class Serie(models.Model):
    serie = models.CharField(max_length=50)  # Serie que puede contener letras
    numero_inicial = models.PositiveIntegerField()  # Número inicial
    numero_final = models.PositiveIntegerField()  # Número final
    activo = models.BooleanField(default=True)  # Campo de activo
    numero_actual = models.PositiveIntegerField(default=0)  # Número actual para seguimiento

    def __str__(self):
        return f'Serie {self.serie} ({self.numero_inicial} - {self.numero_final})'

# Modelo DetalleFactura
class DetalleFactura(models.Model):
    form1h = models.ForeignKey('form1h', related_name='detalles', on_delete=models.CASCADE)  # Relación con form1h
    articulo = models.ForeignKey(Articulo, related_name='detalles_factura', on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    precio_total = models.DecimalField(max_digits=10, decimal_places=2)
    id_linea = models.PositiveIntegerField(unique=True)  # Identificador único de la línea

    def save(self, *args, **kwargs):
        # Calcular el precio total por línea
        self.precio_total = self.precio_unitario * self.cantidad
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Detalle de {self.articulo.nombre} (Linea {self.id_linea})'



# Modelo Form1h (Factura)
class form1h(models.Model):
    articulo = models.ForeignKey(Articulo, related_name='form1h', on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    fecha_ingreso = models.DateTimeField(auto_now_add=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    numero_factura = models.CharField(max_length=50, unique=True)  # Número de factura
    renglon = models.PositiveIntegerField()  # Renglon
    orden_compra = models.CharField(max_length=50, null=True, blank=True)  # Orden de compra
    nit_proveedor = models.CharField(max_length=50, null=True, blank=True)  # NIT del proveedor
    proveedor_nombre = models.CharField(max_length=255, null=True, blank=True)  # Nombre del proveedor
    telefono_proveedor = models.CharField(max_length=20, null=True, blank=True)  # Teléfono del proveedor
    direccion_proveedor = models.CharField(max_length=255, null=True, blank=True)  # Dirección del proveedor
    patente = models.CharField(max_length=50, null=True, blank=True)  # Patente
    fecha_factura = models.DateField(null=True, blank=True)  # Fecha de la factura
    precio_total_ingreso = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Total de ingreso calculado
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Precio unitario del artículo
    fecha_creacion = models.DateTimeField(auto_now_add=True)  # Fecha de creación
    fecha_actualizacion = models.DateTimeField(auto_now=True)  # Fecha de actualización
    serie = models.ForeignKey('Serie', on_delete=models.SET_NULL, null=True, blank=True)  # Relación con Serie
    numero_serie = models.PositiveIntegerField(null=True, blank=True)  # Número de serie actual

    def save(self, *args, **kwargs):
        # Calcular el precio total de ingreso automáticamente
        if self.articulo:
            self.precio_unitario = self.articulo.precio  # Asignamos el precio del artículo
        self.precio_total_ingreso = self.precio_unitario * self.cantidad

        # Asignar automáticamente un número de serie de la serie activa
        if not self.serie:
            serie_activa = Serie.objects.filter(activo=True).first()
            if serie_activa and serie_activa.numero_actual < serie_activa.numero_final:
                self.serie = serie_activa
                self.numero_serie = serie_activa.numero_inicial + serie_activa.numero_actual
                serie_activa.numero_actual += 1
                serie_activa.save()
            else:
                raise ValidationError("No hay series activas disponibles o se ha alcanzado el número final de la serie activa.")

        super().save(*args, **kwargs)

    def numero_serie_completo(self):
        return f'{self.serie.serie}-{self.numero_serie}' if self.serie else None

    def __str__(self):
        return f'Ingreso de {self.cantidad} unidades de {self.articulo.nombre} (Factura: {self.numero_factura})'

# Signal para actualizar el NIT y proveedor
@receiver(pre_save, sender=form1h)
def actualizar_proveedor(sender, instance, **kwargs):
    if instance.nit_proveedor:
        # Buscar el proveedor por NIT
        proveedor = Proveedor.objects.filter(nit=instance.nit_proveedor).first()
        
        if proveedor:
            # Asignar el proveedor al campo proveedor
            instance.proveedor = proveedor
        else:
            # Si no se encuentra el proveedor, puedes lanzar un error o dejar el proveedor como null
            instance.proveedor = None




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
    id_ingreso = models.ForeignKey(form1h, related_name='asignaciones', on_delete=models.SET_NULL, null=True, blank=True)  # Relación con Ingreso

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

class FraseMotivacional(models.Model):
    frase = models.CharField(max_length=500)
    personaje = models.CharField(max_length=100)

    def __str__(self):
        return f'{self.personaje}: {self.frase}'