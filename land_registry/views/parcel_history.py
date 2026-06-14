"""
Views for displaying comprehensive parcel history like a mother patta document.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from land_registry.models import Parcel, ParcelHistory, OwnershipChain, SurveyHistory
from land_registry.services.history_tracker import ParcelHistoryTracker
from land_registry.decorators import role_required
import json
from datetime import datetime


@login_required
def parcel_complete_history(request, parcel_id):
    """Display complete parcel history like a mother patta document."""
    parcel = get_object_or_404(Parcel, id=parcel_id)
    
    # Check if user has permission to view this parcel
    user_can_view = (
        request.user == parcel.owner or
        request.user.role in ['registrar', 'surveyor', 'court'] or
        request.user.is_superuser
    )
    
    if not user_can_view:
        return render(request, 'errors/403.html', {
            'message': 'You do not have permission to view this parcel history.'
        })
    
    # Get complete history using the history tracker service
    complete_history = ParcelHistoryTracker.get_complete_parcel_history(parcel)
    
    # Get additional context data
    context = {
        'parcel': parcel,
        'complete_history': complete_history,
        'current_user': request.user,
        'can_edit': request.user.role in ['registrar', 'surveyor'] or request.user.is_superuser,
        'page_title': f'Complete History - Parcel #{parcel.id}',
    }
    
    return render(request, 'dashboard/parcel/complete_history.html', context)


@login_required
def parcel_mother_patta(request, parcel_id):
    """Generate a mother patta style document for the parcel and store it in IPFS."""
    parcel = get_object_or_404(Parcel, id=parcel_id)
    
    # Check if user has permission to view this parcel
    user_can_view = (
        request.user == parcel.owner or
        request.user.role in ['registrar', 'surveyor', 'court'] or
        request.user.is_superuser
    )
    
    if not user_can_view:
        return render(request, 'errors/403.html', {
            'message': 'You do not have permission to view this parcel document.'
        })
    
    # Generate QR code if it doesn't exist
    if not parcel.qr_code:
        try:
            parcel.generate_qr_code()
        except Exception as e:
            print(f"Error generating QR code: {e}")
    
    # Get complete history
    complete_history = ParcelHistoryTracker.get_complete_parcel_history(parcel)
    
    # Get token_id from blockchain if parcel is registered
    token_id = None
    if parcel.blockchain_tx_hash:
        try:
            from land_registry.blockchain.contracts import ContractManager
            contract_manager = ContractManager()
            blockchain_details = contract_manager.get_land_details(str(parcel.id))
            if blockchain_details:
                token_id = blockchain_details.get('token_id')
        except Exception as e:
            # If blockchain query fails, token_id will remain None
            print(f"Error fetching token_id from blockchain: {e}")
    
    context = {
        'parcel': parcel,
        'complete_history': complete_history,
        'generated_date': datetime.now(),
        'document_title': f'Mother Patta - Parcel #{parcel.id}',
        'is_official_document': True,
        'token_id': token_id,  # Pass token_id to template
    }
    
    # Generate and upload mother patta document to IPFS if not already stored
    if not parcel.mother_patta_ipfs_hash:
        try:
            from land_registry.utils.ipfs import upload_to_ipfs
            # Render the HTML document
            html_content = render_to_string('dashboard/parcel/mother_patta.html', context)
            # Upload to IPFS
            ipfs_hash = upload_to_ipfs(html_content, content_type='html')
            parcel.mother_patta_ipfs_hash = ipfs_hash
            parcel.save(update_fields=['mother_patta_ipfs_hash'])
            print(f"Mother patta document uploaded to IPFS: {ipfs_hash}")
        except Exception as e:
            print(f"Error uploading mother patta to IPFS: {e}")
            # Continue even if IPFS upload fails
    
    # Add IPFS hash to context for display, but validate it first
    if parcel.mother_patta_ipfs_hash:
        from land_registry.utils.ipfs import is_valid_ipfs_hash
        ipfs_hash = str(parcel.mother_patta_ipfs_hash).strip()
        if is_valid_ipfs_hash(ipfs_hash):
            context['mother_patta_ipfs_hash'] = ipfs_hash
            context['mother_patta_ipfs_hash_valid'] = True
            # Generate IPFS URLs
            from django.conf import settings
            context['mother_patta_ipfs_url'] = f"http://{settings.IPFS_HOST}:8080/ipfs/{ipfs_hash}"
        else:
            # Invalid hash - still show it but mark as invalid
            context['mother_patta_ipfs_hash'] = ipfs_hash
            context['mother_patta_ipfs_hash_valid'] = False
            print(f"Warning: Invalid IPFS hash format for mother patta: {ipfs_hash} (length: {len(ipfs_hash)})")
    
    return render(request, 'dashboard/parcel/mother_patta.html', context)


@login_required
def parcel_history_api(request, parcel_id):
    """API endpoint for getting parcel history data."""
    parcel = get_object_or_404(Parcel, id=parcel_id)
    
    # Check permissions
    user_can_view = (
        request.user == parcel.owner or
        request.user.role in ['registrar', 'surveyor', 'court'] or
        request.user.is_superuser
    )
    
    if not user_can_view:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Get complete history
    complete_history = ParcelHistoryTracker.get_complete_parcel_history(parcel)
    
    return JsonResponse({
        'success': True,
        'parcel_id': parcel.id,
        'history': complete_history
    })


@login_required
@role_required('registrar')
def add_parcel_note(request, parcel_id):
    """Add an administrative note to parcel history."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    parcel = get_object_or_404(Parcel, id=parcel_id)
    note_text = request.POST.get('note_text', '').strip()
    
    if not note_text:
        return JsonResponse({'error': 'Note text is required'}, status=400)
    
    # Create a history entry for the administrative note
    ParcelHistory.objects.create(
        parcel=parcel,
        change_type='administrative_note',
        changed_by=request.user,
        previous_data=None,
        new_data={
            'note': note_text,
            'added_by': request.user.get_full_name(),
            'added_date': datetime.now().isoformat()
        },
        notes=f"Administrative note added by {request.user.get_full_name()}"
    )
    
    return JsonResponse({
        'success': True,
        'message': 'Note added successfully'
    })


@login_required
def parcel_timeline(request, parcel_id):
    """Get parcel timeline data for visualization."""
    parcel = get_object_or_404(Parcel, id=parcel_id)
    
    # Check permissions
    user_can_view = (
        request.user == parcel.owner or
        request.user.role in ['registrar', 'surveyor', 'court'] or
        request.user.is_superuser
    )
    
    if not user_can_view:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Get all history entries ordered by date
    history_entries = ParcelHistory.objects.filter(parcel=parcel).order_by('timestamp')
    
    timeline_data = []
    for entry in history_entries:
        timeline_data.append({
            'date': entry.timestamp.isoformat(),
            'type': entry.change_type,
            'title': entry.get_change_type_display(),
            'description': entry.notes or 'No description available',
            'changed_by': entry.changed_by.get_full_name() if entry.changed_by else 'System',
            'blockchain_tx': entry.blockchain_tx_hash,
            'details': {
                'previous_data': entry.previous_data,
                'new_data': entry.new_data
            }
        })
    
    return JsonResponse({
        'success': True,
        'parcel_id': parcel.id,
        'timeline': timeline_data
    })