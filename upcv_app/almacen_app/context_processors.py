# context_processors.py
from .models import FraseMotivacional
import random

def frase_del_dia(request):
    # Obtener todas las frases
    frases = FraseMotivacional.objects.all()
    
    # Verificar si hay frases disponibles
    if frases.exists():
        frase = random.choice(frases)
    else:
        # Si no hay frases, puedes devolver un valor predeterminado o None
        frase = None
    
    return {
        'frase_del_dia': frase
    }
