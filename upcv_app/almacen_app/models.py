from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.db.models import Sum
from django.db.models.signals import post_save


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
    
# Modelo de Categoría
class Categoria(models.Model):
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)  # Fecha de creación automática
    fecha_actualizacion = models.DateTimeField(auto_now=True)  # Fecha de actualización automática

    def __str__(self):
        return self.nombre
    
class Articulo(models.Model):

    nombre = models.CharField(max_length=255)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)
    unidad_medida = models.ForeignKey(UnidadDeMedida, on_delete=models.SET_NULL, null=True, blank=True)
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.SET_NULL, null=True, blank=True)
    activo = models.BooleanField(default=True) # Campo para determinar si el artículo está activo

    def __str__(self):
        return f'{self.nombre} ({self.categoria})'

# Modelo de Departamento
class Departamento(models.Model):
    id_departamento = models.CharField(max_length=50, unique=True)  # ID personalizado del departamento
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)  # Fecha de creación automática
    fecha_actualizacion = models.DateTimeField(auto_now=True)  # Fecha de actualización automática
    activo = models.BooleanField(default=True) # Campo para determinar si el departamento está activo
    
    def __str__(self):
        return self.nombre

class UsuarioDepartamento(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    departamento = models.ForeignKey(Departamento, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('usuario', 'departamento')

    def __str__(self):
        return f'{self.usuario.username} - {self.departamento.nombre}' 
 
class DetalleFactura(models.Model):
    form1h = models.ForeignKey('form1h', related_name='detalles', on_delete=models.CASCADE)
    articulo = models.ForeignKey(Articulo, related_name='detalles_factura', on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    precio_total = models.DecimalField(max_digits=10, decimal_places=2)
    id_linea = models.PositiveIntegerField()
    renglon = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['form1h', 'id_linea'], name='unique_linea_per_form1h')
        ]

    def save(self, *args, **kwargs):
        # Calcular el precio total por línea
        self.precio_total = self.precio_unitario * self.cantidad
        super().save(*args, **kwargs)

    def __str__(self):
        stock_total = DetalleFactura.objects.filter(articulo=self.articulo).aggregate(models.Sum('cantidad'))['cantidad__sum'] or 0
        return f'Detalle de {self.articulo.nombre} (Stock total: {stock_total})'


class AsignacionDetalleFactura(models.Model):
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE)
    cantidad_asignada = models.PositiveIntegerField()
    destino = models.ForeignKey(Departamento, on_delete=models.CASCADE)
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    descripcion = models.TextField(null=True, blank=True)

    def clean(self):
        super().clean()
        if self.articulo is None:
            raise ValidationError("El campo artículo es obligatorio.")
        
        # Calcular el stock total disponible desde DetalleFactura
        total_stock = DetalleFactura.objects.filter(articulo=self.articulo).aggregate(
            total=Sum('cantidad'))['total'] or 0
        total_asignado = AsignacionDetalleFactura.objects.filter(articulo=self.articulo).aggregate(
            total=Sum('cantidad_asignada'))['total'] or 0
        disponible = total_stock - total_asignado

        if self.cantidad_asignada > disponible:
            raise ValidationError("La cantidad asignada no puede ser mayor al stock disponible.")

    def __str__(self):
        return f"{self.cantidad_asignada} de {self.articulo.nombre} a {self.destino.nombre}"

   

class Serie(models.Model):
    serie = models.CharField(max_length=50)  # Serie que puede contener letras
    numero_inicial = models.PositiveIntegerField()  # Número inicial
    numero_final = models.PositiveIntegerField()  # Número final
    activo = models.BooleanField(default=True)  # Campo de activo
    numero_actual = models.PositiveIntegerField(default=0)  # Número actual para seguimiento

    def __str__(self):
        return f'Serie {self.serie} ({self.numero_inicial} - {self.numero_final})'


class Dependencia(models.Model):
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)  # Fecha de creación automática
    fecha_actualizacion = models.DateTimeField(auto_now=True)  # Fecha de actualización automática
    activo = models.BooleanField(default=True)  # Campo para determinar si la ubicación está activa

    def __str__(self):
        return self.nombre


class LineaLibre(models.Model):
    id_linea = models.IntegerField(unique=True)


class Programa(models.Model):
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)  # Fecha de creación automática
    fecha_actualizacion = models.DateTimeField(auto_now=True)  # Fecha de actualización automática
    activo = models.BooleanField(default=True)  # Campo para determinar si la ubicación está activa

    def __str__(self):
        return self.nombre


    
from django.db import models

class LineaReservada(models.Model):
    form1h = models.ForeignKey('form1h', on_delete=models.CASCADE)
    numero_linea = models.IntegerField(unique=True)
    disponible = models.BooleanField(default=True)

    def __str__(self):
        return f"Línea {self.numero_linea} para Formulario {self.form1h.id}"

    
class form1h(models.Model):
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('confirmado', 'Confirmado'),
    ]

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    nit_proveedor = models.CharField(max_length=50, null=True, blank=True)
    proveedor_nombre = models.CharField(max_length=255, null=True, blank=True)
    telefono_proveedor = models.CharField(max_length=20, null=True, blank=True)
    direccion_proveedor = models.CharField(max_length=255, null=True, blank=True)
    numero_factura = models.CharField(max_length=50, unique=True)
    dependencia = models.ForeignKey(Dependencia, on_delete=models.SET_NULL, null=True, blank=True)
    programa = models.ForeignKey(Programa, on_delete=models.SET_NULL, null=True, blank=True)
    orden_compra = models.CharField(max_length=50, null=True, blank=True)
    patente = models.CharField(max_length=50, null=True, blank=True)
    fecha_factura = models.DateField(null=True, blank=True)
    fecha_ingreso = models.DateField(auto_now_add=True)
    serie = models.ForeignKey(Serie, on_delete=models.SET_NULL, null=True, blank=True)
    numero_serie = models.PositiveIntegerField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.numero_serie:
            serie_activa = Serie.objects.filter(activo=True).order_by('numero_inicial').first()

            if not serie_activa:
                raise ValidationError("No hay series activas disponibles para asignar un número.")

            self.serie = serie_activa

            # Obtener el último número asignado dentro de la serie activa
            ultimo_numero = form1h.objects.filter(serie=serie_activa).aggregate(models.Max('numero_serie'))['numero_serie__max']

            # Si hay números asignados, continuar desde el último
            if ultimo_numero is not None:
                nuevo_numero = ultimo_numero + 1
            else:
                nuevo_numero = serie_activa.numero_inicial

            # Verificar que el número no supere el límite de la serie
            if nuevo_numero > serie_activa.numero_final:
                raise ValidationError(f"La serie '{serie_activa.serie}' ha alcanzado su límite. No se pueden asignar más números.")

            self.numero_serie = nuevo_numero
            serie_activa.numero_actual = nuevo_numero
            serie_activa.save()

        super().save(*args, **kwargs)

    def calcular_total_factura(self):
        return self.detalles.aggregate(total=models.Sum('precio_total'))['total'] or 0
    
    @property
    def numero_serie_completo(self):
        if self.serie:
            return f"{self.serie.serie}{self.numero_serie:04d}"  # Ejemplo: A0001, A0002...
        return f"{self.numero_serie:04d}"  # Si no tiene serie, usa 4 dígitos

    def __str__(self):
        return f"Formulario {self.id} - {self.numero_serie_completo}"

# Modelo para el contador global de id_linea
class ContadorDetalleFactura(models.Model):
    contador = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"Contador global de detalles: {self.contador}"

# Modelo de Kardex (Movimientos de Inventario)
class Kardex(models.Model):
    TIPO_MOVIMIENTO = [
        ('INGRESO', 'Ingreso'),
        ('SALIDA', 'Salida'),
    ]

    articulo = models.ForeignKey(Articulo, related_name='kardex', on_delete=models.CASCADE)
    tipo_movimiento = models.CharField(max_length=10, choices=TIPO_MOVIMIENTO)
    cantidad = models.PositiveIntegerField()
    saldo_anterior = models.PositiveIntegerField(default=0)
    saldo_actual = models.PositiveIntegerField(default=0)
    fecha = models.DateTimeField(auto_now_add=True)
    
    fuente_factura = models.ForeignKey(DetalleFactura, null=True, blank=True, on_delete=models.SET_NULL)
    fuente_asignacion = models.ForeignKey(AsignacionDetalleFactura, null=True, blank=True, on_delete=models.SET_NULL)
    
    observacion = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['fecha', 'id']  # Orden cronológico

    def __str__(self):
        return f'{self.tipo_movimiento} {self.cantidad} {self.articulo.nombre} ({self.fecha.date()})'

    def save(self, *args, **kwargs):
        # Calcular saldo actual
        ultimo_kardex = Kardex.objects.filter(articulo=self.articulo).order_by('-fecha', '-id').first()
        self.saldo_anterior = ultimo_kardex.saldo_actual if ultimo_kardex else 0

        if self.tipo_movimiento == 'INGRESO':
            self.saldo_actual = self.saldo_anterior + self.cantidad
        elif self.tipo_movimiento == 'SALIDA':
            self.saldo_actual = self.saldo_anterior - self.cantidad

        super().save(*args, **kwargs)



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
    


def user_directory_path(instance, filename):
    # El archivo se subirá a MEDIA_ROOT/perfil_usuario/<username>/<filename>
    return f'perfil_usuario/{instance.user.username}/{filename}'

class Perfil(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    foto = models.ImageField(upload_to=user_directory_path, null=True, blank=True)

    def __str__(self):
        return f'Perfil de {self.user.username}'

@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(user=instance)

@receiver(post_save, sender=User)
def guardar_perfil_usuario(sender, instance, **kwargs):
    perfil = getattr(instance, 'perfil', None)
    if perfil:
        perfil.save()