from django.apps import AppConfig

class LandRegistryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'land_registry'

    def ready(self):
        import land_registry.signals  # Import signals when app is ready
