from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from ...models import User, Parcel, Dispute
from ...forms import UserCreationForm, UserUpdateForm
from django.db.models import Count, Q
from datetime import datetime, timedelta

def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    # Get system metrics
    total_users = User.objects.count()
    total_parcels = Parcel.objects.count()
    total_disputes = Dispute.objects.count()
    
    # Get recent activity
    recent_parcels = Parcel.objects.order_by('-created_at')[:5]
    recent_disputes = Dispute.objects.order_by('-created_at')[:5]
    
    # Get status breakdowns
    parcel_status = Parcel.objects.values('status').annotate(count=Count('id'))
    dispute_status = Dispute.objects.values('status').annotate(count=Count('id'))
    
    context = {
        'total_users': total_users,
        'total_parcels': total_parcels,
        'total_disputes': total_disputes,
        'recent_parcels': recent_parcels,
        'recent_disputes': recent_disputes,
        'parcel_status': parcel_status,
        'dispute_status': dispute_status,
    }
    
    return render(request, 'dashboard/admin/dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def user_management(request):
    if request.method == 'POST':
        if 'create_user' in request.POST:
            form = UserCreationForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'User created successfully.')
                return redirect('land_registry:user_management')
        elif 'update_user' in request.POST:
            user_id = request.POST.get('user_id')
            user = User.objects.get(id=user_id)
            form = UserUpdateForm(request.POST, instance=user)
            if form.is_valid():
                form.save()
                messages.success(request, 'User updated successfully.')
                return redirect('land_registry:user_management')
    else:
        form = UserCreationForm()
    
    users = User.objects.all().order_by('-date_joined')
    context = {
        'users': users,
        'form': form,
    }
    return render(request, 'dashboard/admin/user_management.html', context)

@login_required
@user_passes_test(is_admin)
def system_metrics(request):
    # Time-based metrics
    now = datetime.now()
    last_week = now - timedelta(days=7)
    last_month = now - timedelta(days=30)
    
    # User metrics
    new_users_week = User.objects.filter(date_joined__gte=last_week).count()
    new_users_month = User.objects.filter(date_joined__gte=last_month).count()
    users_by_role = User.objects.values('role').annotate(count=Count('id'))
    
    # Parcel metrics
    new_parcels_week = Parcel.objects.filter(created_at__gte=last_week).count()
    new_parcels_month = Parcel.objects.filter(created_at__gte=last_month).count()
    parcels_by_status = Parcel.objects.values('status').annotate(count=Count('id'))
    
    # Dispute metrics
    new_disputes_week = Dispute.objects.filter(created_at__gte=last_week).count()
    new_disputes_month = Dispute.objects.filter(created_at__gte=last_month).count()
    disputes_by_status = Dispute.objects.values('status').annotate(count=Count('id'))
    
    context = {
        'new_users_week': new_users_week,
        'new_users_month': new_users_month,
        'users_by_role': users_by_role,
        'new_parcels_week': new_parcels_week,
        'new_parcels_month': new_parcels_month,
        'parcels_by_status': parcels_by_status,
        'new_disputes_week': new_disputes_week,
        'new_disputes_month': new_disputes_month,
        'disputes_by_status': disputes_by_status,
    }
    
    return render(request, 'dashboard/admin/system_metrics.html', context)