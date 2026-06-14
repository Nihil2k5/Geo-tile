from django.core.management.base import BaseCommand
from django.db import transaction
from land_registry.models import User
from land_registry.blockchain.wallet import WalletManager
from eth_account import Account


class Command(BaseCommand):
    help = 'Fix missing private keys for users who have wallet addresses but no encrypted private keys'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Fix private key for a specific user ID only',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        user_id = options.get('user_id')
        
        # Get users with wallet addresses but no private keys
        if user_id:
            users_without_keys = User.objects.filter(
                id=user_id,
                wallet_address__isnull=False,
                encrypted_private_key__isnull=True
            )
        else:
            users_without_keys = User.objects.filter(
                wallet_address__isnull=False,
                encrypted_private_key__isnull=True
            )

        if not users_without_keys.exists():
            if user_id:
                self.stdout.write(
                    self.style.SUCCESS(f'User {user_id} already has a private key or no wallet address.')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('All users with wallet addresses already have private keys.')
                )
            return

        self.stdout.write(f'Found {users_without_keys.count()} users with missing private keys:')
        
        for user in users_without_keys:
            self.stdout.write(f'  - {user.username} (ID: {user.id}) - Wallet: {user.wallet_address}')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nDRY RUN: No changes will be made. Remove --dry-run to apply fixes.')
            )
            return

        # Confirm before proceeding
        if not user_id:
            confirm = input('\nDo you want to generate private keys for these users? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write('Operation cancelled.')
                return

        wallet_manager = WalletManager()
        fixed_count = 0

        with transaction.atomic():
            for user in users_without_keys:
                try:
                    # Generate a new private key for the existing wallet address
                    # Note: This creates a NEW private key, not the original one
                    # The original private key is lost if it was never stored
                    account = Account.create()
                    private_key = account.key.hex()
                    
                    # Encrypt the private key
                    encrypted_private_key = wallet_manager.encrypt_private_key(private_key)
                    
                    # Update the user's wallet address and private key
                    # We need to update the wallet address too since we're creating a new keypair
                    user.wallet_address = account.address
                    user.encrypted_private_key = encrypted_private_key
                    user.save()
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Fixed user {user.username} (ID: {user.id}) - New wallet: {user.wallet_address}'
                        )
                    )
                    fixed_count += 1
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'✗ Failed to fix user {user.username} (ID: {user.id}): {str(e)}'
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully fixed {fixed_count} users.')
        )
        
        if fixed_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    '\nIMPORTANT: New wallet addresses have been generated for these users. '
                    'Any blockchain transactions or NFTs associated with their old wallet addresses '
                    'will need to be transferred to the new addresses.'
                )
            )