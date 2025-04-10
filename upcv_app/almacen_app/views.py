from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group, User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .form import DetalleFacturaForm, Form1hForm, UserForm, UbicacionForm, UnidadDeMedidaForm, CategoriaForm, ProveedorForm, ArticuloForm, DepartamentoForm
from .models import ContadorDetalleFactura, DetalleFactura, LineaLibre, Ubicacion, UnidadDeMedida, Categoria, Proveedor, Articulo, Departamento, Kardex, Asignacion, Movimiento, FraseMotivacional, Serie, form1h, Dependencia, Programa
from django.views.generic import CreateView
from django.views.generic import ListView
from django.urls import reverse_lazy
from django.http import HttpResponseNotAllowed, JsonResponse
from django.core.exceptions import ValidationError
from django.contrib import messages


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

def crear_form1h(request):
    form1h_list = form1h.objects.all()  # Obtener todos los registros de form1h
    form = Form1hForm(request.POST or None)  # Crear el formulario
    
    if request.method == "POST":
        if form.is_valid():
            try:
                form.save()  # Guardar el nuevo registro
                return redirect('almacen:crear_form1h')  # Redirige a la misma página para mostrar el nuevo registro
            except ValidationError as e:
                messages.error(request, e.message)  # Agregar el mensaje de error a Django messages

    return render(request, 'almacen/crear_form1h.html', {'form': form, 'form1h_list': form1h_list})


def agregar_detalle_factura(request, form1h_id):
    form1h_instance = get_object_or_404(form1h, id=form1h_id)
    detalles_factura = DetalleFactura.objects.filter(form1h=form1h_instance)

    total_factura = form1h_instance.calcular_total_factura()
    articulos = Articulo.objects.all()
    categorias = Categoria.objects.all()
    ubicaciones = Ubicacion.objects.all()
    unidades = UnidadDeMedida.objects.all()

    if request.method == "POST":
        form = DetalleFacturaForm(request.POST, form1h_instance=form1h_instance)
        if form.is_valid():
            detalle = form.save(commit=False)
            detalle.form1h = form1h_instance

            # Intentar obtener un id_linea libre
            linea_liberada = LineaLibre.objects.order_by('id_linea').first()

            if linea_liberada:
                id_linea = linea_liberada.id_linea
                linea_liberada.delete()  # Ya lo vamos a usar
            else:
                # Usar el contador global
                contador_obj, _ = ContadorDetalleFactura.objects.get_or_create(pk=1, defaults={'contador': 1})
                id_linea = contador_obj.contador
                contador_obj.contador += 1
                contador_obj.save()

            detalle.id_linea = id_linea
            detalle.save()

            return redirect('almacen:agregar_detalle_factura', form1h_id=form1h_id)
    else:
        form = DetalleFacturaForm()

    return render(request, 'almacen/agregar_detalle_factura.html', {
        'form1h_instance': form1h_instance,
        'form': form,
        'detalles_factura': detalles_factura,
        'total_factura': total_factura,
        'articulos': articulos,
        'categorias': categorias,
        'ubicaciones': ubicaciones,
        'unidades': unidades,
    })



# Views for Departamento

def crear_departamento(request):
    departamentos = Departamento.objects.all()  # Obtener todos los departamentos
    form = DepartamentoForm(request.POST or None)  # Crear el formulario
    if form.is_valid():
        form.save()  # Guardar el nuevo departamento
        return redirect('almacen:crear_departamento')  # Redirige a la misma página para mostrar el nuevo departamento
    return render(request, 'almacen/crear_departamento.html', {'form': form, 'departamentos': departamentos})

def editar_departamento(request, pk):
    departamento = get_object_or_404(Departamento, pk=pk)  # Obtener el departamento por su PK
    form = DepartamentoForm(request.POST or None, instance=departamento)  # Rellenar el formulario con los datos existentes
    if form.is_valid():
        form.save()  # Guardar los cambios en el departamento
        return redirect('almacen:crear_departamento')  # Redirige a la vista de creación (o a donde desees)
    return render(request, 'almacen/editar_departamento.html', {'form': form, 'departamentos': Departamento.objects.all()})


# Create your views here.

def crear_articulo(request):
    articulos = Articulo.objects.all()  # Obtener todos los artículos
    form = ArticuloForm(request.POST or None)  # Crear el formulario
    if form.is_valid():
        form.save()  # Guardar el nuevo artículo
        return redirect('almacen:crear_articulo')  # Redirige a la misma página para mostrar el nuevo artículo
    return render(request, 'almacen/crear_articulo.html', {'form': form, 'articulos': articulos})

def editar_articulo(request, pk):
    articulo = get_object_or_404(Articulo, pk=pk)  # Obtener el artículo por su PK
    form = ArticuloForm(request.POST or None, instance=articulo)  # Rellenar el formulario con los datos existentes
    if form.is_valid():
        form.save()  # Guardar los cambios en el artículo
        return redirect('almacen:crear_articulo')  # Redirige a la vista de creación (o a donde desees)
    return render(request, 'almacen/editar_articulo.html', {'form': form, 'articulos': Articulo.objects.all()})


def crear_proveedor(request):
    proveedores = Proveedor.objects.all()  # Obtener todos los proveedores
    form = ProveedorForm(request.POST or None)  # Crear el formulario
    if form.is_valid():
        form.save()  # Guardar el nuevo proveedor
        return redirect('almacen:crear_proveedor')  # Redirige a la misma página para mostrar el nuevo proveedor
    return render(request, 'almacen/crear_proveedor.html', {'form': form, 'proveedores': proveedores})

def editar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)  # Obtener el proveedor por su PK
    form = ProveedorForm(request.POST or None, instance=proveedor)  # Rellenar el formulario con los datos existentes
    if form.is_valid():
        form.save()  # Guardar los cambios en el proveedor
        return redirect('almacen:crear_proveedor')  # Redirige a la vista de creación (o a donde desees)
    return render(request, 'almacen/editar_proveedor.html', {'form': form, 'proveedores': Proveedor.objects.all()})

# Views for Categoria

def crear_categoria(request):
    categorias = Categoria.objects.all()  # Obtener todas las categorías
    form = CategoriaForm(request.POST or None)  # Crear el formulario
    if form.is_valid():
        form.save()  # Guardar la nueva categoría
        return redirect('almacen:crear_categoria')  # Redirige a la misma página para mostrar la nueva categoría
    return render(request, 'almacen/crear_categoria.html', {'form': form, 'categorias': categorias})

def editar_categoria(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)  # Obtener la categoría por su PK
    form = CategoriaForm(request.POST or None, instance=categoria)  # Rellenar el formulario con los datos existentes
    if form.is_valid():
        form.save()  # Guardar los cambios en la categoría
        return redirect('almacen:crear_categoria')  # Redirige a la vista de creación (o a donde desees)
    return render(request, 'almacen/editar_categoria.html', {'form': form, 'categorias': Categoria.objects.all()})

def crear_unidad(request):
    unidades = UnidadDeMedida.objects.all()  # Obtener todas las unidades de medida
    form = UnidadDeMedidaForm(request.POST or None)  # Crear el formulario
    if form.is_valid():
        form.save()  # Guardar la nueva unidad de medida
        return redirect('almacen:crear_unidad')  # Redirige a la misma página para mostrar la nueva unidad
    return render(request, 'almacen/crear_unidad.html', {'form': form, 'unidades': unidades})

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

def editar_ubicacion(request, pk):
    ubicacion = get_object_or_404(Ubicacion, pk=pk)
    form = UbicacionForm(request.POST or None, instance=ubicacion)
    if form.is_valid():
        form.save()
        return redirect('almacen:crear_ubicacion')  # Redirige a la vista de creación
    return render(request, 'almacen/editar_ubicacion.html', {'form': form, 'ubicaciones': Ubicacion.objects.all()})

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
    return JsonResponse({
        'articulo': detalle.articulo_id,
        'cantidad': detalle.cantidad,
        'precio_unitario': detalle.precio_unitario,
        'renglon': detalle.renglon,
    })
    
def editar_detalle_factura(request):
    if request.method == 'POST':
        detalle_id = request.POST.get("detalle_id")  # Obtener el ID del detalle
        detalle = get_object_or_404(DetalleFactura, id=detalle_id)  # Buscar el detalle existente

        # Actualizar los campos del detalle
        detalle.articulo_id = request.POST.get("articulo")
        detalle.cantidad = int(request.POST.get("cantidad"))  # Convertir a entero
        detalle.precio_unitario = float(request.POST.get("precio_unitario"))  # Convertir a flotante
        detalle.renglon = request.POST.get("renglon")
        detalle.precio_total = detalle.cantidad * detalle.precio_unitario  # Multiplicación correcta
        detalle.save()

        return redirect('almacen:agregar_detalle_factura', form1h_id=detalle.form1h.id)

    return HttpResponseNotAllowed(['POST'])

@login_required
def user_create(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()  # Guarda el usuario si el formulario es válido
            return redirect('almacen:user_create')  # Redirige a la misma página
    else:
        form = UserForm()

    users = User.objects.all()  # Obtener todos los usuarios
    return render(request, 'almacen/user_form.html', {'form': form, 'users': users})


@login_required
def user_delete(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user.delete()
        return redirect('almacen:user_create')  # Redirige a la misma página para mostrar la lista actualizada
    return render(request, 'almacen/user_confirm_delete.html', {'user': user})


def home(request):
    return render(request, 'almacen/login.html')

def dahsboard(request):
    return render(request, 'almacen/dahsboard.html')


def signout(request):
    logout(request)
    return redirect('almacen:signin')


def signin(request):  
    if request.method == 'GET':
        # Deberías instanciar el AuthenticationForm correctamente
        return render(request, 'almacen/login.html', {
            'form': AuthenticationForm()
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
                elif g.name == 'Admin_tickets':
                    return redirect('tickets:tickets_dahsboard_adm')
                elif g.name == 'tecnico':
                    return redirect('tickets:tickets_dahsboard')
            # Si no se encuentra el grupo adecuado, se redirige a una página por defecto
            return redirect('dahsboard')
        else:
            # Si el formulario no es válido, se retorna con el error
            return render(request, 'almacen/login.html', {
                'form': form,  # Pasamos el formulario con los errores
                'error': 'Usuario o contraseña incorrectos'
            })
