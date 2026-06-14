"""
Licensing System Views - GovTech SaaS License Management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json

from land_registry.models import (
    License, LicenseModule, LicenseRequest, LicenseAuditLog, InstitutionUser, User
)


def get_user_license(user):
    """Get the active license for a user (if any)"""
    try:
        institution_user = InstitutionUser.objects.filter(
            user=user,
            license__status='active'
        ).select_related('license').first()
        if institution_user:
            license_obj = institution_user.license
            if license_obj.is_valid:
                return license_obj
    except Exception:
        pass
    return None


@login_required
def gov_admin_overview(request):
    """Government Admin: View active license and module status"""
    user_license = get_user_license(request.user)
    
    # Get all available modules
    all_modules = LicenseModule.objects.filter(is_active=True).order_by('display_order', 'name')
    
    # Get enabled modules for this license
    enabled_module_codes = set()
    if user_license:
        enabled_module_codes = set(user_license.modules.filter(is_active=True).values_list('code', flat=True))
    
    # Prepare module data
    modules_data = []
    for module in all_modules:
        modules_data.append({
            'module': module,
            'enabled': module.code in enabled_module_codes,
            'is_mandatory': module.is_mandatory,
        })
    
    # Get recent audit logs
    recent_logs = []
    if user_license:
        recent_logs = LicenseAuditLog.objects.filter(license=user_license).order_by('-timestamp')[:10]
    
    # Get pending requests
    pending_requests = []
    if user_license:
        pending_requests = LicenseRequest.objects.filter(
            license=user_license,
            status__in=['pending', 'under_review']
        ).order_by('-submitted_at')[:5]
    
    context = {
        'user_license': user_license,
        'modules_data': modules_data,
        'recent_logs': recent_logs,
        'pending_requests': pending_requests,
        'has_license': user_license is not None,
    }
    
    return render(request, 'licensing_ui/gov_admin_overview.html', context)


def license_certificate(request, license_id=None):
    """Display professional license certificate"""
    from datetime import timedelta
    
    # If license_id provided, check if user has access
    if license_id:
        license_obj = get_object_or_404(License, id=license_id)
        if request.user.is_authenticated:
            user_license = get_user_license(request.user)
            # Check access: admin or license owner
            if request.user.role != 'admin' and user_license != license_obj:
                messages.error(request, 'Access denied.')
                return redirect('land_registry:gov_admin_overview')
    else:
        # Get user's license if authenticated
        if request.user.is_authenticated:
            user_license = get_user_license(request.user)
            if user_license:
                license_obj = user_license
            else:
                # Create a sample license for display
                license_obj = create_demo_license(request.user)
        else:
            # Create a sample license for unauthenticated users
            license_obj = create_demo_license(None)
    
    # Get enabled modules
    if hasattr(license_obj, 'modules') and hasattr(license_obj.modules, 'filter'):
        # Real license object
        enabled_modules = license_obj.modules.filter(is_active=True).order_by('display_order', 'name')
    else:
        # Sample license - modules is a list
        enabled_modules = license_obj.modules if isinstance(license_obj.modules, list) else []
    
    context = {
        'license': license_obj,
        'enabled_modules': enabled_modules,
        'is_owner': False,
        'has_license': True,
    }
    
    return render(request, 'licensing_ui/license_certificate.html', context)


def create_demo_license(user=None):
    """Create a sample license object for display"""
    from datetime import timedelta
    from django.utils import timezone
    
    # Create a sample license object
    class SampleLicense:
        license_number = "GL-2024-001"
        license_type = "institution"
        status = "active"
        institution_name = "State Government Administration"
        institution_type = "State Government"
        jurisdiction_state = "State"
        jurisdiction_district = "District"
        primary_contact_name = user.get_full_name() if user and user.get_full_name() else "Administrator"
        primary_contact_email = user.email if user and user.email else "admin@geoledger.gov"
        primary_contact_phone = "+1-234-567-8900"
        valid_from = timezone.now().date() - timedelta(days=30)
        valid_until = timezone.now().date() + timedelta(days=335)
        auto_renew = True
        max_users = 100
        current_user_count = 45
        max_api_calls_per_month = 10000
        current_month_api_calls = 3250
        api_calls_reset_date = None
        approved_by = None
        approved_at = None
        license_hash = "0x" + "a" * 64  # Sample hash
        created_at = timezone.now() - timedelta(days=30)
        updated_at = timezone.now()
        
        @property
        def is_valid(self):
            today = timezone.now().date()
            return self.status == 'active' and self.valid_from <= today <= self.valid_until
        
        @property
        def days_until_expiry(self):
            return (self.valid_until - timezone.now().date()).days
        
        def get_license_type_display(self):
            return "Institution License (State/District)"
        
        def get_status_display(self):
            return "Active"
        
        @property
        def modules(self):
            # Return a list of mock module objects
            class MockModule:
                def __init__(self, name, code, description):
                    self.name = name
                    self.code = code
                    self.description = description
                    self.is_active = True
                    self.display_order = 0
            
            # Return mock modules as a list (not a queryset)
            return [
                MockModule('LandCore', 'landcore', 'Core land registry operations, mandatory for all licenses.'),
                MockModule('LandVerify', 'landverify', 'Advanced verification workflows for banks and field validation.'),
                MockModule('LandAudit', 'landaudit', 'Fraud detection, anomaly reporting, and dispute analytics.'),
            ]
    
    return SampleLicense()


@login_required
def gov_request_upgrade(request):
    """Government Admin: Request license upgrade"""
    user_license = get_user_license(request.user)
    
    if not user_license:
        messages.error(request, 'No active license found. Please contact your administrator.')
        return redirect('land_registry:gov_admin_overview')
    
    # Get available modules
    all_modules = LicenseModule.objects.filter(is_active=True).order_by('display_order', 'name')
    current_module_codes = set(user_license.modules.filter(is_active=True).values_list('code', flat=True))
    
    # Get modules not yet enabled
    available_modules = [m for m in all_modules if m.code not in current_module_codes]
    
    if request.method == 'POST':
        module_ids = request.POST.getlist('requested_modules')
        justification = request.POST.get('justification', '').strip()
        
        if not module_ids:
            messages.error(request, 'Please select at least one module to request.')
        elif not justification:
            messages.error(request, 'Please provide a justification for the upgrade request.')
        else:
            # Create upgrade request
            upgrade_request = LicenseRequest.objects.create(
                request_type='upgrade',
                license=user_license,
                institution_name=user_license.institution_name,
                contact_name=user_license.primary_contact_name,
                contact_email=user_license.primary_contact_email,
                contact_phone=user_license.primary_contact_phone,
                justification=justification,
                submitted_by=request.user,
            )
            
            # Add requested modules
            requested_modules = LicenseModule.objects.filter(id__in=module_ids)
            upgrade_request.requested_modules.set(requested_modules)
            
            # Create audit log
            LicenseAuditLog.objects.create(
                license=user_license,
                action='upgrade_requested',
                performed_by=request.user,
                details={
                    'request_id': upgrade_request.id,
                    'modules': list(requested_modules.values_list('code', flat=True)),
                },
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            
            messages.success(request, 'Upgrade request submitted successfully. It will be reviewed by the provider administrator.')
            return redirect('land_registry:gov_admin_overview')
    
    context = {
        'user_license': user_license,
        'available_modules': available_modules,
    }
    
    return render(request, 'licensing_ui/gov_request_upgrade.html', context)


@login_required
def provider_super_admin(request):
    """Provider Super Admin: Manage all licenses and requests"""
    # Only allow admin users
    if request.user.role != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('land_registry:dashboard')
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '').strip()
    
    # Get all licenses
    licenses = License.objects.all().select_related('issued_by', 'approved_by').prefetch_related('modules')
    
    # Apply filters
    if status_filter:
        licenses = licenses.filter(status=status_filter)
    
    if search_query:
        licenses = licenses.filter(
            Q(license_number__icontains=search_query) |
            Q(institution_name__icontains=search_query) |
            Q(jurisdiction_state__icontains=search_query) |
            Q(jurisdiction_district__icontains=search_query)
        )
    
    licenses = licenses.order_by('-created_at')
    
    # Get pending requests
    pending_requests = LicenseRequest.objects.filter(
        status__in=['pending', 'under_review']
    ).select_related('license', 'submitted_by').prefetch_related('requested_modules').order_by('-submitted_at')
    
    # Statistics
    stats = {
        'total_licenses': License.objects.count(),
        'active_licenses': License.objects.filter(status='active').count(),
        'expired_licenses': License.objects.filter(status='expired').count(),
        'pending_requests': LicenseRequest.objects.filter(status='pending').count(),
    }
    
    context = {
        'licenses': licenses,
        'pending_requests': pending_requests,
        'stats': stats,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'licensing_ui/provider_super_admin.html', context)


@login_required
@require_http_methods(["POST"])
def provider_approve_request(request, request_id):
    """Provider: Approve a license upgrade request"""
    if request.user.role != 'admin':
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    upgrade_request = get_object_or_404(LicenseRequest, id=request_id)
    
    if upgrade_request.status not in ['pending', 'under_review']:
        return JsonResponse({'success': False, 'error': 'Request already processed'}, status=400)
    
    # Approve the request
    upgrade_request.status = 'approved'
    upgrade_request.reviewed_by = request.user
    upgrade_request.reviewed_at = timezone.now()
    upgrade_request.review_notes = request.POST.get('review_notes', '').strip()
    upgrade_request.save()
    
    # Add modules to license
    if upgrade_request.license:
        license_obj = upgrade_request.license
        requested_modules = upgrade_request.requested_modules.all()
        license_obj.modules.add(*requested_modules)
        
        # Create audit log
        LicenseAuditLog.objects.create(
            license=license_obj,
            action='upgrade_approved',
            performed_by=request.user,
            details={
                'request_id': upgrade_request.id,
                'modules_added': list(requested_modules.values_list('code', flat=True)),
            },
            ip_address=request.META.get('REMOTE_ADDR'),
        )
    
    messages.success(request, f'Upgrade request #{upgrade_request.id} approved successfully.')
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def provider_reject_request(request, request_id):
    """Provider: Reject a license upgrade request"""
    if request.user.role != 'admin':
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    upgrade_request = get_object_or_404(LicenseRequest, id=request_id)
    
    if upgrade_request.status not in ['pending', 'under_review']:
        return JsonResponse({'success': False, 'error': 'Request already processed'}, status=400)
    
    # Reject the request
    upgrade_request.status = 'rejected'
    upgrade_request.reviewed_by = request.user
    upgrade_request.reviewed_at = timezone.now()
    upgrade_request.review_notes = request.POST.get('review_notes', '').strip()
    upgrade_request.save()
    
    # Create audit log
    if upgrade_request.license:
        LicenseAuditLog.objects.create(
            license=upgrade_request.license,
            action='upgrade_rejected',
            performed_by=request.user,
            details={
                'request_id': upgrade_request.id,
                'reason': upgrade_request.review_notes,
            },
            ip_address=request.META.get('REMOTE_ADDR'),
        )
    
    messages.success(request, f'Upgrade request #{upgrade_request.id} rejected.')
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def provider_activate_license(request, license_id):
    """Provider: Activate a license"""
    if request.user.role != 'admin':
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    license_obj = get_object_or_404(License, id=license_id)
    
    if license_obj.status != 'pending':
        return JsonResponse({'success': False, 'error': 'License cannot be activated'}, status=400)
    
    # Activate license
    license_obj.status = 'active'
    license_obj.approved_by = request.user
    license_obj.approved_at = timezone.now()
    license_obj.save()
    
    # Create audit log
    LicenseAuditLog.objects.create(
        license=license_obj,
        action='activated',
        performed_by=request.user,
        details={},
        ip_address=request.META.get('REMOTE_ADDR'),
    )
    
    messages.success(request, f'License {license_obj.license_number} activated successfully.')
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def provider_suspend_license(request, license_id):
    """Provider: Suspend a license"""
    if request.user.role != 'admin':
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    license_obj = get_object_or_404(License, id=license_id)
    
    if license_obj.status != 'active':
        return JsonResponse({'success': False, 'error': 'Only active licenses can be suspended'}, status=400)
    
    # Suspend license
    license_obj.status = 'suspended'
    license_obj.save()
    
    # Create audit log
    LicenseAuditLog.objects.create(
        license=license_obj,
        action='suspended',
        performed_by=request.user,
        details={},
        ip_address=request.META.get('REMOTE_ADDR'),
    )
    
    messages.success(request, f'License {license_obj.license_number} suspended.')
    return JsonResponse({'success': True})


@login_required
def license_audit_log(request, license_id):
    """View audit log for a specific license"""
    license_obj = get_object_or_404(License, id=license_id)
    
    # Check access
    user_license = get_user_license(request.user)
    if request.user.role != 'admin' and user_license != license_obj:
        messages.error(request, 'Access denied.')
        return redirect('land_registry:gov_admin_overview')
    
    audit_logs = LicenseAuditLog.objects.filter(license=license_obj).select_related('performed_by').order_by('-timestamp')
    
    context = {
        'license': license_obj,
        'audit_logs': audit_logs,
    }
    
    return render(request, 'licensing_ui/license_audit_log.html', context)
