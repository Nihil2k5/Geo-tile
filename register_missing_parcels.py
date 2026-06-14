#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from land_registry.models import Parcel
from land_registry.blockchain.contracts import ContractManager
from land_registry.utils.ipfs import upload_to_ipfs

def register_missing_parcels():
    """Register all missing parcels from Django DB to blockchain"""
    
    print("=== REGISTERING MISSING PARCELS TO BLOCKCHAIN ===\n")
    
    # Get all active parcels from Django database
    active_parcels = Parcel.objects.filter(status='active')
    print(f"🟢 Found {active_parcels.count()} active parcels in Django DB")
    
    contract_manager = ContractManager()
    registered_count = 0
    failed_count = 0
    
    for parcel in active_parcels:
        print(f"\n--- Processing Parcel {parcel.id} ---")
        print(f"Owner: {parcel.owner.username}")
        print(f"Location: {parcel.location}")
        
        try:
            # Check if parcel already exists on blockchain
            try:
                parcel_info = contract_manager.get_land_details(parcel.id)
                if parcel_info and parcel_info.get('owner') != '0x0000000000000000000000000000000000000000':
                    print(f"✅ Parcel {parcel.id} already exists on blockchain - SKIPPING")
                    continue
            except:
                # Parcel doesn't exist, proceed with registration
                pass
            
            # Get owner's wallet address
            owner_wallet = parcel.owner.wallet_address
            if not owner_wallet:
                print(f"❌ No wallet address for user {parcel.owner.username} - SKIPPING")
                failed_count += 1
                continue
            
            # Prepare parcel data for IPFS
            parcel_data = {
                'parcel_id': parcel.id,
                'location': parcel.location,
                'area': float(parcel.area),
                'owner': parcel.owner.username,
                'registered_at': parcel.created_at.isoformat() if parcel.created_at else None,
                'coordinates': parcel.coordinates if parcel.coordinates else None
            }
            
            # Upload to IPFS (simulated)
            ipfs_hash = upload_to_ipfs(parcel_data)
            print(f"📄 Generated IPFS hash: {ipfs_hash}")
            
            # Register on blockchain
            print(f"🔗 Registering parcel {parcel.id} on blockchain...")
            tx_hash = contract_manager.register_land(
                parcel_id=parcel.id,
                owner_address=owner_wallet,
                ipfs_hash=ipfs_hash,
                area=int(parcel.area * 100),  # Convert to square centimeters for precision
                metadata_uri=""
            )
            
            print(f"✅ Successfully registered parcel {parcel.id}")
            print(f"   Transaction hash: {tx_hash}")
            registered_count += 1
            
        except Exception as e:
            print(f"❌ Failed to register parcel {parcel.id}: {str(e)}")
            failed_count += 1
    
    print(f"\n=== REGISTRATION COMPLETE ===")
    print(f"✅ Successfully registered: {registered_count} parcels")
    print(f"❌ Failed to register: {failed_count} parcels")
    print(f"📊 Total processed: {registered_count + failed_count} parcels")

if __name__ == "__main__":
    register_missing_parcels()