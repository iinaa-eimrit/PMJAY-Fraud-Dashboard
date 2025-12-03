from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from pmjay_fraud_dashboard_app.utils.date_helpers import parse_date
from pmjay_fraud_dashboard_app.utils.pagination import parse_pagination_params
from .selectors import get_distinct_districts, get_distinct_states
from .services import (
    aggregate_flagged_claims,
    get_flagged_claims_details_data,
    get_flagged_claims_by_district_data,
    get_age_distribution_data,
    get_gender_distribution_data,
    get_flagged_claims_geo_counts_data,
)


@require_http_methods(["GET"])
def get_districts(request):
    """Returns a list of all distinct patient districts."""
    districts = get_distinct_districts()
    return JsonResponse({'districts': districts})


@require_http_methods(["GET"])
def get_states(request):
    """Returns a list of all distinct hospital states."""
    states = get_distinct_states()
    return JsonResponse({'states': states})


def _parse_common_params(request):
    """Helper to parse common GET parameters for dashboard endpoints."""
    district_param = request.GET.get('district', '')
    districts = district_param.split(',') if district_param else []
    
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    start_date, end_date = parse_date(start_date_str, end_date_str)
    
    return start_date, end_date, districts


@require_http_methods(["GET"])
def get_flagged_claims(request):
    start_date, end_date, districts = _parse_common_params(request)
    data = aggregate_flagged_claims(start_date, end_date, districts)
    return JsonResponse(data)


@require_http_methods(["GET"])
def get_flagged_claims_details(request):
    start_date, end_date, districts = _parse_common_params(request)
    page, page_size = parse_pagination_params(request)
    search_query = request.GET.get('search', '').strip()
    
    data = get_flagged_claims_details_data(start_date, end_date, districts, search_query, page, page_size)
    return JsonResponse(data)


@require_http_methods(["GET"])
def get_flagged_claims_by_district(request):
    start_date, end_date, districts = _parse_common_params(request)
    data = get_flagged_claims_by_district_data(start_date, end_date, districts)
    return JsonResponse(data)


@require_http_methods(["GET"])
def get_age_distribution(request):
    start_date, end_date, districts = _parse_common_params(request)
    data = get_age_distribution_data(start_date, end_date, districts)
    return JsonResponse(data)


@require_http_methods(["GET"])
def get_gender_distribution(request):
    start_date, end_date, districts = _parse_common_params(request)
    data = get_gender_distribution_data(start_date, end_date, districts)
    return JsonResponse(data)


@require_http_methods(["GET"])
def get_flagged_claims_geo_counts(request):
    start_date, end_date, districts = _parse_common_params(request)
    data = get_flagged_claims_geo_counts_data(start_date, end_date, districts)
    return JsonResponse(data, safe=False)
