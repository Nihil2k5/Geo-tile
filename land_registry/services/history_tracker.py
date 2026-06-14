"""
History tracking service for land parcels.
Handles comprehensive tracking of all parcel changes including registration, transfers, and updates.
"""

from django.utils import timezone
from django.db import transaction
from land_registry.models import (
    Parcel, ParcelHistory, OwnershipChain, SurveyHistory, 
    Transaction, User
)
import json


class ParcelHistoryTracker:
    """Service for tracking comprehensive parcel history like a mother patta document."""
    
    @staticmethod
    def track_initial_registration(parcel, registrar, blockchain_tx_hash=None, notes=None):
        """Track the initial registration of a parcel (first entry in mother patta)."""
        with transaction.atomic():
            # Create parcel history entry
            ParcelHistory.objects.create(
                parcel=parcel,
                change_type='registration',
                changed_by=registrar,
                previous_data=None,  # No previous data for initial registration
                new_data={
                    'owner_id': parcel.owner.id,
                    'owner_name': parcel.owner.get_full_name(),
                    'owner_wallet': parcel.owner.wallet_address,
                    'area': parcel.area,
                    'coordinates': parcel.coordinates,
                    'location': parcel.location,
                    'description': parcel.description,
                    'status': parcel.status,
                    'surveyor_id': parcel.surveyor.id if parcel.surveyor else None,
                    'surveyor_name': parcel.surveyor.get_full_name() if parcel.surveyor else None,
                    'is_legacy': parcel.is_legacy,
                    'registration_date': timezone.now().isoformat()
                },
                blockchain_tx_hash=blockchain_tx_hash,
                notes=notes or f"Initial registration by {registrar.get_full_name()}"
            )
            
            # Create initial ownership chain entry
            OwnershipChain.objects.create(
                parcel=parcel,
                owner=parcel.owner,
                previous_owner=None,  # No previous owner for initial registration
                transfer_transaction=None,  # No transfer transaction for initial registration
                ownership_start_date=parcel.original_registration_date or timezone.now(),
                ownership_end_date=None,  # Current owner
                is_current_owner=True,
                transfer_method='initial_registration',
                blockchain_tx_hash=blockchain_tx_hash
            )
            
            # Update parcel with original registration details if not set
            if not parcel.original_owner:
                parcel.original_owner = parcel.owner
                parcel.original_registration_date = timezone.now()
                parcel.original_registrar = registrar
                parcel.original_area = parcel.area
                parcel.original_coordinates = parcel.coordinates
                parcel.save()
    
    @staticmethod
    def track_ownership_transfer(parcel, transaction_record, blockchain_tx_hash=None, notes=None):
        """Track ownership transfer between users."""
        with transaction.atomic():
            previous_owner = parcel.owner
            new_owner = transaction_record.to_user
            
            # Create parcel history entry
            ParcelHistory.objects.create(
                parcel=parcel,
                change_type='ownership_transfer',
                changed_by=transaction_record.from_user,
                previous_data={
                    'owner_id': previous_owner.id,
                    'owner_name': previous_owner.get_full_name(),
                    'owner_wallet': previous_owner.wallet_address,
                },
                new_data={
                    'owner_id': new_owner.id,
                    'owner_name': new_owner.get_full_name(),
                    'owner_wallet': new_owner.wallet_address,
                    'transfer_transaction_id': transaction_record.id,
                    'transfer_reason': transaction_record.details.get('transfer_reason', ''),
                    'transfer_date': timezone.now().isoformat()
                },
                blockchain_tx_hash=blockchain_tx_hash,
                notes=notes or f"Ownership transferred from {previous_owner.get_full_name()} to {new_owner.get_full_name()}"
            )
            
            # End previous ownership chain entry
            previous_ownership = OwnershipChain.objects.filter(
                parcel=parcel,
                owner=previous_owner,
                is_current_owner=True
            ).first()
            
            if previous_ownership:
                previous_ownership.ownership_end_date = timezone.now()
                previous_ownership.is_current_owner = False
                previous_ownership.save()
            
            # Create new ownership chain entry
            OwnershipChain.objects.create(
                parcel=parcel,
                owner=new_owner,
                previous_owner=previous_owner,
                transfer_transaction=transaction_record,
                ownership_start_date=timezone.now(),
                ownership_end_date=None,  # Current owner
                is_current_owner=True,
                transfer_method='blockchain_transfer',
                blockchain_tx_hash=blockchain_tx_hash
            )
    
    @staticmethod
    def track_survey_update(parcel, surveyor, previous_coordinates=None, previous_area=None, 
                          blockchain_tx_hash=None, survey_notes=None):
        """Track survey updates and modifications."""
        with transaction.atomic():
            # Create parcel history entry
            ParcelHistory.objects.create(
                parcel=parcel,
                change_type='survey_update',
                changed_by=surveyor,
                previous_data={
                    'coordinates': previous_coordinates,
                    'area': previous_area,
                },
                new_data={
                    'coordinates': parcel.coordinates,
                    'area': parcel.area,
                    'surveyor_id': surveyor.id,
                    'surveyor_name': surveyor.get_full_name(),
                    'survey_date': timezone.now().isoformat()
                },
                blockchain_tx_hash=blockchain_tx_hash,
                notes=f"Survey updated by {surveyor.get_full_name()}"
            )
            
            # Create survey history entry
            SurveyHistory.objects.create(
                parcel=parcel,
                surveyor=surveyor,
                previous_coordinates=previous_coordinates,
                new_coordinates=parcel.coordinates,
                previous_area=previous_area,
                new_area=parcel.area,
                survey_notes=survey_notes,
                blockchain_tx_hash=blockchain_tx_hash
            )
    
    @staticmethod
    def track_status_change(parcel, changed_by, previous_status, new_status, 
                          blockchain_tx_hash=None, notes=None):
        """Track status changes (pending -> surveyed -> active, etc.)."""
        ParcelHistory.objects.create(
            parcel=parcel,
            change_type='status_change',
            changed_by=changed_by,
            previous_data={
                'status': previous_status,
            },
            new_data={
                'status': new_status,
                'changed_date': timezone.now().isoformat()
            },
            blockchain_tx_hash=blockchain_tx_hash,
            notes=notes or f"Status changed from {previous_status} to {new_status} by {changed_by.get_full_name()}"
        )
    
    @staticmethod
    def track_dispute_filed(parcel, complainant, dispute, notes=None):
        """Track when a dispute is filed against a parcel."""
        ParcelHistory.objects.create(
            parcel=parcel,
            change_type='dispute_filed',
            changed_by=complainant,
            previous_data={
                'status': parcel.status,
            },
            new_data={
                'dispute_id': dispute.id,
                'dispute_description': dispute.description,
                'complainant_id': complainant.id,
                'complainant_name': complainant.get_full_name(),
                'filed_date': timezone.now().isoformat()
            },
            notes=notes or f"Dispute filed by {complainant.get_full_name()}"
        )
    
    @staticmethod
    def track_dispute_resolved(parcel, resolver, dispute, resolution, notes=None):
        """Track when a dispute is resolved."""
        ParcelHistory.objects.create(
            parcel=parcel,
            change_type='dispute_resolved',
            changed_by=resolver,
            previous_data={
                'dispute_status': 'open',
            },
            new_data={
                'dispute_id': dispute.id,
                'resolution': resolution,
                'resolver_id': resolver.id,
                'resolver_name': resolver.get_full_name(),
                'resolved_date': timezone.now().isoformat()
            },
            notes=notes or f"Dispute resolved by {resolver.get_full_name()}"
        )
    
    @staticmethod
    def get_complete_parcel_history(parcel):
        """Get complete history of a parcel like a mother patta document."""
        return {
            'parcel_info': {
                'id': parcel.id,
                'current_owner': parcel.owner.get_full_name(),
                'current_status': parcel.status,
                'current_area': parcel.area,
                'location': parcel.location,
                'description': parcel.description,
            },
            'original_registration': {
                'original_owner': parcel.original_owner.get_full_name() if parcel.original_owner else None,
                'registration_date': parcel.original_registration_date,
                'registrar': parcel.original_registrar.get_full_name() if parcel.original_registrar else None,
                'original_area': parcel.original_area,
                'survey_number': parcel.original_survey_number,
                'document_reference': parcel.original_document_reference,
                'village': parcel.village_name,
                'district': parcel.district_name,
                'state': parcel.state_name,
            },
            'ownership_chain': list(parcel.ownership_chain.all().values(
                'owner__first_name', 'owner__last_name', 'owner__username',
                'previous_owner__first_name', 'previous_owner__last_name', 'previous_owner__username',
                'ownership_start_date', 'ownership_end_date', 'transfer_method',
                'transfer_transaction__id', 'blockchain_tx_hash'
            )),
            'all_transactions': list(parcel.transactions.all().values(
                'id', 'transaction_type', 'status', 'timestamp', 'transaction_hash',
                'from_user__first_name', 'from_user__last_name',
                'to_user__first_name', 'to_user__last_name',
                'details'
            )),
            'survey_history': list(parcel.survey_history.all().values(
                'surveyor__first_name', 'surveyor__last_name',
                'previous_area', 'new_area', 'survey_date',
                'survey_method', 'equipment_used', 'accuracy_level',
                'survey_notes', 'blockchain_tx_hash'
            )),
            'complete_history': list(parcel.history.all().values(
                'change_type', 'changed_by__first_name', 'changed_by__last_name',
                'previous_data', 'new_data', 'timestamp', 'blockchain_tx_hash', 'notes'
            )),
            'disputes': list(parcel.disputes.all().values(
                'complainant__first_name', 'complainant__last_name',
                'description', 'status', 'resolution', 'created_at', 'resolved_at',
                'resolver__first_name', 'resolver__last_name'
            ))
        }