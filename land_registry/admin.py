from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.admin import AdminSite
from django.template.response import TemplateResponse
from django.urls import path
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from .models import (
    User, Parcel, Dispute, Transaction, ParcelHistory,
    License, LicenseModule, LicenseRequest, LicenseAuditLog, InstitutionUser
)

class GovernmentAdminSite(AdminSite):
    site_header = 'Government Land Registry Administration'
    site_title = 'Land Registry Admin'
    index_title = 'Government Land Registry Dashboard'
    
    def index(self, request, extra_context=None):
        """
        Display the main admin index page with dashboard statistics.
        """
        extra_context = extra_context or {}
        
        # Get dashboard statistics
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        
        # Basic counts
        total_parcels = Parcel.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        pending_disputes = Dispute.objects.filter(status='pending').count()
        blockchain_transactions = Transaction.objects.exclude(transaction_hash__isnull=True).count()
        
        # Recent objects
        latest_parcel = Parcel.objects.order_by('-created_at').first()
        latest_user = User.objects.order_by('-date_joined').first()
        
        # Monthly registration data (last 6 months)
        monthly_data = []
        for i in range(6):
            month_start = (now - timedelta(days=30*i)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            count = Parcel.objects.filter(
                created_at__gte=month_start,
                created_at__lte=month_end
            ).count()
            monthly_data.append({
                'month': month_start.strftime('%b'),
                'count': count
            })
        
        # Parcel status distribution
        parcel_stats = Parcel.objects.aggregate(
            active=Count('id', filter=Q(status='active')),
            pending=Count('id', filter=Q(status='pending')),
            surveyed=Count('id', filter=Q(status='surveyed')),
            disputed=Count('id', filter=Q(status='disputed')),
            locked=Count('id', filter=Q(status='locked')),
            rejected=Count('id', filter=Q(status='rejected'))
        )
        
        extra_context.update({
            'total_parcels': total_parcels,
            'active_users': active_users,
            'pending_disputes': pending_disputes,
            'blockchain_transactions': blockchain_transactions,
            'latest_parcel': latest_parcel,
            'latest_user': latest_user,
            'monthly_registrations': list(reversed(monthly_data)),
            'parcel_stats': parcel_stats,
        })
        
        return super().index(request, extra_context)

# Create custom admin site instance
admin_site = GovernmentAdminSite(name='government_admin')

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'wallet_address', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Role & Wallet', {'fields': ('role', 'wallet_address')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'role'),
        }),
    )
    search_fields = ('username', 'email', 'first_name', 'last_name', 'wallet_address')
    ordering = ('username',)

class ParcelAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner', 'location', 'area', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('location', 'owner__username', 'description')
    readonly_fields = ('created_at', 'updated_at')

class DisputeAdmin(admin.ModelAdmin):
    list_display = ('id', 'parcel', 'complainant', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('parcel__location', 'complainant__username', 'description')
    readonly_fields = ('created_at', 'updated_at', 'resolved_at')

class TransactionAdmin(admin.ModelAdmin):
    list_display = ['transaction_type', 'parcel', 'from_user', 'to_user', 'status', 'timestamp']
    list_filter = ['transaction_type', 'status', 'timestamp']
    search_fields = ['parcel__parcel_id', 'from_user__username', 'to_user__username', 'transaction_hash']
    readonly_fields = ['transaction_hash', 'timestamp', 'approved_at', 'confirmed_at', 'completed_at']
    
class ParcelHistoryAdmin(admin.ModelAdmin):
    list_display = ['parcel', 'change_type', 'changed_by', 'timestamp']
    list_filter = ['change_type', 'timestamp']
    search_fields = ['parcel__parcel_id', 'changed_by__username']
    readonly_fields = ['timestamp']

# Register models with custom admin site
admin_site.register(User, CustomUserAdmin)
admin_site.register(Parcel, ParcelAdmin)
admin_site.register(Dispute, DisputeAdmin)
admin_site.register(Transaction, TransactionAdmin)
admin_site.register(ParcelHistory, ParcelHistoryAdmin)

class LicenseModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_mandatory', 'is_active', 'display_order')
    list_filter = ('is_mandatory', 'is_active')
    search_fields = ('name', 'code', 'description')
    ordering = ('display_order', 'name')


class LicenseAdmin(admin.ModelAdmin):
    list_display = ('license_number', 'institution_name', 'license_type', 'status', 'valid_from', 'valid_until', 'is_valid')
    list_filter = ('status', 'license_type', 'valid_until')
    search_fields = ('license_number', 'institution_name', 'jurisdiction_state', 'jurisdiction_district')
    readonly_fields = ('created_at', 'updated_at', 'license_hash', 'is_valid', 'days_until_expiry')
    filter_horizontal = ('modules',)
    fieldsets = (
        ('License Information', {
            'fields': ('license_number', 'license_type', 'status', 'institution_name', 'institution_type')
        }),
        ('Jurisdiction', {
            'fields': ('jurisdiction_state', 'jurisdiction_district')
        }),
        ('Contact Information', {
            'fields': ('primary_contact_name', 'primary_contact_email', 'primary_contact_phone')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_until', 'auto_renew')
        }),
        ('Usage Limits', {
            'fields': ('max_users', 'current_user_count', 'max_api_calls_per_month', 'current_month_api_calls', 'api_calls_reset_date')
        }),
        ('Modules', {
            'fields': ('modules',)
        }),
        ('Approval', {
            'fields': ('issued_by', 'issued_at', 'approved_by', 'approved_at')
        }),
        ('Audit', {
            'fields': ('license_hash', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


class LicenseRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'request_type', 'institution_name', 'status', 'submitted_at', 'reviewed_by')
    list_filter = ('status', 'request_type', 'submitted_at')
    search_fields = ('institution_name', 'contact_name', 'contact_email', 'justification')
    readonly_fields = ('submitted_at', 'reviewed_at')
    filter_horizontal = ('requested_modules',)
    fieldsets = (
        ('Request Information', {
            'fields': ('request_type', 'status', 'license')
        }),
        ('Institution Details', {
            'fields': ('institution_name', 'contact_name', 'contact_email', 'contact_phone')
        }),
        ('Request Details', {
            'fields': ('requested_modules', 'justification')
        }),
        ('Workflow', {
            'fields': ('submitted_by', 'submitted_at', 'reviewed_by', 'reviewed_at', 'review_notes')
        }),
    )


class LicenseAuditLogAdmin(admin.ModelAdmin):
    list_display = ('license', 'action', 'performed_by', 'timestamp', 'ip_address')
    list_filter = ('action', 'timestamp')
    search_fields = ('license__license_number', 'license__institution_name', 'performed_by__username')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'


class InstitutionUserAdmin(admin.ModelAdmin):
    list_display = ('user', 'license', 'is_primary_contact', 'added_at')
    list_filter = ('is_primary_contact', 'added_at')
    search_fields = ('user__username', 'license__license_number', 'license__institution_name')
    readonly_fields = ('added_at',)


# Register licensing models
admin_site.register(LicenseModule, LicenseModuleAdmin)
admin_site.register(License, LicenseAdmin)
admin_site.register(LicenseRequest, LicenseRequestAdmin)
admin_site.register(LicenseAuditLog, LicenseAuditLogAdmin)
admin_site.register(InstitutionUser, InstitutionUserAdmin)

# Also register with default admin for backward compatibility
admin.site.register(User, CustomUserAdmin)
admin.site.register(Parcel, ParcelAdmin)
admin.site.register(Dispute, DisputeAdmin)
admin.site.register(LicenseModule, LicenseModuleAdmin)
admin.site.register(License, LicenseAdmin)
admin.site.register(LicenseRequest, LicenseRequestAdmin)
admin.site.register(LicenseAuditLog, LicenseAuditLogAdmin)
admin.site.register(InstitutionUser, InstitutionUserAdmin)