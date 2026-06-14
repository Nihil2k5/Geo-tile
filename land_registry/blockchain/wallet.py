from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3
import json
from django.conf import settings
from cryptography.fernet import Fernet
import os

class WalletManager:
    def __init__(self):
        # Initialize Web3 with the provider from settings
        self.w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URI))
        
        # Initialize encryption key
        self.fernet = Fernet(settings.ENCRYPTION_KEY.encode())

    def create_wallet(self):
        """
        Create a new Ethereum wallet
        Returns tuple of (address, encrypted_private_key)
        """
        # Generate a new account
        account = Account.create()
        
        # Get the address and private key
        address = account.address
        private_key = account.key.hex()
        
        # Encrypt the private key
        encrypted_private_key = self.encrypt_private_key(private_key)
        
        return address, encrypted_private_key

    def encrypt_private_key(self, private_key: str) -> str:
        """Encrypt a private key"""
        return self.fernet.encrypt(private_key.encode()).decode()

    def decrypt_private_key(self, encrypted_private_key: str) -> str:
        """Decrypt an encrypted private key"""
        return self.fernet.decrypt(encrypted_private_key.encode()).decode()

    def sign_transaction(self, encrypted_private_key: str, transaction_dict: dict):
        """
        Sign a transaction using a decrypted private key
        """
        private_key = self.decrypt_private_key(encrypted_private_key)
        account = self.w3.eth.account.from_key(private_key)
        signed_txn = account.sign_transaction(transaction_dict)
        return signed_txn

    def verify_wallet_ownership(self, address: str, signature: str, message: str) -> bool:
        """
        Verify that a signature was created by the owner of an address
        """
        message_hash = encode_defunct(text=message)
        recovered_address = Account.recover_message(message_hash, signature=signature)
        return recovered_address.lower() == address.lower()