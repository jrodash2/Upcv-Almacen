from django.urls import path
from . import views

app_name = 'almacen'

urlpatterns = [
    path('', views.home, name='home'), 
    path('dahsboard/', views.dahsboard, name='dahsboard'),
    path('signin/', views.signin, name='signin'),
    path('logout/', views.signout, name='logout'),
    path('usuario/crear/', views.user_create, name='user_create'),
    path('usuario/eliminar/<int:user_id>/', views.user_delete, name='user_delete'),
    path('ubicacion/', views.crear_ubicacion, name='crear_ubicacion'),  # Vista para crear y listar ubicaciones
    path('ubicacion/editar/<int:pk>/', views.editar_ubicacion, name='editar_ubicacion'),  # Vista para editar una ubicación
    path('unidad/', views.crear_unidad, name='crear_unidad'),  
    path('unidad/editar/<int:pk>/', views.editar_unidad, name='editar_unidad'),  
    path('categoria/', views.crear_categoria, name='crear_categoria'),  # Vista para crear y listar categorías
    path('categoria/editar/<int:pk>/', views.editar_categoria, name='editar_categoria'),  # Vista para editar una categoría
    path('proveedor/', views.crear_proveedor, name='crear_proveedor'),  # Vista para crear y listar proveedores
    path('proveedor/editar/<int:pk>/', views.editar_proveedor, name='editar_proveedor'),  # Vista para editar un proveedor
    path('articulo/', views.crear_articulo, name='crear_articulo'),  # Vista para crear y listar artículos
    path('articulo/editar/<int:pk>/', views.editar_articulo, name='editar_articulo'),  # Vista para editar un artículo
    path('departamento/', views.crear_departamento, name='crear_departamento'),  # Vista para crear y listar departamentos
    path('departamento/editar/<int:pk>/', views.editar_departamento, name='editar_departamento'),  # Vista para editar un departamentos
<<<<<<< HEAD
    path('form1h/', views.crear_form1h, name='crear_form1h'),
    path('proveedor/<int:pk>/', views.proveedor_detail, name='proveedor_detail'),
]
=======
    path('crear_form1h/', views.CrearForm1hView.as_view(), name='crear_form1h'),
    path('obtener_proveedor_info/<int:proveedor_id>/', views.obtener_proveedor_info, name='obtener_proveedor_info'),
    path('crear_detalle_factura/<int:pk>/', views.CrearDetalleFacturaView.as_view(), name='crear_detalle_factura'),
    path('detalle_factura/<int:pk>/', views.DetalleFacturaView.as_view(), name='detalle_factura'),

    ]
>>>>>>> 586e3764a27b14c0007006edb37629706ef73ccf
