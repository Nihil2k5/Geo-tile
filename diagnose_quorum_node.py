#!/usr/bin/env python3
"""
Quorum Node Diagnostic Tool
This script diagnoses Quorum-specific issues with empty blocks.
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

def diagnose_quorum_node():
    """Diagnose Quorum node for empty blocks issue"""
    print("=" * 60)
    print("QUORUM NODE DIAGNOSTIC TOOL")
    print("=" * 60)
    print("\nThis tool checks for Quorum-specific issues.")
    print("Use geth attach for advanced diagnostics (raft.role, etc.)\n")
    
    try:
        w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URI))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        if not w3.is_connected():
            print("❌ Failed to connect to Quorum node")
            return False
        
        print("✅ Connected to Quorum node\n")
        
        admin_address = settings.ADMIN_ADDRESS
        
        # Check 1: Latest Block
        print("=" * 60)
        print("1. CHECKING LATEST BLOCK")
        print("=" * 60)
        try:
            latest_block = w3.eth.get_block('latest')
            latest_block_num = latest_block.number
            tx_count = len(latest_block.transactions) if latest_block.transactions else 0
            
            print(f"📦 Latest Block: {latest_block_num}")
            print(f"📊 Transactions in latest block: {tx_count}")
            
            if tx_count == 0:
                print("   ⚠️  LATEST BLOCK IS EMPTY!")
            else:
                print("   ✅ Latest block contains transactions")
            print()
        except Exception as e:
            print(f"   ❌ Error: {str(e)}\n")
        
        # Check 2: Last 5 Blocks
        print("=" * 60)
        print("2. CHECKING LAST 5 BLOCKS")
        print("=" * 60)
        empty_blocks = 0
        total_txs = 0
        
        for i in range(5):
            try:
                block_num = latest_block_num - i
                block = w3.eth.get_block(block_num, full_transactions=True)
                tx_count = len(block.transactions) if block.transactions else 0
                total_txs += tx_count
                
                if tx_count == 0:
                    empty_blocks += 1
                    print(f"   Block {block_num}: ⚠️  EMPTY")
                else:
                    print(f"   Block {block_num}: ✅ {tx_count} transaction(s)")
            except:
                pass
        
        print(f"\n📊 Summary:")
        print(f"   Empty blocks: {empty_blocks}/5")
        print(f"   Total transactions: {total_txs}")
        print()
        
        # Check 3: Pending Transactions
        print("=" * 60)
        print("3. CHECKING PENDING TRANSACTIONS")
        print("=" * 60)
        try:
            pending_block = w3.eth.get_block('pending', full_transactions=True)
            pending_count = len(pending_block.transactions) if pending_block else 0
            
            print(f"⏳ Pending transactions: {pending_count}")
            
            if pending_count > 0:
                print(f"   ⚠️  PROBLEM: {pending_count} transactions pending but blocks are empty!")
                print(f"   This indicates the miner/validator is not including transactions.")
            
            # Count our transactions
            our_pending = [
                tx for tx in (pending_block.transactions if pending_block else [])
                if hasattr(tx, 'from') and tx['from'].lower() == admin_address.lower()
            ]
            print(f"   Our pending transactions: {len(our_pending)}")
            print()
        except Exception as e:
            print(f"   ⚠️  Could not check pending: {str(e)}\n")
        
        # Check 4: Account Status
        print("=" * 60)
        print("4. CHECKING ACCOUNT STATUS")
        print("=" * 60)
        try:
            current_nonce = w3.eth.get_transaction_count(admin_address, 'latest')
            pending_nonce = w3.eth.get_transaction_count(admin_address, 'pending')
            balance = w3.eth.get_balance(admin_address)
            
            print(f"👤 Address: {admin_address}")
            print(f"💰 Balance: {w3.from_wei(balance, 'ether')} ETH")
            print(f"🔢 Current Nonce: {current_nonce}")
            print(f"🔢 Pending Nonce: {pending_nonce}")
            print(f"⏳ Pending Transactions: {pending_nonce - current_nonce}")
            print()
        except Exception as e:
            print(f"   ⚠️  Error: {str(e)}\n")
        
        # Recommendations
        print("=" * 60)
        print("RECOMMENDATIONS FOR QUORUM")
        print("=" * 60)
        print("\nSince you're using Quorum, empty blocks typically mean:")
        print("\n1. ⚠️  CONSENSUS ISSUE (Most Common):")
        print("   - If using Raft: No 'minter' node designated")
        print("   - If using Istanbul BFT: Validators not configured correctly")
        print("   - Solution: Check your Quorum configuration files")
        print("\n2. ⚠️  MINER/VALIDATOR NOT CONFIGURED:")
        print("   - Node might not be configured to mine/validate blocks")
        print("   - Solution: Check node configuration files")
        print("\n3. ⚠️  TRANSACTION POOL ISSUE:")
        print("   - Transactions not reaching the miner node")
        print("   - Solution: Check transaction pool propagation")
        print("\n📋 NEXT STEPS:")
        print("\n1. Attach to your Quorum node:")
        print("   geth attach http://127.0.0.1:8545")
        print("\n2. Check Raft role (if using Raft):")
        print("   raft.role")
        print("   raft.cluster")
        print("\n3. Check transaction pool:")
        print("   txpool.status")
        print("   txpool.content")
        print("\n4. Check node status:")
        print("   admin.peers")
        print("   eth.mining")
        print("\n5. Check your Quorum configuration files:")
        print("   - genesis.json (network configuration)")
        print("   - Node configuration (miner/validator settings)")
        print("   - Network setup (consensus mechanism)")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    diagnose_quorum_node()
