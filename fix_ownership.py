#!/usr/bin/env python
"""
Script to fix ownership mismatches between Django database and blockchain.
"""
import os
import sys
import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "geoledger.settings")
django.setup()

from land_registry.models import Parcel, User, Transaction
from land_registry.blockchain.contracts import get_land_registry_contract, transfer_land
from web3 import Web3

def get_blockchain_owner(parcel_id):
    """Get the current owner of a parcel on the blockchain."""
    contract = get_land_registry_contract()
    parcel_data = contract.functions.parcels(parcel_id).call()
    return parcel_data[1]  # owner address

def check_ownership_mismatches():
    """Check for ownership mismatches between Django and blockchain."""
    mismatches = []
    
    for parcel in Parcel.objects.all():
        try:
            blockchain_owner = get_blockchain_owner(parcel.id)
            django_owner = parcel.owner.wallet_address if parcel.owner else None
            
            if django_owner and blockchain_owner.lower() != django_owner.lower():
                mismatches.append({
                    'parcel_id': parcel.id,
                    'django_owner_username': parcel.owner.username,
                    'django_owner_address': django_owner,
                    'blockchain_owner': blockchain_owner
                })
        except Exception as e:
            print(f"Error checking parcel {parcel.id}: {e}")
    
    return mismatches

def update_django_ownership(parcel_id, blockchain_address):
    """Update Django ownership to match blockchain reality."""
    try:
        # Check if any user has this wallet address
        try:
            user = User.objects.get(wallet_address__iexact=blockchain_address)
            print(f"Found user {user.username} with matching wallet address")
        except User.DoesNotExist:
            print(f"No user found with wallet address {blockchain_address}")
            create = input("Create a new user with this address? (y/n): ")
            if create.lower() == 'y':
                username = input("Enter username for new user: ")
                user = User.objects.create(
                    username=username,
                    wallet_address=blockchain_address,
                    is_active=True
                )
                print(f"Created new user {username}")
            else:
                return False
        
        # Update parcel ownership
        parcel = Parcel.objects.get(id=parcel_id)
        old_owner = parcel.owner.username if parcel.owner else "None"
        parcel.owner = user
        parcel.save()
        
        print(f"Updated parcel {parcel_id} ownership from {old_owner} to {user.username}")
        return True
    except Exception as e:
        print(f"Error updating Django ownership: {e}")
        return False

def transfer_blockchain_ownership(parcel_id, new_owner_address):
    """Transfer ownership on the blockchain to match Django database."""
    try:
        # This would need to be executed by the current blockchain owner
        print(f"To transfer parcel {parcel_id} on blockchain to {new_owner_address}:")
        print("1. The current blockchain owner must execute this transaction")
        print("2. Use the transfer_land function from contracts.py")
        print(f"3. Example: transfer_land({parcel_id}, '{new_owner_address}')")
        
        execute = input("Attempt to execute this transfer now? (y/n): ")
        if execute.lower() == 'y':
            # This will likely fail unless run as the blockchain owner
            result = transfer_land(parcel_id, new_owner_address)
            print(f"Transfer result: {result}")
            return True
        return False
    except Exception as e:
        print(f"Error transferring blockchain ownership: {e}")
        return False

def main():
    print("🔍 Ownership Mismatch Fixer")
    print("==========================")
    
    mismatches = check_ownership_mismatches()
    
    if not mismatches:
        print("✅ No ownership mismatches found!")
        return
    
    print(f"❌ Found {len(mismatches)} ownership mismatches:")
    for i, mismatch in enumerate(mismatches, 1):
        print(f"{i}. Parcel {mismatch['parcel_id']}: Django={mismatch['django_owner_username']} ({mismatch['django_owner_address']}) vs Blockchain={mismatch['blockchain_owner']}")
    
    print("\n💡 Fix Options:")
    print("1. Update Django ownership to match blockchain")
    print("2. Transfer blockchain ownership to match Django")
    print("3. Exit without changes")
    
    choice = input("\nSelect option (1-3): ")
    
    if choice == '1':
        for mismatch in mismatches:
            print(f"\nFixing Parcel {mismatch['parcel_id']}...")
            update_django_ownership(mismatch['parcel_id'], mismatch['blockchain_owner'])
    elif choice == '2':
        for mismatch in mismatches:
            print(f"\nFixing Parcel {mismatch['parcel_id']}...")
            transfer_blockchain_ownership(mismatch['parcel_id'], mismatch['django_owner_address'])
    else:
        print("Exiting without changes")

if __name__ == "__main__":
    main()