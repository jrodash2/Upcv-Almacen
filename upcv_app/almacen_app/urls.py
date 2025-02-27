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

]
