#!/usr/bin/env python
"""
Test script to verify IPFS connection and upload functionality.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from django.conf import settings
from land_registry.utils.ipfs import upload_to_ipfs, is_valid_ipfs_hash

def test_ipfs_connection():
    """Test IPFS connection and upload."""
    print("=" * 60)
    print("Testing IPFS Connection")
    print("=" * 60)
    
    print(f"\nIPFS Configuration:")
    print(f"  Host: {settings.IPFS_HOST}")
    print(f"  Port: {settings.IPFS_PORT}")
    print(f"  Gateway: http://127.0.0.1:8080")
    
    # Test data
    test_data = {
        'test': True,
        'message': 'IPFS connection test',
        'timestamp': '2026-01-11T20:42:05'
    }
    
    print(f"\n1. Testing IPFS upload...")
    try:
        ipfs_hash = upload_to_ipfs(test_data)
        print(f"   ✓ Upload successful!")
        print(f"   IPFS Hash: {ipfs_hash}")
        print(f"   Hash Length: {len(ipfs_hash)}")
        print(f"   Hash Valid: {is_valid_ipfs_hash(ipfs_hash)}")
        
        print(f"\n2. Testing IPFS URLs...")
        print(f"   Local Gateway: http://127.0.0.1:8080/ipfs/{ipfs_hash}")
        print(f"   Public Gateway: https://ipfs.io/ipfs/{ipfs_hash}")
        print(f"   Pinata Gateway: https://gateway.pinata.cloud/ipfs/{ipfs_hash}")
        
        print(f"\n3. Testing hash validation...")
        # Test invalid hash
        invalid_hash = "Qmf20a32b05f9d483a6cda61ae57e45e5e988a488449d8"
        print(f"   Invalid hash '{invalid_hash}': {is_valid_ipfs_hash(invalid_hash)}")
        print(f"   Valid hash '{ipfs_hash}': {is_valid_ipfs_hash(ipfs_hash)}")
        
        print(f"\n✅ IPFS connection test PASSED!")
        print(f"\nYou can now register parcels and they will be stored in IPFS.")
        return True
        
    except Exception as e:
        print(f"\n❌ IPFS connection test FAILED!")
        print(f"   Error: {str(e)}")
        print(f"\nPlease ensure:")
        print(f"   1. IPFS daemon is running: ipfs daemon")
        print(f"   2. IPFS API is accessible at {settings.IPFS_HOST}:{settings.IPFS_PORT}")
        print(f"   3. ipfshttpclient is installed: pip install ipfshttpclient")
        return False

if __name__ == "__main__":
    test_ipfs_connection()
