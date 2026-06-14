from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import qrcode
from io import BytesIO
from django.core.files import File
from PIL import Image

from .blockchain.wallet import WalletManager
from .blockchain.contracts import ContractManager

class User(AbstractUser):
    ROLES = (
        ('admin', 'Admin'),
        ('registrar', 'Registrar'),
        ('surveyor', 'Surveyor'),
        ('citizen', 'Citizen'),
        ('court', 'Court Authority'),
    )
    
    role = models.CharField(max_length=20, choices=ROLES, default='citizen')
    wallet_address = models.CharField(max_length=42, blank=True, null=True)
    encrypted_private_key = models.TextField(blank=True, null=True)
    verification_token = models.CharField(max_length=64, blank=True, null=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        if is_new and not self.wallet_address:
            # Create a new wallet for the user
            wallet_manager = WalletManager()
            wallet_address, encrypted_private_key = wallet_manager.create_wallet()
            
            # Set wallet address and encrypted private key
            self.wallet_address = wallet_address
            self.encrypted_private_key = encrypted_private_key
        
        # Save the user first to ensure we have an ID
        super().save(*args, **kwargs)
        
        # Register on blockchain if this is a new user and we have a wallet address
        if is_new and self.wallet_address:
            try:
                contract_manager = ContractManager()
                contract_manager.register_user(
                    user_id=self.id,
                    wallet_address=self.wallet_address
                )
            except Exception as e:
                # Log the error but don't prevent user creation
                print(f"Failed to register user on blockchain: {str(e)}")
                # You might want to add proper logging here

class Parcel(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),      # Maps to ParcelStatus.Pending (0)
        ('surveyed', 'Surveyed'),    # Intermediate state before verification
        ('active', 'Active'),        # Maps to ParcelStatus.Active (1)
        ('disputed', 'Disputed'),    # Maps to ParcelStatus.Disputed (2)
        ('locked', 'Locked'),        # Maps to ParcelStatus.Locked (3)
        ('rejected', 'Rejected')     # Special case that sets status to Locked (3)
    )

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_parcels')
    surveyor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_surveys', limit_choices_to={'role': 'surveyor'})
    location = models.CharField(max_length=255, null=True, blank=True, help_text="Location description of the land parcel")
    coordinates = models.JSONField(null=True, blank=True, help_text="GeoJSON coordinates of the parcel boundaries")
    area = models.FloatField(help_text="Area in square meters")
    description = models.TextField(null=True, blank=True, help_text="Description of the land parcel")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    verification_data = models.JSONField(null=True, blank=True)
    blockchain_tx_hash = models.CharField(max_length=66, blank=True, null=True, unique=True)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    legacy_document = models.FileField(upload_to='legacy_documents/', blank=True, null=True, help_text="Upload legacy paper documents related to this land parcel")
    is_legacy = models.BooleanField(default=False, help_text="Indicates if this parcel was imported from a legacy system")
    
    # IPFS storage fields
    ipfs_data_hash = models.CharField(max_length=100, blank=True, null=True, help_text="IPFS hash of complete parcel data")
    mother_patta_ipfs_hash = models.CharField(max_length=100, blank=True, null=True, help_text="IPFS hash of mother patta document")
    
    # Original registration details (Mother Patta fields)
    original_owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='originally_owned_parcels', help_text="The first owner who registered this land")
    original_registration_date = models.DateTimeField(null=True, blank=True, help_text="Date when the land was first registered")
    original_registrar = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='originally_registered_parcels', limit_choices_to={'role': 'registrar'}, help_text="Registrar who processed the original registration")
    original_survey_number = models.CharField(max_length=100, blank=True, null=True, help_text="Original survey number from government records")
    original_document_reference = models.CharField(max_length=200, blank=True, null=True, help_text="Reference to original government document")
    original_area = models.FloatField(null=True, blank=True, help_text="Original area as recorded during first registration")
    original_coordinates = models.JSONField(null=True, blank=True, help_text="Original coordinates from first survey")
    village_name = models.CharField(max_length=100, blank=True, null=True, help_text="Village where the land is located")
    district_name = models.CharField(max_length=100, blank=True, null=True, help_text="District where the land is located")
    state_name = models.CharField(max_length=100, blank=True, null=True, help_text="State where the land is located")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Parcel {self.id} - {self.location or 'No location'}"

    def generate_qr_code(self):
        """Generate QR code for the parcel"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # Get blockchain details if available
        try:
            contract_manager = ContractManager()
            blockchain_details = contract_manager.get_land_details(str(self.id))
            token_id = blockchain_details.get('token_id')
            blockchain_status = blockchain_details.get('status', self.status)
        except:
            token_id = None
            blockchain_status = self.status
        
        # Prepare QR code data
        qr_data = {
            'id': str(self.id),
            'token_id': str(token_id) if token_id else 'pending',
            'location': self.location or 'No location',
            'area': self.area,
            'owner': self.owner.get_full_name(),
            'owner_wallet': self.owner.wallet_address,
            'status': blockchain_status,
            'blockchain_tx': self.blockchain_tx_hash or 'pending',
            'last_updated': self.updated_at.isoformat() if self.updated_at else None
        }
        
        qr.add_data(qr_data)
        qr.make(fit=True)

        # Create QR code image
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR code image
        buffer = BytesIO()
        qr_image.save(buffer, format='PNG')
        filename = f'parcel_{self.id}_qr.png'
        
        # Delete old QR code if it exists
        if self.qr_code:
            self.qr_code.delete(save=False)
        
        self.qr_code.save(filename, File(buffer), save=False)

    def save(self, *args, **kwargs):
        # Save first to ensure we have an ID
        super().save(*args, **kwargs)
        
        # Generate QR code with updated information
        self.generate_qr_code()
        
        # Save again to store the new QR code
        if self.qr_code:
            super().save(update_fields=['qr_code'])

class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('register', 'Registration'),
        ('transfer', 'Transfer'),
        ('update', 'Update'),
        ('dispute', 'Dispute')
    )
    
    TRANSACTION_STATUS = (
        ('pending_approval', 'Pending Approval'),  # Waiting for registrar approval
        ('approved', 'Approved'),                  # Approved by registrar, ready for blockchain
        ('pending', 'Pending'),                    # Blockchain transaction submitted
        ('confirmed', 'Confirmed'),                # Blockchain transaction confirmed
        ('completed', 'Completed'),                # Ownership synced in Django DB
        ('rejected', 'Rejected'),                  # Rejected by registrar
        ('failed', 'Failed')                       # Blockchain transaction failed
    )

    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    transaction_hash = models.CharField(max_length=66, blank=True, null=True)  # Allow null for pending approval
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default='pending_approval')
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions_sent')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions_received', null=True, blank=True)
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name='transactions')
    details = models.JSONField(null=True, blank=True)
    
    # Approval workflow fields
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transactions', limit_choices_to={'role': 'registrar'})
    approval_notes = models.TextField(null=True, blank=True, help_text="Notes from the registrar regarding approval/rejection")
    
    # Timestamps
    timestamp = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.transaction_type} - {self.transaction_hash[:10] if self.transaction_hash else 'No Hash'} ({self.status})"
    
    def approve(self, registrar, notes=None):
        """Approve the transaction for blockchain execution"""
        self.status = 'approved'
        self.approved_by = registrar
        self.approved_at = timezone.now()
        if notes:
            self.approval_notes = notes
        self.save()
    
    def reject(self, registrar, notes=None):
        """Reject the transaction"""
        self.status = 'rejected'
        self.approved_by = registrar
        self.approved_at = timezone.now()
        if notes:
            self.approval_notes = notes
        self.save()
    
    def mark_pending_blockchain(self, tx_hash):
        """Mark transaction as submitted to blockchain"""
        self.status = 'pending'
        self.transaction_hash = tx_hash
        self.save()
    
    def mark_confirmed(self):
        """Mark transaction as confirmed on blockchain"""
        self.status = 'confirmed'
        self.confirmed_at = timezone.now()
        self.save()
    
    def mark_completed(self):
        """Mark transaction as fully completed (ownership synced)"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def mark_failed(self, error_message=None):
        """Mark transaction as failed"""
        self.status = 'failed'
        if error_message:
            if not self.details:
                self.details = {}
            self.details['error'] = error_message
        self.save()
    
    @property
    def requires_approval(self):
        """Check if this transaction type requires registrar approval"""
        return self.transaction_type == 'transfer'
    
    @property
    def can_be_executed(self):
        """Check if transaction can be executed on blockchain"""
        return self.status == 'approved' and self.requires_approval

class Dispute(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('under_review', 'Under Review'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    )

    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name='disputes')
    complainant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='filed_disputes')
    description = models.TextField(null=True, blank=True, help_text="Description of the dispute")
    evidence = models.FileField(upload_to='dispute_evidence/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    resolution = models.TextField(null=True, blank=True)
    resolver = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='resolved_disputes',
        limit_choices_to={'role': 'court'}
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Dispute {self.id} - Parcel {self.parcel.id}"

    def resolve(self, resolver, resolution):
        self.status = 'resolved'
        self.resolver = resolver
        self.resolution = resolution
        self.resolved_at = timezone.now()
        self.save()


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('property_transfer', 'Property Transfer'),
        ('property_received', 'Property Received'),
        ('transfer_approval_request', 'Transfer Approval Request'),
        ('transfer_approved', 'Transfer Approved'),
        ('transfer_rejected', 'Transfer Rejected'),
        ('dispute_filed', 'Dispute Filed'),
        ('dispute_resolved', 'Dispute Resolved'),
        ('system_alert', 'System Alert'),
    )
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    related_parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, null=True, blank=True)
    related_transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.recipient.username}"
    
    def mark_as_read(self):
        self.is_read = True
        self.save()


class ParcelHistory(models.Model):
    """Track all changes made to a parcel over time"""
    CHANGE_TYPES = (
        ('registration', 'Initial Registration'),
        ('ownership_transfer', 'Ownership Transfer'),
        ('survey_update', 'Survey Update'),
        ('status_change', 'Status Change'),
        ('data_update', 'Data Update'),
        ('dispute_filed', 'Dispute Filed'),
        ('dispute_resolved', 'Dispute Resolved'),
    )
    
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name='history')
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPES)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    previous_data = models.JSONField(null=True, blank=True, help_text="Previous state of the data")
    new_data = models.JSONField(null=True, blank=True, help_text="New state of the data")
    blockchain_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['parcel', '-timestamp']),
            models.Index(fields=['change_type', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.parcel} - {self.get_change_type_display()} at {self.timestamp}"


class OwnershipChain(models.Model):
    """Track complete ownership chain for each parcel"""
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name='ownership_chain')
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    previous_owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='previous_ownerships')
    transfer_transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True)
    ownership_start_date = models.DateTimeField()
    ownership_end_date = models.DateTimeField(null=True, blank=True)
    is_current_owner = models.BooleanField(default=False)
    transfer_method = models.CharField(max_length=50, blank=True, null=True, help_text="How ownership was acquired")
    blockchain_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    
    class Meta:
        ordering = ['-ownership_start_date']
        indexes = [
            models.Index(fields=['parcel', '-ownership_start_date']),
            models.Index(fields=['owner', '-ownership_start_date']),
            models.Index(fields=['is_current_owner']),
        ]
    
    def __str__(self):
        return f"{self.parcel} - {self.owner.username} ({self.ownership_start_date})"


class SurveyHistory(models.Model):
    """Track all survey modifications for each parcel"""
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name='survey_history')
    surveyor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={'role': 'surveyor'})
    previous_coordinates = models.JSONField(null=True, blank=True)
    new_coordinates = models.JSONField(null=True, blank=True)
    previous_area = models.FloatField(null=True, blank=True)
    new_area = models.FloatField(null=True, blank=True)
    survey_method = models.CharField(max_length=100, blank=True, null=True)
    equipment_used = models.CharField(max_length=200, blank=True, null=True)
    accuracy_level = models.CharField(max_length=50, blank=True, null=True)
    survey_notes = models.TextField(blank=True, null=True)
    blockchain_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    survey_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-survey_date']
        indexes = [
            models.Index(fields=['parcel', '-survey_date']),
            models.Index(fields=['surveyor', '-survey_date']),
        ]
    
    def __str__(self):
        return f"{self.parcel} - Survey by {self.surveyor.username if self.surveyor else 'Unknown'} on {self.survey_date}"


# ============================================================================
# LICENSING SYSTEM MODELS (GovTech SaaS)
# ============================================================================

class LicenseModule(models.Model):
    """Available modules that can be licensed"""
    MODULE_CHOICES = (
        ('landcore', 'LandCore'),
        ('landverify', 'LandVerify'),
        ('landaudit', 'LandAudit'),
        ('landexchange', 'LandExchange'),
    )
    
    code = models.CharField(max_length=50, choices=MODULE_CHOICES, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(help_text="Module description and capabilities")
    is_mandatory = models.BooleanField(default=False, help_text="Required for all licenses")
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'License Module'
        verbose_name_plural = 'License Modules'
    
    def __str__(self):
        return self.name


class License(models.Model):
    """Government institution license"""
    LICENSE_TYPES = (
        ('institution', 'Institution License'),
        ('department', 'Department License'),
        ('api', 'API License'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked'),
    )
    
    # License identification
    license_number = models.CharField(max_length=100, unique=True, help_text="Unique license identifier")
    license_type = models.CharField(max_length=20, choices=LICENSE_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Institution details
    institution_name = models.CharField(max_length=255, help_text="State/District/Department name")
    institution_type = models.CharField(max_length=100, help_text="e.g., State Government, District Administration")
    jurisdiction_state = models.CharField(max_length=100, blank=True, null=True)
    jurisdiction_district = models.CharField(max_length=100, blank=True, null=True)
    
    # Contact information
    primary_contact_name = models.CharField(max_length=255)
    primary_contact_email = models.EmailField()
    primary_contact_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # License validity
    valid_from = models.DateField()
    valid_until = models.DateField()
    auto_renew = models.BooleanField(default=False)
    
    # Usage limits
    max_users = models.IntegerField(default=10, help_text="Maximum number of users")
    max_api_calls_per_month = models.IntegerField(default=1000, help_text="Maximum API calls per month")
    current_user_count = models.IntegerField(default=0)
    current_month_api_calls = models.IntegerField(default=0)
    api_calls_reset_date = models.DateField(null=True, blank=True)
    
    # Modules
    modules = models.ManyToManyField(LicenseModule, related_name='licenses', help_text="Enabled modules")
    
    # Approval workflow
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                  related_name='issued_licenses', limit_choices_to={'role': 'admin'})
    issued_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='approved_licenses', limit_choices_to={'role': 'admin'})
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Digital signature and audit
    license_hash = models.CharField(max_length=64, blank=True, null=True, 
                                    help_text="Hash for blockchain audit trail")
    notes = models.TextField(blank=True, null=True, help_text="Internal notes")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['license_number']),
            models.Index(fields=['status', 'valid_until']),
            models.Index(fields=['institution_name']),
        ]
        verbose_name = 'Government License'
        verbose_name_plural = 'Government Licenses'
    
    def __str__(self):
        return f"{self.license_number} - {self.institution_name}"
    
    @property
    def is_valid(self):
        """Check if license is currently valid"""
        from django.utils import timezone
        today = timezone.now().date()
        return (
            self.status == 'active' and
            self.valid_from <= today <= self.valid_until
        )
    
    @property
    def days_until_expiry(self):
        """Calculate days until license expires"""
        from django.utils import timezone
        today = timezone.now().date()
        if self.valid_until < today:
            return 0
        return (self.valid_until - today).days
    
    def has_module(self, module_code):
        """Check if license has access to a specific module"""
        return self.modules.filter(code=module_code, is_active=True).exists()
    
    def can_add_user(self):
        """Check if license can add another user"""
        return self.current_user_count < self.max_users
    
    def can_make_api_call(self):
        """Check if license can make another API call this month"""
        from django.utils import timezone
        today = timezone.now().date()
        
        # Reset counter if new month
        if self.api_calls_reset_date and self.api_calls_reset_date < today:
            self.current_month_api_calls = 0
            self.api_calls_reset_date = today.replace(day=1)
            self.save(update_fields=['current_month_api_calls', 'api_calls_reset_date'])
        
        return self.current_month_api_calls < self.max_api_calls_per_month


class LicenseRequest(models.Model):
    """License upgrade/modification requests"""
    REQUEST_TYPES = (
        ('new', 'New License'),
        ('upgrade', 'Module Upgrade'),
        ('renewal', 'License Renewal'),
        ('modification', 'License Modification'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    )
    
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Related license (if upgrade/modification)
    license = models.ForeignKey(License, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='requests')
    
    # Request details
    requested_modules = models.ManyToManyField(LicenseModule, related_name='license_requests')
    institution_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    justification = models.TextField(help_text="Reason for request")
    
    # Review workflow
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='submitted_license_requests')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='reviewed_license_requests', 
                                     limit_choices_to={'role': 'admin'})
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['status', 'request_type']),
            models.Index(fields=['submitted_at']),
        ]
        verbose_name = 'License Request'
        verbose_name_plural = 'License Requests'
    
    def __str__(self):
        return f"{self.get_request_type_display()} - {self.institution_name} ({self.status})"


class LicenseAuditLog(models.Model):
    """Audit trail for all license-related activities"""
    ACTION_TYPES = (
        ('created', 'License Created'),
        ('activated', 'License Activated'),
        ('suspended', 'License Suspended'),
        ('renewed', 'License Renewed'),
        ('expired', 'License Expired'),
        ('module_added', 'Module Added'),
        ('module_removed', 'Module Removed'),
        ('upgrade_requested', 'Upgrade Requested'),
        ('upgrade_approved', 'Upgrade Approved'),
        ('upgrade_rejected', 'Upgrade Rejected'),
        ('user_added', 'User Added'),
        ('user_removed', 'User Removed'),
        ('api_limit_reached', 'API Limit Reached'),
        ('revoked', 'License Revoked'),
    )
    
    license = models.ForeignKey(License, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=50, choices=ACTION_TYPES)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='license_audit_actions')
    details = models.JSONField(default=dict, help_text="Additional action details")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['license', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]
        verbose_name = 'License Audit Log'
        verbose_name_plural = 'License Audit Logs'
    
    def __str__(self):
        return f"{self.license.license_number} - {self.get_action_display()} at {self.timestamp}"


class InstitutionUser(models.Model):
    """Link users to licenses (for multi-license support)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='institution_licenses')
    license = models.ForeignKey(License, on_delete=models.CASCADE, related_name='institution_users')
    is_primary_contact = models.BooleanField(default=False)
    added_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='added_institution_users')
    
    class Meta:
        unique_together = ['user', 'license']
        indexes = [
            models.Index(fields=['user', 'license']),
        ]
        verbose_name = 'Institution User'
        verbose_name_plural = 'Institution Users'
    
    def __str__(self):
        return f"{self.user.username} - {self.license.license_number}"
