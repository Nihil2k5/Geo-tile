import json
import qrcode
import base64
from io import BytesIO
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.db import models
from django.conf import settings
from django.contrib import messages
from django.utils import timezone

from land_registry.decorators import role_required
from land_registry.models import Parcel, Dispute, Transaction, Notification
from land_registry.blockchain.contracts import ContractManager
from land_registry.services.history_tracker import ParcelHistoryTracker
from land_registry.utils.ipfs import upload_to_ipfs

def generate_user_qr_code(user):
    """Generate QR code for user with unique details"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # Prepare QR code data with user details
        qr_data = {
            'user_id': str(user.id),
            'username': user.username,
            'full_name': user.get_full_name(),
            'email': user.email,
            'wallet_address': user.wallet_address or 'Not assigned',
            'role': user.role,
            'member_since': user.date_joined.isoformat() if user.date_joined else None,
        }
        
        # Convert to JSON string and add to QR code
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        
        # Create QR code image
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 string
        buffer = BytesIO()
        qr_image.save(buffer, format='PNG')
        qr_image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return qr_image_base64
    except Exception as e:
        print(f"Error generating user QR code: {e}")
        return None

@login_required
@role_required('citizen')
def citizen_dashboard(request):
    """
    Display the citizen dashboard with property information and statistics
    """
    # Get properties owned by the citizen (exclude transferred properties)
    # Exclude properties that have completed transfers where user was the sender
    completed_transfer_parcel_ids = Transaction.objects.filter(
        from_user=request.user,
        transaction_type='transfer',
        status='completed'
    ).values_list('parcel_id', flat=True)
    
    properties = Parcel.objects.filter(owner=request.user).exclude(
        id__in=completed_transfer_parcel_ids
    )
    
    # Get active disputes
    active_disputes = Dispute.objects.filter(
        complainant=request.user,
        status__in=['open', 'under_review']
    ).select_related('parcel')
    
    # Calculate total area of active properties
    total_area = properties.filter(status='active').aggregate(total_area=models.Sum('area'))['total_area'] or 0
    
    # Get pending transfer requests (outgoing)
    pending_transfers = Transaction.objects.filter(
        from_user=request.user,
        transaction_type='transfer',
        status='pending_approval'
    ).select_related('parcel', 'to_user').order_by('-timestamp')
    
    # Get approved transfers that need execution (exclude completed ones)
    approved_transfers = Transaction.objects.filter(
        from_user=request.user,
        transaction_type='transfer',
        status='approved'
    ).select_related('parcel', 'to_user').order_by('-approved_at')
    
    # Get recent transactions (property transfers)
    recent_transactions = Transaction.objects.filter(
        models.Q(from_user=request.user) | models.Q(to_user=request.user),
        transaction_type='transfer'
    ).select_related('parcel', 'from_user', 'to_user').order_by('-timestamp')[:5]
    
    # Generate user QR code
    user_qr_code = generate_user_qr_code(request.user)
    
    context = {
        'total_parcels': properties.count(),
        'total_area': total_area,
        'active_disputes': active_disputes,
        'pending_transfers': pending_transfers,
        'pending_transfers_count': pending_transfers.count(),
        'approved_transfers': approved_transfers,
        'approved_transfers_count': approved_transfers.count(),
        'recent_transactions': recent_transactions,
        'recent_properties': properties.order_by('-created_at')[:5],
        'properties': properties,  # Add all properties for history and patta links
        'user_qr_code': user_qr_code,  # User QR code as base64 image
    }
    
    return render(request, 'dashboard/citizen/dashboard.html', context)

@login_required
@role_required('citizen')
def manage_disputes(request):
    """
    Display and manage property disputes for the citizen
    """
    if request.method == 'POST':
        # Handle new dispute filing
        parcel_id = request.POST.get('parcel_id')
        description = request.POST.get('description', '').strip()
        evidence = request.FILES.get('evidence')
        
        if not parcel_id or not description:
            messages.error(request, 'Parcel ID and description are required.')
        else:
            try:
                # Validate parcel exists and belongs to current user
                parcel = get_object_or_404(Parcel, id=parcel_id)
                if parcel.owner != request.user:
                    messages.error(request, 'You do not own the selected property.')
                    raise ValueError('Parcel ownership validation failed')

                # Create dispute in Django database
                dispute = Dispute.objects.create(
                    parcel_id=parcel_id,
                    complainant=request.user,
                    description=description,
                    evidence=evidence,
                    status='open'
                )
                
                # Prepare data for IPFS upload
                dispute_data = {
                    'dispute_id': str(dispute.id),
                    'parcel_id': parcel_id,
                    'complainant': request.user.username,
                    'description': description,
                    'filed_at': dispute.created_at.isoformat(),
                    'has_evidence_file': evidence is not None
                }
                
                # If evidence file is uploaded, include its metadata
                if evidence:
                    dispute_data['evidence_filename'] = evidence.name
                    dispute_data['evidence_size'] = evidence.size
                    dispute_data['evidence_content_type'] = evidence.content_type
                
                # Upload dispute data to IPFS (simulated)
                evidence_ipfs_hash = upload_to_ipfs(dispute_data)
                
                # File dispute on blockchain
                contract_manager = ContractManager()
                
                tx_hash = contract_manager.file_dispute(
                    dispute.id,
                    parcel_id,
                    evidence_ipfs_hash
                )
                
                messages.success(request, f'Dispute filed successfully. Transaction: {tx_hash}')
                return redirect('land_registry:manage_disputes')
                
            except Exception as e:
                messages.error(request, f'Error filing dispute: {str(e)}')
                # If blockchain filing fails, delete the Django dispute
                if 'dispute' in locals():
                    dispute.delete()
    
    # Get disputes where the user is the complainant
    disputes = Dispute.objects.filter(complainant=request.user).select_related('parcel')
    
    # Separate disputes by status
    active_disputes = disputes.filter(status__in=['open', 'under_review'])
    resolved_disputes = disputes.filter(status__in=['resolved', 'rejected'])
    
    # Get user's parcels for the dispute form
    # Exclude properties that have completed transfers where user was the sender
    completed_transfer_parcel_ids = Transaction.objects.filter(
        from_user=request.user,
        transaction_type='transfer',
        status='completed'
    ).values_list('parcel_id', flat=True)

    # Show all currently owned parcels (regardless of status), excluding transferred ones
    user_parcels = Parcel.objects.filter(owner=request.user).exclude(
        id__in=completed_transfer_parcel_ids
    )
    
    context = {
        'active_disputes': active_disputes,
        'resolved_disputes': resolved_disputes,
        'properties': user_parcels,  # Template expects 'properties'
        'total_disputes': disputes.count(),
        'pending_disputes_count': active_disputes.count(),
        'resolved_disputes_count': resolved_disputes.count(),
        # Preserve selection after POST errors
        'selected_parcel_id': request.POST.get('parcel_id', '') if request.method == 'POST' else ''
    }
    
    return render(request, 'dashboard/citizen/disputes.html', context)

@login_required
@role_required('citizen')
def my_properties(request):
    """
    Display all properties owned by the citizen (excluding transferred properties)
    """
    # Exclude properties that have completed transfers where user was the sender
    completed_transfer_parcel_ids = Transaction.objects.filter(
        from_user=request.user,
        transaction_type='transfer',
        status='completed'
    ).values_list('parcel_id', flat=True)
    
    # Get all properties owned by the user, excluding transferred ones
    properties = Parcel.objects.filter(owner=request.user).exclude(
        id__in=completed_transfer_parcel_ids
    ).order_by('-created_at')
    
    print("DEBUG: Found", properties.count(), "properties for user", request.user.username)
    
    # Process coordinates for each property - simplified approach
    for property in properties:
        print(f"DEBUG: Processing property {property.id}, coordinates type: {type(property.coordinates)}")
        
        # Check if coordinates are None or empty string
        if property.coordinates is None or property.coordinates == "":
            print(f"DEBUG: Property {property.id} has no coordinates, creating placeholder")
            # Create a placeholder for properties with no coordinates
            property.coordinates = {
                'type': 'Feature',
                'properties': {
                    'id': property.id,
                    'location': property.location,
                    'area': property.area,
                    'status': property.status,
                    'placeholder': True,
                    'reason': 'No coordinates available'
                },
                'geometry': None
            }
        elif isinstance(property.coordinates, str):
            # Coordinates are stored as JSON string - validate but don't parse
            print(f"DEBUG: Property {property.id} has string coordinates: {property.coordinates[:50]}...")
            try:
                # Just validate that it's valid JSON, but keep as string
                json.loads(property.coordinates)
                print(f"DEBUG: Property {property.id} has valid JSON coordinates")
            except json.JSONDecodeError as e:
                print(f"ERROR: Property {property.id} has malformed coordinates: {str(e)}")
                # Create a placeholder for properties with malformed coordinates
                property.coordinates = {
                    'type': 'Feature',
                    'properties': {
                        'id': property.id,
                        'location': property.location,
                        'area': property.area,
                        'status': property.status,
                        'placeholder': True,
                        'reason': f'Malformed coordinates: {str(e)}'
                    },
                    'geometry': None
                }
    
    # Add JSON-encoded coordinates for template rendering
    for property in properties:
        if isinstance(property.coordinates, str):
            # Coordinates are already a JSON string, use as-is
            property.coordinates_json = property.coordinates
        elif isinstance(property.coordinates, dict):
            # Coordinates were converted to dict (placeholder), JSON encode them
            property.coordinates_json = json.dumps(property.coordinates)
        else:
            # Handle None or other types
            property.coordinates_json = json.dumps({
                'type': 'Feature',
                'properties': {
                    'id': property.id,
                    'location': property.location,
                    'area': property.area,
                    'status': property.status,
                    'placeholder': True,
                    'reason': 'No coordinates available'
                },
                'geometry': None
            })
    
    context = {
        'properties': properties,
        'mapbox_token': settings.MAPBOX_TOKEN
    }
    
    return render(request, 'dashboard/citizen/properties.html', context)


@login_required
@role_required('citizen')
def execute_approved_transfer(request, transaction_id):
    """Execute an approved transfer on the blockchain."""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method')
        return redirect('land_registry:citizen_dashboard')
    
    transaction_record = get_object_or_404(Transaction, id=transaction_id)
    
    # Verify transaction belongs to the current user and is approved
    if transaction_record.from_user != request.user:
        messages.error(request, 'You are not authorized to execute this transfer')
        return redirect('land_registry:citizen_dashboard')
    
    if transaction_record.status != 'approved':
        messages.error(request, 'This transfer is not approved for execution')
        return redirect('land_registry:citizen_dashboard')
    
    try:
        # Execute the blockchain transfer
        contract_manager = ContractManager()
        
        # Get recipient address from transaction details
        recipient_address = transaction_record.details.get('recipient_address')
        property_id = transaction_record.details.get('property_id')
        
        # Transfer the property on the blockchain
        tx_hash = contract_manager.transfer_land(
            str(property_id),
            transaction_record.from_user.wallet_address,
            recipient_address
        )
        
        # Update transaction with blockchain hash and mark as confirmed
        transaction_record.transaction_hash = tx_hash
        transaction_record.mark_confirmed()
        
        # Update parcel ownership in Django database if recipient is registered
        if transaction_record.to_user:
            transaction_record.parcel.owner = transaction_record.to_user
            transaction_record.parcel.save()
            
            # Track ownership transfer in history
            ParcelHistoryTracker.track_ownership_transfer(
                parcel=transaction_record.parcel,
                transaction_record=transaction_record,
                blockchain_tx_hash=tx_hash,
                notes=f"Ownership transferred from {transaction_record.from_user.get_full_name()} to {transaction_record.to_user.get_full_name()}"
            )
        
        # Mark transaction as completed (regardless of whether recipient is registered)
        transaction_record.mark_completed()
        
        # Create notifications
        # Notification for the recipient (if registered)
        if transaction_record.to_user:
            Notification.objects.create(
                recipient=transaction_record.to_user,
                notification_type='property_received',
                title='Property Received',
                message=f'You have received property #{property_id} from {transaction_record.from_user.get_full_name()}. The transfer has been completed successfully.',
                related_parcel=transaction_record.parcel,
                related_transaction=transaction_record
            )
        
        # Notification for registrars about the completion
        from land_registry.models import User
        registrars = User.objects.filter(role='registrar')
        for registrar in registrars:
            Notification.objects.create(
                recipient=registrar,
                notification_type='transfer_approved',
                title='Transfer Completed',
                message=f'Transfer for property #{property_id} has been completed successfully. The property has been transferred from {transaction_record.from_user.get_full_name()} to {transaction_record.to_user.get_full_name() if transaction_record.to_user else recipient_address}.',
                related_parcel=transaction_record.parcel,
                related_transaction=transaction_record
            )
        
        messages.success(request, f'Transfer executed successfully! Property #{property_id} has been transferred.')
        
    except Exception as e:
        # Mark transaction as failed
        transaction_record.mark_failed(str(e))
        messages.error(request, f'Error executing transfer: {str(e)}')
    
    return redirect('land_registry:citizen_dashboard')