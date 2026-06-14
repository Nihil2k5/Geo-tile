"""
View for displaying all registered land parcels on a map.
"""
from django.shortcuts import render
from django.db import models
from django.conf import settings
from land_registry.models import Parcel
import json

def registered_lands_map(request):
    """Display a map showing all registered land parcels."""
    # Get ALL parcels that have been registered on blockchain (have blockchain_tx_hash)
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
    
    return render(request, 'map.html', {
        'parcels': json.dumps(parcels_data),  # Serialize to JSON for JavaScript
        'parcel_count': len(parcels_data),
        'mapbox_token': settings.MAPBOX_TOKEN,
        'total_registered': registered_parcels.count(),
        'parcels_without_coords': parcels_without_coords.count()
    })
