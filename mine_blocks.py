#!/usr/bin/env python3
"""
Manual Block Mining Script for Hardhat
This script manually mines blocks on Hardhat to process pending transactions.
Hardhat should mine blocks automatically, but this script can be used if needed.
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

def enable_automining():
    """
    Enable automining on Hardhat using evm_setAutomine RPC method.
    This will make Hardhat automatically mine blocks when there are pending transactions.
    """
    try:
        w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URI))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        if not w3.is_connected():
            print("❌ Failed to connect to Hardhat node")
            return False
        
        try:
            # Enable automining
            w3.manager.request_blocking("evm_setAutomine", [True])
            print("✅ Automining enabled - blocks will mine automatically when there are pending transactions")
            return True
        except Exception as e:
            # Method might not be available in all Hardhat versions
            print(f"⚠️  Could not enable automining (method may not be available): {str(e)}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def mine_blocks(num_blocks=1):
    """
    Manually mine blocks on Hardhat using the evm_mine RPC method.
    This will mine blocks that include pending transactions.
    
    Args:
        num_blocks: Number of blocks to mine (default: 1)
    """
    try:
        # Connect to Hardhat node
        w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URI))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        if not w3.is_connected():
            print("❌ Failed to connect to Hardhat node")
            print(f"   URL: {settings.WEB3_PROVIDER_URI}")
            return False
        
        print("✅ Connected to Hardhat node")
        
        # Get current block number
        current_block = w3.eth.block_number
        print(f"📦 Current block number: {current_block}")
        
        # Check pending transactions
        pending_tx_hashes = []
        try:
            pending_block = w3.eth.get_block('pending', full_transactions=True)
            pending_count = len(pending_block.transactions) if pending_block else 0
            if pending_block and pending_block.transactions:
                pending_tx_hashes = [tx.hash.hex() for tx in pending_block.transactions]
            print(f"⏳ Pending transactions: {pending_count}")
            if pending_count > 0:
                print(f"   First 3 TX hashes: {[h[:20] + '...' for h in pending_tx_hashes[:3]]}")
        except Exception as e:
            print(f"⚠️  Could not check pending transactions: {str(e)}")
            pending_count = 0
        
        # Mine blocks
        print(f"\n⛏️  Mining {num_blocks} block(s) (this should include pending transactions)...")
        mined_blocks = []
        for i in range(num_blocks):
            try:
                # Try to use evm_mine to manually mine a block (this includes pending transactions)
                # Note: This method may not be available on all node types
                try:
                    w3.manager.request_blocking("evm_mine", [])
                except Exception as e:
                    # If evm_mine is not available, try alternative methods
                    error_msg = str(e).lower()
                    if 'evm_mine' in error_msg or 'does not exist' in error_msg:
                        raise ValueError(
                            f"evm_mine method not available on this node. "
                            f"Your node may not support manual mining, or blocks are already mining automatically. "
                            f"Blocks are mining every 5 seconds - transactions should be included automatically."
                        )
                    raise
                new_block_num = w3.eth.block_number
                mined_blocks.append(new_block_num)
                print(f"   ✅ Mined block {new_block_num}")
            except Exception as e:
                print(f"   ❌ Error mining block: {str(e)}")
                return False
        
        # Check new block number
        final_block = w3.eth.block_number
        blocks_mined = final_block - current_block
        print(f"\n📦 New block number: {final_block}")
        print(f"📊 Mined {blocks_mined} block(s) successfully")
        
        # Check if pending transactions were processed
        if pending_count > 0:
            try:
                new_pending_block = w3.eth.get_block('pending', full_transactions=True)
                new_pending_count = len(new_pending_block.transactions) if new_pending_block else 0
                processed = pending_count - new_pending_count
                if processed > 0:
                    print(f"✅ Processed {processed} pending transaction(s)")
                else:
                    print(f"⚠️  Still {new_pending_count} pending transaction(s) - may need more blocks")
            except:
                pass
        
        # Check specific parcel transactions
        if pending_tx_hashes:
            print("\n📋 Checking parcel transactions...")
            from land_registry.models import Parcel
            parcels = Parcel.objects.filter(
                blockchain_tx_hash__isnull=False
            ).exclude(blockchain_tx_hash='').order_by('-created_at')[:3]
            
            for parcel in parcels:
                tx_hash = parcel.blockchain_tx_hash
                try:
                    receipt = w3.eth.get_transaction_receipt(tx_hash)
                    print(f"   ✅ Parcel {parcel.id} - TX {tx_hash[:20]}... MINED in block {receipt.blockNumber}")
                except:
                    if tx_hash in pending_tx_hashes:
                        print(f"   ⏳ Parcel {parcel.id} - TX {tx_hash[:20]}... still pending")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Manually mine blocks on Hardhat or enable automining")
    parser.add_argument("-n", "--num-blocks", type=int, default=3, help="Number of blocks to mine (default: 3)")
    parser.add_argument("-a", "--auto", action="store_true", help="Enable automining instead of mining blocks")
    args = parser.parse_args()
    
    print("=" * 60)
    print("HARDHAT BLOCK MINING TOOL")
    print("=" * 60)
    
    if args.auto:
        print("\n🔧 Attempting to enable automining...\n")
        success = enable_automining()
        if success:
            print("\n✅ Automining enabled!")
            print("   Blocks will now mine automatically when there are pending transactions.")
        else:
            print("\n⚠️  Could not enable automining.")
            print("   Try manually mining blocks instead: python3 mine_blocks.py -n 5")
    else:
        print("\n⛏️  Manually mining blocks...")
        print("   NOTE: Hardhat should mine blocks automatically.")
        print("   This script is useful if transactions are stuck pending.\n")
        
        success = mine_blocks(args.num_blocks)
        
        if success:
            print("\n✅ Block mining completed successfully!")
            print("\n💡 TIP: If transactions are still pending, try:")
            print("   - Mining more blocks: python3 mine_blocks.py -n 10")
            print("   - Or enable automining: python3 mine_blocks.py --auto")
        else:
            print("\n❌ Block mining failed!")
            print("\nTroubleshooting:")
            print("1. Make sure Hardhat node is running: cd blockchain && npx hardhat node")
            print("2. Check the connection URL in settings.py")
            print("3. Try restarting the Hardhat node")
