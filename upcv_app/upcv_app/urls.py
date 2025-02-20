from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('almacen/', include('almacen_app.urls')),  # Incluye las URLs de tu aplicación
    path('', include('almacen_app.urls')),  # Esto redirige la raíz al signin o vista principal
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
