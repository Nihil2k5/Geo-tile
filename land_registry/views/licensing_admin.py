"""
Licensing Admin Panel - Separate admin interface for license management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from datetime import timedelta

from land_registry.models import (
    License, LicenseModule, LicenseRequest, LicenseAuditLog, InstitutionUser, User
)


def is_provider_admin(user):
    """Check if user is a provider admin (admin role)"""
    return user.is_authenticated and user.role == 'admin'


def get_pending_requests_count():
    """Helper to get pending requests count for sidebar"""
    return LicenseRequest.objects.filter(status__in=['pending', 'under_review']).count()


@login_required
def licensing_admin_dashboard(request):
    """Main dashboard for licensing admin panel"""
    if not is_provider_admin(request.user):
        messages.error(request, 'Access denied. Provider admin privileges required.')
        return redirect('land_registry:dashboard')
    
    # Statistics
    total_licenses = License.objects.count()
    active_licenses = License.objects.filter(status='active').count()
    pending_licenses = License.objects.filter(status='pending').count()
    expired_licenses = License.objects.filter(status='expired').count()
    suspended_licenses = License.objects.filter(status='suspended').count()
    
    # Expiring soon (within 30 days)
    thirty_days_from_now = timezone.now().date() + timedelta(days=30)
    expiring_soon = License.objects.filter(
        status='active',
        valid_until__lte=thirty_days_from_now,
        valid_until__gte=timezone.now().date()
    ).count()
    
    # Pending requests
    pending_requests = LicenseRequest.objects.filter(status__in=['pending', 'under_review']).count()
    
    # Recent activity
    recent_licenses = License.objects.order_by('-created_at')[:5]
    recent_requests = LicenseRequest.objects.order_by('-submitted_at')[:5]
    recent_audit_logs = LicenseAuditLog.objects.select_related('license', 'performed_by').order_by('-timestamp')[:10]
    
    # Module usage statistics
    module_stats = LicenseModule.objects.annotate(
        license_count=Count('licenses', filter=Q(licenses__status='active'))
    ).order_by('display_order')
    
    context = {
        'total_licenses': total_licenses,
        'active_licenses': active_licenses,
        'pending_licenses': pending_licenses,
        'expired_licenses': expired_licenses,
        'suspended_licenses': suspended_licenses,
        'expiring_soon': expiring_soon,
        'pending_requests': pending_requests,
        'pending_requests_count': pending_requests,
        'recent_licenses': recent_licenses,
        'recent_requests': recent_requests,
        'recent_audit_logs': recent_audit_logs,
        'module_stats': module_stats,
    }
    
    return render(request, 'licensing_admin/dashboard.html', context)


@login_required
def licensing_admin_licenses(request):
    """List and manage all licenses"""
    if not is_provider_admin(request.user):
        messages.error(request, 'Access denied.')
        return redirect('land_registry:dashboard')
    
    # Filters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '').strip()
    license_type_filter = request.GET.get('type', '')
    
    licenses = License.objects.select_related('issued_by', 'approved_by').prefetch_related('modules').all()
    
    if status_filter:
        licenses = licenses.filter(status=status_filter)
    
    if license_type_filter:
        licenses = licenses.filter(license_type=license_type_filter)
    
    if search_query:
        licenses = licenses.filter(
            Q(license_number__icontains=search_query) |
            Q(institution_name__icontains=search_query) |
            Q(jurisdiction_state__icontains=search_query) |
            Q(jurisdiction_district__icontains=search_query) |
            Q(primary_contact_email__icontains=search_query)
        )
    
    licenses = licenses.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(licenses, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'licenses': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'license_type_filter': license_type_filter,
        'status_choices': License.STATUS_CHOICES,
        'license_type_choices': License.LICENSE_TYPES,
    }
    
    return render(request, 'licensing_admin/licenses.html', context)


@login_required
def licensing_admin_license_detail(request, license_id):
    """View detailed information about a specific license"""
    if not is_provider_admin(request.user):
        messages.error(request, 'Access denied.')
        return redirect('land_registry:dashboard')
    
    license_obj = get_object_or_404(
        License.objects.select_related('issued_by', 'approved_by').prefetch_related('modules'),
        id=license_id
    )
    
    # Get related data
    institution_users = InstitutionUser.objects.filter(license=license_obj).select_related('user', 'added_by')
    audit_logs = LicenseAuditLog.objects.filter(license=license_obj).select_related('performed_by').order_by('-timestamp')[:20]
    requests = LicenseRequest.objects.filter(license=license_obj).select_related('submitted_by', 'reviewed_by').order_by('-submitted_at')
    
    context = {
        'license': license_obj,
        'institution_users': institution_users,
        'audit_logs': audit_logs,
        'requests': requests,
    }
    
    return render(request, 'licensing_admin/license_detail.html', context)


@login_required
def licensing_admin_requests(request):
    """Manage license requests"""
    if not is_provider_admin(request.user):
        messages.error(request, 'Access denied.')
        return redirect('land_registry:dashboard')
    
    # Filters
    status_filter = request.GET.get('status', '')
    request_type_filter = request.GET.get('type', '')
    
    requests = LicenseRequest.objects.select_related(
        'license', 'submitted_by', 'reviewed_by'
    ).prefetch_related('requested_modules').all()
    
    if status_filter:
        requests = requests.filter(status=status_filter)
    
    if request_type_filter:
        requests = requests.filter(request_type=request_type_filter)
    
    requests = requests.order_by('-submitted_at')
    
    # Pagination
    paginator = Paginator(requests, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'requests': page_obj,
        'status_filter': status_filter,
        'request_type_filter': request_type_filter,
        'status_choices': LicenseRequest.STATUS_CHOICES,
        'request_type_choices': LicenseRequest.REQUEST_TYPES,
    }
    
    return render(request, 'licensing_admin/requests.html', context)


@login_required
def licensing_admin_modules(request):
    """Manage license modules"""
    if not is_provider_admin(request.user):
        messages.error(request, 'Access denied.')
        return redirect('land_registry:dashboard')
    
    modules = LicenseModule.objects.annotate(
        active_license_count=Count('licenses', filter=Q(licenses__status='active'))
    ).order_by('display_order', 'name')
    
    context = {
        'modules': modules,
    }
    
    return render(request, 'licensing_admin/modules.html', context)


@login_required
def licensing_admin_audit_log(request):
    """View comprehensive audit log"""
    if not is_provider_admin(request.user):
        messages.error(request, 'Access denied.')
        return redirect('land_registry:dashboard')
    
    # Filters
    action_filter = request.GET.get('action', '')
    license_filter = request.GET.get('license', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    audit_logs = LicenseAuditLog.objects.select_related(
        'license', 'performed_by'
    ).all()
    
    if action_filter:
        audit_logs = audit_logs.filter(action=action_filter)
    
    if license_filter:
        audit_logs = audit_logs.filter(license_id=license_filter)
    
    if date_from:
        audit_logs = audit_logs.filter(timestamp__date__gte=date_from)
    
    if date_to:
        audit_logs = audit_logs.filter(timestamp__date__lte=date_to)
    
    audit_logs = audit_logs.order_by('-timestamp')
    
    # Pagination
    paginator = Paginator(audit_logs, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get licenses for filter dropdown
    licenses = License.objects.order_by('license_number')
    
    context = {
        'audit_logs': page_obj,
        'action_filter': action_filter,
        'license_filter': license_filter,
        'date_from': date_from,
        'date_to': date_to,
        'licenses': licenses,
        'action_choices': LicenseAuditLog.ACTION_TYPES,
    }
    
    return render(request, 'licensing_admin/audit_log.html', context)


@login_required
@require_http_methods(["POST"])
def licensing_admin_create_license(request):
    """Create a new license (AJAX)"""
    if not is_provider_admin(request.user):
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    try:
        # Get form data
        license_number = request.POST.get('license_number', '').strip()
        institution_name = request.POST.get('institution_name', '').strip()
        license_type = request.POST.get('license_type', '')
        
        if not license_number or not institution_name or not license_type:
            return JsonResponse({'success': False, 'error': 'Missing required fields'}, status=400)
        
        # Check if license number already exists
        if License.objects.filter(license_number=license_number).exists():
            return JsonResponse({'success': False, 'error': 'License number already exists'}, status=400)
        
        # Create license
        license_obj = License.objects.create(
            license_number=license_number,
            institution_name=institution_name,
            license_type=license_type,
            institution_type=request.POST.get('institution_type', ''),
            jurisdiction_state=request.POST.get('jurisdiction_state', ''),
            jurisdiction_district=request.POST.get('jurisdiction_district', ''),
            primary_contact_name=request.POST.get('primary_contact_name', ''),
            primary_contact_email=request.POST.get('primary_contact_email', ''),
            primary_contact_phone=request.POST.get('primary_contact_phone', ''),
            valid_from=request.POST.get('valid_from') or timezone.now().date(),
            valid_until=request.POST.get('valid_until') or (timezone.now().date() + timedelta(days=365)),
            max_users=int(request.POST.get('max_users', 10)),
            max_api_calls_per_month=int(request.POST.get('max_api_calls_per_month', 1000)),
            status='pending',
            issued_by=request.user,
            issued_at=timezone.now(),
        )
        
        # Add modules
        module_ids = request.POST.getlist('modules')
        if module_ids:
            modules = LicenseModule.objects.filter(id__in=module_ids)
            license_obj.modules.set(modules)
        
        # Create audit log
        LicenseAuditLog.objects.create(
            license=license_obj,
            action='created',
            performed_by=request.user,
            details={'license_number': license_number},
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        
        return JsonResponse({
            'success': True,
            'message': f'License {license_number} created successfully',
            'license_id': license_obj.id
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
