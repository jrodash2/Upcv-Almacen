# signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import DetalleFactura, AsignacionDetalleFactura, Kardex, User, Perfil

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
        ultimo_kardex = Kardex.objects.filter(articulo=instance.articulo).order_by('-fecha', '-id').first()
        saldo_actual = ultimo_kardex.saldo_actual if ultimo_kardex else 0

        if instance.cantidad_asignada > saldo_actual:
            raise ValueError(f"No hay suficiente stock para asignar {instance.cantidad_asignada} unidades de {instance.articulo.nombre}. Stock actual: {saldo_actual}")

        Kardex.objects.create(
            articulo=instance.articulo,
            tipo_movimiento='SALIDA',
            cantidad=instance.cantidad_asignada,
            observacion=f'Salida hacia {instance.destino.nombre}',
            fuente_asignacion=instance
        )


@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created and not hasattr(instance, 'perfil'):
        Perfil.objects.create(usuario=instance)