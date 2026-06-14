import json
import hashlib
import os
from django.conf import settings
from io import BytesIO
import requests

def upload_to_ipfs(data, content_type='json'):
    """
    Uploads data to IPFS and returns the IPFS hash (CID).
    Uses local IPFS node HTTP API directly to avoid version compatibility issues.
    
    Args:
        data: Can be:
            - dict/list: Will be converted to JSON
            - str: Will be uploaded as-is
            - bytes: Will be uploaded as binary data
        content_type: 'json', 'html', 'text', or 'binary'
    """
    # Convert 'localhost' to '127.0.0.1'
    ipfs_host = settings.IPFS_HOST
    if ipfs_host == 'localhost':
        ipfs_host = '127.0.0.1'
    
    ipfs_api_url = f"http://{ipfs_host}:{settings.IPFS_PORT}/api/v0/add"
    
    try:
        # Prepare data based on type
        if isinstance(data, (dict, list)):
            data_bytes = json.dumps(data, sort_keys=True, ensure_ascii=False).encode('utf-8')
        elif isinstance(data, str):
            data_bytes = data.encode('utf-8')
        elif isinstance(data, bytes):
            data_bytes = data
        else:
            data_bytes = str(data).encode('utf-8')
        
        # Upload to IPFS using HTTP API
        files = {
            'file': ('data', data_bytes)
        }
        
        response = requests.post(ipfs_api_url, files=files, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        # Extract hash from response
        if isinstance(result, dict):
            ipfs_hash = result.get('Hash', result.get('Name'))
        elif isinstance(result, list) and len(result) > 0:
            ipfs_hash = result[0].get('Hash', result[0].get('Name'))
        else:
            ipfs_hash = str(result)
        
        # Validate the hash before returning
        if is_valid_ipfs_hash(ipfs_hash):
            return ipfs_hash
        else:
            raise ValueError(f"IPFS returned invalid hash format: {ipfs_hash}")
            
    except requests.exceptions.RequestException as e:
        print(f"IPFS API connection failed: {e}")
        raise Exception(f"Failed to upload to IPFS: {str(e)}. Please ensure your IPFS node is running at {ipfs_host}:{settings.IPFS_PORT}")
    except Exception as e:
        print(f"IPFS upload error: {e}")
        raise Exception(f"Failed to upload to IPFS: {str(e)}")


def upload_file_to_ipfs(file_path):
    """
    Uploads a file to IPFS and returns the IPFS hash.
    Uses local IPFS node HTTP API directly to avoid version compatibility issues.
    
    Args:
        file_path: Path to the file to upload
    
    Returns:
        str: Valid IPFS CID (hash)
    
    Raises:
        Exception: If IPFS upload fails
    """
    # Convert 'localhost' to '127.0.0.1'
    ipfs_host = settings.IPFS_HOST
    if ipfs_host == 'localhost':
        ipfs_host = '127.0.0.1'
    
    ipfs_api_url = f"http://{ipfs_host}:{settings.IPFS_PORT}/api/v0/add"
    
    try:
        # Upload file to IPFS using HTTP API
        with open(file_path, 'rb') as f:
            files = {
                'file': (os.path.basename(file_path), f)
            }
            
            response = requests.post(ipfs_api_url, files=files, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            
            # Extract hash from result
            if isinstance(result, dict):
                ipfs_hash = result.get('Hash', result.get('Name'))
            elif isinstance(result, list) and len(result) > 0:
                ipfs_hash = result[0].get('Hash', result[0].get('Name'))
            else:
                ipfs_hash = str(result)
            
            # Validate the hash before returning
            if is_valid_ipfs_hash(ipfs_hash):
                return ipfs_hash
            else:
                raise ValueError(
                    f"IPFS returned invalid hash format: {ipfs_hash}. "
                    f"Please check your IPFS node."
                )
    except FileNotFoundError:
        raise Exception(f"File not found: {file_path}")
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if 'connection' in error_msg.lower() or 'refused' in error_msg.lower():
            raise Exception(
                f"Failed to connect to IPFS node at {ipfs_host}:{settings.IPFS_PORT}. "
                f"Please ensure your IPFS daemon is running. Error: {error_msg}"
            )
        else:
            raise Exception(f"Failed to upload file to IPFS: {error_msg}")
    except Exception as e:
        raise Exception(f"Failed to upload file to IPFS: {str(e)}")


def is_valid_ipfs_hash(ipfs_hash):
    """
    Validates if an IPFS hash is in a valid format.
    CIDv0: Qm + 44 base58 chars = 46 chars (exactly)
    CIDv1: Starts with different prefixes (bafy, bafk, etc.), variable length but typically 59+ chars
    
    Base58 alphabet: 123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz
    Note: '0', 'O', 'I', 'l' are NOT in base58 to avoid confusion
    """
    if not ipfs_hash or not isinstance(ipfs_hash, str):
        return False
    
    # Remove any whitespace
    ipfs_hash = ipfs_hash.strip()
    
    # Base58 alphabet (excluding 0, O, I, l)
    base58_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
    
    # CIDv0 format (most common) - must be exactly 46 characters
    if ipfs_hash.startswith('Qm') and len(ipfs_hash) == 46:
        # Check if all characters after "Qm" are valid base58 characters
        # Invalid characters like '0', 'O', 'I', 'l', or hex-only chars indicate fake hash
        hash_body = ipfs_hash[2:]  # Everything after "Qm"
        
        # Check for invalid characters that indicate hex encoding
        invalid_chars = set('0OIl')  # These are NOT in base58
        if any(char in invalid_chars for char in hash_body):
            return False
        
        # Check if all characters are valid base58
        if all(char in base58_chars for char in hash_body):
            return True
        else:
            # Contains invalid characters (likely hex)
            return False
    
    # CIDv1 formats (bafy..., bafk..., etc.) - typically 59+ characters
    if ipfs_hash.startswith('baf') and len(ipfs_hash) >= 59:
        # For CIDv1, check base58 characters
        if all(char in base58_chars for char in ipfs_hash):
            return True
    
    # Other CIDv1 prefixes
    if ipfs_hash.startswith('ba') and len(ipfs_hash) >= 46:
        if all(char in base58_chars for char in ipfs_hash):
            return True
    
    return False