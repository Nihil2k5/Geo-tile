from django.conf import settings
from land_registry.blockchain.contracts import ContractManager

def debug_contracts():
    print("=== Contract Loading Debug ===")
    
    print(f"CONTRACT_ADDRESSES: {settings.CONTRACT_ADDRESSES}")
    print(f"CONTRACT_ABIS keys: {list(settings.CONTRACT_ABIS.keys()) if settings.CONTRACT_ABIS else 'None'}")
    
    try:
        contract_manager = ContractManager()
        print(f"Loaded contracts: {list(contract_manager.contracts.keys())}")
        
        for name, contract in contract_manager.contracts.items():
            print(f"  - {name}: {contract.address if contract else 'None'}")
        
        dispute_manager = contract_manager.dispute_manager
        print(f"DisputeManager accessible: {dispute_manager is not None}")
        
        if dispute_manager:
            print(f"DisputeManager address: {dispute_manager.address}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

debug_contracts()