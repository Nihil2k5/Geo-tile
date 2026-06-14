from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.conf import settings
from .models import User, Transaction, Parcel
from .blockchain.wallet import WalletManager
from .blockchain.contracts import ContractManager
import logging

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=User)
def create_wallet_for_user(sender, instance, **kwargs):
    """
    Signal handler to automatically create a wallet for new users
    """
    # Only create wallet if user doesn't have one and is being created by admin
    if not instance.wallet_address and (not instance.pk or not User.objects.filter(pk=instance.pk).exists()):
        wallet_manager = WalletManager()
        address, encrypted_private_key = wallet_manager.create_wallet()
        
        instance.wallet_address = address
        instance.encrypted_private_key = encrypted_private_key


@receiver(post_save, sender=Transaction)
def sync_ownership_after_transfer(sender, instance, created, **kwargs):
    """
    Automatically sync parcel ownership in Django DB after a transfer transaction
    """
    if created and instance.transaction_type == 'transfer' and instance.status == 'confirmed':
        try:
            contract_manager = ContractManager()
            parcel = instance.parcel
            
            # Get current owner from blockchain
            blockchain_owner = contract_manager.get_parcel_owner(parcel.id)
            
            # Check if the blockchain owner matches the transaction recipient
            if instance.to_user and blockchain_owner.lower() == instance.to_user.wallet_address.lower():
                # Update Django database ownership
                parcel.owner = instance.to_user
                parcel.save()
                
                # Mark transaction as completed
                instance.mark_completed()
                
                logger.info(f"Successfully synced ownership for parcel {parcel.id} to user {instance.to_user.username}")
            elif blockchain_owner.lower() == instance.details.get('recipient_address', '').lower():
                # Blockchain transfer successful but recipient not in our system
                logger.info(f"Parcel {parcel.id} transferred on blockchain to {blockchain_owner} but recipient not registered")
            else:
                # Ownership mismatch - log error
                logger.error(f"Ownership mismatch for parcel {parcel.id}. Expected: {instance.to_user.wallet_address if instance.to_user else instance.details.get('recipient_address')}, Got: {blockchain_owner}")
                instance.mark_failed("Ownership verification failed")
                
        except Exception as e:
            logger.error(f"Error syncing ownership for transaction {instance.id}: {str(e)}")
            instance.mark_failed(f"Sync error: {str(e)}")