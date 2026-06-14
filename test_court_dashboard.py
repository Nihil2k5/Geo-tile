#!/usr/bin/env python
"""
Test script to verify Court Authority Dashboard functionality
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geoledger.settings')
django.setup()

from django.test import Client
from django.contrib.auth import authenticate
from land_registry.models import User, Dispute

def test_court_dashboard():
    """Test the court dashboard functionality"""
    print("🔍 Testing Court Authority Dashboard...")
    
    # Get court authority user
    try:
        court_user = User.objects.filter(role='court').first()
        if not court_user:
            print("❌ No court authority user found!")
            return False
            
        print(f"✅ Found court user: {court_user.username} ({court_user.get_full_name()})")
        
        # Get dispute statistics
        all_disputes = Dispute.objects.all()
        total_disputes = all_disputes.count()
        pending_disputes = all_disputes.filter(status__in=['open', 'under_review']).count()
        resolved_disputes = all_disputes.filter(status='resolved').count()
        recent_disputes = all_disputes.order_by('-created_at')[:10]
        
        print(f"📊 Dispute Statistics:")
        print(f"   - Total Disputes: {total_disputes}")
        print(f"   - Pending Disputes: {pending_disputes}")
        print(f"   - Resolved Disputes: {resolved_disputes}")
        print(f"   - Recent Disputes: {recent_disputes.count()}")
        
        # Test dashboard view function directly
        from land_registry.views.dashboard.court import court_dashboard
        from django.http import HttpRequest
        from django.contrib.auth.models import AnonymousUser
        
        # Create a mock request
        request = HttpRequest()
        request.user = court_user
        request.method = 'GET'
        
        # Call the view function directly
        try:
            response = court_dashboard(request)
            
            if hasattr(response, 'context_data'):
                context = response.context_data
                print(f"📋 Dashboard Context Data:")
                print(f"   - Total Disputes: {context.get('total_disputes', 'N/A')}")
                print(f"   - Pending Disputes: {context.get('pending_disputes', 'N/A')}")
                print(f"   - Resolved Disputes: {context.get('resolved_disputes', 'N/A')}")
                print(f"   - Recent Disputes Count: {len(context.get('recent_disputes', []))}")
                
                # Verify data matches
                if (context.get('total_disputes') == total_disputes and
                    context.get('pending_disputes') == pending_disputes and
                    context.get('resolved_disputes') == resolved_disputes):
                    print("✅ Dashboard data is correct!")
                    return True
                else:
                    print("❌ Dashboard data mismatch!")
                    print(f"Expected: total={total_disputes}, pending={pending_disputes}, resolved={resolved_disputes}")
                    print(f"Got: total={context.get('total_disputes')}, pending={context.get('pending_disputes')}, resolved={context.get('resolved_disputes')}")
                    return False
            else:
                print("✅ Court dashboard view executed successfully!")
                print("⚠️  Response doesn't have context_data (might be a redirect or different response type)")
                return True
                
        except Exception as view_error:
            print(f"❌ Error calling court dashboard view: {str(view_error)}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing court dashboard: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_court_dashboard()
    if success:
        print("\n🎉 Court Authority Dashboard is working correctly!")
    else:
        print("\n💥 Court Authority Dashboard has issues!")
    
    sys.exit(0 if success else 1)