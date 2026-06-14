#!/usr/bin/env python
"""
Script to synchronize parcel statuses between Django database and blockchain.
This prevents "Parcel is not active" errors during transfers.
"""
import os
import sys
import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "geoledger.settings")
django.setup()

from land_registry.models import Parcel
from land_registry.blockchain.contracts import ContractManager

def check_status_mismatches():
    """Check for status mismatches between Django and blockchain."""
    print('🔍 Checking for status mismatches between Django and blockchain...')
    print('=' * 60)
    
    contract_manager = ContractManager()
    mismatches = []
    
    # Check all parcels in Django
    all_parcels = Parcel.objects.all()
    print(f'Checking {all_parcels.count()} parcels...')
    
    for parcel in all_parcels:
        try:
            blockchain_details = contract_manager.get_land_details(str(parcel.id))
            django_status = parcel.status
            blockchain_status = blockchain_details['status']
            
            if django_status != blockchain_status:
                mismatches.append({
                    'parcel_id': parcel.id,
                    'django_status': django_status,
                    'blockchain_status': blockchain_status,
                    'owner': parcel.owner.username if parcel.owner else 'None'
                })
                print(f'❌ Parcel {parcel.id}: Django={django_status}, Blockchain={blockchain_status}, Owner={parcel.owner.username if parcel.owner else "None"}')
            else:
                print(f'✅ Parcel {parcel.id}: Status synchronized ({blockchain_status})')
                
        except Exception as e:
            print(f'⚠️  Error checking parcel {parcel.id}: {e}')
    
    return mismatches

def fix_status_mismatches(mismatches, fix_mode='blockchain'):
    """Fix status mismatches by updating either blockchain or Django."""
    if not mismatches:
        print('✅ No mismatches to fix!')
        return
    
    print(f'\n🔧 Fixing {len(mismatches)} status mismatches...')
    print('=' * 50)
    
    contract_manager = ContractManager()
    
    for mismatch in mismatches:
        parcel_id = mismatch['parcel_id']
        django_status = mismatch['django_status']
        blockchain_status = mismatch['blockchain_status']
        
        try:
            if fix_mode == 'blockchain':
                # Update blockchain to match Django
                status_map = {'pending': 0, 'active': 1, 'disputed': 2, 'locked': 3}
                new_status = status_map.get(django_status, 1)  # Default to active
                
                tx_hash = contract_manager.update_parcel_status(
                    str(parcel_id),
                    new_status
                )
                print(f'✅ Updated parcel {parcel_id} blockchain status to {django_status}. TX: {tx_hash[:10]}...')
                
            elif fix_mode == 'django':
                # Update Django to match blockchain
                parcel = Parcel.objects.get(id=parcel_id)
                parcel.status = blockchain_status
                parcel.save()
                print(f'✅ Updated parcel {parcel_id} Django status to {blockchain_status}')
                
        except Exception as e:
            print(f'❌ Error fixing parcel {parcel_id}: {e}')

def main():
    print("🔄 Parcel Status Synchronizer")
    print("============================")
    
    # Check for mismatches
    mismatches = check_status_mismatches()
    
    if not mismatches:
        print('\n🎉 All parcel statuses are synchronized!')
        return
    
    print(f'\n📊 Found {len(mismatches)} status mismatches:')
    for mismatch in mismatches:
        print(f'   - Parcel {mismatch["parcel_id"]}: Django={mismatch["django_status"]} vs Blockchain={mismatch["blockchain_status"]} (Owner: {mismatch["owner"]})')
    
    print('\n💡 Fix Options:')
    print('1. Update blockchain to match Django (recommended for active parcels)')
    print('2. Update Django to match blockchain')
    print('3. Exit without changes')
    
    choice = input('\nSelect option (1-3): ')
    
    if choice == '1':
        fix_status_mismatches(mismatches, 'blockchain')
        print('\n🎉 Blockchain statuses updated to match Django!')
    elif choice == '2':
        fix_status_mismatches(mismatches, 'django')
        print('\n🎉 Django statuses updated to match blockchain!')
    else:
        print('Exiting without changes')
    
    # Final verification
    if choice in ['1', '2']:
        print('\n🔍 Final verification...')
        final_mismatches = check_status_mismatches()
        if not final_mismatches:
            print('✅ All statuses are now synchronized!')
        else:
            print(f'⚠️  {len(final_mismatches)} mismatches still remain')

if __name__ == "__main__":
    main()