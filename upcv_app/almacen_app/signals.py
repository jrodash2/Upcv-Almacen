# signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver

from .views import enviar_correo_asignacion

from .models import DetalleFactura, AsignacionDetalleFactura, Kardex, User, Perfil, UsuarioDepartamento

@receiver(post_save, sender=DetalleFactura)
def crear_kardex_ingreso(sender, instance, created, **kwargs):
    if created:
        Kardex.objects.create(
            articulo=instance.articulo,
            tipo_movimiento='INGRESO',
            cantidad=instance.cantidad,
            observacion=f'Ingreso desde Form 1H {instance.form1h.numero_serie_completo}'
        )


@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created and not hasattr(instance, 'perfil'):
        Perfil.objects.create(usuario=instance)
        
        
import logging
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

@receiver(post_save, sender=AsignacionDetalleFactura)
def notificar_asignacion(sender, instance, created, **kwargs):
    if created:
        # Verifica si la señal fue activada
        logger.info(f"Señal activada para AsignacionDetalleFactura con ID: {instance.id}")
        
        articulo = instance.articulo
        departamento = instance.destino
        usuario = UsuarioDepartamento.objects.filter(departamento=departamento).first().usuario

        if usuario and usuario.email:
            # Asegúrate de que el correo está siendo enviado
            logger.info(f"Enviando correo a {usuario.email} sobre la asignación del artículo {articulo.nombre}")
            enviar_correo_asignacion(articulo, departamento, usuario)
        else:
            logger.error(f"No se encontró un usuario o un correo electrónico para el artículo {articulo.nombre}")
        