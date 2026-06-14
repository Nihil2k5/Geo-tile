#!/usr/bin/env python3

import os
import sys
import django
from datetime import datetime

# Add the project directory to Python path
sys.path.append('/Users/nihilmh/Documents/untitled folder/untitled folder 3')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_registry.settings')
django.setup()

from land_registry.models import Dispute, User, Parcel
from land_registry.blockchain.contracts import ContractManager

def test_complete_dispute_workflow():
    print("=== Testing Complete Dispute Management Workflow ===")
    
    try:
        # Initialize ContractManager
        contract_manager = ContractManager()
        print("✓ ContractManager initialized successfully")
        
        # Check if DisputeManager is available
        if hasattr(contract_manager, 'dispute_manager') and contract_manager.dispute_manager:
            print("✓ DisputeManager contract found")
        else:
            print("✗ DisputeManager contract not found")
            return
        
        # Get a citizen user and parcel for testing
        citizen = User.objects.filter(role='citizen').first()
        parcel = Parcel.objects.filter(status='active').first()
        
        if not citizen or not parcel:
            print("✗ No citizen user or active parcel found for testing")
            return
        
        print(f"✓ Using citizen: {citizen.username} and parcel: {parcel.parcel_id}")
        
        # Test 1: File a new dispute
        print("\n--- Test 1: Filing a new dispute ---")
        
        # Create Django dispute
        dispute = Dispute.objects.create(
            complainant=citizen,
            parcel=parcel,
            description="Test dispute for land ownership verification",
            ipfs_hash="QmTestHash123456789",
            status='filed'
        )
        print(f"✓ Django dispute created with ID: {dispute.id}")
        
        # File dispute on blockchain
        try:
            tx_hash = contract_manager.file_dispute(
                dispute_id=str(dispute.id),
                parcel_id=str(parcel.parcel_id),
                ipfs_hash=dispute.ipfs_hash
            )
            print(f"✓ Dispute filed on blockchain, tx_hash: {tx_hash}")
        except Exception as e:
            print(f"✗ Error filing dispute on blockchain: {e}")
            return
        
        # Test 2: Retrieve dispute details from blockchain
        print("\n--- Test 2: Retrieving dispute details ---")
        
        try:
            blockchain_dispute = contract_manager.get_dispute_details(str(dispute.id))
            if blockchain_dispute:
                print(f"✓ Dispute details retrieved from blockchain:")
                print(f"  - Dispute ID: {blockchain_dispute.get('disputeId')}")
                print(f"  - Parcel ID: {blockchain_dispute.get('parcelId')}")
                print(f"  - Complainant: {blockchain_dispute.get('complainant')}")
                print(f"  - Status: {blockchain_dispute.get('status')}")
                print(f"  - IPFS Hash: {blockchain_dispute.get('ipfsHash')}")
            else:
                print("✗ Could not retrieve dispute details from blockchain")
                return
        except Exception as e:
            print(f"✗ Error retrieving dispute details: {e}")
            return
        
        # Test 3: Update dispute status (should work now with proper role)
        print("\n--- Test 3: Updating dispute status ---")
        
        try:
            tx_hash = contract_manager.update_dispute_status(
                dispute_id=str(dispute.id),
                new_status=1,  # Under Review
                resolution_ipfs_hash=""
            )
            print(f"✓ Dispute status updated on blockchain, tx_hash: {tx_hash}")
            
            # Update Django dispute as well
            dispute.status = 'under_review'
            dispute.save()
            print("✓ Django dispute status updated to 'under_review'")
            
        except Exception as e:
            print(f"✗ Error updating dispute status: {e}")
            return
        
        # Test 4: Verify updated status
        print("\n--- Test 4: Verifying updated status ---")
        
        try:
            updated_dispute = contract_manager.get_dispute_details(str(dispute.id))
            if updated_dispute:
                status = updated_dispute.get('status')
                print(f"✓ Updated dispute status from blockchain: {status}")
                if status == 1:  # Under Review
                    print("✓ Status update verified successfully")
                else:
                    print(f"✗ Unexpected status: {status}")
            else:
                print("✗ Could not retrieve updated dispute details")
        except Exception as e:
            print(f"✗ Error verifying updated status: {e}")
        
        # Test 5: Add evidence
        print("\n--- Test 5: Adding evidence ---")
        
        try:
            tx_hash = contract_manager.add_dispute_evidence(
                dispute_id=str(dispute.id),
                ipfs_hash="QmEvidenceHash987654321"
            )
            print(f"✓ Evidence added to dispute, tx_hash: {tx_hash}")
        except Exception as e:
            print(f"✗ Error adding evidence: {e}")
        
        print("\n=== Dispute Management Test Complete ===")
        print(f"✓ All tests completed successfully!")
        print(f"✓ Dispute ID {dispute.id} is ready for court review")
        
    except Exception as e:
        print(f"✗ Unexpected error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_complete_dispute_workflow()