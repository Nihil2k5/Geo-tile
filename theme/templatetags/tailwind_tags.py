from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()

@register.simple_tag
def tailwind_css():
    """Return the path to the compiled Tailwind CSS file."""
    return static('css/dist/styles.css')