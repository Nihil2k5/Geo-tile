from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.conf import settings
from django.utils import timezone
from ...decorators import role_required
from ...models import Parcel, User
from ...blockchain.contracts import ContractManager
from ...services.history_tracker import ParcelHistoryTracker
import json

@login_required
@role_required('surveyor')
def surveyor_dashboard(request):
    """Main dashboard view for surveyors."""
    # Get statistics for parcels assigned to this surveyor
    total_parcels = Parcel.objects.filter(surveyor=request.user).count()
    pending_surveys = Parcel.objects.filter(surveyor=request.user, status='pending_survey').count()
    completed_surveys = Parcel.objects.filter(surveyor=request.user, status='surveyed').count()
    recent_parcels = Parcel.objects.filter(surveyor=request.user).order_by('-updated_at')[:5]

    context = {
        'total_parcels': total_parcels,
        'pending_surveys': pending_surveys,
        'completed_surveys': completed_surveys,
        'recent_parcels': recent_parcels,
    }
    return render(request, 'dashboard/surveyor/dashboard.html', context)

@login_required
@role_required('surveyor')
def survey_list(request):
    """View for listing all land parcels assigned to this surveyor."""
    parcels = Parcel.objects.filter(surveyor=request.user)
    paginator = Paginator(parcels, 10)
    page = request.GET.get('page')
    parcels = paginator.get_page(page)
    
    context = {
        'parcels': parcels
    }
    return render(request, 'dashboard/surveyor/survey_list.html', context)

@login_required
@role_required('surveyor')
def survey_map(request):
    """View for displaying assigned land parcels on a map."""
    parcels = Parcel.objects.filter(surveyor=request.user)
    
    # Convert parcels to GeoJSON features
    features = []
    for parcel in parcels:
        if parcel.coordinates:
            feature = {
                'type': 'Feature',
                'geometry': parcel.coordinates,
                'properties': {
                    'id': parcel.id,
                    'location': parcel.location,
                    'area': parcel.area,
                    'status': parcel.status,
                    'owner': parcel.owner.get_full_name()
                }
            }
            features.append(feature)
    
    geojson = {
        'type': 'FeatureCollection',
        'features': features
    }
    
    context = {
        'mapbox_token': settings.MAPBOX_TOKEN,
        'geojson_data': json.dumps(geojson)
    }
    return render(request, 'dashboard/surveyor/survey_map.html', context)

@login_required
@role_required('surveyor')
def update_survey(request, parcel_id):
    """View for updating survey details."""
    if request.method == 'POST':
        try:
            parcel = Parcel.objects.get(id=parcel_id)
            # Update survey data
            parcel.survey_data = {
                'coordinates': request.POST.get('coordinates'),
                'area': float(request.POST.get('area')),
                'boundaries': request.POST.get('boundaries'),
                'surveyed_by': request.user.id,
                'survey_date': timezone.now().isoformat(),
            }
            parcel.status = 'surveyed'
            parcel.save()
            
            # Update blockchain
            contract_manager = ContractManager()
            tx_hash = contract_manager.update_land_survey(
                parcel_id,
                request.POST.get('coordinates'),
                float(request.POST.get('area'))
            )
            
            # Track survey update in history
            ParcelHistoryTracker.track_survey_update(
                parcel=parcel,
                surveyor=request.user,
                survey_data=parcel.survey_data,
                transaction_hash=tx_hash,
                notes=f"Survey completed by {request.user.get_full_name()}"
            )
            
            messages.success(request, 'Survey updated successfully.')
            return redirect('land_registry:survey_list')
        except Exception as e:
            messages.error(request, f'Error updating survey: {str(e)}')
            return redirect('land_registry:survey_list')
    
    try:
        parcel = Parcel.objects.get(id=parcel_id)
        context = {
            'parcel': parcel,
        }
        return render(request, 'dashboard/surveyor/update_survey.html', context)
    except Parcel.DoesNotExist:
        messages.error(request, 'Parcel not found.')
        return redirect('land_registry:survey_list')