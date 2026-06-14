#!/usr/bin/env python
import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from land_registry.utils.ipfs import upload_to_ipfs

def test_ipfs_hash_generation():
    """Test that IPFS hash generation works correctly"""
    
    # Test data similar to what would be generated in dispute filing
    dispute_data = {
        'dispute_id': '123',
        'parcel_id': 'PARCEL_001',
        'complainant': 'testuser',
        'description': 'Test dispute description',
        'filed_at': '2025-11-01T10:00:00',
        'has_evidence_file': False
    }
    
    print("Testing IPFS hash generation...")
    print(f"Input data: {dispute_data}")
    
    # Generate IPFS hash
    ipfs_hash = upload_to_ipfs(dispute_data)
    
    print(f"Generated IPFS hash: {ipfs_hash}")
    print(f"Hash length: {len(ipfs_hash)}")
    print(f"Hash starts with 'Qm': {ipfs_hash.startswith('Qm')}")
    
    # Test with evidence file metadata
    dispute_data_with_evidence = dispute_data.copy()
    dispute_data_with_evidence.update({
        'has_evidence_file': True,
        'evidence_filename': 'test_document.pdf',
        'evidence_size': 1024,
        'evidence_content_type': 'application/pdf'
    })
    
    ipfs_hash_with_evidence = upload_to_ipfs(dispute_data_with_evidence)
    
    print(f"\nWith evidence file:")
    print(f"Generated IPFS hash: {ipfs_hash_with_evidence}")
    print(f"Different from first hash: {ipfs_hash != ipfs_hash_with_evidence}")
    
    # Verify hash is not empty (this was the original issue)
    assert len(ipfs_hash) > 0, "IPFS hash should not be empty"
    assert ipfs_hash.startswith('Qm'), "IPFS hash should start with 'Qm'"
    
    print("\n✅ IPFS hash generation test passed!")
    return ipfs_hash

if __name__ == "__main__":
    test_ipfs_hash_generation()