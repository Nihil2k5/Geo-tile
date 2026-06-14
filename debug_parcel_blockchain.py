#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from land_registry.models import Parcel
from land_registry.blockchain.contracts import ContractManager

def debug_parcel_blockchain_sync():
    """Debug parcel synchronization between Django DB and blockchain"""
    
    print("=== PARCEL BLOCKCHAIN SYNC DEBUG ===\n")
    
    # Get all parcels from Django database
    db_parcels = Parcel.objects.all()
    print(f"📊 Total parcels in Django DB: {db_parcels.count()}")
    
    # Get active parcels (what shows in dispute dropdown)
    active_parcels = Parcel.objects.filter(status='active')
    print(f"🟢 Active parcels in Django DB: {active_parcels.count()}")
    
    print("\n--- Active Parcels in Database ---")
    for parcel in active_parcels:
        print(f"ID: {parcel.id}, Owner: {parcel.owner.username}, Location: {parcel.location}, Status: {parcel.status}")
    
    # Check blockchain contract
    try:
        contract_manager = ContractManager()
        print(f"\n🔗 Blockchain contract initialized successfully")
        
        # Try to check if parcels exist on blockchain
        print("\n--- Checking Blockchain Parcel Existence ---")
        for parcel in active_parcels:
            try:
                # Try to get parcel info from blockchain
                parcel_info = contract_manager.get_land_details(parcel.id)
                if parcel_info and parcel_info.get('owner') != '0x0000000000000000000000000000000000000000':  # Check if owner is not zero address
                    print(f"✅ Parcel {parcel.id} EXISTS on blockchain - Owner: {parcel_info['owner']}, Status: {parcel_info['status']}")
                else:
                    print(f"❌ Parcel {parcel.id} NOT FOUND on blockchain (zero address owner)")
            except Exception as e:
                print(f"❌ Parcel {parcel.id} ERROR checking blockchain: {str(e)}")
                
    except Exception as e:
        print(f"❌ Error connecting to blockchain: {str(e)}")
    
    print("\n=== DEBUG COMPLETE ===")

if __name__ == "__main__":
    debug_parcel_blockchain_sync()