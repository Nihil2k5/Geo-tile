#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from land_registry.models import User, Parcel
from land_registry.blockchain.contracts import ContractManager

def main():
    print("=== Registering Parcel on Blockchain ===")
    
    # Initialize contract manager
    contract_manager = ContractManager()
    print("✓ ContractManager initialized")
    
    # Get the first parcel
    parcel = Parcel.objects.first()
    if not parcel:
        print("✗ No parcels found in database")
        return
    
    print(f"✓ Using parcel {parcel.id}: Owner={parcel.owner.username}, Area={parcel.area}")
    
    try:
        # Check if already exists on blockchain
        if contract_manager.parcel_exists(str(parcel.id)):
            print(f"✗ Parcel {parcel.id} already exists on blockchain. Skipping.")
            return parcel.id
            
        # Register the parcel on blockchain
        tx_hash = contract_manager.register_land(
            parcel_id=str(parcel.id),
            owner_address=parcel.owner.wallet_address,
            ipfs_hash="QmTestParcelHash123456789",
            area=parcel.area
        )
        print(f"✓ Parcel registered on blockchain, tx_hash: {tx_hash}")
        
        # Update the parcel with blockchain transaction hash
        parcel.blockchain_tx_hash = tx_hash
        parcel.save()
        print(f"✓ Updated parcel {parcel.id} with blockchain tx_hash")
        
        # Verify registration
        details = contract_manager.get_land_details(str(parcel.id))
        print(f"✓ Verification successful: Token ID {details.get('token_id')}")
        
        return parcel.id
        
    except Exception as e:
        print(f"✗ Error registering parcel: {str(e)}")
        return None

if __name__ == "__main__":
    main()