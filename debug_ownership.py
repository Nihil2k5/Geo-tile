#!/usr/bin/env python3
"""
Debug script to check parcel ownership states and identify transfer issues
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from land_registry.models import User, Parcel, Transaction
from land_registry.blockchain.contracts import ContractManager

def debug_ownership_issue():
    """Debug the ownership issue causing transfer failures"""
    print("🔍 Debugging Parcel Ownership Issue")
    print("=" * 50)
    
    # Initialize contract manager
    contract_manager = ContractManager()
    
    # Get recent failed transactions
    print("\n📋 Recent Transfer Transactions:")
    recent_transactions = Transaction.objects.filter(
        transaction_type='transfer'
    ).order_by('-timestamp')[:5]
    
    for tx in recent_transactions:
        print(f"   - Transaction ID: {tx.id}")
        print(f"     Status: {tx.status}")
        print(f"     From: {tx.from_user.username if tx.from_user else 'Unknown'}")
        print(f"     To: {tx.to_user.username if tx.to_user else 'Unknown'}")
        print(f"     Parcel: {tx.parcel.id if tx.parcel else 'Unknown'}")
        print(f"     Created: {tx.timestamp}")
        print()
    
    # Check approved transactions that need execution
    print("\n🔄 Approved Transfers Awaiting Execution:")
    approved_transfers = Transaction.objects.filter(
        transaction_type='transfer',
        status='approved'
    )
    
    for tx in approved_transfers:
        print(f"\n📦 Transaction ID: {tx.id}")
        print(f"   Parcel ID: {tx.parcel.id}")
        print(f"   From User: {tx.from_user.username}")
        print(f"   From Wallet: {tx.from_user.wallet_address}")
        
        # Get recipient address from transaction details
        recipient_address = tx.details.get('recipient_address', 'Not found')
        print(f"   To Address: {recipient_address}")
        
        # Check Django database ownership
        parcel = tx.parcel
        print(f"\n   📊 Django Database State:")
        print(f"      Owner: {parcel.owner.username}")
        print(f"      Owner Wallet: {parcel.owner.wallet_address}")
        print(f"      Status: {parcel.status}")
        print(f"      Blockchain TX Hash: {parcel.blockchain_tx_hash}")
        
        # Check blockchain ownership
        try:
            print(f"\n   🔗 Blockchain State:")
            blockchain_details = contract_manager.get_land_details(str(parcel.id))
            print(f"      Blockchain Owner: {blockchain_details['owner']}")
            print(f"      Blockchain Status: {blockchain_details['status']}")
            
            # Check if addresses match
            django_owner_address = parcel.owner.wallet_address.lower() if parcel.owner.wallet_address else None
            blockchain_owner_address = blockchain_details['owner'].lower()
            
            print(f"\n   ✅ Ownership Verification:")
            print(f"      Django Owner Address: {django_owner_address}")
            print(f"      Blockchain Owner Address: {blockchain_owner_address}")
            
            if django_owner_address == blockchain_owner_address:
                print(f"      ✅ Addresses MATCH")
            else:
                print(f"      ❌ Addresses DO NOT MATCH - This is the problem!")
                
                # Try to find the correct owner in Django
                try:
                    correct_owner = User.objects.get(wallet_address__iexact=blockchain_owner_address)
                    print(f"      💡 Correct owner should be: {correct_owner.username}")
                except User.DoesNotExist:
                    print(f"      ⚠️  Blockchain owner {blockchain_owner_address} not found in Django database")
            
            # Check if the transaction sender matches the blockchain owner
            tx_sender_address = tx.from_user.wallet_address.lower() if tx.from_user.wallet_address else None
            print(f"\n   🔄 Transfer Verification:")
            print(f"      Transaction Sender: {tx_sender_address}")
            print(f"      Blockchain Owner: {blockchain_owner_address}")
            
            if tx_sender_address == blockchain_owner_address:
                print(f"      ✅ Sender IS the blockchain owner - Transfer should work")
            else:
                print(f"      ❌ Sender is NOT the blockchain owner - This will fail with 'Not parcel owner'")
                
        except Exception as e:
            print(f"      ❌ Error getting blockchain details: {str(e)}")
        
        print("-" * 40)
    
    # Check for ownership sync issues
    print(f"\n🔄 Checking for Ownership Sync Issues:")
    all_parcels = Parcel.objects.filter(status='active')[:10]  # Check first 10 active parcels
    
    sync_issues = []
    for parcel in all_parcels:
        try:
            blockchain_details = contract_manager.get_land_details(str(parcel.id))
            django_owner = parcel.owner.wallet_address.lower() if parcel.owner.wallet_address else None
            blockchain_owner = blockchain_details['owner'].lower()
            
            if django_owner != blockchain_owner:
                sync_issues.append({
                    'parcel_id': parcel.id,
                    'django_owner': parcel.owner.username,
                    'django_address': django_owner,
                    'blockchain_address': blockchain_owner
                })
        except Exception as e:
            print(f"   ⚠️  Could not check parcel {parcel.id}: {str(e)}")
    
    if sync_issues:
        print(f"   ❌ Found {len(sync_issues)} ownership sync issues:")
        for issue in sync_issues:
            print(f"      Parcel {issue['parcel_id']}: Django={issue['django_owner']} vs Blockchain={issue['blockchain_address']}")
    else:
        print(f"   ✅ No ownership sync issues found in checked parcels")
    
    print(f"\n💡 Recommendations:")
    print(f"   1. Run the sync_blockchain_ownership management command to fix ownership mismatches")
    print(f"   2. Ensure users are trying to transfer parcels they actually own on the blockchain")
    print(f"   3. Check that wallet addresses are correctly stored and formatted")

if __name__ == '__main__':
    debug_ownership_issue()