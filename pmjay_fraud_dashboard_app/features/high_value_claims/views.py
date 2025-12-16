from django.http import JsonResponse
from pmjay_fraud_dashboard_app.utils.date_helpers import parse_date
from pmjay_fraud_dashboard_app.utils.logging import Timer
from . import services

def get_high_value_claims(request):
    with Timer("get_high_value_claims TOTAL"):
        district_param = request.GET.get('district', '')
        districts = district_param.split(',') if district_param else []

        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        start_date, end_date = parse_date(start_date_str, end_date_str)

        data = services.get_high_value_claims_summary(start_date, end_date, districts)
        return JsonResponse(data)

def get_high_value_claims_details(request):
    with Timer("get_high_value_claims_details TOTAL"):
        case_type = request.GET.get('case_type', 'all').upper()
        district_param = request.GET.get('district', '')
        districts = district_param.split(',') if district_param else []
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        start_date, end_date = parse_date(start_date_str, end_date_str)

        data = services.get_high_value_claims_details_list(
            start_date, end_date, case_type, districts, page, page_size
        )
        return JsonResponse(data)

def get_high_value_claims_by_district(request):
    with Timer("get_high_value_claims_by_district TOTAL"):
        case_type = request.GET.get('case_type', 'all').upper()
        district_param = request.GET.get('district', '')
        districts = district_param.split(',') if district_param else []

        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        start_date, end_date = parse_date(start_date_str, end_date_str)

        data = services.get_high_value_claims_district_distribution(
            start_date, end_date, case_type, districts
        )
        return JsonResponse(data)

def get_high_value_age_distribution(request):
    with Timer("get_high_value_age_distribution TOTAL"):
        case_type = request.GET.get('case_type', 'all').upper()
        district_param = request.GET.get('district', '')
        districts = district_param.split(',') if district_param else []

        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        start_date, end_date = parse_date(start_date_str, end_date_str)

        data = services.get_high_value_claims_age_distribution(
            start_date, end_date, case_type, districts
        )
        return JsonResponse(data)

def get_high_value_gender_distribution(request):
    with Timer("get_high_value_gender_distribution TOTAL"):
        case_type = request.GET.get('case_type', 'all').upper()
        district_param = request.GET.get('district', '')
        districts = district_param.split(',') if district_param else []

        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        start_date, end_date = parse_date(start_date_str, end_date_str)

        data = services.get_high_value_claims_gender_distribution(
            start_date, end_date, case_type, districts
        )
        return JsonResponse(data)

def get_high_value_claims_geo(request):
    with Timer("get_high_value_claims_geo TOTAL"):
        case_type = request.GET.get('case_type', 'all').upper()
        district_param = request.GET.get('district', '')
        districts = district_param.split(',') if district_param else []

        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        start_date, end_date = parse_date(start_date_str, end_date_str)

        result = services.get_high_value_claims_geo_distribution(
            start_date, end_date, case_type, districts
        )
        return JsonResponse(result, safe=False)
