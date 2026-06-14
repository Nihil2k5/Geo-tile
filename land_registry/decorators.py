from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def role_required(role):
    """
    Decorator for views that checks that the user has the required role,
    redirecting to the login page if necessary.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Please log in to access this page.')
                return redirect('login')
            if not request.user.role == role:
                messages.error(request, f'Access denied. You must be a {role} to view this page.')
                return redirect('land_registry:dashboard')
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def citizen_required(function):
    """
    Decorator for views that checks that the logged-in user is a citizen.
    """
    return role_required('citizen')(function)

def registrar_required(function):
    """
    Decorator for views that checks that the logged-in user is a registrar.
    """
    return role_required('registrar')(function)

def surveyor_required(function):
    """
    Decorator for views that checks that the logged-in user is a surveyor.
    """
    return role_required('surveyor')(function)

def court_required(function):
    """
    Decorator for views that checks that the logged-in user is a court authority.
    """
    return role_required('court')(function)

def admin_required(function):
    """
    Decorator for views that checks that the logged-in user is an admin.
    """
    return role_required('admin')(function)