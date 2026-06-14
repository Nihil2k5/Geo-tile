import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from django.contrib.sites.models import Site

try:
    site = Site.objects.get_current()
    print(f"Current site: {site.name} (ID: {site.id})")
except Exception as e:
    print(f"Error: {e}")
