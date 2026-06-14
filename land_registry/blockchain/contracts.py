from web3 import Web3
from web3.exceptions import ContractLogicError, TimeExhausted
from web3.middleware import geth_poa_middleware
from django.conf import settings
from .wallet import WalletManager
import time
import logging

logger = logging.getLogger(__name__)

class ContractManager:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URI))
        # CRITICAL: Add POA middleware for Quorum/private networks
        # Quorum uses Proof-of-Authority consensus, which requires this middleware
        # to properly decode blocks (the extraData field is larger than 32 bytes)
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.wallet_manager = WalletManager()
        
        # Load contract ABIs and addresses
        self.contracts = {}
        for name, address in settings.CONTRACT_ADDRESSES.items():
            if name in settings.CONTRACT_ABIS:
                self.contracts[name] = self.w3.eth.contract(
                    address=address,
                    abi=settings.CONTRACT_ABIS[name]
                )
    
    @property
    def dispute_manager(self):
        """Get the DisputeManager contract"""
        return self.contracts.get('DisputeManager')

    def _get_admin_account(self):
        """Get admin account for contract interactions"""
        return self.w3.eth.account.from_key(settings.ADMIN_PRIVATE_KEY)

    def _get_gas_price(self):
        """
        Get appropriate gas price for the network.
        
        - Quorum/private networks: Use 0 (gas-free transactions)
        - Ethereum/Polygon: Use network gas_price
        
        Returns:
            int: Gas price in wei (0 for Quorum, network price for public chains)
        """
        try:
            network_gas_price = self.w3.eth.gas_price
            
            # If gas price is 0, we're on Quorum/private network - use 0
            if network_gas_price == 0:
                return 0
            
            # For public networks, use network gas price
            return network_gas_price
        except Exception as e:
            logger.warning(f"Error getting gas price, defaulting to 0: {str(e)}")
            # Default to 0 for Quorum/private networks
            return 0

    def _get_pending_nonce(self, address):
        """
        Get nonce including pending transactions in the mempool.
        
        CRITICAL FIX: Using 'pending' parameter ensures we get the correct nonce
        even if previous transactions haven't been mined yet. This prevents
        "replacement transaction underpriced" errors when multiple transactions
        are submitted in quick succession.
        
        Args:
            address: The Ethereum address to get nonce for
            
        Returns:
            int: The nonce including pending transactions
        """
        try:
            # Use 'pending' to include pending transactions in mempool
            # This is the key fix for "replacement transaction underpriced" errors
            nonce = self.w3.eth.get_transaction_count(address, 'pending')
            return nonce
        except Exception as e:
            logger.warning(f"Error getting pending nonce, using 'latest': {str(e)}")
            # Fallback to latest if pending fails
            return self.w3.eth.get_transaction_count(address, 'latest')

    def _build_and_send_transaction(self, contract_function, account):
        """
        Helper method to preflight, build, sign, and send a transaction.
        
        FIXES:
        - Proper nonce handling (includes pending transactions) - FIXES "replacement transaction underpriced"
        - Safe gas price (0 for Quorum, network price for public chains)
        - Works on Quorum and Ethereum-compatible chains
        """
        # Preflight: try a static call to capture revert reasons early
        try:
            contract_function.call({'from': account.address})
        except ContractLogicError as e:
            # Surface smart contract revert reason
            raise ValueError(f"Contract reverted: {str(e)}")
        except Exception:
            # Some state-changing functions may not allow call; proceed to gas estimation
            pass

        # Estimate gas to avoid over/under specifying
        try:
            gas_estimate = contract_function.estimate_gas({'from': account.address})
        except ContractLogicError as e:
            raise ValueError(f"Gas estimation failed due to contract revert: {str(e)}")
        except Exception:
            gas_estimate = 2_000_000

        # Get gas price (0 for Quorum, network price for public chains)
        gas_price = self._get_gas_price()
        
        # CRITICAL FIX: Use 'pending' parameter to get nonce including pending transactions
        # This prevents "replacement transaction underpriced" errors
        nonce = self._get_pending_nonce(account.address)

        # Build transaction
        tx = contract_function.build_transaction({
            'from': account.address,
            'nonce': nonce,  # Uses pending nonce to avoid conflicts
            'gas': gas_estimate,
            'gasPrice': gas_price,  # 0 for Quorum, network price for public chains
            'chainId': self.w3.eth.chain_id
        })

        # Sign and send
        signed_tx = account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        logger.info(f"Transaction sent: {tx_hash.hex()}, nonce: {nonce}")

        # For Quorum networks (gas_price == 0), return immediately after sending
        # Transactions will be mined asynchronously - don't wait for receipt
        # This makes the registration fast and responsive
        if gas_price == 0:
            # Quorum/private network - return immediately
            logger.info(f"Transaction sent to Quorum network: {tx_hash.hex()}. Will be mined asynchronously.")
            return tx_hash.hex()

        # For public networks, wait for receipt
        try:
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(
                tx_hash,
                timeout=30,
                poll_latency=1
            )
            if tx_receipt.status != 1:
                raise ValueError("Transaction failed")
            return tx_hash.hex()
        except TimeExhausted:
            # Transaction sent but not mined within timeout
            # Return the hash anyway - transaction is submitted
            logger.warning(f"Transaction sent but not mined within timeout: {tx_hash.hex()}")
            return tx_hash.hex()

    def _ensure_admin_has_registrar_role(self):
        """Ensure the admin account has the registrar role"""
        user_registry = self.contracts.get('UserRegistry')
        if not user_registry:
            raise ValueError("UserRegistry contract not found")
        
        admin_account = self._get_admin_account()
        registrar_role = user_registry.functions.REGISTRAR_ROLE().call()
        
        # Check if admin already has the role
        if not user_registry.functions.hasRole(registrar_role, admin_account.address).call():
            # Do not attempt to grant at runtime; this requires DEFAULT_ADMIN_ROLE and can revert.
            # Instead, raise a clear error so deployment or setup scripts can grant the role.
            raise PermissionError(
                f"Admin address {admin_account.address} lacks REGISTRAR_ROLE. "
                f"Grant this role during deployment or via an admin account."
            )

    def register_user(self, user_id, wallet_address):
        """Register a new user on the blockchain"""
        contract = self.contracts.get('UserRegistry')
        if not contract:
            raise ValueError("UserRegistry contract not found")
        
        admin_account = self._get_admin_account()
        
        # Build contract function call
        # UserRegistry.sol: registerUser(string userId, address walletAddress)
        contract_function = contract.functions.registerUser(
            str(user_id),
            wallet_address
        )
        
        # Build, sign, and send transaction
        return self._build_and_send_transaction(contract_function, admin_account)

    def register_land(self, parcel_id, owner_address, ipfs_hash, area, metadata_uri=None):
        """Register a new land parcel on the blockchain"""
        contract = self.contracts.get('LandRegistry')
        if not contract:
            raise ValueError("LandRegistry contract not found")
            
        # Ensure admin has registrar role before proceeding
        self._ensure_admin_has_registrar_role()
        
        admin_account = self._get_admin_account()
        
        # Convert area to integer (uint256)
        area_uint256 = int(area)
        
        # Use ipfs_hash as metadata URI if not provided
        if metadata_uri is None:
            metadata_uri = ipfs_hash
        
        # Normalize owner address
        try:
            owner_checksum = self.w3.to_checksum_address(owner_address)
        except Exception:
            raise ValueError("Invalid owner wallet address")

        # Build transaction
        contract_function = contract.functions.registerParcel(
            str(parcel_id),  # Ensure parcel_id is a string
            owner_checksum,
            ipfs_hash,
            area_uint256,
            metadata_uri
        )
        
        # Use the common transaction building and sending method
        return self._build_and_send_transaction(contract_function, admin_account)

    def update_land_survey(self, parcel_id, coordinates, area, ipfs_hash="", metadata_uri=""):
        """Update land survey data on the blockchain"""
        contract = self.contracts.get('LandRegistry')
        if not contract:
            raise ValueError("LandRegistry contract not found")
        
        admin_account = self._get_admin_account()
        
        # Convert area to integer (uint256)
        area_uint256 = int(area)
        
        # Use default values if not provided
        if not ipfs_hash:
            ipfs_hash = f"survey_data_{parcel_id}"
        if not metadata_uri:
            metadata_uri = ipfs_hash
        
        # Build transaction
        contract_function = contract.functions.updateParcelData(
            str(parcel_id),  # Ensure parcel_id is a string
            ipfs_hash,
            area_uint256,
            metadata_uri
        )
        
        # Use the common transaction building and sending method
        return self._build_and_send_transaction(contract_function, admin_account)

    def transfer_land(self, parcel_id, from_address, to_address):
        """Transfer land ownership"""
        contract = self.contracts.get('LandRegistry')
        if not contract:
            raise ValueError("LandRegistry contract not found")
        
        # Get the user's encrypted private key from the database
        from land_registry.models import User
        user = User.objects.get(wallet_address=from_address)
        if not user.encrypted_private_key:
            raise ValueError("User's private key not found")
        
        # Convert to_address to proper Web3 address format
        to_address_checksum = self.w3.to_checksum_address(to_address)
        
        # Build transaction
        tx = contract.functions.transferParcel(
            parcel_id,  # Pass parcel_id as string (parcelId parameter)
            to_address_checksum  # Pass to_address as proper Web3 address (newOwner parameter)
        ).build_transaction({
            'from': from_address,
            'nonce': self.w3.eth.get_transaction_count(from_address),
            'gas': 2000000,
            'gasPrice': 0,  # Set gas price to 0 for gas-free transactions
            'chainId': self.w3.eth.chain_id
        })
        
        # Sign transaction using WalletManager
        signed_tx = self.wallet_manager.sign_transaction(user.encrypted_private_key, tx)
        
        # Send transaction
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if tx_receipt.status != 1:
            raise ValueError("Transaction failed")
            
        return tx_hash.hex()

    def parcel_exists(self, parcel_id):
        """Check if a parcel exists on the blockchain"""
        contract = self.contracts.get('LandRegistry')
        if not contract:
            return False
        
        try:
            # We can use getParcelByParcelId which has the parcelExists modifier
            # or directly check the public mapping if we had access to it easily.
            # getParcelByParcelId will revert if it doesn't exist.
            contract.functions.getParcelByParcelId(str(parcel_id)).call()
            return True
        except Exception:
            return False

    def get_land_details(self, parcel_id):
        """Get land details from the blockchain"""
        contract = self.contracts.get('LandRegistry')
        if not contract:
            raise ValueError("LandRegistry contract not found")
        
        # Get raw data from blockchain
        token_id, owner, ipfs_hash, area, status, registered_at, last_modified = contract.functions.getParcelByParcelId(str(parcel_id)).call()
        
        # Convert status to string
        status_map = {0: 'pending', 1: 'active', 2: 'disputed', 3: 'locked'}
        status_str = status_map.get(status, 'unknown')
        
        # Return formatted data
        return {
            'token_id': token_id,
            'owner': owner,
            'ipfs_hash': ipfs_hash,
            'area': area,
            'status': status_str,
            'registered_at': registered_at,
            'last_modified': last_modified
        }

    def update_parcel_status(self, parcel_id, new_status):
        """Update the status of a land parcel on the blockchain"""
        contract = self.contracts.get('LandRegistry')
        if not contract:
            raise ValueError("LandRegistry contract not found")
        
        admin_account = self._get_admin_account()
        
        # Build transaction
        contract_function = contract.functions.updateParcelStatus(
            str(parcel_id),  # Ensure parcel_id is a string
            int(new_status)  # Convert to integer for enum value
        )
        
        # Use the common transaction building and sending method
        return self._build_and_send_transaction(contract_function, admin_account)

    def get_total_tokens(self):
        """Get the total number of tokens (parcels) from the blockchain"""
        contract = self.contracts.get('LandRegistry')
        if not contract:
            raise ValueError("LandRegistry contract not found")
        
        # Get the current token ID counter
        return contract.functions._tokenIds().call()

    # DisputeManager Methods
    def file_dispute(self, dispute_id, parcel_id, ipfs_hash):
        """File a new dispute on the blockchain"""
        admin_account = self._get_admin_account()
        contract = self.contracts.get('DisputeManager')
        if not contract:
            raise ValueError("DisputeManager contract not found")
        
        contract_function = contract.functions.fileDispute(
            str(dispute_id),  # Convert to string
            str(parcel_id),   # Convert to string
            ipfs_hash
        )
        
        return self._build_and_send_transaction(contract_function, admin_account)

    def update_dispute_status(self, dispute_id, new_status, resolution_ipfs_hash=""):
        """Update dispute status on the blockchain"""
        admin_account = self._get_admin_account()
        contract = self.contracts.get('DisputeManager')
        if not contract:
            raise ValueError("DisputeManager contract not found")
        
        # Status mapping: 0=Filed, 1=UnderReview, 2=Resolved, 3=Rejected
        status_map = {'filed': 0, 'under_review': 1, 'resolved': 2, 'rejected': 3}
        status_value = status_map.get(new_status, 0)
        
        contract_function = contract.functions.updateDisputeStatus(
            str(dispute_id),  # Convert to string
            status_value,
            resolution_ipfs_hash
        )
        
        return self._build_and_send_transaction(contract_function, admin_account)

    def get_dispute_details(self, dispute_id):
        """Get dispute details from the blockchain"""
        contract = self.contracts.get('DisputeManager')
        if not contract:
            raise ValueError("DisputeManager contract not found")
        
        try:
            # Convert dispute_id to string as expected by the smart contract
            result = contract.functions.getDisputeById(str(dispute_id)).call()
            
            # Map status numbers to strings
            status_map = {0: 'filed', 1: 'under_review', 2: 'resolved', 3: 'rejected'}
            
            return {
                'parcel_id': result[0],
                'token_id': result[1],
                'complainant': result[2],
                'ipfs_hash': result[3],
                'status': status_map.get(result[4], 'unknown'),
                'resolution': result[5],
                'filed_at': result[6],
                'last_modified': result[7]
            }
        except Exception as e:
            print(f"Error getting dispute details: {e}")
            return None

    def add_dispute_evidence(self, dispute_id, ipfs_hash):
        """Add evidence to an existing dispute"""
        admin_account = self._get_admin_account()
        contract = self.contracts.get('DisputeManager')
        if not contract:
            raise ValueError("DisputeManager contract not found")
        
        contract_function = contract.functions.addEvidence(
            str(dispute_id),  # Convert to string
            ipfs_hash
        )
        
        return self._build_and_send_transaction(contract_function, admin_account)