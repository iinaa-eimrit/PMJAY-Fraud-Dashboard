from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from pmjay_fraud_dashboard_app.utils.date_helpers import parse_date
from pmjay_fraud_dashboard_app.utils.pagination import parse_pagination_params
from .services import (
    aggregate_ophthalmology_cases,
    get_ophthalmology_details_data,
    get_ophthalmology_distribution_data,
    get_ophthalmology_demographics_data,
    get_ophthalmology_violations_geo_data
)

def _parse_common_params(request):
    """Helper to parse common GET parameters for ophthalmology endpoints."""
    district_param = request.GET.get('district', '').strip()
    districts = [d.strip() for d in district_param.split(',')] if district_param else []
    
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    start_date, end_date = parse_date(start_date_str, end_date_str)
    
    return start_date, end_date, districts


@require_http_methods(["GET"])
def get_ophthalmology_cases(request):
    start_date, end_date, districts = _parse_common_params(request)
    data = aggregate_ophthalmology_cases(start_date, end_date, districts)
    return JsonResponse(data)


@require_http_methods(["GET"])
def get_ophthalmology_details(request):
    start_date, end_date, districts = _parse_common_params(request)
    violation_type = request.GET.get('type', 'all')
    page, page_size = parse_pagination_params(request)
    
    data = get_ophthalmology_details_data(start_date, end_date, districts, violation_type, page, page_size)
    return JsonResponse(data)


@require_http_methods(["GET"])
def get_ophthalmology_distribution(request):
    start_date, end_date, districts = _parse_common_params(request)
    violation_type = request.GET.get('type', 'all')
    
    data = get_ophthalmology_distribution_data(start_date, end_date, districts, violation_type)
    return JsonResponse(data)


@require_http_methods(["GET"])
def get_ophthalmology_demographics(request, type):
    start_date, end_date, districts = _parse_common_params(request)
    violation_type = request.GET.get('violation_type', 'all')
    
    data = get_ophthalmology_demographics_data(start_date, end_date, districts, type, violation_type)
    return JsonResponse(data)


@require_http_methods(["GET"])
def get_ophthalmology_violations_geo(request):
    start_date, end_date, districts = _parse_common_params(request)
    violation_type = request.GET.get('type', 'all')
    
    data = get_ophthalmology_violations_geo_data(start_date, end_date, districts, violation_type)
    return JsonResponse(data, safe=False)
