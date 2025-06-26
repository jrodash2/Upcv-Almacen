from .models import ContadorDetalleFactura, LineaLibre, LineaReservada, AsignacionDetalleFactura

from django.contrib.auth.decorators import user_passes_test

def reservar_lineas(cantidad, form1h_instance):
    contador_global, _ = ContadorDetalleFactura.objects.get_or_create(id=1)
    lineas_reservadas = []

    for _ in range(cantidad):
        if LineaLibre.objects.exists():
            libre = LineaLibre.objects.first()
            numero_linea = libre.id_linea
            libre.delete()
        else:
            numero_linea = contador_global.contador
            contador_global.contador += 1

        # Verifica que no haya duplicado antes de crear
        if not LineaReservada.objects.filter(numero_linea=numero_linea).exists():
            linea_reservada = LineaReservada.objects.create(
                numero_linea=numero_linea,
                disponible=True,
                form1h=form1h_instance
            )
            lineas_reservadas.append(linea_reservada)

    contador_global.save()
    return lineas_reservadas



def grupo_requerido(nombre_grupo):
    def in_group(user):
        return user.is_authenticated and user.groups.filter(name=nombre_grupo).exists()
    return user_passes_test(in_group)

from django.db.models import Sum

def obtener_articulos_asignados(departamento):
    asignaciones = AsignacionDetalleFactura.objects.filter(destino=departamento)
    return asignaciones.values('articulo').annotate(
        total_asignado=Sum('cantidad_asignada')
    )
