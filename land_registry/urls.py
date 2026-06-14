from django.urls import path
from django.contrib.auth.views import LogoutView

from .views.auth import register, login_view, dashboard, verify_email
from .views.dashboard.admin import admin_dashboard, user_management, system_metrics
from .views.dashboard.registrar import registrar_dashboard, land_registration, verify_land as registrar_verify_land, process_document_ai, extract_document_ai, pending_transfers, approve_transfer, reject_transfer
from .views.dashboard.surveyor import surveyor_dashboard, survey_list, survey_map, update_survey
from .views.dashboard.citizen import citizen_dashboard, manage_disputes, my_properties, execute_approved_transfer
from .views.dashboard.court import court_dashboard, dispute_list, resolve_dispute, court_metrics
from .views.dashboard.transfer import transfer_property
from .views.verify import verify_land
from .views.map import registered_lands_map
from .views.parcel_history import parcel_complete_history, parcel_mother_patta, parcel_history_api, add_parcel_note, parcel_timeline
from .views.block_explorer import block_explorer, parcel_explorer_detail
from .views.licensing_ui import (
    gov_admin_overview, gov_request_upgrade, provider_super_admin,
    provider_approve_request, provider_reject_request,
    provider_activate_license, provider_suspend_license, license_audit_log,
    license_certificate
)
from .views.licensing_admin import (
    licensing_admin_dashboard, licensing_admin_licenses, licensing_admin_license_detail,
    licensing_admin_requests, licensing_admin_modules, licensing_admin_audit_log,
    licensing_admin_create_license
)

app_name = 'land_registry'

urlpatterns = [
    # Landing Page
    path('', verify_land, name='landing'),
    
    # Public Verification
    path('verify/', verify_land, name='verify_land'),
    
    # Registered Lands Map
    path('map/', registered_lands_map, name='registered_lands_map'),
    
    # Block Explorer
    path('explorer/', block_explorer, name='block_explorer'),
    path('explorer/parcel/<int:parcel_id>/', parcel_explorer_detail, name='explorer_parcel_detail'),

    # Licensing System (Government Users)
    path('licensing/', gov_admin_overview, name='gov_admin_overview'),
    path('licensing/request-upgrade/', gov_request_upgrade, name='gov_request_upgrade'),
    path('licensing/certificate/', license_certificate, name='license_certificate'),
    path('licensing/certificate/<int:license_id>/', license_certificate, name='license_certificate_detail'),
    path('licensing/audit-log/<int:license_id>/', license_audit_log, name='license_audit_log'),
    
    # Licensing Admin Panel (Provider Admin)
    path('licensing-admin/', licensing_admin_dashboard, name='licensing_admin_dashboard'),
    path('licensing-admin/licenses/', licensing_admin_licenses, name='licensing_admin_licenses'),
    path('licensing-admin/licenses/<int:license_id>/', licensing_admin_license_detail, name='licensing_admin_license_detail'),
    path('licensing-admin/requests/', licensing_admin_requests, name='licensing_admin_requests'),
    path('licensing-admin/modules/', licensing_admin_modules, name='licensing_admin_modules'),
    path('licensing-admin/audit-log/', licensing_admin_audit_log, name='licensing_admin_audit_log'),
    path('licensing-admin/create-license/', licensing_admin_create_license, name='licensing_admin_create_license'),
    
    # Legacy provider admin routes (redirect to new admin panel)
    path('licensing/provider-admin/', provider_super_admin, name='provider_super_admin'),
    path('licensing/provider/approve-request/<int:request_id>/', provider_approve_request, name='provider_approve_request'),
    path('licensing/provider/reject-request/<int:request_id>/', provider_reject_request, name='provider_reject_request'),
    path('licensing/provider/activate-license/<int:license_id>/', provider_activate_license, name='provider_activate_license'),
    path('licensing/provider/suspend-license/<int:license_id>/', provider_suspend_license, name='provider_suspend_license'),
    
    # Authentication URLs
    path('login/', login_view, name='login'),
    path('logout/', LogoutView.as_view(next_page='land_registry:login'), name='logout'),
    path('register/', register, name='register'),
    path('verify-email/<str:token>/', verify_email, name='verify_email'),
    path('dashboard/', dashboard, name='dashboard'),
    
    # Admin Dashboard
    path('admin/dashboard/', admin_dashboard, name='admin_dashboard'),
    path('admin/users/', user_management, name='user_management'),
    path('admin/metrics/', system_metrics, name='system_metrics'),
    
    # Registrar Dashboard
    path('registrar/dashboard/', registrar_dashboard, name='registrar_dashboard'),
    path('registrar/register-land/', land_registration, name='land_registration'),
    path('registrar/verify-land/', registrar_verify_land, name='registrar_verify_land'),
    path('registrar/extract-document-ai/', extract_document_ai, name='extract_document_ai'),
    path('registrar/process-document-ai/<int:parcel_id>/', process_document_ai, name='process_document_ai'),
    path('registrar/pending-transfers/', pending_transfers, name='pending_transfers'),
    path('registrar/approve-transfer/<int:transaction_id>/', approve_transfer, name='approve_transfer'),
    path('registrar/reject-transfer/<int:transaction_id>/', reject_transfer, name='reject_transfer'),
    
    # Surveyor Dashboard
    path('surveyor/dashboard/', surveyor_dashboard, name='surveyor_dashboard'),
    path('surveyor/surveys/', survey_list, name='survey_list'),
    path('surveyor/map/', survey_map, name='survey_map'),
    path('surveyor/survey/<int:parcel_id>/update/', update_survey, name='update_survey'),
    
    # Citizen Dashboard
    path('citizen/dashboard/', citizen_dashboard, name='citizen_dashboard'),
    path('citizen/disputes/', manage_disputes, name='manage_disputes'),
    path('citizen/properties/', my_properties, name='my_properties'),
    path('citizen/property/transfer/', transfer_property, name='transfer_property'),
    path('citizen/execute-transfer/<int:transaction_id>/', execute_approved_transfer, name='execute_approved_transfer'),
    
    # Court Authority Dashboard
    path('court/dashboard/', court_dashboard, name='court_dashboard'),
    path('court/disputes/', dispute_list, name='dispute_list'),
    path('court/dispute/<int:dispute_id>/resolve/', resolve_dispute, name='resolve_dispute'),
    path('court/metrics/', court_metrics, name='court_metrics'),
    
    # Parcel History and Documentation
    path('parcel/<int:parcel_id>/history/', parcel_complete_history, name='parcel_complete_history'),
    path('parcel/<int:parcel_id>/mother-patta/', parcel_mother_patta, name='parcel_mother_patta'),
    path('parcel/<int:parcel_id>/history/api/', parcel_history_api, name='parcel_history_api'),
    path('parcel/<int:parcel_id>/add-note/', add_parcel_note, name='add_parcel_note'),
    path('parcel/<int:parcel_id>/timeline/', parcel_timeline, name='parcel_timeline'),
]