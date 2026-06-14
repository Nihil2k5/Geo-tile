"""
Context processors for templates
"""
from land_registry.models import LicenseRequest


def licensing_admin_context(request):
    """Add licensing admin context to all templates"""
    if request.user.is_authenticated and request.user.role == 'admin':
        pending_count = LicenseRequest.objects.filter(status__in=['pending', 'under_review']).count()
        return {
            'pending_requests_count': pending_count,
        }
    return {
        'pending_requests_count': 0,
    }
