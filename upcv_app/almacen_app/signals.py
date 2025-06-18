# signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import DetalleFactura, AsignacionDetalleFactura, Kardex

@receiver(post_save, sender=DetalleFactura)
def crear_kardex_ingreso(sender, instance, created, **kwargs):
    if created:
        Kardex.objects.create(
            articulo=instance.articulo,
            tipo_movimiento='INGRESO',
            cantidad=instance.cantidad,
            observacion=f'Ingreso desde Form 1H {instance.form1h.numero_serie_completo}'
        )

@receiver(post_save, sender=AsignacionDetalleFactura)
def crear_kardex_salida(sender, instance, created, **kwargs):
    if created:
        Kardex.objects.create(
            articulo=instance.articulo,
            tipo_movimiento='SALIDA',
            cantidad=instance.cantidad_asignada,
            observacion=f'Salida hacia {instance.destino.nombre}'
        )
