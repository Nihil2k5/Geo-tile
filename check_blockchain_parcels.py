#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from land_registry.models import User, Parcel
from land_registry.blockchain.contracts import ContractManager

def main():
    print("=== Checking Blockchain Parcels ===")
    
    # Initialize contract manager
    contract_manager = ContractManager()
    print("✓ ContractManager initialized")
    
    # Get all parcels from Django
    parcels = Parcel.objects.all()
    print(f"✓ Found {parcels.count()} parcels in Django database")
    
    blockchain_parcels = []
    
    for parcel in parcels:
        print(f"\nChecking parcel {parcel.id}:")
        print(f"  - Owner: {parcel.owner.username}")
        print(f"  - Status: {parcel.status}")
        print(f"  - Blockchain TX: {parcel.blockchain_tx_hash}")
        
        try:
            # Try to get parcel details from blockchain
            details = contract_manager.get_land_details(str(parcel.id))
            print(f"  ✓ Found on blockchain: Token ID {details.get('token_id')}")
            blockchain_parcels.append(parcel.id)
        except Exception as e:
            print(f"  ✗ Not found on blockchain: {str(e)}")
    
    print(f"\n=== Summary ===")
    print(f"Django parcels: {parcels.count()}")
    print(f"Blockchain parcels: {len(blockchain_parcels)}")
    print(f"Blockchain parcel IDs: {blockchain_parcels}")
    
    if blockchain_parcels:
        print(f"\nUsing parcel {blockchain_parcels[0]} for dispute test")
        return blockchain_parcels[0]
    else:
        print("\nNo parcels found on blockchain. Need to register one first.")
        return None

if __name__ == "__main__":
    main()