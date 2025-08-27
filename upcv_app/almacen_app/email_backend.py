# almacen_app/email_backend.py

from django.core.mail.backends.smtp import EmailBackend
import logging

logger = logging.getLogger(__name__)

class CustomEmailBackend(EmailBackend):
    def send_messages(self, email_messages):
        try:
            result = super().send_messages(email_messages)
            logger.info(f"{result} correos enviados correctamente.")
            return result
        except Exception as e:
            logger.error(f"Error al enviar correos: {e}")
            return 0  # Devolver 0 si no se envían correos
