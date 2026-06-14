#!/usr/bin/env python
"""
Script to re-upload parcel data to IPFS for parcels with invalid IPFS hashes.
This will generate new valid IPFS hashes for existing parcels.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from land_registry.models import Parcel
from land_registry.utils.ipfs import upload_to_ipfs, is_valid_ipfs_hash
from land_registry.blockchain.contracts import ContractManager

def fix_invalid_ipfs_hashes():
    """Re-upload parcel data to IPFS for parcels with invalid hashes."""
    print("=" * 60)
    print("Fixing Invalid IPFS Hashes")
    print("=" * 60)
    
    # Get all parcels
    parcels = Parcel.objects.all()
    print(f"\nFound {parcels.count()} parcels in database")
    
    fixed_count = 0
    error_count = 0
    
    for parcel in parcels:
        print(f"\n--- Processing Parcel {parcel.id} ---")
        
        # Check if parcel has invalid IPFS hash on blockchain
        try:
            contract_manager = ContractManager()
            blockchain_details = contract_manager.get_land_details(str(parcel.id))
            
            if blockchain_details:
                ipfs_hash = blockchain_details.get('ipfs_hash')
                if ipfs_hash:
                    print(f"  Blockchain IPFS Hash: {ipfs_hash}")
                    print(f"  Hash Valid: {is_valid_ipfs_hash(ipfs_hash)}")
                    
                    if not is_valid_ipfs_hash(ipfs_hash):
                        print(f"  ⚠️  Invalid hash detected - re-uploading to IPFS...")
                        
                        # Prepare complete parcel data
                        parcel_data = {
                            'parcel_id': str(parcel.id),
                            'owner': parcel.owner.wallet_address if parcel.owner.wallet_address else None,
                            'owner_name': parcel.owner.get_full_name(),
                            'area': float(parcel.area),
                            'coordinates': parcel.coordinates,
                            'location': parcel.location,
                            'description': parcel.description,
                            'status': parcel.status,
                            'created_at': parcel.created_at.isoformat() if parcel.created_at else None,
                            'village_name': parcel.village_name,
                            'district_name': parcel.district_name,
                            'state_name': parcel.state_name,
                            'original_survey_number': parcel.original_survey_number,
                            'original_document_reference': parcel.original_document_reference,
                            'original_area': float(parcel.original_area) if parcel.original_area else None,
                            'original_coordinates': parcel.original_coordinates,
                        }
                        
                        try:
                            # Upload to IPFS
                            new_ipfs_hash = upload_to_ipfs(parcel_data)
                            print(f"  ✓ New valid IPFS hash: {new_ipfs_hash}")
                            
                            # Update parcel's IPFS data hash
                            parcel.ipfs_data_hash = new_ipfs_hash
                            parcel.save(update_fields=['ipfs_data_hash'])
                            
                            print(f"  ✓ Parcel {parcel.id} updated with new IPFS hash")
                            fixed_count += 1
                        except Exception as e:
                            print(f"  ✗ Error uploading to IPFS: {e}")
                            error_count += 1
                    else:
                        print(f"  ✓ Hash is valid, no action needed")
                else:
                    print(f"  ⚠️  No IPFS hash on blockchain")
            else:
                print(f"  ⚠️  Parcel not found on blockchain")
        except Exception as e:
            print(f"  ✗ Error checking parcel: {e}")
            error_count += 1
    
    print(f"\n" + "=" * 60)
    print(f"Summary:")
    print(f"  Fixed: {fixed_count}")
    print(f"  Errors: {error_count}")
    print(f"=" * 60)

if __name__ == "__main__":
    fix_invalid_ipfs_hashes()
