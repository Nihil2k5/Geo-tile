#!/usr/bin/env python3
"""
Verification script to confirm gas-free transactions are working properly.
This script checks transaction receipts to verify gas usage and costs.
"""

import os
import sys
import django
from web3 import Web3

# Add the project root to the Python path
sys.path.append('/Users/nihilmh/Documents/untitled folder/untitled folder 3')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from land_registry.models import User, Parcel
from land_registry.blockchain.contracts import ContractManager

def verify_gas_free_transactions():
    """Verify that transactions are indeed gas-free by checking recent transaction receipts."""
    print("🔍 Verifying gas-free transactions...")
    
    try:
        # Initialize Web3 connection
        w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))
        
        if not w3.is_connected():
            print("❌ Failed to connect to blockchain")
            return False
            
        print(f"✅ Connected to blockchain")
        
        # Get the latest block
        latest_block = w3.eth.get_block('latest')
        print(f"📦 Latest block: {latest_block.number}")
        
        # Check recent transactions for gas usage
        recent_transactions = []
        for i in range(max(0, latest_block.number - 10), latest_block.number + 1):
            try:
                block = w3.eth.get_block(i, full_transactions=True)
                for tx in block.transactions:
                    if tx.to:  # Skip contract creation transactions
                        recent_transactions.append(tx.hash.hex())
            except Exception as e:
                continue
        
        print(f"🔍 Found {len(recent_transactions)} recent transactions")
        
        # Analyze the most recent transactions
        gas_free_count = 0
        total_analyzed = 0
        
        for tx_hash in recent_transactions[-5:]:  # Check last 5 transactions
            try:
                tx_receipt = w3.eth.get_transaction_receipt(tx_hash)
                tx_details = w3.eth.get_transaction(tx_hash)
                
                gas_used = tx_receipt.gasUsed
                gas_price = tx_details.gasPrice
                gas_cost = gas_used * gas_price
                
                print(f"\n📋 Transaction: {tx_hash}")
                print(f"   Gas Used: {gas_used:,}")
                print(f"   Gas Price: {gas_price} wei")
                print(f"   Gas Cost: {gas_cost} wei ({Web3.from_wei(gas_cost, 'ether')} ETH)")
                
                if gas_price == 0:
                    gas_free_count += 1
                    print(f"   ✅ Gas-free transaction!")
                else:
                    print(f"   💰 Transaction with gas cost")
                
                total_analyzed += 1
                
            except Exception as e:
                print(f"   ❌ Error analyzing transaction {tx_hash}: {e}")
        
        print(f"\n📊 Summary:")
        print(f"   Total transactions analyzed: {total_analyzed}")
        print(f"   Gas-free transactions: {gas_free_count}")
        print(f"   Gas-free percentage: {(gas_free_count/total_analyzed*100) if total_analyzed > 0 else 0:.1f}%")
        
        # Test a new gas-free transaction
        print(f"\n🧪 Testing new gas-free transaction...")
        
        user1 = User.objects.get(username='citi')
        user2 = User.objects.get(username='nihil')
        
        # Get user balances before transaction
        balance1_before = w3.eth.get_balance(user1.wallet_address)
        balance2_before = w3.eth.get_balance(user2.wallet_address)
        
        print(f"💰 Balances before transaction:")
        print(f"   {user1.username}: {Web3.from_wei(balance1_before, 'ether')} ETH")
        print(f"   {user2.username}: {Web3.from_wei(balance2_before, 'ether')} ETH")
        
        # Find an active parcel owned by user1
        parcel = Parcel.objects.filter(owner=user1, status='active').first()
        
        if parcel:
            contract_manager = ContractManager()
            
            # Perform a transfer back to original owner (for testing)
            tx_hash = contract_manager.transfer_land(
                str(parcel.id),
                user2.wallet_address,  # From user2
                user1.wallet_address   # Back to user1
            )
            
            print(f"✅ Test transaction completed: {tx_hash}")
            
            # Get transaction receipt
            tx_receipt = w3.eth.get_transaction_receipt(tx_hash)
            tx_details = w3.eth.get_transaction(tx_hash)
            
            # Get user balances after transaction
            balance1_after = w3.eth.get_balance(user1.wallet_address)
            balance2_after = w3.eth.get_balance(user2.wallet_address)
            
            print(f"\n💰 Balances after transaction:")
            print(f"   {user1.username}: {Web3.from_wei(balance1_after, 'ether')} ETH")
            print(f"   {user2.username}: {Web3.from_wei(balance2_after, 'ether')} ETH")
            
            print(f"\n📋 Transaction Analysis:")
            print(f"   Gas Used: {tx_receipt.gasUsed:,}")
            print(f"   Gas Price: {tx_details.gasPrice} wei")
            print(f"   Gas Cost: {tx_receipt.gasUsed * tx_details.gasPrice} wei")
            
            # Check if balances changed (they shouldn't for gas-free)
            balance1_change = balance1_after - balance1_before
            balance2_change = balance2_after - balance2_before
            
            print(f"\n💸 Balance Changes:")
            if balance1_change >= 0:
                print(f"   {user1.username}: +{Web3.from_wei(balance1_change, 'ether')} ETH")
            else:
                print(f"   {user1.username}: -{Web3.from_wei(abs(balance1_change), 'ether')} ETH")
            
            if balance2_change >= 0:
                print(f"   {user2.username}: +{Web3.from_wei(balance2_change, 'ether')} ETH")
            else:
                print(f"   {user2.username}: -{Web3.from_wei(abs(balance2_change), 'ether')} ETH")
            
            if tx_details.gasPrice == 0:
                print(f"\n🎉 SUCCESS: Transaction is gas-free!")
                return True
            else:
                print(f"\n⚠️  WARNING: Transaction has gas cost!")
                return False
        else:
            print(f"❌ No active parcel found for testing")
            return False
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = verify_gas_free_transactions()
    if success:
        print(f"\n✅ Gas-free verification completed successfully!")
    else:
        print(f"\n❌ Gas-free verification failed!")