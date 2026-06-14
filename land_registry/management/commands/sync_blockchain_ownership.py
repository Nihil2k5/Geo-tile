from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from land_registry.models import Parcel, User, Notification
from land_registry.blockchain.contracts import ContractManager
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sync parcel ownership from blockchain to Django database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--parcel-id',
            type=int,
            help='Sync specific parcel by ID',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Sync all parcels',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        contract_manager = ContractManager()
        
        if options['parcel_id']:
            parcels = Parcel.objects.filter(id=options['parcel_id'])
            if not parcels.exists():
                raise CommandError(f'Parcel with ID {options["parcel_id"]} does not exist')
        elif options['all']:
            parcels = Parcel.objects.all()
        else:
            # Default: sync parcels that might be out of sync
            parcels = Parcel.objects.filter(status='active')
        
        synced_count = 0
        error_count = 0
        
        for parcel in parcels:
            try:
                # Get blockchain ownership
                blockchain_details = contract_manager.get_land_details(str(parcel.id))
                blockchain_owner_address = blockchain_details.get('owner')
                
                if not blockchain_owner_address:
                    self.stdout.write(
                        self.style.WARNING(f'Parcel {parcel.id}: No blockchain owner found')
                    )
                    continue
                
                # Find user with this wallet address
                try:
                    blockchain_owner = User.objects.get(wallet_address=blockchain_owner_address)
                except User.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Parcel {parcel.id}: Blockchain owner {blockchain_owner_address} not registered in system'
                        )
                    )
                    continue
                
                # Check if ownership needs updating
                if parcel.owner != blockchain_owner:
                    old_owner = parcel.owner
                    
                    if options['dry_run']:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'[DRY RUN] Would update Parcel {parcel.id} owner from {old_owner.username} to {blockchain_owner.username}'
                            )
                        )
                    else:
                        with transaction.atomic():
                            # Update ownership
                            parcel.owner = blockchain_owner
                            parcel.save()
                            
                            # Create notification for new owner
                            Notification.objects.create(
                                recipient=blockchain_owner,
                                notification_type='system_alert',
                                title='Property Ownership Synchronized',
                                message=f'Your ownership of property #{parcel.id} has been synchronized from the blockchain.',
                                related_parcel=parcel
                            )
                            
                            # Create notification for old owner if different
                            if old_owner != blockchain_owner:
                                Notification.objects.create(
                                    recipient=old_owner,
                                    notification_type='system_alert',
                                    title='Property Ownership Updated',
                                    message=f'Property #{parcel.id} ownership has been updated based on blockchain records.',
                                    related_parcel=parcel
                                )
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Updated Parcel {parcel.id} owner from {old_owner.username} to {blockchain_owner.username}'
                            )
                        )
                    
                    synced_count += 1
                else:
                    self.stdout.write(f'Parcel {parcel.id}: Already in sync')
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'Error syncing Parcel {parcel.id}: {str(e)}')
                )
                logger.error(f'Error syncing Parcel {parcel.id}: {str(e)}')
        
        if options['dry_run']:
            self.stdout.write(
                self.style.SUCCESS(f'[DRY RUN] Would sync {synced_count} parcels, {error_count} errors')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Synced {synced_count} parcels, {error_count} errors')
            )