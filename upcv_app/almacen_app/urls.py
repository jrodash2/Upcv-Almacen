from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'almacen'

# Manejador global de errores (esto debe estar fuera de urlpatterns)
handler403 = 'almacen_app.views.acceso_denegado'  # Asegúrate que el nombre de tu app sea correcto

urlpatterns = [
    path('', views.home, name='home'), 
    path('dahsboard/', views.dahsboard, name='dahsboard'),
    path('signin/', views.signin, name='signin'),
    path('logout/', views.signout, name='logout'),

    # Acceso denegado
    path('no-autorizado/', views.acceso_denegado, name='acceso_denegado'),

    # Usuarios
    path('usuario/crear/', views.user_create, name='user_create'),
    path('usuario/editar/<int:user_id>/', views.user_edit, name='user_edit'),

    path('usuario/eliminar/<int:user_id>/', views.user_delete, name='user_delete'),

    # Ubicaciones
    path('ubicacion/', views.crear_ubicacion, name='crear_ubicacion'),
    path('ubicacion/editar/<int:pk>/', views.editar_ubicacion, name='editar_ubicacion'),

    # Unidades
    path('unidad/', views.crear_unidad, name='crear_unidad'),
    path('unidad/editar/<int:pk>/', views.editar_unidad, name='editar_unidad'),

    # Categorías
    path('categoria/', views.crear_categoria, name='crear_categoria'),
    path('categoria/editar/<int:pk>/', views.editar_categoria, name='editar_categoria'),

    # Proveedores
    path('proveedor/', views.crear_proveedor, name='crear_proveedor'),
    path('proveedor/editar/<int:pk>/', views.editar_proveedor, name='editar_proveedor'),

    # Artículos
    path('articulo/', views.crear_articulo, name='crear_articulo'),
    path('articulo/editar/<int:pk>/', views.editar_articulo, name='editar_articulo'),

    # Departamentos
    path('departamento/', views.crear_departamento, name='crear_departamento'),
    path('departamento/editar/<int:pk>/', views.editar_departamento, name='editar_departamento'),
    path('departamentos/', views.lista_departamentos, name='lista_departamentos'),
    path('departamento/<int:pk>/', views.detalle_departamento, name='detalle_departamento'),

    # Asignación de usuarios a departamentos
    path('asignar-usuario-departamento/', views.asignar_departamento_usuario, name='asignar_departamento'),
    path('eliminar-asignacion/<int:usuario_id>/<int:departamento_id>/', views.eliminar_asignacion, name='eliminar_asignacion'),

    # Formularios 1H
    path('form1h/', views.crear_form1h, name='crear_form1h'),
    path('factura/<int:form1h_id>/detalle/', views.agregar_detalle_factura, name='agregar_detalle_factura'),
    path('eliminar-detalle/<int:detalle_id>/', views.eliminar_detalle_factura, name='eliminar_detalle_factura'),
    path('almacen/editar-detalle-factura/', views.editar_detalle_factura, name='editar_detalle_factura'),
    path('almacen/obtener-detalle-factura/<int:detalle_id>/', views.obtener_detalle_factura, name='obtener_detalle_factura'),
    path('agregar-detalle/<int:form1h_id>/', views.agregar_detalle_factura, name='agregar_detalle_factura'),
    path('confirmar-form1h/<int:form1h_id>/', views.confirmar_form1h, name='confirmar_form1h'),

    # Series
    path('series/', views.serie_form_list, name='lista_series'),
    path('series/<int:pk>/editar/', views.serie_form_list, name='editar_serie'),

    # Asignaciones
    path('asignacion-detalle/nueva/', views.crear_asignacion_detalle, name='crear_asignacion_detalle'),
    path('asignacion-detalle/nueva2/', views.crear_asignacion_detalle_articulo, name='crear_asignacion_detalle_articulo'),
    
    

    # Utilidades
    path('buscar-proveedor-nit/<str:nit>/', views.buscar_proveedor_nit, name='buscar_proveedor_nit'),
    path('buscar-proveedor-id/<int:proveedor_id>/', views.buscar_proveedor_id, name='buscar_proveedor_id'),
    path('buscar-articulos/', views.buscar_articulos, name='buscar_articulos'),
    path('stock-formulario-1h/', views.ver_stock_formulario_1h, name='ver_stock_formulario_1h'),
    
    # Kardex
    path('kardex/<int:articulo_id>/', views.historial_kardex_articulo, name='historial_kardex'),
    path('kardex/<int:articulo_id>/exportar/', views.exportar_kardex_pdf, name='exportar_kardex_pdf'),
    
    # Cambiar contraseña
    path('cambiar-contraseña/', auth_views.PasswordChangeView.as_view(
        template_name='almacen/password_change_form.html',
        success_url='/cambiar-contraseña/hecho/'  # Redirección tras éxito
    ), name='password_change'),

    path('cambiar-contraseña/hecho/', auth_views.PasswordChangeDoneView.as_view(
        template_name='almacen/password_change_done.html'
    ), name='password_change_done'),
    
  
    path('requerimientos/crear/', views.crear_requerimiento, name='crear_requerimiento'),
    path('requerimientos/<int:requerimiento_id>/', views.detalle_requerimiento, name='detalle_requerimiento'),
    path('detalle-requerimiento/eliminar/<int:pk>/', views.eliminar_detalle_requerimiento, name='eliminar_detalle_requerimiento'),
    path('api/detalle_requerimiento/<int:detalle_id>/', views.detalle_requerimiento_api, name='detalle_requerimiento_api'),
    path('editar_detalle_requerimiento/', views.editar_detalle_requerimiento, name='editar_detalle_requerimiento'),
    path('enviar_requerimiento/<int:requerimiento_id>/', views.enviar_requerimiento, name='enviar_requerimiento'),
    path('requerimientos/despachar/<int:requerimiento_id>/', views.despachar_requerimiento, name='despachar_requerimiento'),
    path('requerimiento/<int:requerimiento_id>/pdf/', views.exportar_requerimiento_pdf, name='exportar_requerimiento_pdf'),
    path('institucion/editar/', views.editar_institucion, name='editar_institucion'),
    
    
    path('programa/crear/', views.crear_programa, name='crear_programa'),
    path('programa/editar/<int:pk>/', views.editar_programa, name='editar_programa'),
    
    path('dependencia/crear/', views.crear_dependencia, name='crear_dependencia'),
    path('dependencia/editar/<int:pk>/', views.editar_dependencia, name='editar_dependencia'),
    
    path('transferir-articulos/', views.transferir_articulos, name='transferir_articulos'),
    path('historial-transferencias/', views.historial_transferencias, name='historial_transferencias'),
    path('api/articulos_asignados/<int:departamento_id>/', views.articulos_asignados, name='articulos_asignados'),
    path('articulos/por-vencer/', views.articulos_por_vencer, name='articulos_por_vencer'),









]
