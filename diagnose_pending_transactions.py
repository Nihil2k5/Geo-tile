#!/usr/bin/env python3
"""
Diagnose Pending Transactions
This script checks why transactions are pending and provides recommendations.
"""

import os
import sys
import django
from web3 import Web3
from web3.middleware import geth_poa_middleware

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from django.conf import settings
from land_registry.models import Parcel

def diagnose_pending_transactions():
    """Diagnose why transactions are pending"""
    print("=" * 60)
    print("PENDING TRANSACTION DIAGNOSTICS")
    print("=" * 60)
    
    try:
        # Connect to node
        w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URI))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        if not w3.is_connected():
            print("❌ Failed to connect to node")
            return False
        
        print("✅ Connected to node\n")
        
        # Get pending parcels
        pending_parcels = Parcel.objects.filter(
            blockchain_tx_hash__isnull=False
        ).exclude(blockchain_tx_hash='').order_by('-created_at')[:5]
        
        if not pending_parcels.exists():
            print("ℹ️  No pending parcels found")
            return True
        
        print(f"📋 Found {pending_parcels.count()} parcels with transaction hashes:\n")
        
        admin_address = settings.ADMIN_ADDRESS
        admin_account = w3.eth.account.from_key(settings.ADMIN_PRIVATE_KEY)
        
        print(f"👤 Admin Address: {admin_address}\n")
        
        # Check account balance
        try:
            balance = w3.eth.get_balance(admin_address)
            print(f"💰 Account Balance: {w3.from_wei(balance, 'ether')} ETH")
            if balance == 0:
                print("   ⚠️  WARNING: Account has zero balance (but this is OK for gas-free networks)")
            print()
        except Exception as e:
            print(f"⚠️  Could not check balance: {str(e)}\n")
        
        # Check current nonce
        try:
            current_nonce = w3.eth.get_transaction_count(admin_address, 'latest')
            pending_nonce = w3.eth.get_transaction_count(admin_address, 'pending')
            print(f"🔢 Current Nonce (latest): {current_nonce}")
            print(f"🔢 Pending Nonce (includes pending): {pending_nonce}")
            if pending_nonce > current_nonce:
                print(f"   ⏳ {pending_nonce - current_nonce} transaction(s) pending")
            print()
        except Exception as e:
            print(f"⚠️  Could not check nonce: {str(e)}\n")
        
        # Check each transaction
        for parcel in pending_parcels:
            tx_hash = parcel.blockchain_tx_hash
            print(f"{'='*60}")
            print(f"Parcel {parcel.id} - TX: {tx_hash}")
            print(f"{'='*60}")
            
            # Try to get transaction receipt (mined)
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                print(f"✅ Transaction MINED!")
                print(f"   Block Number: {receipt.blockNumber}")
                print(f"   Status: {'Success' if receipt.status == 1 else 'Failed'}")
                if receipt.status == 0:
                    print(f"   ⚠️  Transaction FAILED in block")
                print()
                continue
            except:
                pass  # Not mined yet
            
            # Try to get transaction from mempool
            try:
                tx = w3.eth.get_transaction(tx_hash)
                print(f"⏳ Transaction PENDING (in mempool)")
                print(f"   From: {tx['from']}")
                print(f"   To: {tx['to']}")
                print(f"   Nonce: {tx['nonce']}")
                print(f"   Gas: {tx['gas']}")
                print(f"   Gas Price: {tx.get('gasPrice', 0)}")
                print(f"   Value: {w3.from_wei(tx['value'], 'ether')} ETH")
                
                # Check if nonce is correct
                if tx['nonce'] < current_nonce:
                    print(f"   ❌ PROBLEM: Transaction nonce ({tx['nonce']}) is LOWER than current nonce ({current_nonce})")
                    print(f"   ⚠️  This transaction is STALE and will never be mined!")
                elif tx['nonce'] == current_nonce:
                    print(f"   ✅ Nonce is correct (matches current nonce)")
                else:
                    print(f"   ⏳ Nonce is higher ({tx['nonce']}) - waiting for previous transactions")
                
                # Check gas
                if tx.get('gasPrice', 0) > 0:
                    print(f"   ℹ️  Gas Price: {tx['gasPrice']} wei")
                else:
                    print(f"   ✅ Gas Price: 0 (gas-free network)")
                
                print()
                
            except Exception as e:
                print(f"❌ Transaction NOT found in mempool or blockchain")
                print(f"   Error: {str(e)}")
                print(f"   ⚠️  This transaction may have been dropped or never submitted")
                print()
        
        # Summary and recommendations
        print("=" * 60)
        print("RECOMMENDATIONS")
        print("=" * 60)
        print("\nIf transactions are pending but blocks are mining:")
        print("1. ⏳ Wait a bit longer - blocks are mining every 5 seconds")
        print("2. 🔄 Check if nonce issues exist (see diagnostics above)")
        print("3. 🔄 Try registering a new parcel - it might trigger block mining")
        print("4. 🔄 If transactions are stale (nonce too low), they won't be mined")
        print("   - In this case, the parcels need to be re-registered")
        print("\nIf blocks are NOT mining:")
        print("1. Check your Hardhat node is running: cd blockchain && npx hardhat node")
        print("2. Make sure automining is enabled (Hardhat mines by default)")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    diagnose_pending_transactions()
