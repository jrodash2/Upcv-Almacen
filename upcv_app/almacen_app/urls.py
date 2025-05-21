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
    path('form1h/', views.crear_form1h, name='crear_form1h'),
    path('factura/<int:form1h_id>/detalle/', views.agregar_detalle_factura, name='agregar_detalle_factura'),
    path('eliminar-detalle/<int:detalle_id>/', views.eliminar_detalle_factura, name='eliminar_detalle_factura'),
    path('almacen/editar-detalle-factura/', views.editar_detalle_factura, name='editar_detalle_factura'),
    path('almacen/obtener-detalle-factura/<int:detalle_id>/', views.obtener_detalle_factura, name='obtener_detalle_factura'),
    path('buscar-proveedor-nit/<str:nit>/', views.buscar_proveedor_nit, name='buscar_proveedor_nit'),
    path('buscar-proveedor-id/<int:proveedor_id>/', views.buscar_proveedor_id, name='buscar_proveedor_id'),
    path('agregar-detalle/<int:form1h_id>/', views.agregar_detalle_factura, name='agregar_detalle_factura'),
    path('confirmar-form1h/<int:form1h_id>/', views.confirmar_form1h, name='confirmar_form1h'),
    path('series/', views.serie_form_list, name='lista_series'),
    path('series/<int:pk>/editar/', views.serie_form_list, name='editar_serie'),


]
