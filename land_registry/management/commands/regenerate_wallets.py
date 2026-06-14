from django.core.management.base import BaseCommand
from land_registry.models import User
from land_registry.blockchain.wallet import WalletManager


class Command(BaseCommand):
    help = 'Regenerate wallet keys for existing users due to encryption key change'

    def handle(self, *args, **options):
        wallet_manager = WalletManager()
        users_updated = 0
        
        # Get all users with wallet addresses but potentially corrupted private keys
        users = User.objects.filter(wallet_address__isnull=False)
        
        self.stdout.write(f"Found {users.count()} users with wallet addresses")
        
        for user in users:
            try:
                # Try to decrypt the existing private key
                wallet_manager.decrypt_private_key(user.encrypted_private_key)
                self.stdout.write(f"User {user.username}: Private key is valid, skipping")
            except Exception:
                # Private key is corrupted, regenerate
                self.stdout.write(f"User {user.username}: Regenerating wallet...")
                
                # Create new wallet
                new_address, new_encrypted_private_key = wallet_manager.create_wallet()
                
                # Update user with new wallet info
                user.wallet_address = new_address
                user.encrypted_private_key = new_encrypted_private_key
                user.save()
                
                users_updated += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"User {user.username}: New wallet address {new_address}"
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully regenerated wallets for {users_updated} users"
            )
        )