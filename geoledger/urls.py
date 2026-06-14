"""
URL configuration for geoledger project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from land_registry.admin import admin_site

urlpatterns = [
    path('admin/', admin_site.urls),  # Custom government admin
    path('django-admin/', admin.site.urls),  # Default Django admin (backup)
    path('', include('land_registry.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # Serve media files in development
