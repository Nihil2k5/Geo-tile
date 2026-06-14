#!/usr/bin/env python3
"""
Check Nonce Gap
This script checks for nonce gaps in pending transactions and finds missing transactions.
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

def check_nonce_gap():
    """Check for nonce gaps in pending transactions"""
    print("=" * 60)
    print("NONCE GAP ANALYSIS")
    print("=" * 60)
    
    try:
        w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URI))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        if not w3.is_connected():
            print("❌ Failed to connect to node")
            return False
        
        print("✅ Connected to node\n")
        
        admin_address = settings.ADMIN_ADDRESS
        current_nonce = w3.eth.get_transaction_count(admin_address, 'latest')
        pending_nonce = w3.eth.get_transaction_count(admin_address, 'pending')
        
        print(f"👤 Admin Address: {admin_address}")
        print(f"🔢 Current Nonce (latest): {current_nonce}")
        print(f"🔢 Pending Nonce (includes pending): {pending_nonce}")
        print(f"📊 Gap: {pending_nonce - current_nonce} transactions pending\n")
        
        # Check for transactions in the gap
        print("=" * 60)
        print("CHECKING FOR TRANSACTIONS IN NONCE GAP")
        print("=" * 60)
        print(f"\n🔍 Checking nonces {current_nonce} to {pending_nonce}...\n")
        
        found_transactions = []
        missing_nonces = []
        
        # Get pending block to see all pending transactions
        try:
            pending_block = w3.eth.get_block('pending', full_transactions=True)
            pending_txs = pending_block.transactions if pending_block else []
            
            # Filter transactions from our address
            our_pending_txs = [
                tx for tx in pending_txs 
                if tx['from'].lower() == admin_address.lower()
            ]
            
            # Get nonces of pending transactions
            pending_nonces = sorted([tx['nonce'] for tx in our_pending_txs])
            
            print(f"📋 Found {len(our_pending_txs)} pending transactions from our address:")
            for tx in sorted(our_pending_txs, key=lambda x: x['nonce']):
                print(f"   Nonce {tx['nonce']}: {tx['hash'].hex()[:20]}...")
            
            print(f"\n🔍 Checking for missing nonces between {current_nonce} and {pending_nonces[-1] if pending_nonces else current_nonce}...")
            
            # Check each nonce in the range
            for nonce in range(current_nonce, pending_nonces[-1] + 1 if pending_nonces else current_nonce + 1):
                if nonce in pending_nonces:
                    found_transactions.append(nonce)
                    # Try to get transaction receipt (might be mined)
                    for tx in our_pending_txs:
                        if tx['nonce'] == nonce:
                            try:
                                receipt = w3.eth.get_transaction_receipt(tx['hash'])
                                print(f"   ✅ Nonce {nonce}: MINED in block {receipt.blockNumber}")
                            except:
                                print(f"   ⏳ Nonce {nonce}: PENDING - {tx['hash'].hex()[:20]}...")
                            break
                else:
                    missing_nonces.append(nonce)
                    print(f"   ❌ Nonce {nonce}: MISSING (gap!)")
            
        except Exception as e:
            print(f"⚠️  Error checking pending transactions: {str(e)}")
            missing_nonces = list(range(current_nonce + 1, pending_nonce))
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        
        if missing_nonces:
            print(f"\n❌ PROBLEM: Missing nonces {missing_nonces}")
            print(f"\n⚠️  Transactions with higher nonces ({pending_nonces[0] if pending_nonces else 'N/A'}+) cannot be mined")
            print(f"   until the missing nonces are processed.")
            print(f"\n💡 SOLUTIONS:")
            print(f"   1. Check if transactions with nonces {missing_nonces} exist elsewhere")
            print(f"   2. Send a dummy transaction with nonce {missing_nonces[0]} to fill the gap")
            print(f"   3. Or wait for the missing transactions to appear (unlikely)")
            print(f"   4. If the missing transactions were dropped, re-register parcels")
        else:
            print(f"\n✅ No nonce gaps found!")
            print(f"   All nonces from {current_nonce} to {pending_nonce} are present.")
            print(f"   Transactions should be mined in order.")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    check_nonce_gap()
