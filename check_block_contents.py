#!/usr/bin/env python3
"""
Check Block Contents
This script checks if blocks are actually including transactions or if they're empty.
"""

import os
import sys
import django
from web3 import Web3
from web3.middleware import geth_poa_middleware
from datetime import datetime

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from django.conf import settings

def check_block_contents():
    """Check if blocks are including transactions"""
    print("=" * 60)
    print("BLOCK CONTENTS ANALYSIS")
    print("=" * 60)
    
    try:
        w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URI))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        if not w3.is_connected():
            print("❌ Failed to connect to node")
            return False
        
        print("✅ Connected to node\n")
        
        admin_address = settings.ADMIN_ADDRESS
        
        # Get latest block
        latest_block_num = w3.eth.block_number
        print(f"📦 Latest Block Number: {latest_block_num}\n")
        
        # Check last 5 blocks
        print("=" * 60)
        print("LAST 5 BLOCKS ANALYSIS")
        print("=" * 60)
        print()
        
        blocks_with_txs = 0
        total_txs = 0
        our_txs_mined = 0
        
        for i in range(5):
            try:
                block_num = latest_block_num - i
                block = w3.eth.get_block(block_num, full_transactions=True)
                
                tx_count = len(block.transactions)
                block_time = datetime.fromtimestamp(block.timestamp)
                
                # Count our transactions
                our_txs = [
                    tx for tx in block.transactions
                    if hasattr(tx, 'from') and tx['from'].lower() == admin_address.lower()
                ]
                
                if tx_count > 0:
                    blocks_with_txs += 1
                    total_txs += tx_count
                    our_txs_mined += len(our_txs)
                    
                    print(f"Block {block_num} ({block_time.strftime('%H:%M:%S')}):")
                    print(f"   📊 Total Transactions: {tx_count}")
                    print(f"   👤 Our Transactions: {len(our_txs)}")
                    if our_txs:
                        for tx in our_txs:
                            try:
                                receipt = w3.eth.get_transaction_receipt(tx['hash'])
                                status = "✅ SUCCESS" if receipt.status == 1 else "❌ FAILED"
                                print(f"      {status} - Nonce {tx['nonce']}: {tx['hash'].hex()[:20]}...")
                            except:
                                print(f"      ⏳ Nonce {tx['nonce']}: {tx['hash'].hex()[:20]}...")
                    print()
                else:
                    print(f"Block {block_num} ({block_time.strftime('%H:%M:%S')}): ⚠️  EMPTY (no transactions)")
                    print()
                    
            except Exception as e:
                print(f"⚠️  Error reading block {block_num}: {str(e)}\n")
        
        # Summary
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"\n📊 Last 5 blocks:")
        print(f"   Blocks with transactions: {blocks_with_txs}/5")
        print(f"   Total transactions mined: {total_txs}")
        print(f"   Our transactions mined: {our_txs_mined}")
        
        if blocks_with_txs == 0:
            print(f"\n⚠️  PROBLEM: All blocks are EMPTY!")
            print(f"   Blocks are mining but not including ANY transactions.")
            print(f"   This suggests the node is configured to mine empty blocks.")
        elif our_txs_mined == 0:
            print(f"\n⚠️  PROBLEM: No transactions from our address were mined!")
            print(f"   Blocks are including transactions but not ours.")
            print(f"   This suggests our transactions might be invalid or rejected.")
        else:
            print(f"\n✅ Transactions are being mined!")
            print(f"   {our_txs_mined} of our transactions were mined in the last 5 blocks.")
        
        # Check pending transactions again
        print(f"\n📋 Current Status:")
        current_nonce = w3.eth.get_transaction_count(admin_address, 'latest')
        pending_nonce = w3.eth.get_transaction_count(admin_address, 'pending')
        print(f"   Current Nonce (latest): {current_nonce}")
        print(f"   Pending Nonce: {pending_nonce}")
        print(f"   Pending Transactions: {pending_nonce - current_nonce}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    check_block_contents()
