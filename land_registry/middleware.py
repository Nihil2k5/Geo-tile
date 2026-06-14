from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from functools import wraps

class RoleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not hasattr(view_func, 'required_role'):
            return None

        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to access this page.')
            return redirect('land_registry:login')

        required_role = getattr(view_func, 'required_role')
        if request.user.role != required_role:
            messages.error(request, f'Access denied. {required_role.title()} role required.')
            return redirect('land_registry:dashboard')

        return None

def role_required(role):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Please log in to access this page.')
                return redirect('land_registry:login')
            
            if request.user.role != role:
                messages.error(request, f'Access denied. {role.title()} role required.')
                return redirect('land_registry:dashboard')
            
            return view_func(request, *args, **kwargs)
        
        _wrapped_view.required_role = role
        return _wrapped_view
    return decorator