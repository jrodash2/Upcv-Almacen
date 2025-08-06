from datetime import datetime, timezone
from django.forms import IntegerField
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group, User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .form import DependenciaForm, DetalleFacturaForm, DetalleRequerimientoForm, DetalleRequerimientoFormSet, Form1hForm, PerfilForm, ProgramaForm, RequerimientoForm, UserCreateForm, UserEditForm, UserCreateForm, UbicacionForm, UnidadDeMedidaForm, CategoriaForm, ProveedorForm, ArticuloForm, DepartamentoForm, SerieForm, AsignacionDetalleFacturaForm, UsuarioDepartamentoForm, InstitucionForm
from .models import ContadorDetalleFactura, DetalleFactura, DetalleRequerimiento, HistorialTransferencia, LineaLibre, Perfil, Requerimiento, Ubicacion, UnidadDeMedida, Categoria, Proveedor, Articulo, Departamento, Kardex, AsignacionDetalleFactura, Movimiento, FraseMotivacional, Serie, form1h, Dependencia, Programa, LineaReservada, UsuarioDepartamento, Institucion
from django.views.generic import CreateView
from django.views.generic import ListView
from django.urls import reverse_lazy
from django.http import Http404, HttpResponseNotAllowed, JsonResponse
from django.core.exceptions import ValidationError
from django.contrib import messages
from .utils import reservar_lineas
from .models import LineaLibre, ContadorDetalleFactura, LineaReservada
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .models import Serie
from django.db import models
from django.db.models import Sum, F, Value, Count, Q, Case, When
from django.contrib.auth.decorators import login_required, user_passes_test
from collections import defaultdict
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
import json
from django.contrib.auth.models import Group
from .utils import grupo_requerido
from django.views.decorators.http import require_GET
from django.db.models.functions import Coalesce
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import render
from .models import DetalleFactura, AsignacionDetalleFactura, Articulo
from django.template.loader import render_to_string
from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa
from weasyprint import HTML
from django.db.models.functions import Cast, TruncWeek
from django.utils import timezone
from datetime import timedelta

@login_required
def transferir_articulos(request):
    departamentos = Departamento.objects.all()

    if request.method == 'POST':
        departamento_origen_id = request.POST.get('departamento_origen')
        articulo_id = request.POST.get('articulo')
        cantidad_str = request.POST.get('cantidad_transferir')
        departamento_destino_id = request.POST.get('departamento_destino')
        observacion = request.POST.get('observacion', '').strip()  # <-- aquí

        if not (departamento_origen_id and articulo_id and cantidad_str and departamento_destino_id):
            messages.error(request, 'Faltan datos para realizar la transferencia.')
            return redirect('almacen:lista_departamentos')

        try:
            cantidad = int(cantidad_str)
        except ValueError:
            messages.error(request, 'Cantidad inválida.')
            return redirect('almacen:detalle_departamento', pk=departamento_origen_id)

        departamento_origen = get_object_or_404(Departamento, id=departamento_origen_id)
        articulo = get_object_or_404(Articulo, id=articulo_id)
        departamento_destino = get_object_or_404(Departamento, id=departamento_destino_id)

        asignacion_origen = AsignacionDetalleFactura.objects.filter(
            articulo=articulo, destino=departamento_origen
        ).first()

        if not asignacion_origen or asignacion_origen.cantidad_asignada < cantidad:
            messages.error(request, 'No hay suficiente cantidad en el departamento de origen.')
            return redirect('almacen:detalle_departamento', pk=departamento_origen_id)

        # Reducir cantidad en origen
        asignacion_origen.cantidad_asignada -= cantidad
        asignacion_origen.save()

        # Incrementar cantidad en destino, o crear asignación si no existe
        asignacion_destino, created = AsignacionDetalleFactura.objects.get_or_create(
            articulo=articulo, destino=departamento_destino,
            defaults={'cantidad_asignada': 0}
        )
        asignacion_destino.cantidad_asignada += cantidad
        asignacion_destino.save()

        # Guardar historial de transferencia con observación
        HistorialTransferencia.objects.create(
            articulo=articulo,
            cantidad=cantidad,
            departamento_origen=departamento_origen,
            departamento_destino=departamento_destino,
            usuario=request.user,
            observacion=observacion
        )

        messages.success(request, f'Se transfirieron {cantidad} unidades de {articulo.nombre} de {departamento_origen.nombre} a {departamento_destino.nombre}.')

        return redirect('almacen:detalle_departamento', pk=departamento_origen_id)

    return redirect('almacen:lista_departamentos')




def historial_transferencias(request):
    # Obtén todos los registros del historial de transferencias
    transferencias = HistorialTransferencia.objects.all().order_by('-fecha_transferencia')
    
    return render(request, 'almacen/historial_transferencias.html', {'transferencias': transferencias})

def articulos_asignados(request, departamento_id):
    try:
        departamento = Departamento.objects.get(id=departamento_id)
        articulos = AsignacionDetalleFactura.objects.filter(destino=departamento)

        data = {
            'articulos': [{
                'id': asignacion.articulo.id,
                'nombre': asignacion.articulo.nombre,
                'cantidad_asignada': asignacion.cantidad_asignada
            } for asignacion in articulos]
        }
        return JsonResponse(data)
    except Departamento.DoesNotExist:
        return JsonResponse({'error': 'Departamento no encontrado'}, status=404)
    
    
@login_required
def editar_institucion(request):
    institucion = Institucion.objects.first()  # Solo debería haber una

    if request.method == 'POST':
        form = InstitucionForm(request.POST, request.FILES, instance=institucion)
        if form.is_valid():
            form.save()
            messages.success(request, "Datos institucionales actualizados correctamente.")
            return redirect('almacen:editar_institucion')  # Reemplaza con la URL real
    else:
        form = InstitucionForm(instance=institucion)

    return render(request, 'almacen/editar_institucion.html', {'form': form})


@login_required
@transaction.atomic
def despachar_requerimiento(request, requerimiento_id):
    if not request.user.groups.filter(name='Administrador').exists():
        messages.error(request, "No tienes permiso para despachar requerimientos.")
        return redirect('almacen:detalle_requerimiento', requerimiento_id=requerimiento_id)

    requerimiento = get_object_or_404(Requerimiento, id=requerimiento_id)

    if requerimiento.estado != 'enviado':
        messages.warning(request, "Solo se pueden despachar requerimientos en estado 'enviado'.")
        return redirect('almacen:detalle_requerimiento', requerimiento_id=requerimiento.id)

    if request.method == 'POST':
        cantidades_dict = {}
        for key in request.POST:
            if key.startswith('cantidades[') and key.endswith(']'):
                detalle_id = key[11:-1]
                try:
                    cantidades_dict[int(detalle_id)] = int(request.POST[key])
                except ValueError:
                    cantidades_dict[int(detalle_id)] = 0

        detalles = DetalleRequerimiento.objects.filter(requerimiento=requerimiento)

        # Validar cantidades
        for detalle in detalles:
            cantidad_a_despachar = cantidades_dict.get(detalle.id, 0)
            if cantidad_a_despachar != detalle.cantidad:
                messages.error(request, f"Debes despachar exactamente {detalle.cantidad} unidades de {detalle.articulo.nombre}.")
                return redirect('almacen:detalle_requerimiento', requerimiento_id=requerimiento.id)

        # Registrar salida en Kardex y actualizar estado
        for detalle in detalles:
            cantidad_a_despachar = cantidades_dict.get(detalle.id, 0)

            Kardex.objects.create(
                articulo=detalle.articulo,
                tipo_movimiento='SALIDA',
                cantidad=cantidad_a_despachar,
                observacion=f"Despacho de requerimiento #{requerimiento.id} para {requerimiento.departamento.nombre}"
            )

            detalle.estado = 'despachado'
            detalle.save()

        requerimiento.estado = 'despachado'
        requerimiento.save()

        messages.success(request, "Requerimiento despachado exitosamente.")
        return redirect('almacen:detalle_requerimiento', requerimiento_id=requerimiento.id)

    messages.error(request, "Método no permitido.")
    return redirect('almacen:detalle_requerimiento', requerimiento_id=requerimiento.id)

    
@login_required
def crear_requerimiento(request):
    form = RequerimientoForm(request.POST or None, usuario=request.user)

    # Filtrar los requerimientos según el rol del usuario
    if request.user.groups.filter(name='Administrador').exists():
        requerimientos = Requerimiento.objects.filter( estado__in=['enviado', 'despachado']).order_by('-fecha_creacion')
    else:
        requerimientos = Requerimiento.objects.filter(creado_por=request.user)

    if request.method == "POST":
        if form.is_valid():
            nuevo = form.save(commit=False)
            nuevo.creado_por = request.user
            nuevo.save()
            messages.success(request, "Requerimiento creado exitosamente.")
            return redirect('almacen:detalle_requerimiento', requerimiento_id=nuevo.id)
        else:
            messages.error(request, "Por favor revisa el formulario.")

    return render(request, 'almacen/crear_requerimiento.html', {
        'form': form,
        'requerimientos': requerimientos,
        'mostrar_modal': request.method == "POST" and not form.is_valid(),
    })

@login_required
def enviar_requerimiento(request, requerimiento_id):
    requerimiento = get_object_or_404(Requerimiento, id=requerimiento_id)

    if requerimiento.estado != 'confirmado':  # Evita cambiar si ya fue confirmado
        requerimiento.estado = 'enviado'
        requerimiento.save()
        messages.success(request, "Requerimiento enviado correctamente.")
    else:
        messages.warning(request, "El requerimiento ya está confirmado y no puede ser enviado.")

    return redirect('almacen:detalle_requerimiento', requerimiento_id=requerimiento.id)

@login_required
def detalle_requerimiento(request, requerimiento_id):
    requerimiento = get_object_or_404(Requerimiento, id=requerimiento_id)

    # Asignaciones
    asignaciones_qs = (
        AsignacionDetalleFactura.objects
        .filter(destino=requerimiento.departamento)
        .values('articulo')
        .annotate(total_asignado=Sum('cantidad_asignada'))
    )
    asignaciones_dict = {item['articulo']: item['total_asignado'] for item in asignaciones_qs}

    # Despachados
    despachos_qs = (
        DetalleRequerimiento.objects
        .filter(requerimiento__departamento=requerimiento.departamento, requerimiento__estado='despachado')
        .values('articulo')
        .annotate(total_despachado=Sum('cantidad'))
    )
    despachos_dict = {item['articulo']: item['total_despachado'] for item in despachos_qs}

    # Calcular stock disponible
    stock_disponible = {}
    for articulo_id, total_asignado in asignaciones_dict.items():
        total_despachado = despachos_dict.get(articulo_id, 0)
        disponible = total_asignado - total_despachado
        if disponible > 0:
            stock_disponible[articulo_id] = disponible

    # 🔁 Convertir claves del stock a str para compatibilidad con Django template
    stock_disponible = {
        str(articulo_id): disponible
        for articulo_id, disponible in stock_disponible.items()
    }

    # Filtrar artículos que tienen stock disponible
    articulos = Articulo.objects.filter(id__in=stock_disponible.keys())

    # Lista de detalles ya agregados al requerimiento
    detalles_requerimiento = DetalleRequerimiento.objects.filter(requerimiento=requerimiento)

    es_admin = request.user.groups.filter(name='Administrador').exists()

    if request.method == 'POST':
        articulo_id = request.POST.get('articulo')
        cantidad = int(request.POST.get('cantidad', 0))
        observacion = request.POST.get('observaciones', '')

        if not articulo_id or cantidad <= 0:
            messages.error(request, "Debe seleccionar un artículo y una cantidad válida.")
        else:
            articulo = Articulo.objects.get(id=articulo_id)
            disponible = stock_disponible.get(str(articulo.id), 0)

            if cantidad > disponible:
                messages.error(request, f"No puedes requerir más de {disponible} unidades de {articulo.nombre}.")
            else:
                DetalleRequerimiento.objects.create(
                    requerimiento=requerimiento,
                    articulo=articulo,
                    cantidad=cantidad,
                    observacion=observacion
                )
                messages.success(request, "Detalle agregado correctamente.")
                return redirect('almacen:detalle_requerimiento', requerimiento_id=requerimiento.id)

    return render(request, 'almacen/detalle_requerimiento.html', {
        'requerimiento': requerimiento,
        'articulos': articulos,
        'detalles_requerimiento': detalles_requerimiento,
        'stock_disponible': stock_disponible,
        'es_admin': es_admin,
    })


@require_GET
def detalle_requerimiento_api(request, detalle_id):
    try:
        detalle = DetalleRequerimiento.objects.get(id=detalle_id)
        data = {
            'id': detalle.id,
            'articulo_id': detalle.articulo.id,
            'cantidad': detalle.cantidad,
            'observacion': detalle.observacion,  # usa el nombre real del campo en tu modelo
        }
        return JsonResponse(data)
    except DetalleRequerimiento.DoesNotExist:
        raise Http404("Detalle no encontrado")
  
@login_required
def editar_detalle_requerimiento(request):
    if request.method == 'POST':
        detalle_id = request.POST.get('detalle_id')
        articulo_id = request.POST.get('articulo')
        cantidad = request.POST.get('cantidad')
        observaciones = request.POST.get('observaciones')

        try:
            detalle = DetalleRequerimiento.objects.get(id=detalle_id)
            articulo = Articulo.objects.get(id=articulo_id)
            detalle.articulo = articulo
            detalle.cantidad = int(cantidad)
            detalle.observacion = observaciones  # o 'observaciones' según modelo
            detalle.save()
            messages.success(request, "Detalle actualizado correctamente.")
        except (DetalleRequerimiento.DoesNotExist, Articulo.DoesNotExist):
            messages.error(request, "Error al actualizar el detalle.")
        
        return redirect('almacen:detalle_requerimiento', requerimiento_id=detalle.requerimiento.id)

    return redirect('almacen:detalle_requerimiento')  # o donde quieras    

def exportar_kardex_pdf(request, articulo_id):
    articulo = get_object_or_404(Articulo, id=articulo_id)
    movimientos = Kardex.objects.filter(articulo=articulo).order_by('fecha')

    # Renderizas la plantilla a HTML
    html_string = render(request, 'almacen/pdf_kardex.html', {
        'articulo': articulo,
        'movimientos': movimientos,
    }).content.decode('utf-8')

    # Generas PDF desde el HTML
    pdf_file = HTML(string=html_string).write_pdf()

    # Construyes la respuesta para mostrar en navegador (inline)
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="kardex_{}.pdf"'.format(articulo.id)

    return response

def exportar_requerimiento_pdf(request, requerimiento_id):
    requerimiento = get_object_or_404(Requerimiento, id=requerimiento_id)
    detalles = requerimiento.detalles.all()
    institucion = Institucion.objects.first()  # ✅ Agregamos esto

    html_string = render_to_string('almacen/pdf_requerimiento.html', {
        'requerimiento': requerimiento,
        'detalles_requerimiento': detalles,
        'institucion': institucion,  # ✅ Pasamos la instancia al template
    })

    # ✅ base_url ayuda a resolver rutas de imágenes y estáticos
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="requerimiento_{requerimiento.id}.pdf"'
    return response

def historial_kardex_articulo(request, articulo_id):
    articulo = get_object_or_404(Articulo, id=articulo_id)
    movimientos = Kardex.objects.filter(articulo=articulo).order_by('fecha', 'id')
    return render(request, 'almacen/historial_kardex.html', {
        'articulo': articulo,
        'movimientos': movimientos
    })



def ver_stock_formulario_1h(request):
    ingresos = DetalleFactura.objects.filter(
        form1h__estado='confirmado'
    ).values('articulo__id', 'articulo__nombre').annotate(
        total_ingresado=Sum('cantidad')
    )

    ingreso_dict = {item['articulo__id']: item for item in ingresos}

    asignaciones = AsignacionDetalleFactura.objects.values('articulo__id').annotate(
        total_asignado=Sum('cantidad_asignada')
    )

    asignaciones_departamento = AsignacionDetalleFactura.objects.values(
        'articulo__id', 'destino__nombre'
    ).annotate(total_asignado_dept=Sum('cantidad_asignada'))

    asignaciones_dept_dict = {}
    for asig in asignaciones_departamento:
        art_id = asig['articulo__id']
        depto_nombre = asig['destino__nombre']
        cantidad = asig['total_asignado_dept']
        if art_id not in asignaciones_dept_dict:
            asignaciones_dept_dict[art_id] = []
        asignaciones_dept_dict[art_id].append(f"{depto_nombre} ({cantidad})")

    for item in asignaciones:
        articulo_id = item['articulo__id']
        if articulo_id in ingreso_dict:
            ingreso_dict[articulo_id]['total_asignado'] = item['total_asignado']
        else:
            ingreso_dict[articulo_id] = {
                'articulo__id': articulo_id,
                'articulo__nombre': Articulo.objects.get(id=articulo_id).nombre,
                'total_ingresado': 0,
                'total_asignado': item['total_asignado'],
            }

    stock_list = []
    for item in ingreso_dict.values():
        total_ingresado = item.get('total_ingresado') or 0
        total_asignado = item.get('total_asignado') or 0
        disponible = total_ingresado - total_asignado
        departamentos = ", ".join(asignaciones_dept_dict.get(item['articulo__id'], [])) or "Sin asignar"

        stock_list.append({
            'articulo_id': item['articulo__id'],
            'articulo': item['articulo__nombre'],
            'ingresado': total_ingresado,
            'asignado': total_asignado,
            'disponible': disponible,
            'departamentos': departamentos,
        })

    context = {
        'stock_list': stock_list,
        'departamentos': Departamento.objects.all(),
    }
    return render(request, 'almacen/stock_formulario_1h.html', context)
    

@login_required
@grupo_requerido('Administrador')
@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Administrador').exists())
def asignar_departamento_usuario(request):
    if request.method == 'POST':
        form = UsuarioDepartamentoForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Departamento asignado correctamente al usuario.')
                return redirect('almacen:asignar_departamento')
            except:
                messages.error(request, 'Este usuario ya está asignado a ese departamento.')
    else:
        form = UsuarioDepartamentoForm()

    # Agrupar departamentos por usuario
    asignaciones = UsuarioDepartamento.objects.select_related('usuario', 'departamento')
    usuarios_con_departamentos = defaultdict(list)
    for asignacion in asignaciones:
        usuarios_con_departamentos[asignacion.usuario].append(asignacion.departamento)

    context = {
        'form': form,
        'usuarios_con_departamentos': usuarios_con_departamentos.items(),
    }
    return render(request, 'almacen/asignar_departamento.html', context)

def eliminar_asignacion(request, usuario_id, departamento_id):
    if request.method == 'POST':
        asignacion = get_object_or_404(UsuarioDepartamento, usuario_id=usuario_id, departamento_id=departamento_id)
        asignacion.delete()
        messages.success(request, 'Asignación eliminada correctamente.')
    else:
        messages.error(request, 'Método no permitido.')
    return redirect('almacen:asignar_departamento')


@login_required
def lista_departamentos(request):
    es_departamento = request.user.groups.filter(name='Departamento').exists()

    if es_departamento:
        # Obtener todos los objetos UsuarioDepartamento vinculados al usuario
        usuario_departamentos = UsuarioDepartamento.objects.filter(usuario=request.user)
        # Mostrar todos los departamentos asociados a esas instancias
        departamentos = Departamento.objects.filter(usuariodepartamento__in=usuario_departamentos)
    else:
        departamentos = Departamento.objects.all()

    return render(request, 'almacen/lista_departamentos.html', {
        'departamentos': departamentos,
        'es_departamento': es_departamento
    })

def acceso_denegado(request, exception=None):
    return render(request, 'almacen/403.html', status=403)

from django.db.models import Q

@login_required
def detalle_departamento(request, pk):
    departamento = get_object_or_404(Departamento, pk=pk)

    es_departamento = request.user.groups.filter(name='Departamento').exists()
    es_admin = request.user.groups.filter(name='Administrador').exists()

    tiene_acceso = es_admin or UsuarioDepartamento.objects.filter(usuario=request.user, departamento=departamento).exists()

    asignaciones_agrupadas = []
    asignaciones_detalle = []
    resumen_stock = []
    departamentos = []
    historial_transferencias = []

    if tiene_acceso:
        departamentos = Departamento.objects.exclude(id=departamento.id)

        asignaciones_agrupadas = (
            AsignacionDetalleFactura.objects
            .filter(destino=departamento)
            .values('articulo__id', 'articulo__nombre')
            .annotate(total_asignado=Sum('cantidad_asignada'))
            .order_by('articulo__nombre')
        )

        despachados = (
            DetalleRequerimiento.objects
            .filter(requerimiento__departamento=departamento, requerimiento__estado='despachado')
            .values('articulo__id')
            .annotate(total_despachado=Sum('cantidad'))
        )
        despachados_dict = {d['articulo__id']: d['total_despachado'] for d in despachados}

        resumen_stock = []
        for item in asignaciones_agrupadas:
            articulo_id = item['articulo__id']
            total_asignado = item['total_asignado']
            total_despachado = despachados_dict.get(articulo_id, 0)
            disponible = total_asignado - total_despachado

            resumen_stock.append({
                'nombre_articulo': item['articulo__nombre'],
                'asignado': total_asignado,
                'despachado': total_despachado,
                'disponible': disponible
            })

        asignaciones_detalle = (
            AsignacionDetalleFactura.objects
            .filter(destino=departamento)
            .order_by('-fecha_asignacion')
        )

        # Historial de transferencias donde el departamento es origen o destino
        historial_transferencias = (
            HistorialTransferencia.objects
            .filter(Q(departamento_origen=departamento) | Q(departamento_destino=departamento))
            .order_by('-fecha_transferencia')
        )

    return render(request, 'almacen/detalle_departamento.html', {
        'departamento': departamento,
        'asignaciones_agrupadas': asignaciones_agrupadas,
        'asignaciones_detalle': asignaciones_detalle,
        'resumen_stock': resumen_stock,
        'tiene_acceso': tiene_acceso,
        'es_departamento': es_departamento,
        'departamentos': departamentos,
        'historial_transferencias': historial_transferencias,
    })




@login_required
@grupo_requerido('Administrador')
def crear_asignacion_detalle(request):
    if request.method == 'POST':
        form = AsignacionDetalleFacturaForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Asignación creada correctamente.")
                return redirect('almacen:crear_asignacion_detalle')
            except Exception as e:
                messages.error(request, f"Error al asignar: {e}")
    else:
        form = AsignacionDetalleFacturaForm()

    # 👇 Estas líneas deben estar bien indentadas dentro de la función
    stock_por_articulo = DetalleFactura.objects.filter(
        form1h__estado='confirmado'
    ).values('articulo').annotate(stock_total=Sum('cantidad'))

    asignado_por_articulo = AsignacionDetalleFactura.objects.values('articulo').annotate(
        asignado_total=Sum('cantidad_asignada'))

    stock_dict = {}
    for item in stock_por_articulo:
        articulo_id = item['articulo']
        total_stock = item['stock_total'] or 0
        total_asignado = next((a['asignado_total'] for a in asignado_por_articulo if a['articulo'] == articulo_id), 0)
        stock_disponible = total_stock - (total_asignado or 0)
        stock_dict[articulo_id] = stock_disponible

    ultima_asignacion = AsignacionDetalleFactura.objects.order_by('-fecha_asignacion').first()

    return render(request, 'almacen/crear_asignacion_detalle.html', {
        'form': form,
        'stock_dict': stock_dict,
        'ultima_asignacion': ultima_asignacion,
    })

   
@login_required
@grupo_requerido('Administrador')
def crear_asignacion_detalle_articulo(request):
    if request.method == 'POST':
        form = AsignacionDetalleFacturaForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Asignación creada correctamente.")
                return redirect('almacen:crear_asignacion_detalle_articulo')
            except Exception as e:
                messages.error(request, f"Error al asignar: {e}")
    else:
        form = AsignacionDetalleFacturaForm()

    # Calcular stock ingresado
    ingresos = DetalleFactura.objects.filter(
        form1h__estado='confirmado'
    ).values('articulo__id', 'articulo__nombre').annotate(
        total_ingresado=Sum('cantidad')
    )

    ingreso_dict = {item['articulo__id']: item for item in ingresos}

    # Asignaciones totales
    asignaciones = AsignacionDetalleFactura.objects.values('articulo__id').annotate(
        total_asignado=Sum('cantidad_asignada')
    )

    # Asignaciones por departamento
    asignaciones_departamento = AsignacionDetalleFactura.objects.values(
        'articulo__id', 'destino__nombre'
    ).annotate(total_asignado_dept=Sum('cantidad_asignada'))

    asignaciones_dept_dict = {}
    for asig in asignaciones_departamento:
        art_id = asig['articulo__id']
        depto_nombre = asig['destino__nombre']
        cantidad = asig['total_asignado_dept']
        if art_id not in asignaciones_dept_dict:
            asignaciones_dept_dict[art_id] = []
        asignaciones_dept_dict[art_id].append(f"{depto_nombre} ({cantidad})")

    # Combinar ingresos y asignaciones
    for item in asignaciones:
        articulo_id = item['articulo__id']
        if articulo_id in ingreso_dict:
            ingreso_dict[articulo_id]['total_asignado'] = item['total_asignado']
        else:
            ingreso_dict[articulo_id] = {
                'articulo__id': articulo_id,
                'articulo__nombre': Articulo.objects.get(id=articulo_id).nombre,
                'total_ingresado': 0,
                'total_asignado': item['total_asignado'],
            }

    # Construir stock_list
    stock_list = []
    for item in ingreso_dict.values():
        total_ingresado = item.get('total_ingresado') or 0
        total_asignado = item.get('total_asignado') or 0
        disponible = total_ingresado - total_asignado
        departamentos = ", ".join(asignaciones_dept_dict.get(item['articulo__id'], [])) or "Sin asignar"

        stock_list.append({
            'articulo_id': item['articulo__id'],
            'articulo': item['articulo__nombre'],
            'ingresado': total_ingresado,
            'asignado': total_asignado,
            'disponible': disponible,
            'departamentos': departamentos,
        })

    context = {
    'form': form,
    'stock_list': stock_list,
    'departamentos': Departamento.objects.all(),  
}


    return render(request, 'almacen/stock_formulario_1h.html', context)


    
def buscar_articulos(request):
    term = request.GET.get('q', '')
    articulos = Articulo.objects.filter(nombre__icontains=term)[:10]
    results = [{'id': art.id, 'nombre': art.nombre} for art in articulos]
    return JsonResponse(results, safe=False)
    
@login_required
@grupo_requerido('Administrador')    
def serie_form_list(request, pk=None):
    if pk:
        instance = get_object_or_404(Serie, pk=pk)
    else:
        instance = None

    if request.method == 'POST':
        form = SerieForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            return redirect('almacen:lista_series')
    else:
        form = SerieForm(instance=instance)

    series = Serie.objects.all()
    return render(request, 'almacen/serie_list.html', {
        'form': form,
        'series': series,
    })

@login_required
@grupo_requerido('Administrador')
@require_POST
def confirmar_form1h(request, form1h_id):
    formulario = get_object_or_404(form1h, id=form1h_id)

    if formulario.estado == 'borrador':
        formulario.estado = 'confirmado'
        formulario.save()
        messages.success(request, f'El formulario Serie {formulario.serie.serie} {formulario.numero_serie}  ha sido confirmado exitosamente.')
    elif formulario.estado == 'confirmado':
        messages.info(request, f'El formulario Serie {formulario.serie.serie} {formulario.numero_serie}  ya está confirmado.')
    else:
        messages.warning(request, f'El formulario Serie {formulario.serie.serie} {formulario.numero_serie}  no se puede confirmar en su estado actual.')

    return redirect('almacen:agregar_detalle_factura', form1h_id=form1h_id)


def buscar_proveedor_nit(request, nit):
    try:
        proveedor = Proveedor.objects.get(nit=nit)
        data = {
            'nombre': proveedor.nombre,
            'telefono': proveedor.telefono,
            'direccion': proveedor.direccion,
            'proveedor_id': proveedor.id,
        }
        return JsonResponse(data)
    except Proveedor.DoesNotExist:
        return JsonResponse({'error': 'Proveedor no encontrado'}, status=404)
    
def buscar_proveedor_id(request, proveedor_id):
    try:
        proveedor = Proveedor.objects.get(id=proveedor_id)
        data = {
            'nombre': proveedor.nombre,
            'telefono': proveedor.telefono,
            'direccion': proveedor.direccion,
            'nit': proveedor.nit,
        }
        return JsonResponse(data)
    except Proveedor.DoesNotExist:
        return JsonResponse({'error': 'Proveedor no encontrado'}, status=404)

@login_required
@grupo_requerido('Administrador')
def crear_form1h(request):
    form1h_list = form1h.objects.all()
    form = Form1hForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            try:
                cantidad = form.cleaned_data.get('cantidad_detalles')
                nuevo_formulario = form.save()

                # Obtener o crear el contador global
                contador, _ = ContadorDetalleFactura.objects.get_or_create(id=1)

                for _ in range(cantidad):
                    if LineaLibre.objects.exists():
                        libre = LineaLibre.objects.first()
                        numero_linea = libre.id_linea
                        libre.delete()
                    else:
                        numero_linea = contador.contador
                        contador.contador += 1

                    # Asegúrate de que no esté duplicado
                    if not LineaReservada.objects.filter(numero_linea=numero_linea).exists():
                        LineaReservada.objects.create(
                            form1h=nuevo_formulario,
                            numero_linea=numero_linea,
                            disponible=True
                        )

                contador.save()

                messages.success(request, f"Formulario creado y se reservaron {cantidad} líneas.")
                return redirect('almacen:agregar_detalle_factura', form1h_id=nuevo_formulario.id)
            except ValidationError as e:
                messages.error(request, e.message)

    return render(request, 'almacen/crear_form1h.html', {
        'form': form,
        'form1h_list': form1h_list
    })


@login_required
@grupo_requerido('Administrador')
def agregar_detalle_factura(request, form1h_id):
    form1h_instance = get_object_or_404(form1h, id=form1h_id)
    detalles_factura = DetalleFactura.objects.filter(form1h=form1h_instance)

    total_factura = form1h_instance.calcular_total_factura()
    articulos = Articulo.objects.all()
    categorias = Categoria.objects.all()
    ubicaciones = Ubicacion.objects.all()
    unidades = UnidadDeMedida.objects.all()

    # Filtrar líneas disponibles para este form1h
    lineas_reservadas = LineaReservada.objects.filter(
        form1h=form1h_instance,
        disponible=True
    ).order_by('numero_linea')

    print("======= LÍNEAS RESERVADAS =======")
    for linea in lineas_reservadas:
        print(f"Línea: {linea.numero_linea} | Disponible: {linea.disponible} | Formulario ID: {linea.form1h_id}")

    if request.method == "POST":
        numero_linea = request.POST.get('detalle_numero_linea')
        renglon = request.POST.get('renglon')

        # Clonar POST y añadir el id_linea que necesita el form
        post_data = request.POST.copy()
        post_data['id_linea'] = numero_linea  # Esto se inyecta en el form

        form = DetalleFacturaForm(post_data, form1h_instance=form1h_instance)

        if form.is_valid():
            detalle = form.save(commit=False)
            detalle.form1h = form1h_instance
            detalle.renglon = renglon  # Puedes usar directamente: detalle.renglon = numero_linea

            try:
                linea_reservada = LineaReservada.objects.get(
                    numero_linea=numero_linea,
                    form1h=form1h_instance,
                    disponible=True
                )

                detalle.save()

                # Marcar la línea como no disponible
                linea_reservada.disponible = False
                linea_reservada.save()

                messages.success(request, f"Detalle agregado usando línea #{numero_linea}.")
                return redirect('almacen:agregar_detalle_factura', form1h_id=form1h_id)

            except LineaReservada.DoesNotExist:
                messages.error(request, "La línea seleccionada no está disponible o ya fue utilizada.")
        else:
            print("Errores del formulario:", form.errors)
            messages.error(request, "Error al guardar el detalle. Verifica los campos.")
    else:
        form = DetalleFacturaForm(form1h_instance=form1h_instance)

    return render(request, 'almacen/agregar_detalle_factura.html', {
        'form1h_instance': form1h_instance,
        'form': form,
        'detalles_factura': detalles_factura,
        'total_factura': total_factura,
        'articulos': articulos,
        'categorias': categorias,
        'ubicaciones': ubicaciones,
        'unidades': unidades,
        'lineas_reservadas': lineas_reservadas,
    })


@require_POST

def eliminar_detalle_requerimiento(request, pk):
    if request.method == 'POST':
        try:
            detalle = DetalleRequerimiento.objects.get(pk=pk)
            detalle.delete()
            return JsonResponse({'success': True})
        except DetalleRequerimiento.DoesNotExist:
            return JsonResponse({'error': 'Detalle no encontrado'}, status=404)
    return HttpResponseNotAllowed(['POST'])

# Views for Departamento
@login_required
@grupo_requerido('Administrador')
def crear_departamento(request):
    departamentos = Departamento.objects.all()  # Obtener todos los departamentos
    form = DepartamentoForm(request.POST or None)  # Crear el formulario
    if form.is_valid():
        form.save()  # Guardar el nuevo departamento
        return redirect('almacen:crear_departamento')  # Redirige a la misma página para mostrar el nuevo departamento
    return render(request, 'almacen/crear_departamento.html', {'form': form, 'departamentos': departamentos})

@login_required
@grupo_requerido('Administrador')
def editar_departamento(request, pk):
    departamento = get_object_or_404(Departamento, pk=pk)  # Obtener el departamento por su PK
    form = DepartamentoForm(request.POST or None, instance=departamento)  # Rellenar el formulario con los datos existentes
    if form.is_valid():
        form.save()  # Guardar los cambios en el departamento
        return redirect('almacen:crear_departamento')  # Redirige a la vista de creación (o a donde desees)
    return render(request, 'almacen/editar_departamento.html', {'form': form, 'departamentos': Departamento.objects.all()})


# Create your views here.
@login_required
@grupo_requerido('Administrador')
def crear_articulo(request):
    articulos = Articulo.objects.all()  # Obtener todos los artículos
    form = ArticuloForm(request.POST or None)  # Crear el formulario
    if form.is_valid():
        form.save()  # Guardar el nuevo artículo
        return redirect('almacen:crear_articulo')  # Redirige a la misma página para mostrar el nuevo artículo
    return render(request, 'almacen/crear_articulo.html', {'form': form, 'articulos': articulos})

@login_required
@grupo_requerido('Administrador')
def editar_articulo(request, pk):
    articulo = get_object_or_404(Articulo, pk=pk)  # Obtener el artículo por su PK
    form = ArticuloForm(request.POST or None, instance=articulo)  # Rellenar el formulario con los datos existentes
    if form.is_valid():
        form.save()  # Guardar los cambios en el artículo
        return redirect('almacen:crear_articulo')  # Redirige a la vista de creación (o a donde desees)
    return render(request, 'almacen/editar_articulo.html', {'form': form, 'articulos': Articulo.objects.all()})

@login_required
@grupo_requerido('Administrador')
def crear_proveedor(request):
    proveedores = Proveedor.objects.all()  # Obtener todos los proveedores
    form = ProveedorForm(request.POST or None)  # Crear el formulario
    if form.is_valid():
        form.save()  # Guardar el nuevo proveedor
        return redirect('almacen:crear_proveedor')  # Redirige a la misma página para mostrar el nuevo proveedor
    return render(request, 'almacen/crear_proveedor.html', {'form': form, 'proveedores': proveedores})

@login_required
@grupo_requerido('Administrador')
def editar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)  # Obtener el proveedor por su PK
    form = ProveedorForm(request.POST or None, instance=proveedor)  # Rellenar el formulario con los datos existentes
    if form.is_valid():
        form.save()  # Guardar los cambios en el proveedor
        return redirect('almacen:crear_proveedor')  # Redirige a la vista de creación (o a donde desees)
    return render(request, 'almacen/editar_proveedor.html', {'form': form, 'proveedores': Proveedor.objects.all()})

# Views for Categoria
@login_required
@grupo_requerido('Administrador')
def crear_categoria(request):
    categorias = Categoria.objects.all()  # Obtener todas las categorías
    form = CategoriaForm(request.POST or None)  # Crear el formulario
    if form.is_valid():
        form.save()  # Guardar la nueva categoría
        return redirect('almacen:crear_categoria')  # Redirige a la misma página para mostrar la nueva categoría
    return render(request, 'almacen/crear_categoria.html', {'form': form, 'categorias': categorias})

@login_required
@grupo_requerido('Administrador')
def editar_categoria(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)  # Obtener la categoría por su PK
    form = CategoriaForm(request.POST or None, instance=categoria)  # Rellenar el formulario con los datos existentes
    if form.is_valid():
        form.save()  # Guardar los cambios en la categoría
        return redirect('almacen:crear_categoria')  # Redirige a la vista de creación (o a donde desees)
    return render(request, 'almacen/editar_categoria.html', {'form': form, 'categorias': Categoria.objects.all()})

@login_required
@grupo_requerido('Administrador')
def crear_unidad(request):
    unidades = UnidadDeMedida.objects.all()  # Obtener todas las unidades de medida
    form = UnidadDeMedidaForm(request.POST or None)  # Crear el formulario
    if form.is_valid():
        form.save()  # Guardar la nueva unidad de medida
        return redirect('almacen:crear_unidad')  # Redirige a la misma página para mostrar la nueva unidad
    return render(request, 'almacen/crear_unidad.html', {'form': form, 'unidades': unidades})

@login_required
@grupo_requerido('Administrador')
def editar_unidad(request, pk):
    unidad = get_object_or_404(UnidadDeMedida, pk=pk)
    if request.method == 'POST':
        form = UnidadDeMedidaForm(request.POST, instance=unidad)
        if form.is_valid():
            form.save()
            return redirect('almacen:crear_unidad')  # Redirige a la lista de unidades
    else:
        form = UnidadDeMedidaForm(instance=unidad)

    return render(request, 'almacen/crear_unidad.html', {'form': form})

@login_required
@grupo_requerido('Administrador')
def crear_programa(request):
    programas = Programa.objects.all()
    form = ProgramaForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('almacen:crear_programa')  # Ajusta a tu namespace de URLs
    return render(request, 'almacen/crear_programa.html', {'form': form, 'programas': programas})


@login_required
@grupo_requerido('Administrador')
def editar_programa(request, pk):
    programa = get_object_or_404(Programa, pk=pk)
    programas = Programa.objects.all()
    if request.method == 'POST':
        form = ProgramaForm(request.POST, instance=programa)
        if form.is_valid():
            form.save()
            return redirect('almacen:crear_programa')
    else:
        form = ProgramaForm(instance=programa)
    return render(request, 'almacen/crear_programa.html', {'form': form, 'programas': programas})

@login_required
@grupo_requerido('Administrador')
def crear_dependencia(request):
    dependencias = Dependencia.objects.all()
    form = DependenciaForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('almacen:crear_dependencia')
    return render(request, 'almacen/crear_dependencia.html', {'form': form, 'dependencias': dependencias})


@login_required
@grupo_requerido('Administrador')
def editar_dependencia(request, pk):
    dependencia = get_object_or_404(Dependencia, pk=pk)
    dependencias = Dependencia.objects.all()

    if request.method == 'POST':
        form = DependenciaForm(request.POST, instance=dependencia)
        if form.is_valid():
            form.save()
            return redirect('almacen:crear_dependencia')
    else:
        form = DependenciaForm(instance=dependencia)

    return render(request, 'almacen/crear_dependencia.html', {'form': form, 'dependencias': dependencias})

@login_required
@grupo_requerido('Administrador')
def crear_ubicacion(request):
    ubicaciones = Ubicacion.objects.all()
    form = UbicacionForm(request.POST or None)

    if form.is_valid():
        # Guardamos el formulario sin el commit para poder manipular el objeto antes de guardarlo
        ubicacion = form.save(commit=False)
        
        # Solo establecer 'activo' como True si es una nueva ubicación (sin pk)
        if not ubicacion.pk:
            ubicacion.activo = True
        
        # Guardamos la ubicación
        ubicacion.save()
        
        # Redirigimos a la misma página para mostrar la nueva ubicación creada
        return redirect('almacen:crear_ubicacion')

    return render(request, 'almacen/crear_ubicacion.html', {'form': form, 'ubicaciones': ubicaciones})

@login_required
@grupo_requerido('Administrador')
def editar_ubicacion(request, pk):
    ubicacion = get_object_or_404(Ubicacion, pk=pk)
    form = UbicacionForm(request.POST or None, instance=ubicacion)
    if form.is_valid():
        form.save()
        return redirect('almacen:crear_ubicacion')  # Redirige a la vista de creación
    return render(request, 'almacen/editar_ubicacion.html', {'form': form, 'ubicaciones': Ubicacion.objects.all()})

@login_required
@grupo_requerido('Administrador')
def buscar_proveedor_por_nit(request, nit):
    try:
        proveedor = Proveedor.objects.get(nit=nit)
        # Devuelve los datos del proveedor en formato JSON
        return JsonResponse({
            'nombre': proveedor.nombre,
            'telefono': proveedor.telefono,
            'direccion': proveedor.direccion,
        })
    except Proveedor.DoesNotExist:
        # Si no se encuentra el proveedor, devuelve un error
        return JsonResponse({'error': 'Proveedor no encontrado'}, status=404)


def eliminar_detalle_factura(request, detalle_id):
    if request.method == "POST":
        detalle = get_object_or_404(DetalleFactura, id=detalle_id)
        detalle.delete()
        return JsonResponse({'success': True})  # Respuesta JSON para indicar éxito
    return JsonResponse({'success': False}, status=400)  # Respuesta en caso de error

def obtener_detalle_factura(request, detalle_id):
    detalle = get_object_or_404(DetalleFactura, id=detalle_id)
    data = {
        'articulo': detalle.articulo.id,
        'cantidad': detalle.cantidad,
        'precio_unitario': detalle.precio_unitario,
        'renglon': detalle.renglon,
        'fecha_vencimiento': detalle.fecha_vencimiento.strftime('%Y-%m-%d') if detalle.fecha_vencimiento else '',
    }
    return JsonResponse(data)

@login_required
@grupo_requerido('Administrador')    
def editar_detalle_factura(request):
    if request.method == 'POST':
        detalle_id = request.POST.get("detalle_id")  # Obtener el ID del detalle
        detalle = get_object_or_404(DetalleFactura, id=detalle_id)  # Buscar el detalle existente

        # Obtener el artículo y validar si requiere fecha de vencimiento
        articulo_id = request.POST.get("articulo")
        articulo = get_object_or_404(Articulo, id=articulo_id)

        # Verificar si el artículo requiere fecha de vencimiento
        if articulo.requiere_vencimiento:
            fecha_vencimiento = request.POST.get("fecha_vencimiento")
            if not fecha_vencimiento:  # Si no se envió la fecha de vencimiento
                raise ValidationError("Este artículo requiere una fecha de vencimiento.")
        else:
            fecha_vencimiento = None  # No es necesario asignar fecha si no se requiere

        # Actualizar los campos del detalle
        detalle.articulo_id = articulo_id
        detalle.cantidad = int(request.POST.get("cantidad"))  # Convertir a entero
        detalle.precio_unitario = float(request.POST.get("precio_unitario"))  # Convertir a flotante
        detalle.renglon = request.POST.get("renglon")
        detalle.precio_total = detalle.cantidad * detalle.precio_unitario  # Multiplicación correcta
        
        # Si se requiere fecha de vencimiento y está presente, guardarla
        if fecha_vencimiento:
            detalle.fecha_vencimiento = fecha_vencimiento
        
        detalle.save()

        # Redirigir después de la actualización
        return redirect('almacen:agregar_detalle_factura', form1h_id=detalle.form1h.id)

    return HttpResponseNotAllowed(['POST'])

@login_required
@grupo_requerido('Administrador')
def user_create(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            password = form.cleaned_data.get('new_password')
            user.set_password(password)
            user.save()

            group = form.cleaned_data.get('group')
            user.groups.add(group)

            # ✅ Espera a que la señal cree el perfil automáticamente
            foto = form.cleaned_data.get('foto')
            try:
                perfil = user.perfil  # accede al perfil creado por la señal
                if foto:
                    perfil.foto = foto
                    perfil.save()
            except Perfil.DoesNotExist:
                # Fallback solo si la señal falló (raro)
                Perfil.objects.create(user=user, foto=foto)

            messages.success(request, 'Usuario creado correctamente.')
            return redirect('almacen:user_create')
    else:
        form = UserCreateForm()

    users = User.objects.all()
    return render(request, 'almacen/user_form_create.html', {'form': form, 'users': users})

@login_required
@grupo_requerido('Administrador')
def user_edit(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    try:
        perfil = user.perfil
    except Perfil.DoesNotExist:
        perfil = Perfil(user=user)

    if request.method == 'POST':
        form_user = UserEditForm(request.POST, request.FILES, instance=user)
        form_perfil = PerfilForm(request.POST, request.FILES, instance=perfil)
        if form_user.is_valid() and form_perfil.is_valid():
            form_user.save()
            form_perfil.save()
            return redirect('almacen:user_create')
    else:
        form_user = UserEditForm(instance=user)
        form_perfil = PerfilForm(instance=perfil)

    context = {
        'form': form_user,
        'perfil_form': form_perfil,
        'users': User.objects.all(),
    }
    return render(request, 'almacen/user_form_edit.html', context)

@login_required
def perfil_edit(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    try:
        perfil = user.perfil
    except Perfil.DoesNotExist:
        perfil = Perfil(user=user)
    
    if request.method == 'POST':
        form = PerfilForm(request.POST, request.FILES, instance=perfil)
        if form.is_valid():
            form.save()
            return redirect('almacen:user_edit', user_id=user.id)
    else:
        form = PerfilForm(instance=perfil)
    
    return render(request, 'almacen/perfil_edit.html', {'form': form, 'user': user})

@login_required
def user_delete(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user.delete()
        return redirect('almacen:user_create')  # Redirige a la misma página para mostrar la lista actualizada
    return render(request, 'almacen/user_confirm_delete.html', {'user': user})


def home(request):
    return render(request, 'almacen/login.html')

from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q, Sum
import json

@login_required
def dahsboard(request):
    # Totales de artículos activos/inactivos
    totales_articulos = Articulo.objects.aggregate(
        activos=Count('id', filter=Q(activo=True)),
        inactivos=Count('id', filter=Q(activo=False))
    )

    # Suma de Kardex: entradas/salidas
    ingresos = Kardex.objects.filter(tipo_movimiento='INGRESO').aggregate(total=Sum('cantidad'))['total'] or 0
    salidas = Kardex.objects.filter(tipo_movimiento='SALIDA').aggregate(total=Sum('cantidad'))['total'] or 0

    # Requerimientos por estado
    estados_orden = ['pendiente', 'despachado', 'rechazado', 'enviado']
    req_por_estado = Requerimiento.objects.values('estado').annotate(cuenta=Count('id'))
    req_por_estado = sorted(
        list(req_por_estado),
        key=lambda r: estados_orden.index(r['estado']) if r['estado'] in estados_orden else len(estados_orden)
    )

    labels_req = [r['estado'].capitalize() for r in req_por_estado]
    data_req = [r['cuenta'] for r in req_por_estado]
    total_reqs = sum(data_req)

    # Evolución semanal de requerimientos (este mes)
    today = timezone.now().date()
    stm = today.replace(day=1)
    etm = (stm + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    req_sem = Requerimiento.objects.annotate(
        week=TruncWeek('fecha_creacion')
    ).filter(fecha_creacion__range=(stm, etm)).values('week').annotate(cuenta=Count('id')).order_by('week')

    semanas = [r['week'].strftime('%b %d') for r in req_sem]
    cantidad_sem = [r['cuenta'] for r in req_sem]

    # NUEVO: Artículos por vencer (en los próximos 30 días)
    limite = today + timedelta(days=30)

    detalles_por_vencer = DetalleFactura.objects.filter(
        articulo__requiere_vencimiento=True,
        fecha_vencimiento__gte=today,
        fecha_vencimiento__lte=limite,
    ).values('fecha_vencimiento').annotate(cantidad=Count('id')).order_by('fecha_vencimiento')

    fechas_vencimiento = [item['fecha_vencimiento'].strftime('%Y-%m-%d') for item in detalles_por_vencer]
    cantidades_vencimiento = [item['cantidad'] for item in detalles_por_vencer]
    total_por_vencer = sum(cantidades_vencimiento)

    context = {
        'totales_articulos': totales_articulos,
        'ingresos': ingresos,
        'salidas': salidas,
        'labels_req': json.dumps(labels_req),
        'data_req': json.dumps(data_req),
        'semanas': json.dumps(semanas),
        'cantidad_sem': json.dumps(cantidad_sem),
        'total_por_vencer': total_por_vencer,
        'fechas_vencimiento': json.dumps(fechas_vencimiento),
        'cantidades_vencimiento': json.dumps(cantidades_vencimiento),
    }

    return render(request, 'almacen/dashboard.html', context)


def signout(request):
    logout(request)
    return redirect('almacen:signin')


def signin(request):  
    institucion = Institucion.objects.first()
    if request.method == 'GET':
        # Deberías instanciar el AuthenticationForm correctamente
        return render(request, 'almacen/login.html', {
            'form': AuthenticationForm(),
            'institucion': institucion,
        })
    else:
        # Se instancia AuthenticationForm con los datos del POST para mantener el estado
        form = AuthenticationForm(request, data=request.POST)
        
        if form.is_valid():
            # El método authenticate devuelve el usuario si es válido
            user = form.get_user()
            
            # Si el usuario es encontrado, se inicia sesión
            auth_login(request, user)
            
            # Ahora verificamos los grupos
            for g in user.groups.all():
                print(g.name)
                if g.name == 'Administrador':
                    return redirect('almacen:dahsboard')
                elif g.name == 'Departamento':
                    return redirect('almacen:dahsboard')
                elif g.name == 'tecnico':
                    return redirect('tickets:tickets_dahsboard')
            # Si no se encuentra el grupo adecuado, se redirige a una página por defecto
            return redirect('dahsboard')
        else:
            # Si el formulario no es válido, se retorna con el error
            return render(request, 'almacen/login.html', {
                'form': form,  # Pasamos el formulario con los errores
                'error': 'Usuario o contraseña incorrectos',
                'institucion': institucion,
            })

