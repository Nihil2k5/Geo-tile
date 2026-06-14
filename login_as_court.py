#!/usr/bin/env python
"""
Script to get court authority user login credentials
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from land_registry.models import User

def get_court_user_info():
    """Get court authority user information for login"""
    print("🔍 Finding Court Authority User...")
    
    try:
        court_user = User.objects.filter(role='court').first()
        if not court_user:
            print("❌ No court authority user found!")
            print("💡 You may need to create a court authority user first.")
            return False
            
        print(f"✅ Found court user:")
        print(f"   - Username: {court_user.username}")
        print(f"   - Full Name: {court_user.get_full_name()}")
        print(f"   - Email: {court_user.email}")
        print(f"   - Role: {court_user.role}")
        print(f"   - Wallet Address: {court_user.wallet_address}")
        
        print(f"\n🔑 Login Information:")
        print(f"   - Username: {court_user.username}")
        print(f"   - Password: [You'll need to know the password or reset it]")
        
        print(f"\n🌐 Login Steps:")
        print(f"   1. Go to: http://localhost:8001/login/")
        print(f"   2. Enter username: {court_user.username}")
        print(f"   3. Enter the password for this user")
        print(f"   4. After login, go to: http://localhost:8001/court/dashboard/")
        
        # Check if we can reset password (for development)
        print(f"\n💡 Development Tip:")
        print(f"   If you don't know the password, you can reset it using Django admin")
        print(f"   or create a new court user with a known password.")
        
        return True
        
    except Exception as e:
        print(f"❌ Error getting court user info: {str(e)}")
        return False

def create_test_court_user():
    """Create a test court user with known credentials"""
    print("\n🔧 Creating test court user...")
    
    try:
        # Check if test court user already exists
        test_user = User.objects.filter(username='court_test').first()
        if test_user:
            print(f"✅ Test court user already exists:")
            print(f"   - Username: court_test")
            print(f"   - Password: testpass123")
            return True
        
        # Create new test court user
        test_user = User.objects.create_user(
            username='court_test',
            email='court@test.com',
            password='testpass123',
            first_name='Court',
            last_name='Authority',
            role='court'
        )
        
        print(f"✅ Created test court user:")
        print(f"   - Username: court_test")
        print(f"   - Password: testpass123")
        print(f"   - Email: court@test.com")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating test court user: {str(e)}")
        return False

if __name__ == "__main__":
    print("🏛️  Court Authority User Information\n")
    
    # Get existing court user info
    success = get_court_user_info()
    
    # Offer to create test user if needed
    if success:
        create_test = input("\n❓ Create additional test court user? (y/n): ").lower().strip()
        if create_test == 'y':
            create_test_court_user()
    else:
        create_test = input("\n❓ Create test court user? (y/n): ").lower().strip()
        if create_test == 'y':
            create_test_court_user()
    
    print(f"\n🎯 Next Steps:")
    print(f"   1. Use the login credentials above")
    print(f"   2. Go to http://localhost:8001/login/")
    print(f"   3. After login, visit http://localhost:8001/court/dashboard/")
    print(f"   4. You should see the Court Authority Dashboard with dispute statistics!")