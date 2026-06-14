#!/usr/bin/env python3
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from django.utils import timezone
from land_registry.models import User, Parcel
from land_registry.blockchain.contracts import ContractManager

def main():
    print("=== Debug Blockchain Registration ===")
    cm = ContractManager()
    print("✓ ContractManager initialized")

    # Pick an existing citizen with a wallet
    owner = User.objects.filter(role='citizen').exclude(wallet_address__isnull=True).exclude(wallet_address='').first()
    if not owner:
        print("✗ No citizen with wallet_address found")
        return
    print(f"✓ Using owner {owner.id} {owner.username} {owner.wallet_address}")

    area = 58942.5
    coordinates = [[[77.697565648406,8.303837227056945],[77.69766514695868,8.302200402253746],[77.70032673325119,8.302089639426839],[77.70046354376115,8.303911068616301],[77.697565648406,8.303837227056945]]]
    location = "Radhapuram - Idayankudi Road, Tirunelveli, Radhapuram, Tamil Nadu, India 627111"

    # Create parcel record
    parcel = Parcel.objects.create(
        owner=owner,
        surveyor=User.objects.filter(role='surveyor').order_by('?').first(),
        area=area,
        coordinates=coordinates,
        location=location,
        description='',
        status='pending',
    )
    parcel.original_owner = owner
    parcel.original_registration_date = timezone.now()
    parcel.original_registrar = None
    parcel.original_area = area
    parcel.original_coordinates = coordinates
    parcel.save()
    print(f"✓ Created parcel {parcel.id}")

    try:
        # Check if already exists on blockchain
        if cm.parcel_exists(str(parcel.id)):
            print(f"✗ Parcel {parcel.id} already exists on blockchain. Skipping.")
        else:
            tx_hash = cm.register_land(
                str(parcel.id),
                owner.wallet_address,
                "QmDebugTestParcelHash",
                area,
                "QmDebugTestParcelHash"
            )
            print("✓ Registered parcel on-chain:", tx_hash)
    except Exception as e:
        print("✗ Registration failed:", e)
    finally:
        # Clean up parcel to avoid duplicates in further tests
        parcel.delete()
        print("✓ Cleaned up test parcel")

if __name__ == "__main__":
    main()