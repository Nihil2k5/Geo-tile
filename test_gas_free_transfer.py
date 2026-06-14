#!/usr/bin/env python3

import os
import sys
import django

# Add the project directory to the Python path
sys.path.append('/Users/nihilmh/Documents/untitled folder/untitled folder 3')

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from land_registry.models import User, Parcel
from land_registry.blockchain.contracts import ContractManager

def test_gas_free_transfer():
    """Test gas-free property transfer"""
    try:
        # Get test users
        user1 = User.objects.get(username='citi')
        user2 = User.objects.get(username='nihil')
        
        # Create a test parcel if one doesn't exist
        parcel, created = Parcel.objects.get_or_create(
            owner=user1,
            defaults={
                'location': 'Test Location',
                'description': 'Test parcel for gas-free transfer',
                'area': 1000,
                'coordinates': '[[0,0],[1,0],[1,1],[0,1],[0,0]]',
                'status': 'pending'
            }
        )
        
        if created:
            print(f"✅ Created test parcel with ID: {parcel.id}")
        else:
            print(f"✅ Using existing parcel with ID: {parcel.id}")
        
        print(f"📍 Parcel details:")
        print(f"   - ID: {parcel.id}")
        print(f"   - Owner: {parcel.owner.username}")
        print(f"   - Location: {parcel.location}")
        print(f"   - Area: {parcel.area}")
        
        # Initialize contract manager
        contract_manager = ContractManager()
        
        # Check if parcel exists on blockchain, if not register it
        try:
            blockchain_details = contract_manager.get_land_details(str(parcel.id))
            print(f"✅ Parcel already exists on blockchain")
        except Exception as e:
            if 'Parcel does not exist' in str(e):
                print(f"📝 Registering parcel on blockchain...")
                
                # Create a simple IPFS hash (mock)
                ipfs_hash = f"QmTest{parcel.id}"
                
                # Register the parcel on blockchain
                register_tx_hash = contract_manager.register_land(
                    str(parcel.id),
                    user1.wallet_address,
                    ipfs_hash,
                    parcel.area,
                    ipfs_hash
                )
                
                print(f"✅ Parcel registered on blockchain with tx: {register_tx_hash}")
                
                # Update parcel status to active
                update_tx_hash = contract_manager.update_parcel_status(str(parcel.id), 1)  # Active status
                print(f"✅ Parcel status updated to active with tx: {update_tx_hash}")
                
                # Update Django model
                parcel.blockchain_tx_hash = register_tx_hash
                parcel.status = 'active'
                parcel.save()
            else:
                raise e
        
        # Test gas-free land transfer
        print(f"\n🔄 Testing gas-free land transfer...")
        print(f"   From: {user1.username} ({user1.wallet_address})")
        print(f"   To: {user2.username} ({user2.wallet_address})")
        
        try:
            # Perform the transfer
            tx_hash = contract_manager.transfer_land(
                str(parcel.id),
                user1.wallet_address,
                user2.wallet_address
            )
            
            print(f"✅ Transfer successful! Transaction hash: {tx_hash}")
            print("🎉 Gas-free property transfer is working!")
            
        except Exception as transfer_error:
            print(f"❌ Transfer failed: {transfer_error}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gas_free_transfer()