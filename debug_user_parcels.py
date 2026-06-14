#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from land_registry.models import User, Parcel

# Get the citizen user (assuming username 'citi')
try:
    citizen_user = User.objects.get(username='citi')
    print(f"Found citizen user: {citizen_user.username}")
    
    # Get all parcels owned by this user
    all_parcels = Parcel.objects.filter(owner=citizen_user)
    print(f"\nTotal parcels owned by {citizen_user.username}: {all_parcels.count()}")
    
    if all_parcels.exists():
        print("\nAll parcels:")
        for parcel in all_parcels:
            print(f"  - Parcel ID: {parcel.id}, Location: {parcel.location}, Status: {parcel.status}")
        
        # Check verified parcels specifically
        verified_parcels = all_parcels.filter(status='verified')
        print(f"\nVerified parcels: {verified_parcels.count()}")
        
        if verified_parcels.exists():
            print("Verified parcels:")
            for parcel in verified_parcels:
                print(f"  - Parcel ID: {parcel.id}, Location: {parcel.location}")
        else:
            print("No verified parcels found!")
            
            # Show what statuses exist
            statuses = all_parcels.values_list('status', flat=True).distinct()
            print(f"Available statuses: {list(statuses)}")
    else:
        print("No parcels found for this user!")
        
except User.DoesNotExist:
    print("Citizen user 'citi' not found!")
    
    # Show all users
    users = User.objects.all()
    print(f"Available users: {[u.username for u in users]}")