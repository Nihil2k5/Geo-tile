"""
License Access Control Decorators
"""
from functools import wraps
from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
from land_registry.views.licensing_ui import get_user_license


def require_license_module(module_code, redirect_url='land_registry:gov_admin_overview'):
    """
    Decorator to check if user's license has access to a specific module.
    
    Usage:
        @require_license_module('landaudit')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user_license = get_user_license(request.user)
            
            if not user_license:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'No active license found. Please contact your administrator.'
                    }, status=403)
                messages.error(request, 'No active license found. Please contact your administrator.')
                return redirect(redirect_url)
            
            if not user_license.is_valid:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'License has expired or is not active.'
                    }, status=403)
                messages.error(request, 'License has expired or is not active.')
                return redirect(redirect_url)
            
            if not user_license.has_module(module_code):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': f'This feature requires the {module_code} module. Please request an upgrade.'
                    }, status=403)
                messages.warning(
                    request,
                    f'This feature requires an upgraded government license. '
                    f'Please request an upgrade to access {module_code}.'
                )
                return redirect('land_registry:gov_request_upgrade')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_valid_license(redirect_url='land_registry:gov_admin_overview'):
    """
    Decorator to check if user has a valid active license.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user_license = get_user_license(request.user)
            
            if not user_license or not user_license.is_valid:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'No valid license found.'
                    }, status=403)
                messages.error(request, 'No valid license found. Please contact your administrator.')
                return redirect(redirect_url)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
