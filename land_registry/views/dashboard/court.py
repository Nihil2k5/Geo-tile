from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from ...middleware import role_required
from ...blockchain.contracts import ContractManager
from ...models import Dispute

@login_required
@role_required('court')
def court_dashboard(request):
    """
    Main dashboard view for court authorities showing dispute statistics
    """
    try:
        # Get all disputes from Django database
        all_disputes = Dispute.objects.all()
        
        # Calculate statistics
        total_disputes = all_disputes.count()
        pending_disputes = all_disputes.filter(status__in=['open', 'under_review']).count()
        resolved_disputes = all_disputes.filter(status='resolved').count()
        
        # Get recent disputes (last 10)
        recent_disputes = all_disputes.select_related('parcel', 'complainant').order_by('-created_at')[:10]
        
        context = {
            'total_disputes': total_disputes,
            'pending_disputes': pending_disputes,
            'resolved_disputes': resolved_disputes,
            'recent_disputes': recent_disputes,
        }
        
    except Exception as e:
        # Handle any errors gracefully
        messages.error(request, f"Error loading dashboard data: {str(e)}")
        context = {
            'total_disputes': 0,
            'pending_disputes': 0,
            'resolved_disputes': 0,
            'recent_disputes': [],
        }
    
    return render(request, 'dashboard/court/dashboard.html', context)

@login_required
@role_required('court')
def dispute_list(request):
    """
    View for listing all land-related disputes
    """
    try:
        # Base queryset
        django_disputes = Dispute.objects.select_related('parcel', 'complainant').all().order_by('-created_at')

        # Apply filters from query parameters
        status = request.GET.get('status')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        valid_statuses = {'open', 'under_review', 'resolved', 'rejected'}
        if status in valid_statuses:
            django_disputes = django_disputes.filter(status=status)

        from datetime import datetime
        # Date range filters (YYYY-MM-DD)
        if date_from:
            try:
                df = datetime.strptime(date_from, '%Y-%m-%d').date()
                django_disputes = django_disputes.filter(created_at__date__gte=df)
            except ValueError:
                pass
        if date_to:
            try:
                dt = datetime.strptime(date_to, '%Y-%m-%d').date()
                django_disputes = django_disputes.filter(created_at__date__lte=dt)
            except ValueError:
                pass

        # Separate active and resolved disputes
        active_disputes = django_disputes.filter(status__in=['open', 'under_review'])
        resolved_disputes = django_disputes.filter(status='resolved')
        
        # Get blockchain data for each dispute (optional, for detailed view)
        contract_manager = ContractManager()
        disputes_with_blockchain = []
        
        for dispute in django_disputes:
            try:
                blockchain_data = contract_manager.get_dispute_details(dispute.id)
                disputes_with_blockchain.append({
                    'django': dispute,
                    'blockchain': blockchain_data
                })
            except Exception as blockchain_error:
                # If blockchain data fails, still include the Django data
                disputes_with_blockchain.append({
                    'django': dispute,
                    'blockchain': None
                })
        
        context = {
            'disputes': disputes_with_blockchain,
            'total_disputes': django_disputes.count(),
            'active_disputes': active_disputes,
            'resolved_disputes': resolved_disputes,
            # Preserve selected filters in the template
            'selected_status': status or '',
            'selected_date_from': date_from or '',
            'selected_date_to': date_to or ''
        }
        
    except Exception as e:
        messages.error(request, f'Error loading disputes: {str(e)}')
        context = {
            'disputes': [],
            'total_disputes': 0,
            'active_disputes': [],
            'resolved_disputes': []
        }
    
    return render(request, 'dashboard/court/disputes.html', context)

@login_required
@role_required('court')
def resolve_dispute(request, dispute_id):
    """
    View for resolving a specific dispute
    """
    try:
        # Get dispute from Django database
        dispute = get_object_or_404(Dispute, id=dispute_id)
        
        if request.method == 'POST':
            resolution = request.POST.get('resolution', '').strip()
            status = request.POST.get('status', 'resolved')
            
            if not resolution:
                messages.error(request, 'Resolution text is required.')
                return redirect('land_registry:resolve_dispute', dispute_id=dispute_id)
            
            try:
                # Update Django database
                dispute.resolution = resolution
                dispute.status = status
                dispute.resolver = request.user
                dispute.resolved_at = timezone.now()
                dispute.save()
                
                # Update blockchain
                contract_manager = ContractManager()
                
                # For now, use empty IPFS hash - in production, upload resolution to IPFS
                resolution_ipfs_hash = ""
                
                tx_hash = contract_manager.update_dispute_status(
                    dispute_id, 
                    status, 
                    resolution_ipfs_hash
                )
                
                messages.success(request, f'Dispute resolved successfully. Transaction: {tx_hash}')
                return redirect('land_registry:dispute_list')
                
            except Exception as e:
                messages.error(request, f'Error resolving dispute: {str(e)}')
        
        # Get blockchain data for display
        contract_manager = ContractManager()
        blockchain_data = contract_manager.get_dispute_details(dispute_id)
        
        context = {
            'dispute': dispute,
            'blockchain_data': blockchain_data
        }
        
    except Exception as e:
        messages.error(request, f'Error loading dispute: {str(e)}')
        return redirect('land_registry:dispute_list')
    
    return render(request, 'dashboard/court/resolve.html', context)

@login_required
@role_required('court')
def court_metrics(request):
    """
    View for displaying court performance metrics
    """
    from django.db.models import Avg, Count, Q
    from datetime import datetime, timedelta
    import calendar
    import json
    
    contract_manager = ContractManager()
    
    # Get all disputes
    all_disputes = Dispute.objects.all()
    resolved_disputes = all_disputes.filter(status='resolved')
    pending_disputes = all_disputes.filter(status='pending')
    
    # Calculate average resolution time
    avg_resolution_time = 0
    if resolved_disputes.exists():
        total_days = 0
        count = 0
        for dispute in resolved_disputes:
            if dispute.resolved_at and dispute.created_at:
                days = (dispute.resolved_at - dispute.created_at).days
                total_days += days
                count += 1
        avg_resolution_time = round(total_days / count, 1) if count > 0 else 0
    
    # Calculate resolution rate
    total_disputes = all_disputes.count()
    resolved_count = resolved_disputes.count()
    resolution_rate = round((resolved_count / total_disputes * 100), 1) if total_disputes > 0 else 0
    
    # Calculate pending cases
    pending_cases = pending_disputes.count()
    
    # Calculate appeals rate (assuming appeals are disputes that were resolved and then reopened)
    # For now, we'll use a placeholder calculation
    appeals_rate = 5.2  # Placeholder - would need appeal tracking in real system
    
    # Generate monthly statistics for the last 6 months
    monthly_stats = []
    current_date = timezone.now()
    
    for i in range(6):
        month_start = current_date.replace(day=1) - timedelta(days=i*30)
        month_end = month_start.replace(day=calendar.monthrange(month_start.year, month_start.month)[1])
        
        month_disputes = all_disputes.filter(
            created_at__gte=month_start,
            created_at__lte=month_end
        )
        
        month_resolved = resolved_disputes.filter(
            resolved_at__gte=month_start,
            resolved_at__lte=month_end
        )
        
        new_cases = month_disputes.count()
        resolved_cases = month_resolved.count()
        
        # Calculate average resolution time for the month
        month_avg_time = 0
        if month_resolved.exists():
            total_days = 0
            count = 0
            for dispute in month_resolved:
                if dispute.resolved_at and dispute.created_at:
                    days = (dispute.resolved_at - dispute.created_at).days
                    total_days += days
                    count += 1
            month_avg_time = round(total_days / count, 1) if count > 0 else 0
        
        success_rate = round((resolved_cases / new_cases * 100), 1) if new_cases > 0 else 0
        
        monthly_stats.append({
            'month': month_start.strftime('%B %Y'),
            'new_cases': new_cases,
            'resolved': resolved_cases,
            'avg_time': month_avg_time,
            'success_rate': success_rate
        })
    
    # Reverse to show oldest first
    monthly_stats.reverse()
    
    # Generate chart data for JavaScript
    chart_data = {
        'monthly_labels': [stat['month'] for stat in monthly_stats[-6:]],
        'monthly_resolutions': [stat['resolved'] for stat in monthly_stats[-6:]],
        'dispute_types_labels': ['Boundary Disputes', 'Ownership Claims', 'Usage Rights', 'Documentation Issues', 'Other'],
        'dispute_types_data': [],
        'resolution_time_labels': ['< 7 days', '7-14 days', '15-30 days', '> 30 days'],
        'resolution_time_data': [0, 0, 0, 0]
    }
    
    # Calculate dispute types distribution
    dispute_descriptions = resolved_disputes.values_list('description', flat=True)
    boundary_count = sum(1 for desc in dispute_descriptions if 'boundary' in desc.lower())
    ownership_count = sum(1 for desc in dispute_descriptions if 'ownership' in desc.lower() or 'owner' in desc.lower())
    usage_count = sum(1 for desc in dispute_descriptions if 'usage' in desc.lower() or 'use' in desc.lower())
    doc_count = sum(1 for desc in dispute_descriptions if 'document' in desc.lower() or 'paper' in desc.lower())
    other_count = resolved_count - (boundary_count + ownership_count + usage_count + doc_count)
    
    chart_data['dispute_types_data'] = [boundary_count, ownership_count, usage_count, doc_count, other_count]
    
    # Calculate resolution time distribution
    for dispute in resolved_disputes:
        if dispute.resolved_at and dispute.created_at:
            days = (dispute.resolved_at - dispute.created_at).days
            if days < 7:
                chart_data['resolution_time_data'][0] += 1
            elif days < 15:
                chart_data['resolution_time_data'][1] += 1
            elif days < 31:
                chart_data['resolution_time_data'][2] += 1
            else:
                chart_data['resolution_time_data'][3] += 1
    
    context = {
        'resolution_time': avg_resolution_time,
        'resolution_rate': resolution_rate,
        'pending_cases': pending_cases,
        'appeals_rate': appeals_rate,
        'monthly_stats': monthly_stats,
        'chart_data_json': json.dumps(chart_data),
        'total_disputes': total_disputes,
        'resolved_disputes': resolved_count,
    }
    
    return render(request, 'dashboard/court/metrics.html', context)