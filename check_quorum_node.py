#!/usr/bin/env python
"""
Check Quorum Node Status
This script checks if your Quorum blockchain node is running and mining blocks.
"""

import os
import sys
import django
from web3 import Web3
from web3.middleware import geth_poa_middleware
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from django.conf import settings

def check_quorum_node():
    """Check Quorum node status and block mining"""
    print("=" * 60)
    print("QUORUM NODE STATUS CHECK")
    print("=" * 60)
    
    try:
        # Connect to Hardhat/Quorum node
        w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URI))
        
        # CRITICAL: Add POA middleware for Hardhat/Quorum/private networks
        # Hardhat uses Proof-of-Authority consensus, which requires this middleware
        # to properly decode blocks (the extraData field is larger than 32 bytes)
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        # Check 1: Connection
        print("\n1. CHECKING CONNECTION...")
        if w3.is_connected():
            print("   ✅ Connected to Quorum node")
            print(f"   URL: {settings.WEB3_PROVIDER_URI}")
        else:
            print("   ❌ NOT CONNECTED to Quorum node")
            print(f"   URL: {settings.WEB3_PROVIDER_URI}")
            print("   Please check if your Quorum node is running!")
            return False
        
        # Check 2: Chain ID
        print("\n2. CHECKING NETWORK...")
        try:
            chain_id = w3.eth.chain_id
            print(f"   ✅ Chain ID: {chain_id}")
            print(f"   Network: {'Quorum/Private Network' if chain_id in [1337, 10, 13371337] else 'Unknown'}")
        except Exception as e:
            print(f"   ⚠️  Error getting chain ID: {str(e)}")
        
        # Check 3: Current Block
        print("\n3. CHECKING LATEST BLOCK...")
        try:
            latest_block = w3.eth.get_block('latest')
            block_number = latest_block.number
            block_timestamp = latest_block.timestamp
            block_time = datetime.fromtimestamp(block_timestamp)
            current_time = datetime.now()
            time_diff = current_time - block_time
            
            print(f"   ✅ Latest Block Number: {block_number}")
            print(f"   ✅ Block Timestamp: {block_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   ⏱️  Time Since Last Block: {time_diff.total_seconds():.1f} seconds")
            
            if time_diff.total_seconds() > 300:  # 5 minutes
                print("   ⚠️  WARNING: Last block was more than 5 minutes ago!")
                print("   ⚠️  Your Quorum network may not be mining blocks automatically!")
            elif time_diff.total_seconds() > 60:  # 1 minute
                print("   ⚠️  WARNING: Last block was more than 1 minute ago.")
                print("   ⚠️  Blocks may not be mining automatically.")
            else:
                print("   ✅ Blocks are being mined (last block was recent)")
                
        except Exception as e:
            print(f"   ❌ Error getting latest block: {str(e)}")
        
        # Check 4: Pending Transactions
        print("\n4. CHECKING PENDING TRANSACTIONS...")
        try:
            pending_tx = w3.eth.get_block('pending', full_transactions=True)
            pending_count = len(pending_tx.transactions) if pending_tx else 0
            print(f"   📋 Pending Transactions in Mempool: {pending_count}")
            
            if pending_count > 0:
                print("   ⚠️  You have pending transactions waiting to be mined!")
                print("   ⚠️  Your Quorum network needs to mine blocks to process them.")
                for i, tx in enumerate(pending_tx.transactions[:5]):  # Show first 5
                    print(f"      - Tx {i+1}: {tx.hash.hex()[:20]}...")
        except Exception as e:
            print(f"   ⚠️  Could not check pending transactions: {str(e)}")
        
        # Check 5: Gas Price (for Quorum)
        print("\n5. CHECKING GAS PRICE...")
        try:
            gas_price = w3.eth.gas_price
            if gas_price == 0:
                print("   ✅ Gas Price: 0 (Quorum/Private Network - gas-free)")
            else:
                print(f"   ℹ️  Gas Price: {gas_price} wei ({w3.from_wei(gas_price, 'gwei'):.2f} gwei)")
        except Exception as e:
            print(f"   ⚠️  Error getting gas price: {str(e)}")
        
        # Check 6: Block Mining History (last 5 blocks)
        print("\n6. CHECKING BLOCK MINING HISTORY...")
        try:
            latest_block_num = w3.eth.get_block_number()
            print(f"   📊 Analyzing last 5 blocks:")
            
            block_times = []
            for i in range(5):
                try:
                    block_num = latest_block_num - i
                    if block_num < 0:
                        break
                    block = w3.eth.get_block(block_num)
                    block_time = datetime.fromtimestamp(block.timestamp)
                    block_times.append((block_num, block_time))
                    
                    if i == 0:
                        print(f"      Block {block_num}: {block_time.strftime('%H:%M:%S')} (Latest)")
                    else:
                        prev_block_time = block_times[i-1][1] if i > 0 else datetime.now()
                        time_diff = (prev_block_time - block_time).total_seconds()
                        print(f"      Block {block_num}: {block_time.strftime('%H:%M:%S')} ({time_diff:.1f}s after previous)")
                except:
                    break
            
            if len(block_times) > 1:
                avg_time = sum((block_times[i][1] - block_times[i+1][1]).total_seconds() 
                              for i in range(len(block_times)-1)) / (len(block_times)-1)
                print(f"\n   ⏱️  Average Time Between Blocks: {avg_time:.1f} seconds")
                
                if avg_time > 60:
                    print("   ⚠️  WARNING: Blocks are mining very slowly!")
                    print("   ⚠️  Your Quorum network may need manual mining!")
        except Exception as e:
            print(f"   ⚠️  Error analyzing block history: {str(e)}")
        
        # Check 7: Test Transaction Status
        print("\n7. CHECKING SPECIFIC TRANSACTION...")
        from land_registry.models import Parcel
        pending_parcels = Parcel.objects.filter(
            blockchain_tx_hash__isnull=False
        ).exclude(blockchain_tx_hash='').order_by('-created_at')[:3]
        
        if pending_parcels.exists():
            print(f"   📋 Found {pending_parcels.count()} parcels with transaction hashes:")
            for parcel in pending_parcels:
                tx_hash = parcel.blockchain_tx_hash
                print(f"\n   Parcel {parcel.id} - TX: {tx_hash[:20]}...")
                try:
                    # Try to get transaction receipt
                    receipt = w3.eth.get_transaction_receipt(tx_hash)
                    print(f"      ✅ Transaction MINED in block {receipt.blockNumber}")
                    print(f"      Status: {'Success' if receipt.status == 1 else 'Failed'}")
                except:
                    # Transaction not mined yet
                    try:
                        # Check if transaction exists in mempool
                        tx = w3.eth.get_transaction(tx_hash)
                        print(f"      ⏳ Transaction PENDING (not mined yet)")
                        print(f"      From: {tx['from']}")
                        print(f"      Nonce: {tx['nonce']}")
                    except:
                        print(f"      ❓ Transaction not found in mempool or blockchain")
        else:
            print("   ℹ️  No pending parcels found")
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY & RECOMMENDATIONS")
        print("=" * 60)
        print("\n✅ If your Quorum node is connected and blocks are mining:")
        print("   - Wait a few moments and try verifying again")
        print("   - Transactions will be processed when blocks are mined")
        print("\n⚠️  If blocks are NOT mining automatically:")
        print("   - Check your Quorum node logs")
        print("   - You may need to manually mine blocks")
        print("   - Or configure Quorum to mine blocks automatically")
        print("\n❌ If node is NOT connected:")
        print("   - Start your Quorum node")
        print("   - Check the URL: " + settings.WEB3_PROVIDER_URI)
        print()
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        print(f"\nPlease check:")
        print(f"1. Is your Quorum node running?")
        print(f"2. Is the URL correct? {settings.WEB3_PROVIDER_URI}")
        print(f"3. Can you access the node from this machine?")
        return False

if __name__ == "__main__":
    check_quorum_node()
