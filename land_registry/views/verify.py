from django.shortcuts import render
from django.db import models
from django.conf import settings
from land_registry.blockchain.contracts import ContractManager
from land_registry.models import Parcel, Transaction
import json
import qrcode
from PIL import Image

def verify_land(request):
    # Check if this is the landing page (root URL)
    if request.path == '/' and not request.GET and not request.FILES:
        # Get ALL parcels that have been registered on blockchain (have blockchain_tx_hash)
        # This is the most reliable indicator that a parcel is registered
        registered_parcels = Parcel.objects.filter(
            blockchain_tx_hash__isnull=False
        ).exclude(blockchain_tx_hash='')
        
        print(f"DEBUG: Found {registered_parcels.count()} parcels with blockchain_tx_hash")
        
        # Also check parcels without coordinates to see what we're missing
        parcels_without_coords = registered_parcels.filter(
            models.Q(coordinates__isnull=True) | models.Q(coordinates='')
        )
        print(f"DEBUG: {parcels_without_coords.count()} parcels have no coordinates")
        
        # Filter to only parcels with coordinates
        parcels_with_coords = registered_parcels.exclude(
            models.Q(coordinates__isnull=True) | models.Q(coordinates='')
        )
        print(f"DEBUG: {parcels_with_coords.count()} parcels have coordinates")
        
        # Prepare parcel data for map
        parcels_data = []
        for parcel in parcels_with_coords:
            try:
                # Parse coordinates - could be JSON string or dict
                coords = parcel.coordinates
                print(f"DEBUG: Parcel {parcel.id} - coordinates type: {type(coords)}, value: {coords}")
                
                if isinstance(coords, str):
                    import json
                    try:
                        coords = json.loads(coords)
                    except json.JSONDecodeError:
                        print(f"DEBUG: Parcel {parcel.id} - Failed to parse JSON string: {coords}")
                        continue
                
                # Handle None or empty coordinates
                if coords is None or coords == '' or coords == [] or coords == {}:
                    print(f"DEBUG: Parcel {parcel.id} - Empty coordinates, skipping")
                    continue
                
                # Extract center point for marker (handle different coordinate formats)
                lon = None
                lat = None
                
                if isinstance(coords, dict):
                    # GeoJSON format
                    if coords.get('type') == 'Point':
                        point_coords = coords.get('coordinates', [])
                        if len(point_coords) >= 2:
                            lon, lat = point_coords[0], point_coords[1]
                    elif coords.get('type') == 'Polygon':
                        # Get center of polygon
                        coords_list = coords.get('coordinates', [[[]]])[0]
                        if coords_list and len(coords_list) > 0:
                            lons = [c[0] for c in coords_list if isinstance(c, (list, tuple)) and len(c) >= 2]
                            lats = [c[1] for c in coords_list if isinstance(c, (list, tuple)) and len(c) >= 2]
                            if lons and lats:
                                lon = sum(lons) / len(lons)
                                lat = sum(lats) / len(lats)
                    else:
                        # Try to extract lat/lon from other formats
                        lon = coords.get('lng', coords.get('longitude', coords.get('lon')))
                        lat = coords.get('lat', coords.get('latitude'))
                elif isinstance(coords, list):
                    # Array format [lon, lat] or [[lon, lat], ...] or [[[lon, lat], ...]]
                    if len(coords) >= 2 and isinstance(coords[0], (int, float)):
                        # Simple [lon, lat] format
                        lon, lat = coords[0], coords[1]
                    elif len(coords) > 0:
                        # Nested array format - could be [[lon, lat], ...] or [[[lon, lat], ...]]
                        first_item = coords[0]
                        if isinstance(first_item, list):
                            if len(first_item) >= 2 and isinstance(first_item[0], (int, float)):
                                # [[lon, lat], [lon, lat], ...] - get center
                                lons = [c[0] for c in coords if isinstance(c, list) and len(c) >= 2]
                                lats = [c[1] for c in coords if isinstance(c, list) and len(c) >= 2]
                                if lons and lats:
                                    lon = sum(lons) / len(lons)
                                    lat = sum(lats) / len(lats)
                            elif isinstance(first_item, list) and len(first_item) > 0:
                                # [[[lon, lat], ...], ...] - polygon format, get first ring
                                ring = first_item
                                lons = [c[0] for c in ring if isinstance(c, (list, tuple)) and len(c) >= 2]
                                lats = [c[1] for c in ring if isinstance(c, (list, tuple)) and len(c) >= 2]
                                if lons and lats:
                                    lon = sum(lons) / len(lons)
                                    lat = sum(lats) / len(lats)
                
                # Only add if we have valid coordinates
                if lon is not None and lat is not None and (lon != 0 or lat != 0):
                    print(f"DEBUG: Parcel {parcel.id} - Successfully extracted coordinates: lon={lon}, lat={lat}")
                    parcels_data.append({
                        'id': parcel.id,
                        'location': parcel.location or 'Location not specified',
                        'area': parcel.area,
                        'status': parcel.status,
                        'lon': lon,
                        'lat': lat,
                        'owner': parcel.owner.get_full_name() if parcel.owner else 'Unknown',
                        'coordinates': coords  # Full coordinates for polygon display
                    })
            except Exception as e:
                # Skip parcels with invalid coordinate data
                print(f"Error processing parcel {parcel.id} coordinates: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"DEBUG: Successfully processed {len(parcels_data)} parcels for map")
        
        return render(request, 'landing.html', {
            'parcels': json.dumps(parcels_data),  # Serialize to JSON for JavaScript
            'parcel_count': len(parcels_data),
            'mapbox_token': settings.MAPBOX_TOKEN,
            'debug_parcels': parcels_data  # For debugging in template
        })
    
    search_performed = False
    results = []
    
    # Handle QR code upload or scanned data
    if request.method == 'POST':
        # Check for scanned QR data (from camera)
        if request.POST.get('qr_data'):
            try:
                qr_data = json.loads(request.POST.get('qr_data'))
                
                # Get parcel details from blockchain using token_id from QR code
                if qr_data.get('token_id') and qr_data['token_id'] != 'pending':
                    contract_manager = ContractManager()
                    land_details = contract_manager.get_land_details(qr_data['token_id'])
                    if land_details:
                        # Remove sensitive information
                        land_details.pop('owner', None)
                        land_details.pop('last_updated', None)
                        land_details.pop('registered_at', None)
                        land_details.pop('last_modified', None)
                        # Add location from IPFS hash if available
                        land_details['location'] = land_details.get('ipfs_hash', 'Location not available')
                        # Add transaction hash from QR data
                        land_details['blockchain_tx_hash'] = qr_data.get('blockchain_tx', None)
                        # Add IPFS URLs (local gateway first, then public gateways as fallback)
                        ipfs_hash = land_details.get('ipfs_hash')
                        if ipfs_hash:
                            from land_registry.utils.ipfs import is_valid_ipfs_hash
                            
                            # Clean and validate the hash
                            ipfs_hash = str(ipfs_hash).strip()
                            
                            # Don't try to fix invalid hashes - just validate
                            # Invalid hashes can't be fixed by truncation as they need proper base58 encoding
                            if is_valid_ipfs_hash(ipfs_hash):
                                # Local IPFS gateway (primary)
                                land_details['ipfs_url'] = f"http://127.0.0.1:8080/ipfs/{ipfs_hash}"
                            else:
                                # Invalid hash format - don't create URLs, but keep the hash for display
                                print(f"Warning: Invalid IPFS hash format: {ipfs_hash} (length: {len(ipfs_hash)})")
                                # Don't set ipfs_hash to None - keep it for debugging, just don't create URLs
                                land_details['ipfs_hash_invalid'] = True
                        results.append(land_details)
                        search_performed = True
            except Exception as e:
                print(f"Error processing scanned QR code: {e}")
        
        # Handle QR code file upload
        elif request.FILES.get('qr_code'):
            try:
                qr_image = Image.open(request.FILES['qr_code'])
                qr_decoder = qrcode.QRCode()
                qr_decoder.add_data(qr_image)
                qr_data = json.loads(qr_decoder.get_data())
                
                # Get parcel details from blockchain using token_id from QR code
                if qr_data.get('token_id') and qr_data['token_id'] != 'pending':
                    contract_manager = ContractManager()
                    land_details = contract_manager.get_land_details(qr_data['token_id'])
                    if land_details:
                        # Remove sensitive information
                        land_details.pop('owner', None)
                        land_details.pop('last_updated', None)
                        land_details.pop('registered_at', None)
                        land_details.pop('last_modified', None)
                        # Add location from IPFS hash if available
                        land_details['location'] = land_details.get('ipfs_hash', 'Location not available')
                        # Add transaction hash from QR data
                        land_details['blockchain_tx_hash'] = qr_data.get('blockchain_tx', None)
                        # Add IPFS URLs (local gateway first, then public gateways as fallback)
                        ipfs_hash = land_details.get('ipfs_hash')
                        if ipfs_hash:
                            from land_registry.utils.ipfs import is_valid_ipfs_hash
                            
                            # Clean and validate the hash
                            ipfs_hash = str(ipfs_hash).strip()
                            
                            # Don't try to fix invalid hashes - just validate
                            # Invalid hashes can't be fixed by truncation as they need proper base58 encoding
                            if is_valid_ipfs_hash(ipfs_hash):
                                # Local IPFS gateway (primary)
                                land_details['ipfs_url'] = f"http://127.0.0.1:8080/ipfs/{ipfs_hash}"
                            else:
                                # Invalid hash format - don't create URLs, but keep the hash for display
                                print(f"Warning: Invalid IPFS hash format: {ipfs_hash} (length: {len(ipfs_hash)})")
                                # Don't set ipfs_hash to None - keep it for debugging, just don't create URLs
                                land_details['ipfs_hash_invalid'] = True
                        results.append(land_details)
                        search_performed = True
            except Exception as e:
                print(f"Error processing QR code: {e}")
    
    # Handle transaction hash search
    elif request.method == 'GET' and request.GET.get('search_type') == 'tx_hash' and request.GET.get('search_query'):
        search_performed = True
        tx_hash = request.GET['search_query']
        
        try:
            # Find the parcel associated with this transaction hash
            transaction = Transaction.objects.filter(transaction_hash=tx_hash).first()
            
            # Debug output
            print(f"Searching for transaction hash: {tx_hash}")
            print(f"Transaction found: {transaction}")
            
            if transaction and transaction.parcel:
                print(f"Associated parcel ID: {transaction.parcel.id}")
                contract_manager = ContractManager()
                land_details = contract_manager.get_land_details(str(transaction.parcel.id))
                if land_details:
                    # Remove sensitive information
                    land_details.pop('owner', None)
                    land_details.pop('last_updated', None)
                    land_details.pop('registered_at', None)
                    land_details.pop('last_modified', None)
                    # Add location from IPFS hash if available
                    land_details['location'] = land_details.get('ipfs_hash', 'Location not available')
                    # Add transaction hash
                    land_details['blockchain_tx_hash'] = tx_hash
                    # Add IPFS URLs (local gateway first, then public gateways as fallback)
                    ipfs_hash = land_details.get('ipfs_hash')
                    if ipfs_hash:
                        from land_registry.utils.ipfs import is_valid_ipfs_hash
                        
                        # Clean and validate the hash
                        ipfs_hash = str(ipfs_hash).strip()
                        
                        # Only create URLs for valid hashes
                        if is_valid_ipfs_hash(ipfs_hash):
                            # Local IPFS gateway (primary)
                            land_details['ipfs_url'] = f"http://127.0.0.1:8080/ipfs/{ipfs_hash}"
                        else:
                            # Invalid hash format - don't create URLs
                            print(f"Warning: Invalid IPFS hash format: {ipfs_hash} (length: {len(ipfs_hash)})")
                            land_details['ipfs_hash_invalid'] = True
                    results.append(land_details)
            else:
                # Try direct blockchain lookup if no transaction found in database
                print(f"No transaction found in database, trying direct blockchain lookup")
                
                # Check if there are any transactions in the database
                transaction_count = Transaction.objects.count()
                print(f"Total transactions in database: {transaction_count}")
                
                # Check if there are any parcels with this transaction hash
                parcel = Parcel.objects.filter(blockchain_tx_hash=tx_hash).first()
                if parcel:
                    print(f"Found parcel with transaction hash: {parcel.id}")
                    contract_manager = ContractManager()
                    land_details = contract_manager.get_land_details(str(parcel.id))
                    if land_details:
                        # Remove sensitive information
                        land_details.pop('owner', None)
                        land_details.pop('last_updated', None)
                        land_details.pop('registered_at', None)
                        land_details.pop('last_modified', None)
                        # Add location from IPFS hash if available
                        land_details['location'] = land_details.get('ipfs_hash', 'Location not available')
                        # Add transaction hash
                        land_details['blockchain_tx_hash'] = tx_hash
                        # Add IPFS URLs (local gateway first, then public gateways as fallback)
                        ipfs_hash = land_details.get('ipfs_hash')
                        if ipfs_hash:
                            from land_registry.utils.ipfs import is_valid_ipfs_hash
                            
                            # Clean and validate the hash
                            ipfs_hash = str(ipfs_hash).strip()
                            
                            # Don't try to fix invalid hashes - just validate
                            # Invalid hashes can't be fixed by truncation as they need proper base58 encoding
                            if is_valid_ipfs_hash(ipfs_hash):
                                # Local IPFS gateway (primary)
                                land_details['ipfs_url'] = f"http://127.0.0.1:8080/ipfs/{ipfs_hash}"
                            else:
                                # Invalid hash format - don't create URLs, but keep the hash for display
                                print(f"Warning: Invalid IPFS hash format: {ipfs_hash} (length: {len(ipfs_hash)})")
                                # Don't set ipfs_hash to None - keep it for debugging, just don't create URLs
                                land_details['ipfs_hash_invalid'] = True
                        results.append(land_details)
                else:
                    # This is a placeholder for direct blockchain lookup
                    # You would need to implement this functionality in ContractManager
                    print(f"Direct blockchain lookup not implemented yet")
        except Exception as e:
            print(f"Error during transaction search: {e}")
    
    return render(request, 'verify.html', {
        'results': results,
        'search_performed': search_performed
    })