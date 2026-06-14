from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
import uuid
import json
from ...middleware import role_required
from ...models import Parcel, User, Transaction, Notification
from ...blockchain.contracts import ContractManager
from django.conf import settings
from ...utils.ipfs import upload_to_ipfs
from ...decorators import role_required
from ...utils.document_processor import DocumentProcessor
from ...services.history_tracker import ParcelHistoryTracker
from ...utils.email_service import send_land_registration_email, send_land_verification_email
import os

def is_registrar(user):
    return user.role == 'registrar'

@login_required
@role_required('registrar')
def extract_document_ai(request):
    """Extract text from uploaded document using OCR - called before parcel creation."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method allowed'}, status=405)
    
    try:
        # Check if file was uploaded
        if 'document' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No document file provided'
            }, status=400)
        
        uploaded_file = request.FILES['document']
        
        # Validate file size (max 10MB)
        if uploaded_file.size > 10 * 1024 * 1024:
            return JsonResponse({
                'success': False,
                'error': 'File size exceeds 10MB limit'
            }, status=400)
        
        # Save uploaded file temporarily
        import tempfile
        import os
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as temp_file:
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)
            temp_file_path = temp_file.name
        
        try:
            # Process the document with AI extraction
            try:
                document_processor = DocumentProcessor(lang='eng+hin')  # Multi-language mode: English + Hindi
                extracted_data = document_processor.process_document(temp_file_path)
            except ImportError as import_err:
                # Re-raise ImportError with more context
                return JsonResponse({
                    'success': False,
                    'error': f'OCR library not available: {str(import_err)}'
                }, status=500)
            
            return JsonResponse({
                'success': True,
                'data': extracted_data,
                'document_type': extracted_data.get('document_type', 'unknown'),
                'message': 'Document processed successfully'
            })
        finally:
            # Clean up temporary file
            try:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
            except Exception:
                pass  # Ignore cleanup errors
                
    except ImportError as e:
        return JsonResponse({
            'success': False,
            'error': f'OCR library not available: {str(e)}'
        }, status=500)
    except Exception as e:
        import traceback
        print(f"AI Extraction Error: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'AI extraction failed: {str(e)}'
        }, status=500)

def process_document_ai(request, parcel_id):
    """Process a legacy document with AI and return extracted data as JSON."""
    try:
        parcel = get_object_or_404(Parcel, id=parcel_id)
        
        # Only process legacy documents
        if not parcel.is_legacy or not parcel.legacy_document:
            return JsonResponse({
                'success': False,
                'error': 'This parcel does not have a legacy document to process.'
            })
        
        # Process the document with AI extraction
        try:
            # Initialize DocumentProcessor with multi-language support
            # You can specify Tesseract language codes: 'eng', 'hin', 'tam', 'tel', 'kan', 'mal', 'mar', 'guj', 'ben', 'urd', 'pan', etc.
            # For multiple languages, use '+' e.g., 'eng+hin' for English and Hindi
            document_processor = DocumentProcessor(lang='eng+hin')  # Multi-language mode: English + Hindi
            extracted_data = document_processor.process_document(parcel.legacy_document.path)
            
            # Update parcel with extracted data
            verification_data = {
                'ai_extracted': True,
                'extracted_at': timezone.now().isoformat(),
                'extracted_by': request.user.id,
                'document_type': extracted_data.get('document_type', 'unknown'),
                'extracted_fields': {
                    'owner_name': extracted_data.get('owner_name'),
                    'coordinates': extracted_data.get('coordinates'),
                    'area': extracted_data.get('area'),
                    'address': extracted_data.get('address')
                }
            }
            
            # Save the extracted data to the parcel
            parcel.verification_data = verification_data
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'AI processing failed: {str(e)}'
            })
        parcel.save()
        
        return JsonResponse({
            'success': True,
            'data': extracted_data,
            'document_type': extracted_data.get('document_type', 'unknown'),
            'message': 'Document processed successfully'
        })
            
    except Exception as e:
        import traceback
        print(f"AI Processing Error: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f"AI processing failed: {str(e)}"
        })

@login_required
@role_required('registrar')
def registrar_dashboard(request):
    """Main dashboard view for registrars."""
    # Get statistics
    total_parcels = Parcel.objects.count()
    pending_verifications = Parcel.objects.filter(status='surveyed').count()  # Changed from 'pending' to 'surveyed'
    verified_parcels = Parcel.objects.filter(status='verified').count()
    pending_transfers = Transaction.objects.filter(transaction_type='transfer', status='pending_approval').count()
    recent_parcels = Parcel.objects.order_by('-created_at')[:5]
    recent_transfer_requests = Transaction.objects.filter(
        transaction_type='transfer', 
        status='pending_approval'
    ).select_related('from_user', 'to_user', 'parcel').order_by('-timestamp')[:5]
    
    context = {
        'total_parcels': total_parcels,
        'pending_verifications': pending_verifications,
        'verified_parcels': verified_parcels,
        'pending_transfers': pending_transfers,
        'recent_parcels': recent_parcels,
        'recent_transfer_requests': recent_transfer_requests,
    }
    return render(request, 'dashboard/registrar/dashboard.html', context)

@login_required
@role_required('registrar')
@user_passes_test(is_registrar)
def land_registration(request):
    """View for registering new land parcels with map integration."""
    if request.method == 'POST':
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            messages.error(request, 'Invalid request method')
            return redirect(reverse('land_registry:registrar_dashboard'))
            
        try:
            # Get form data
            owner_id = request.POST.get('owner')
            if not owner_id:
                return JsonResponse({'success': False, 'error': 'Please select a property owner'}, status=400)
                
            try:
                area = float(request.POST.get('area', 0))
            except (TypeError, ValueError):
                return JsonResponse({'success': False, 'error': 'Invalid area value'}, status=400)
                
            coordinates = request.POST.get('coordinates')
            if not coordinates:
                return JsonResponse({'success': False, 'error': 'Coordinates are required'}, status=400)
                
            location = request.POST.get('location')
            if not location:
                return JsonResponse({'success': False, 'error': 'Location is required'}, status=400)
                
            # Log request data for debugging
            print(f"Form data received: owner={owner_id}, area={area}, coordinates={coordinates}, location={location}")
                
            description = request.POST.get('description', '')
            
            # Get a random surveyor to assign to this parcel
            try:
                surveyor = User.objects.filter(role='surveyor').order_by('?').first()
                if not surveyor:
                    return JsonResponse({'success': False, 'error': 'No surveyors available in the system'}, status=400)
            except Exception as e:
                return JsonResponse({'success': False, 'error': f'Error assigning surveyor: {str(e)}'}, status=500)
            
            # Validate area (must be positive)
            if area <= 0:
                return JsonResponse({'success': False, 'error': 'Area must be positive'}, status=400)
            
            # Get owner
            try:
                owner = User.objects.get(id=owner_id)
                if not owner.wallet_address:
                    return JsonResponse({'success': False, 'error': 'Owner does not have a wallet address'}, status=400)
            except User.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Owner not found'}, status=404)
            
            # Check if this is a legacy record
            is_legacy = request.POST.get('is_legacy') == 'on'
            legacy_document = request.FILES.get('legacy_document')
            
            # Check for potential duplicate parcels (same owner, identical coordinates AND area)
            # This is a warning check - only block if coordinates AND area are identical
            try:
                import json as json_module
                coordinates_data = json_module.loads(coordinates) if isinstance(coordinates, str) else coordinates
                
                # Check if a parcel with the same owner, identical coordinates AND identical area exists
                existing_parcels = Parcel.objects.filter(
                    owner=owner,
                    coordinates__isnull=False,
                    area=area  # Also check area to reduce false positives
                ).exclude(status='rejected')
                
                for existing_parcel in existing_parcels:
                    if existing_parcel.coordinates:
                        try:
                            existing_coords = existing_parcel.coordinates if isinstance(existing_parcel.coordinates, dict) else json_module.loads(existing_parcel.coordinates)
                            # Only block if coordinates AND area match exactly
                            # This allows for subdivisions, different uses at same location, etc.
                            if coordinates_data == existing_coords:
                                # Check if user explicitly wants to proceed (via bypass_duplicate_check parameter)
                                bypass_check = request.POST.get('bypass_duplicate_check') == 'true'
                                if not bypass_check:
                                    return JsonResponse({
                                        'success': False, 
                                        'error': f'A parcel with identical coordinates and area already exists for this owner (Parcel ID: {existing_parcel.id}). '
                                                f'If this is a different parcel (e.g., subdivision, different floor), please check the "Bypass duplicate check" option.',
                                        'duplicate_parcel_id': existing_parcel.id,
                                        'requires_override': True
                                    }, status=400)
                        except (json_module.JSONDecodeError, TypeError):
                            continue
                            
            except (json_module.JSONDecodeError, TypeError) as e:
                return JsonResponse({'success': False, 'error': 'Invalid coordinates format'}, status=400)
            
            # Create parcel
            try:
                parcel = Parcel.objects.create(
                    owner=owner,
                    surveyor=surveyor,
                    area=area,
                    coordinates=coordinates,
                    location=location,
                    description=description,
                    status='pending',
                    is_legacy=is_legacy,
                    legacy_document=legacy_document if legacy_document else None
                )
                
                # Set original registration details for mother patta functionality
                parcel.original_owner = owner
                parcel.original_registration_date = timezone.now()
                parcel.original_registrar = request.user
                parcel.original_area = area
                parcel.original_coordinates = coordinates
                
                # Normalize input values
                survey_number_input = (request.POST.get('survey_number', '') or '').strip()
                document_reference_input = (request.POST.get('document_reference', '') or '').strip()
                village_name_input = (request.POST.get('village_name', '') or '').strip()
                district_name_input = (request.POST.get('district_name', '') or '').strip()
                state_name_input = (request.POST.get('state_name', '') or '').strip()

                # Auto-generate values when missing
                date_code = timezone.now().strftime('%Y%m%d')
                if not survey_number_input:
                    survey_number_input = f"SURV-{date_code}-{parcel.id}"
                if not document_reference_input:
                    document_reference_input = f"DOC-{date_code}-{uuid.uuid4().hex[:8].upper()}"

                # Persist original registration fields
                parcel.original_survey_number = survey_number_input
                parcel.original_document_reference = document_reference_input
                parcel.village_name = village_name_input
                parcel.district_name = district_name_input
                parcel.state_name = state_name_input

                parcel.save()
                
            except Exception as e:
                return JsonResponse({'success': False, 'error': f'Failed to create parcel: {str(e)}'}, status=500)
            
            # Upload complete parcel data to IPFS
            try:
                # Prepare complete parcel data for IPFS
                parcel_data = {
                    'parcel_id': str(parcel.id),
                    'owner': owner.wallet_address,
                    'owner_name': owner.get_full_name(),
                    'area': area,
                    'coordinates': coordinates,
                    'location': location,
                    'description': description,
                    'status': parcel.status,
                    'created_at': parcel.created_at.isoformat() if parcel.created_at else None,
                    'village_name': village_name_input,
                    'district_name': district_name_input,
                    'state_name': state_name_input,
                    'original_survey_number': survey_number_input,
                    'original_document_reference': document_reference_input,
                    'original_area': parcel.original_area,
                    'original_coordinates': parcel.original_coordinates,
                }
                ipfs_hash = upload_to_ipfs(parcel_data)
                parcel.ipfs_data_hash = ipfs_hash
                parcel.save(update_fields=['ipfs_data_hash'])
            except Exception as e:
                parcel.delete()  # Rollback parcel creation
                return JsonResponse({'success': False, 'error': f'Failed to upload to IPFS: {str(e)}'}, status=500)
            
            # Register on blockchain
            try:
                contract_manager = ContractManager()
                
                # Check if this parcel ID already exists on blockchain
                # This prevents "Parcel already exists" errors when database and blockchain are out of sync
                if contract_manager.parcel_exists(str(parcel.id)):
                    print(f"Parcel {parcel.id} already exists on blockchain, linking instead of re-registering")
                    # Try to get existing blockchain details to sync
                    try:
                        blockchain_details = contract_manager.get_land_details(str(parcel.id))
                        # We don't have the original tx_hash, so we'll use a placeholder or the token_id
                        tx_hash = f"RECOVERED_FROM_CHAIN_TOKEN_{blockchain_details.get('token_id', 'UNKNOWN')}"
                    except Exception:
                        tx_hash = f"RECOVERED_FROM_CHAIN_{parcel.id}"
                else:
                    tx_hash = contract_manager.register_land(
                        str(parcel.id),  # Ensure parcel_id is a string
                        owner.wallet_address,
                        ipfs_hash,
                        area,
                        ipfs_hash  # Use ipfs_hash as metadata_uri
                    )
                
                # Update parcel with transaction hash
                parcel.blockchain_tx_hash = tx_hash
                parcel.save()
                
                # Send email notification to the owner
                try:
                    send_land_registration_email(parcel, owner)
                except Exception as email_error:
                    # Log email error but don't fail registration
                    print(f"Failed to send registration email: {str(email_error)}")
                
                # Try to verify, but don't fail if verification doesn't work immediately
                # (Quorum transactions may take time to mine)
                verification_warning = None
                try:
                    blockchain_details = contract_manager.get_land_details(str(parcel.id))
                    if not blockchain_details:
                        verification_warning = "Transaction sent but verification pending (transaction may still be mining)"
                except Exception as e:
                    # Verification failed, but transaction is sent - it will be processed
                    verification_warning = f"Transaction sent but not yet confirmed: {str(e)}"
                
                # Track initial registration in history
                ParcelHistoryTracker.track_initial_registration(
                    parcel=parcel,
                    registrar=request.user,
                    blockchain_tx_hash=tx_hash,
                    notes=f"Initial registration by {request.user.get_full_name()}"
                )
                
                response_data = {
                    'success': True,
                    'tx_hash': tx_hash,
                    'parcel_id': parcel.id,
                    'message': 'Land parcel registered successfully'
                }
                if verification_warning:
                    response_data['warning'] = verification_warning
                
                return JsonResponse(response_data)
                
            except Exception as e:
                # If blockchain registration fails, delete the parcel and return error
                parcel.delete()
                return JsonResponse({
                    'success': False,
                    'error': f'Blockchain registration failed: {str(e)}'
                }, status=500)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Registration failed: {str(e)}'
            }, status=500)
    
    # Get all users for owner selection
    users = User.objects.filter(role='citizen')
    context = {
        'users': users,
        'mapbox_token': settings.MAPBOX_TOKEN
    }
    return render(request, 'dashboard/registrar/register_land.html', context)

@login_required
@role_required('registrar')
def verify_land(request):
    """View for verifying land parcels."""
    parcels = Parcel.objects.filter(status='pending')  # Changed from 'surveyed' to 'pending'
    paginator = Paginator(parcels, 10)
    page = request.GET.get('page')
    parcels = paginator.get_page(page)

    if request.method == 'POST':
        parcel_id = request.POST.get('parcel_id')
        action = request.POST.get('action')
        try:
            parcel = Parcel.objects.get(id=parcel_id)
            contract_manager = ContractManager()

            # Handle legacy documents differently
            if parcel.is_legacy:
                if action == 'verify':
                    # For legacy parcels, we still want to register on blockchain if not already done
                    if not parcel.blockchain_tx_hash:
                        try:
                            # Upload to IPFS
                            ipfs_hash = upload_to_ipfs({
                                'parcel_id': str(parcel.id),
                                'owner': parcel.owner.wallet_address if parcel.owner.wallet_address else "LEGACY_NO_WALLET",
                                'area': parcel.area,
                                'coordinates': parcel.coordinates,
                                'location': parcel.location,
                                'description': parcel.description,
                                'is_legacy': True,
                                'legacy_verified': True
                            })
                            
                            # Register on blockchain if owner has wallet
                            if parcel.owner.wallet_address:
                                # Check if already exists on blockchain
                                if contract_manager.parcel_exists(str(parcel.id)):
                                    print(f"Legacy parcel {parcel.id} already exists on blockchain, linking instead")
                                    try:
                                        blockchain_details = contract_manager.get_land_details(str(parcel.id))
                                        tx_hash = f"RECOVERED_FROM_CHAIN_TOKEN_{blockchain_details.get('token_id', 'UNKNOWN')}"
                                    except Exception:
                                        tx_hash = f"RECOVERED_FROM_CHAIN_{parcel.id}"
                                else:
                                    tx_hash = contract_manager.register_land(
                                        str(parcel.id),
                                        parcel.owner.wallet_address,
                                        ipfs_hash,
                                        parcel.area,
                                        ipfs_hash
                                    )
                                    
                                    # Update blockchain status to Active (1) immediately for legacy records
                                    contract_manager.update_parcel_status(
                                        str(parcel.id),
                                        1  # ParcelStatus.Active
                                    )
                            else:
                                # Generate a placeholder hash for legacy records without blockchain registration
                                tx_hash = f"LEGACY_{uuid.uuid4().hex}"
                            
                            parcel.blockchain_tx_hash = tx_hash
                        except Exception as e:
                            messages.warning(request, f'Legacy document verified but blockchain registration failed: {str(e)}')
                    
                    # Update status and verification data
                    parcel.status = 'active'
                    parcel.verification_data = {
                        'verified_by': request.user.id,
                        'verified_at': timezone.now().isoformat(),
                        'legacy_verification': True,
                        'document_verified': bool(parcel.legacy_document),
                        'tx_hash': parcel.blockchain_tx_hash
                    }
                    parcel.save()
                    
                    # Send email notification to the owner
                    try:
                        send_land_verification_email(parcel, parcel.owner)
                    except Exception as email_error:
                        # Log email error but don't fail verification
                        print(f"Failed to send verification email: {str(email_error)}")
                    
                    # Track status change in history
                    ParcelHistoryTracker.track_status_change(
                        parcel=parcel,
                        changed_by=request.user,
                        previous_status='pending',
                        new_status='active',
                        blockchain_tx_hash=parcel.blockchain_tx_hash,
                        notes=f"Legacy parcel verified by {request.user.get_full_name()}"
                    )
                    
                    messages.success(request, 'Legacy land parcel verified successfully.')
                
                elif action == 'reject':
                    parcel.status = 'rejected'
                    parcel.verification_data = {
                        'rejected_by': request.user.id,
                        'rejected_at': timezone.now().isoformat(),
                        'legacy_verification': True,
                        'reason': request.POST.get('reason', 'No reason provided')
                    }
                    parcel.save()
                    
                    # Track status change in history
                    ParcelHistoryTracker.track_status_change(
                        parcel=parcel,
                        changed_by=request.user,
                        previous_status='pending',
                        new_status='rejected',
                        blockchain_tx_hash=None,
                        notes=f"Legacy parcel rejected by {request.user.get_full_name()}: {request.POST.get('reason', 'No reason provided')}"
                    )
                    
                    messages.success(request, 'Legacy land parcel rejected.')
            
            # Handle regular blockchain parcels
            else:
                # First, check if the parcel exists on the blockchain and get its current status
                try:
                    blockchain_details = contract_manager.get_land_details(str(parcel.id))
                    
                    # Check if parcel exists on blockchain
                    if blockchain_details is None:
                        # Parcel not found on blockchain - transaction may not be mined yet
                        # Check if we have a transaction hash - if yes, transaction is sent but not mined
                        if parcel.blockchain_tx_hash:
                            # Try to wait for transaction to be mined (for Quorum networks)
                            import time
                            tx_hash = parcel.blockchain_tx_hash
                            
                            # Wait a bit for transaction to be mined (up to 10 seconds)
                            receipt = None
                            for i in range(10):  # Check 10 times over 10 seconds
                                try:
                                    receipt = contract_manager.wait_for_transaction_mined(tx_hash, timeout=1)
                                    if receipt and receipt.status == 1:
                                        # Transaction mined successfully - try getting parcel details again
                                        blockchain_details = contract_manager.get_land_details(str(parcel.id))
                                        if blockchain_details:
                                            break  # Parcel now exists, continue with verification
                                except:
                                    pass
                                time.sleep(1)  # Wait 1 second between checks
                            
                            # If still not found after waiting, show warning
                            blockchain_details = contract_manager.get_land_details(str(parcel.id))
                            if blockchain_details is None:
                                messages.warning(
                                    request, 
                                    f'Transaction sent (tx: {tx_hash[:10]}...) but not yet mined on blockchain. '
                                    'Your Quorum network may need to mine blocks manually. '
                                    'Please wait a few moments and try again, or check your Quorum node status.'
                                )
                                return redirect('land_registry:verify_land')
                            # If parcel now exists, continue with verification below
                        else:
                            messages.error(request, 'This parcel has not been registered on the blockchain yet. Please ensure it is properly registered first.')
                            return redirect('land_registry:verify_land')
                    
                    # Verify the parcel's blockchain status is 'pending'
                    if blockchain_details['status'] != 'pending':
                        messages.error(request, f'Invalid parcel status on blockchain: {blockchain_details["status"]}. Only pending parcels can be verified.')
                        return redirect('land_registry:verify_land')
                    
                except Exception as e:
                    # Handle other errors (network issues, etc.)
                    error_msg = str(e)
                    if 'Parcel does not exist' in error_msg or 'not found' in error_msg.lower():
                        # Parcel not found - check if transaction hash exists
                        if parcel.blockchain_tx_hash:
                            messages.warning(
                                request, 
                                f'Transaction sent (tx: {parcel.blockchain_tx_hash[:10]}...) but parcel not yet on blockchain. '
                                'Please wait a few moments for transaction to be mined and try again. '
                                'If using Quorum, ensure your network is mining blocks.'
                            )
                        else:
                            messages.error(request, 'This parcel has not been registered on the blockchain yet. Please ensure it is properly registered first.')
                    else:
                        messages.error(request, f'Failed to verify parcel on blockchain: {str(e)}')
                    return redirect('land_registry:verify_land')

                if action == 'verify':
                    try:
                        # Update blockchain status from Pending (0) to Active (1)
                        tx_hash = contract_manager.update_parcel_status(
                            str(parcel.id),  # Ensure parcel_id is a string
                            1  # ParcelStatus.Active
                        )
                        
                        parcel.status = 'active'  # Change to 'active' to match smart contract
                        parcel.verification_data = {
                            'verified_by': request.user.id,
                            'verified_at': timezone.now().isoformat(),
                            'tx_hash': tx_hash
                        }
                        parcel.blockchain_tx_hash = tx_hash  # Ensure tx_hash is stored
                        parcel.save()
                        
                        # Send email notification to the owner
                        try:
                            send_land_verification_email(parcel, parcel.owner)
                        except Exception as email_error:
                            # Log email error but don't fail verification
                            print(f"Failed to send verification email: {str(email_error)}")
                        
                        # Track status change in history
                        ParcelHistoryTracker.track_status_change(
                            parcel=parcel,
                            changed_by=request.user,
                            previous_status='pending',
                            new_status='active',
                            blockchain_tx_hash=tx_hash,
                            notes=f"Parcel verified by {request.user.get_full_name()}"
                        )
                        
                        messages.success(request, 'Land parcel verified successfully.')
                    except Exception as e:
                        # Keep current status if blockchain update fails
                        messages.error(request, f'Failed to update parcel status on blockchain: {str(e)}')
                        return redirect('land_registry:registrar_verify_land')
                
                elif action == 'update_from_ai':
                    try:
                        parcel_id = request.POST.get('parcel_id')
                        parcel = Parcel.objects.get(id=parcel_id)
                        
                        # Only process legacy documents
                        if parcel.is_legacy and parcel.legacy_document:
                            # Initialize document processor
                            document_processor = DocumentProcessor()
                            
                            # Process the document
                            extracted_data = document_processor.process_document(parcel.legacy_document.path)
                            
                            # Update parcel with extracted data if available
                            if extracted_data:
                                # Log the extracted data
                                parcel.verification_data = {
                                    'ai_extracted': True,
                                    'extracted_at': timezone.now().isoformat(),
                                    'extracted_by': request.user.id,
                                    'document_type': extracted_data.get('document_type', 'unknown'),
                                    'extracted_fields': {
                                        'owner_name': extracted_data.get('owner_name'),
                                        'coordinates': extracted_data.get('coordinates'),
                                        'area': extracted_data.get('area'),
                                        'address': extracted_data.get('address')
                                    }
                                }
                                parcel.save()
                                messages.success(request, 'Document processed with AI. Data extracted successfully.')
                            else:
                                messages.warning(request, 'Could not extract data from document.')
                        else:
                            messages.error(request, 'This parcel does not have a legacy document to process.')
                    except Exception as e:
                        messages.error(request, f'Error processing document with AI: {str(e)}')
                    
                    return redirect('land_registry:registrar_verify_land')
                
                elif action == 'reject':
                    try:
                        # Update blockchain status from Pending (0) to Locked (3)
                        tx_hash = contract_manager.update_parcel_status(
                            str(parcel.id),  # Ensure parcel_id is a string
                            3  # ParcelStatus.Locked
                        )
                        
                        parcel.status = 'rejected'  # This will show as 'Rejected' in UI but use Locked (3) status on chain
                        parcel.verification_data = {
                            'rejected_by': request.user.id,
                            'rejected_at': timezone.now().isoformat(),
                            'tx_hash': tx_hash,
                            'reason': request.POST.get('reason', 'No reason provided')
                        }
                        parcel.save()
                        messages.success(request, 'Land parcel rejected.')
                    except Exception as e:
                        # Keep current status if blockchain update fails
                        messages.error(request, f'Failed to update parcel status on blockchain: {str(e)}')
                        return redirect('land_registry:verify_land')
        
        except Exception as e:
            messages.error(request, f'Error processing verification: {str(e)}')

    context = {
        'parcels': parcels,
    }
    return render(request, 'dashboard/registrar/verify_land.html', context)


@login_required
@role_required('registrar')
def pending_transfers(request):
    """View for managing pending transfer approvals."""
    # Get all pending approval transactions
    pending_transactions = Transaction.objects.filter(
        transaction_type='transfer',
        status='pending_approval'
    ).select_related('from_user', 'to_user', 'parcel').order_by('-timestamp')
    
    # Paginate results
    paginator = Paginator(pending_transactions, 10)
    page_number = request.GET.get('page')
    transactions = paginator.get_page(page_number)
    
    context = {
        'transactions': transactions,
        'total_pending': pending_transactions.count(),
    }
    return render(request, 'dashboard/registrar/pending_transfers.html', context)


@login_required
@role_required('registrar')
def approve_transfer(request, transaction_id):
    """Approve a pending transfer request."""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method')
        return redirect('land_registry:pending_transfers')
    
    transaction_record = get_object_or_404(Transaction, id=transaction_id)
    
    # Verify transaction is pending approval
    if transaction_record.status != 'pending_approval':
        messages.error(request, 'This transfer is not pending approval')
        return redirect('land_registry:pending_transfers')
    
    # Verify user is registrar
    if request.user.role != 'registrar':
        messages.error(request, 'Only registrars can approve transfers')
        return redirect('land_registry:pending_transfers')
    
    try:
        approval_notes = request.POST.get('approval_notes', '')
        
        # Approve the transaction (this sets status to 'approved')
        transaction_record.approve(request.user, approval_notes)
        
        # Get recipient address and property ID from transaction details
        recipient_address = transaction_record.details.get('recipient_address')
        property_id = transaction_record.details.get('property_id')
        
        # Create notification for the original owner to execute the transfer
        Notification.objects.create(
            recipient=transaction_record.from_user,
            notification_type='transfer_approved',
            title='Transfer Request Approved - Action Required',
            message=f'Your transfer request for property #{property_id} has been approved by registrar {request.user.get_full_name()}. You now need to execute the blockchain transfer to complete the process. Please visit your dashboard to complete the transfer.',
            related_parcel=transaction_record.parcel,
            related_transaction=transaction_record
        )
        
        # Create notification for registrars about the approval
        registrars = User.objects.filter(role='registrar').exclude(id=request.user.id)
        for registrar in registrars:
            Notification.objects.create(
                recipient=registrar,
                notification_type='transfer_approved',
                title='Transfer Approved by Colleague',
                message=f'Transfer request for property #{property_id} has been approved by {request.user.get_full_name()}. The owner must now execute the blockchain transfer.',
                related_parcel=transaction_record.parcel,
                related_transaction=transaction_record
            )
        
        messages.success(request, f'Transfer approved successfully. The property owner will be notified to execute the blockchain transfer for property #{property_id}.')
        
    except Exception as e:
        messages.error(request, f'Error approving transfer: {str(e)}')
    
    return redirect('land_registry:pending_transfers')


@login_required
@role_required('registrar')
def reject_transfer(request, transaction_id):
    """Reject a pending transfer request."""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method')
        return redirect('land_registry:pending_transfers')
    
    transaction_record = get_object_or_404(Transaction, id=transaction_id)
    
    # Verify transaction is pending approval
    if transaction_record.status != 'pending_approval':
        messages.error(request, 'This transfer is not pending approval')
        return redirect('land_registry:pending_transfers')
    
    # Verify user is registrar
    if request.user.role != 'registrar':
        messages.error(request, 'Only registrars can reject transfers')
        return redirect('land_registry:pending_transfers')
    
    try:
        rejection_reason = request.POST.get('rejection_reason', '')
        
        # Reject the transaction
        transaction_record.reject(request.user, rejection_reason)
        
        # Create notification for the original requester
        property_id = transaction_record.details.get('property_id')
        recipient_address = transaction_record.details.get('recipient_address')
        
        Notification.objects.create(
            recipient=transaction_record.from_user,
            notification_type='transfer_rejected',
            title='Transfer Request Rejected',
            message=f'Your transfer request for property #{property_id} to {transaction_record.to_user.get_full_name() if transaction_record.to_user else recipient_address} has been rejected by registrar {request.user.get_full_name()}. Reason: {rejection_reason}',
            related_parcel=transaction_record.parcel,
            related_transaction=transaction_record
        )
        
        messages.success(request, f'Transfer request rejected successfully.')
        
    except Exception as e:
        messages.error(request, f'Error rejecting transfer: {str(e)}')
    
    return redirect('land_registry:pending_transfers')