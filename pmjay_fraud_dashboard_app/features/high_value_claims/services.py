import datetime
from django.db.models import Count, Sum, Q, Case, When, Value, CharField
from django.core.paginator import Paginator
from pmjay_fraud_dashboard_app.utils.constants import SHAPEFILE_DISTRICT_MAPPING
from .selectors import high_value_claims_base_query

def get_high_value_claims_summary(start_date, end_date, districts: list) -> dict:
    qs = high_value_claims_base_query(start_date, end_date)
    
    if districts:
        qs = qs.filter(patient_district_name__in=districts)

    yesterday = end_date - datetime.timedelta(days=1)
    yesterday_next = yesterday + datetime.timedelta(days=1)
    thirty_days_ago = end_date - datetime.timedelta(days=30)
    thirty_next = end_date + datetime.timedelta(days=1)

    aggregated = qs.aggregate(
        surgical_count=Count('id', filter=Q(case_type__iexact='SURGICAL', amount_claim_initiated__gte=100000)),
        medical_count=Count('id', filter=Q(case_type__iexact='MEDICAL', amount_claim_initiated__gte=25000)),
        
        surgical_amount=Sum('amount_claim_initiated', filter=Q(case_type__iexact='SURGICAL', amount_claim_initiated__gte=100000)),
        medical_amount=Sum('amount_claim_initiated', filter=Q(case_type__iexact='MEDICAL', amount_claim_initiated__gte=25000)),
        
        surgical_yesterday=Count('id', filter=Q(case_type__iexact='SURGICAL', amount_claim_initiated__gte=100000, preauth_init_date__gte=yesterday, preauth_init_date__lt=yesterday_next)),
        medical_yesterday=Count('id', filter=Q(case_type__iexact='MEDICAL', amount_claim_initiated__gte=25000, preauth_init_date__gte=yesterday, preauth_init_date__lt=yesterday_next)),
        
        surgical_last_30=Count('id', filter=Q(case_type__iexact='SURGICAL', amount_claim_initiated__gte=100000, preauth_init_date__gte=thirty_days_ago, preauth_init_date__lt=thirty_next)),
        medical_last_30=Count('id', filter=Q(case_type__iexact='MEDICAL', amount_claim_initiated__gte=25000, preauth_init_date__gte=thirty_days_ago, preauth_init_date__lt=thirty_next)),
    )
    
    unique_hospitals = qs.values('hospital_id').distinct().count()
    
    return {
        'total_count': aggregated['surgical_count'] + aggregated['medical_count'],
        'unique_hospitals': unique_hospitals,
        'yesterday_count': aggregated['surgical_yesterday'] + aggregated['medical_yesterday'],
        'last_30_days_count': aggregated['surgical_last_30'] + aggregated['medical_last_30'],
        'surgical': {
            'count': aggregated['surgical_count'],
            'amount': aggregated['surgical_amount'] or 0,
            'yesterday': aggregated['surgical_yesterday'],
            'last_30_days': aggregated['surgical_last_30'],
        },
        'medical': {
            'count': aggregated['medical_count'],
            'amount': aggregated['medical_amount'] or 0,
            'yesterday': aggregated['medical_yesterday'],
            'last_30_days': aggregated['medical_last_30'],
        }
    }

def get_high_value_claims_details_list(start_date, end_date, case_type: str, districts: list, page: int, page_size: int) -> dict:
    base_query = high_value_claims_base_query(start_date, end_date)

    case_filters = Q()
    if case_type == 'SURGICAL':
        case_filters = Q(case_type__iexact='SURGICAL', amount_claim_initiated__gte=100000)
    elif case_type == 'MEDICAL':
        case_filters = Q(case_type__iexact='MEDICAL', amount_claim_initiated__gte=25000)
    else:
        case_filters = (
            Q(case_type__iexact='SURGICAL', amount_claim_initiated__gte=100000) |
            Q(case_type__iexact='MEDICAL', amount_claim_initiated__gte=25000)
        )
    
    base_query = base_query.filter(case_filters)

    if districts:
        base_query = base_query.filter(patient_district_name__in=districts)

    base_query = base_query.only(
        'registration_id', 'case_id', 'patient_name', 'member_id',
        'patient_district_name', 'preauth_init_date', 'hospital_id',
        'hospital_name', 'amount_claim_initiated', 'case_type'
    )

    paginator = Paginator(base_query.order_by('-amount_claim_initiated'), page_size)
    page_obj = paginator.get_page(page)

    data = []
    for idx, case in enumerate(page_obj.object_list, 1):
        data.append({
            'serial_no': (page_obj.number - 1) * page_size + idx,
            'claim_id': case.registration_id or case.case_id or 'N/A',
            'patient_name': case.patient_name or f"Patient {case.member_id}",
            'patient_district_name': case.patient_district_name or 'N/A',
            'preauth_initiated_date': case.preauth_init_date.strftime('%Y-%m-%d') if case.preauth_init_date else 'N/A',
            'preauth_initiated_time': case.preauth_init_date.strftime('%H:%M:%S') if case.preauth_init_date else 'N/A',
            'hospital_id': case.hospital_id or 'N/A',
            'hospital_name': case.hospital_name or 'N/A',
            'amount': float(case.amount_claim_initiated) if case.amount_claim_initiated else 0.0,
            'case_type': case.case_type.upper() if case.case_type else 'N/A'
        })

    return {
        'data': data,
        'pagination': {
            'total_records': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous()
        }
    }

def get_high_value_claims_district_distribution(start_date, end_date, case_type: str, districts: list) -> dict:
    base_query = high_value_claims_base_query(start_date, end_date)

    if case_type == 'SURGICAL':
        base_query = base_query.filter(case_type__iexact='SURGICAL', amount_claim_initiated__gte=100000)
    elif case_type == 'MEDICAL':
        base_query = base_query.filter(case_type__iexact='MEDICAL', amount_claim_initiated__gte=25000)
    else:
        base_query = base_query.filter(
            Q(case_type__iexact='SURGICAL', amount_claim_initiated__gte=100000) |
            Q(case_type__iexact='MEDICAL', amount_claim_initiated__gte=25000)
        )

    if districts:
        base_query = base_query.filter(patient_district_name__in=districts)

    district_data = base_query.values('patient_district_name').annotate(
        count=Count('id')
    ).order_by('-count')

    return {
        'districts': [d['patient_district_name'] or 'Unknown' for d in district_data],
        'counts': [d['count'] for d in district_data]
    }

def get_high_value_claims_age_distribution(start_date, end_date, case_type: str, districts: list) -> dict:
    base_query = high_value_claims_base_query(start_date, end_date)

    if case_type == 'SURGICAL':
        base_query = base_query.filter(case_type__iexact='SURGICAL', amount_claim_initiated__gte=100000)
    elif case_type == 'MEDICAL':
        base_query = base_query.filter(case_type__iexact='MEDICAL', amount_claim_initiated__gte=25000)
    else:
        base_query = base_query.filter(
            Q(case_type__iexact='SURGICAL', amount_claim_initiated__gte=100000) |
            Q(case_type__iexact='MEDICAL', amount_claim_initiated__gte=25000)
        )

    if districts:
        base_query = base_query.filter(patient_district_name__in=districts)

    age_groups = Case(
        When(age__lt=20, then=Value('≤20')),
        When(age__gte=20, age__lt=30, then=Value('21-30')),
        When(age__gte=30, age__lt=40, then=Value('31-40')),
        When(age__gte=40, age__lt=50, then=Value('41-50')),
        When(age__gte=50, age__lt=60, then=Value('51-60')),
        When(age__gte=60, then=Value('60+')),
        default=Value('Unknown'),
        output_field=CharField()
    )

    age_data = base_query.annotate(age_group=age_groups).values('age_group') \
        .annotate(count=Count('id')).order_by('age_group')

    categories = ['≤20', '21-30', '31-40', '41-50', '51-60', '60+', 'Unknown']
    colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#C9CBCF']
    
    age_dict = {item['age_group']: item['count'] for item in age_data}
    
    return {
        'labels': categories,
        'data': [age_dict.get(cat, 0) for cat in categories],
        'colors': colors
    }

def get_high_value_claims_gender_distribution(start_date, end_date, case_type: str, districts: list) -> dict:
    base_query = high_value_claims_base_query(start_date, end_date)

    if case_type == 'SURGICAL':
        base_query = base_query.filter(case_type__iexact='SURGICAL', amount_claim_initiated__gte=100000)
    elif case_type == 'MEDICAL':
        base_query = base_query.filter(case_type__iexact='MEDICAL', amount_claim_initiated__gte=25000)
    else:
        base_query = base_query.filter(
            Q(case_type__iexact='SURGICAL', amount_claim_initiated__gte=100000) |
            Q(case_type__iexact='MEDICAL', amount_claim_initiated__gte=25000)
        )

    if districts:
        base_query = base_query.filter(patient_district_name__in=districts)

    gender_groups = Case(
        When(gender__iexact='M', then=Value('Male')),
        When(gender__iexact='F', then=Value('Female')),
        When(gender__isnull=False, then=Value('Other')),
        default=Value('Unknown'),
        output_field=CharField()
    )

    gender_data = base_query.annotate(gender_group=gender_groups).values('gender_group') \
        .annotate(count=Count('id')).order_by('gender_group')

    categories = ['Male', 'Female', 'Other', 'Unknown']
    colors = ['#36A2EB', '#FF6384', '#4BC0C0', '#C9CBCF']
    
    gender_dict = {item['gender_group']: item['count'] for item in gender_data}
    
    return {
        'labels': categories,
        'data': [gender_dict.get(cat, 0) for cat in categories],
        'colors': colors
    }

def get_high_value_claims_geo_distribution(start_date, end_date, case_type: str, districts: list) -> list:
    qs = high_value_claims_base_query(start_date, end_date)

    if case_type == 'SURGICAL':
        qs = qs.filter(case_type__iexact='SURGICAL', amount_claim_initiated__gte=100000)
    elif case_type == 'MEDICAL':
        qs = qs.filter(case_type__iexact='MEDICAL', amount_claim_initiated__gte=25000)
    else:
        qs = qs.filter(
            Q(case_type__iexact='SURGICAL', amount_claim_initiated__gte=100000) |
            Q(case_type__iexact='MEDICAL',  amount_claim_initiated__gte=25000)
        )
    
    if districts:
        qs = qs.filter(patient_district_name__in=districts)

    agg = qs.values('patient_district_name').annotate(count=Count('id'))

    result = []
    for row in agg:
        district_name = row['patient_district_name']
        if district_name:
            fid = SHAPEFILE_DISTRICT_MAPPING.get(district_name.lower())
            if fid is not None:
                result.append({'fid': fid, 'count': row['count']})

    return result
