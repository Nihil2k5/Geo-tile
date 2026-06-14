#!/usr/bin/env python3

import os
import sys
import django
from web3 import Web3

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from land_registry.models import User

def fund_user_accounts():
    """Fund user accounts with ETH from Hardhat pre-funded accounts"""
    
    # Connect to local blockchain
    w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
    
    if not w3.is_connected():
        print("❌ Failed to connect to blockchain")
        return False
    
    print("✅ Connected to blockchain")
    
    # Get pre-funded accounts from Hardhat
    hardhat_accounts = w3.eth.accounts
    funder_account = hardhat_accounts[0]  # Use first account as funder
    
    print(f"💰 Funder account: {funder_account}")
    funder_balance = w3.eth.get_balance(funder_account)
    print(f"💰 Funder balance: {w3.from_wei(funder_balance, 'ether')} ETH")
    
    # Get all users that need funding
    users = User.objects.filter(wallet_address__isnull=False).exclude(wallet_address='')
    
    print(f"\n📋 Found {users.count()} users to fund:")
    
    for user in users:
        try:
            # Check current balance
            current_balance = w3.eth.get_balance(user.wallet_address)
            current_balance_eth = w3.from_wei(current_balance, 'ether')
            
            print(f"\n👤 User: {user.username}")
            print(f"   Wallet: {user.wallet_address}")
            print(f"   Current balance: {current_balance_eth} ETH")
            
            # Fund with 1 ETH if balance is less than 0.1 ETH
            if current_balance_eth < 0.1:
                amount_to_send = w3.to_wei(1, 'ether')  # Send 1 ETH
                
                # Create transaction
                tx = {
                    'from': funder_account,
                    'to': user.wallet_address,
                    'value': amount_to_send,
                    'gas': 21000,
                    'gasPrice': 0,  # Gas-free transaction
                    'nonce': w3.eth.get_transaction_count(funder_account)
                }
                
                # Send transaction
                tx_hash = w3.eth.send_transaction(tx)
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
                
                if receipt.status == 1:
                    new_balance = w3.eth.get_balance(user.wallet_address)
                    new_balance_eth = w3.from_wei(new_balance, 'ether')
                    print(f"   ✅ Funded successfully! New balance: {new_balance_eth} ETH")
                    print(f"   📄 Transaction hash: {tx_hash.hex()}")
                else:
                    print(f"   ❌ Transaction failed")
            else:
                print(f"   ✅ Already has sufficient balance")
                
        except Exception as e:
            print(f"   ❌ Error funding user {user.username}: {str(e)}")
    
    print(f"\n🎉 Funding process completed!")
    return True

if __name__ == "__main__":
    fund_user_accounts()