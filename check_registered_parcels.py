#!/usr/bin/env python
"""
Diagnostic script to check registered parcels and their coordinates.
"""
import os
import sys
import django
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from django.db import models
from land_registry.models import Parcel

def check_registered_parcels():
    """Check all registered parcels and their coordinates."""
    print("=" * 60)
    print("Registered Parcels Diagnostic")
    print("=" * 60)
    
    # Get all parcels with blockchain_tx_hash
    registered_parcels = Parcel.objects.filter(
        blockchain_tx_hash__isnull=False
    ).exclude(blockchain_tx_hash='')
    
    print(f"\nTotal parcels with blockchain_tx_hash: {registered_parcels.count()}")
    
    # Check parcels without coordinates
    parcels_without_coords = registered_parcels.filter(
        models.Q(coordinates__isnull=True) | models.Q(coordinates='')
    )
    print(f"Parcels WITHOUT coordinates: {parcels_without_coords.count()}")
    
    # Check parcels with coordinates
    parcels_with_coords = registered_parcels.exclude(
        models.Q(coordinates__isnull=True) | models.Q(coordinates='')
    )
    print(f"Parcels WITH coordinates: {parcels_with_coords.count()}")
    
    print(f"\n{'='*60}")
    print("Sample of parcels WITH coordinates:")
    print(f"{'='*60}")
    
    for parcel in parcels_with_coords[:5]:  # Show first 5
        print(f"\nParcel ID: {parcel.id}")
        print(f"  Status: {parcel.status}")
        print(f"  Location: {parcel.location}")
        print(f"  Blockchain TX: {parcel.blockchain_tx_hash[:20]}...")
        print(f"  Coordinates type: {type(parcel.coordinates)}")
        print(f"  Coordinates value: {parcel.coordinates}")
        
        # Try to parse
        coords = parcel.coordinates
        if isinstance(coords, str):
            try:
                coords = json.loads(coords)
                print(f"  Parsed as JSON: {coords}")
            except:
                print(f"  Failed to parse as JSON")
    
    if parcels_without_coords.count() > 0:
        print(f"\n{'='*60}")
        print("Sample of parcels WITHOUT coordinates:")
        print(f"{'='*60}")
        for parcel in parcels_without_coords[:5]:  # Show first 5
            print(f"\nParcel ID: {parcel.id}")
            print(f"  Status: {parcel.status}")
            print(f"  Location: {parcel.location}")
            print(f"  Blockchain TX: {parcel.blockchain_tx_hash[:20]}...")
            print(f"  Coordinates: {parcel.coordinates}")

if __name__ == "__main__":
    check_registered_parcels()
