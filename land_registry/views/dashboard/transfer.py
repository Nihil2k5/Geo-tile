from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse
from django.db import transaction
from django.utils import timezone
import re

from land_registry.decorators import role_required
from land_registry.models import Parcel, Transaction, User, Notification
from land_registry.blockchain.contracts import ContractManager

@login_required
@role_required('citizen')
def transfer_property(request):
    """Handle property transfer between users"""
    if request.method != 'POST':
        # Get all properties owned by the user
        properties = Parcel.objects.filter(owner=request.user).order_by('-created_at')
        context = {
            'properties': properties,
            'mapbox_token': 'your_mapbox_token_here'  # You should get this from settings
        }
        return render(request, 'dashboard/citizen/properties.html', context)
    
    # Get form data
    property_id = request.POST.get('property_id')
    recipient_address = request.POST.get('recipient_address')
    
    # Validate Ethereum address format
    if not recipient_address:
        messages.error(request, 'Recipient address is required')
        return redirect('land_registry:citizen_dashboard')
    
    # Clean and validate Ethereum address
    recipient_address = recipient_address.strip()
    ethereum_address_pattern = r'^0x[a-fA-F0-9]{40}$'
    
    if not re.match(ethereum_address_pattern, recipient_address):
        messages.error(request, 'Invalid Ethereum address format. Address must be 42 characters starting with 0x')
        return redirect('land_registry:citizen_dashboard')
    
    if not property_id:
        messages.error(request, 'Property ID is required')
        return redirect('land_registry:citizen_dashboard')
    
    # Get the parcel and verify ownership
    parcel = get_object_or_404(Parcel, id=property_id)
    if parcel.owner != request.user:
        messages.error(request, 'You do not own this property')
        return redirect('land_registry:citizen_dashboard')
    
    try:
        # Find recipient user by wallet address
        recipient_user = None
        try:
            recipient_user = User.objects.get(wallet_address=recipient_address)
        except User.DoesNotExist:
            # Recipient is not registered in the system
            pass
        
        # Use database transaction to ensure atomicity
        with transaction.atomic():
            # Create transaction record with pending approval status
            transaction_record = Transaction.objects.create(
                transaction_type='transfer',
                from_user=request.user,
                to_user=recipient_user,
                parcel=parcel,
                status='pending_approval',  # Start with pending approval
                details={
                    'recipient_address': recipient_address,
                    'property_id': property_id,
                    'recipient_registered': recipient_user is not None,
                    'recipient_name': recipient_user.get_full_name() if recipient_user else 'Unregistered User',
                    'transfer_reason': request.POST.get('transfer_reason', ''),
                    'requested_at': timezone.now().isoformat()
                }
            )
            
            # Create notification for the citizen (sender)
            Notification.objects.create(
                recipient=request.user,
                notification_type='transfer_approval_request',
                title='Transfer Request Submitted',
                message=f'Your transfer request for property #{property_id} to {recipient_user.get_full_name() if recipient_user else recipient_address} has been submitted for registrar approval.',
                related_parcel=parcel,
                related_transaction=transaction_record
            )
            
            # Create notification for all registrars
            registrars = User.objects.filter(role='registrar')
            for registrar in registrars:
                Notification.objects.create(
                    recipient=registrar,
                    notification_type='transfer_approval_request',
                    title='New Transfer Approval Request',
                    message=f'{request.user.get_full_name()} has requested to transfer property #{property_id} to {recipient_user.get_full_name() if recipient_user else recipient_address}. Please review and approve/reject this request.',
                    related_parcel=parcel,
                    related_transaction=transaction_record
                )
        
        # Success message
        if recipient_user:
            messages.success(request, f'Transfer request submitted for approval. Property will be transferred to {recipient_user.get_full_name()} ({recipient_address}) once approved by a registrar.')
        else:
            messages.success(request, f'Transfer request submitted for approval. Property will be transferred to wallet address {recipient_address} once approved by a registrar. Note: Recipient is not registered in the system.')
        
    except Exception as e:
        messages.error(request, f'Error submitting transfer request: {str(e)}')
    
    return redirect('land_registry:citizen_dashboard')