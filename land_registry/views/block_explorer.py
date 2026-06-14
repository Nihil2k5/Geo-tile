"""
Block Explorer views for viewing all land parcels on the blockchain
"""
import json
from datetime import timedelta

from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count, Exists, OuterRef
from django.core.paginator import Paginator
from django.db.models.functions import TruncMonth
from django.utils import timezone

from land_registry.models import Parcel, Transaction, Dispute
from land_registry.blockchain.contracts import ContractManager


def block_explorer(request):
    """
    Block explorer view to display all land parcels with search and filter capabilities.
    This is a public view (no login required) to promote transparency.
    """
    # Get all parcels ordered by creation date (newest first)
    parcels = (
        Parcel.objects
        .select_related('owner', 'surveyor', 'original_registrar')
        .annotate(has_disputes=Exists(
            Dispute.objects.filter(parcel_id=OuterRef('pk'))
        ))
        .order_by('-created_at')
    )
    
    # Search functionality
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '')
    sort_by = request.GET.get('sort', '-created_at')
    
    # Apply search filter
    if search_query:
        parcels = parcels.filter(
            Q(id__icontains=search_query) |
            Q(location__icontains=search_query) |
            Q(blockchain_tx_hash__icontains=search_query) |
            Q(owner__username__icontains=search_query) |
            Q(owner__first_name__icontains=search_query) |
            Q(owner__last_name__icontains=search_query) |
            Q(owner__wallet_address__icontains=search_query) |
            Q(original_survey_number__icontains=search_query) |
            Q(village_name__icontains=search_query) |
            Q(district_name__icontains=search_query) |
            Q(state_name__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter:
        parcels = parcels.filter(status=status_filter)
    
    # Apply sorting
    valid_sort_fields = ['-created_at', 'created_at', '-updated_at', 'updated_at', 
                         'area', '-area', 'location', '-location', 'status', '-status']
    if sort_by in valid_sort_fields:
        parcels = parcels.order_by(sort_by)
    else:
        parcels = parcels.order_by('-created_at')
    
    # Get statistics
    total_parcels = Parcel.objects.count()
    active_parcels = Parcel.objects.filter(status='active').count()
    pending_parcels = Parcel.objects.filter(status='pending').count()
    disputed_parcels = Parcel.objects.filter(status='disputed').count()
    
    # Status breakdown for charts
    status_qs = Parcel.objects.values('status').annotate(count=Count('id'))
    status_counts = {row['status']: row['count'] for row in status_qs}
    status_chart = {
        'Active': status_counts.get('active', 0),
        'Pending': status_counts.get('pending', 0),
        'Surveyed': status_counts.get('surveyed', 0),
        'Disputed': status_counts.get('disputed', 0),
        'Locked': status_counts.get('locked', 0),
        'Rejected': status_counts.get('rejected', 0),
    }

    # Monthly registrations for last 6 months (for charts)
    now = timezone.now()
    six_months_ago = now - timedelta(days=180)
    monthly_qs = (
        Parcel.objects.filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    monthly_chart = [
        {
            'label': row['month'].strftime('%b %Y') if row['month'] else '',
            'count': row['count'],
        }
        for row in monthly_qs
    ]

    # Get blockchain statistics
    parcels_with_tx = Parcel.objects.exclude(blockchain_tx_hash__isnull=True).exclude(blockchain_tx_hash='').count()
    
    # Pagination
    paginator = Paginator(parcels, 20)  # Show 20 parcels per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Try to get blockchain details for each parcel (optional, can be slow)
    parcels_with_blockchain = []
    contract_manager = None
    try:
        contract_manager = ContractManager()
    except Exception as e:
        print(f"Warning: Could not initialize ContractManager: {e}")
    
    for parcel in page_obj:
        parcel_data = {
            'parcel': parcel,
            'blockchain_details': None,
            'has_disputes': getattr(parcel, 'has_disputes', False),
        }
        
        # Try to get blockchain details if transaction hash exists
        if parcel.blockchain_tx_hash and contract_manager:
            try:
                blockchain_details = contract_manager.get_land_details(str(parcel.id))
                parcel_data['blockchain_details'] = blockchain_details
            except Exception as e:
                # Silently fail - blockchain details are optional
                pass
        
        parcels_with_blockchain.append(parcel_data)
    
    # Status choices for filter dropdown
    status_choices = Parcel.STATUS_CHOICES
    
    context = {
        'parcels_data': parcels_with_blockchain,
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'sort_by': sort_by,
        'status_choices': status_choices,
        'total_parcels': total_parcels,
        'active_parcels': active_parcels,
        'pending_parcels': pending_parcels,
        'disputed_parcels': disputed_parcels,
        'parcels_with_tx': parcels_with_tx,
        'status_chart': status_chart,
        'monthly_chart': monthly_chart,
        'is_authenticated': request.user.is_authenticated,
    }
    
    return render(request, 'block_explorer/explorer.html', context)


def parcel_explorer_detail(request, parcel_id: int):
    """
    Etherscan-style detail page for a single parcel:
    - Overview (owner, status, location, area, timestamps)
    - On-chain info (best-effort)
    - Related transactions (best-effort, from local DB)
    - Raw JSON (coordinates / verification_data / on-chain response)
    """
    parcel = get_object_or_404(
        Parcel.objects.select_related('owner', 'surveyor', 'original_registrar'),
        id=parcel_id,
    )

    # Best-effort chain lookup (may fail in dev)
    blockchain_details = None
    blockchain_error = None
    try:
        cm = ContractManager()
        blockchain_details = cm.get_land_details(str(parcel.id))
    except Exception as e:
        blockchain_error = str(e)

    # Local transaction history (best-effort based on schema)
    tx_qs = Transaction.objects.filter(parcel=parcel).select_related('from_user', 'to_user').order_by('-timestamp')
    tx_recent = tx_qs[:20]

    # Safe JSON strings for display
    coordinates_json = json.dumps(parcel.coordinates, indent=2, default=str) if parcel.coordinates else None
    verification_json = json.dumps(parcel.verification_data, indent=2, default=str) if parcel.verification_data else None
    chain_json = json.dumps(blockchain_details, indent=2, default=str) if blockchain_details else None

    context = {
        'parcel': parcel,
        'blockchain_details': blockchain_details,
        'blockchain_error': blockchain_error,
        'transactions': tx_recent,
        'coordinates_json': coordinates_json,
        'verification_json': verification_json,
        'chain_json': chain_json,
        'is_authenticated': request.user.is_authenticated,
    }
    return render(request, 'block_explorer/parcel_detail.html', context)
