from typing import List, Dict, Any
from django.db.models import Count, Q
from django.core.paginator import Paginator

from .selectors import get_watchlist_base_query, get_last_30_days_watchlist_query
from pmjay_fraud_dashboard_app.utils.constants import SHAPEFILE_DISTRICT_MAPPING


def aggregate_flagged_claims(start_date, end_date, districts: List[str]) -> Dict[str, int]:
    """Aggregates total, yesterday, and 30-day flagged claim counts."""
    base_qs, suspicious_hospitals = get_watchlist_base_query(start_date, end_date, districts)
    
    from django.utils.timezone import timedelta
    yesterday = end_date - timedelta(days=1)
    yesterday_next = yesterday + timedelta(days=1)
    
    aggs = base_qs.aggregate(
        total=Count('id'),
        yesterday=Count('id', filter=Q(preauth_init_date__gte=yesterday, preauth_init_date__lt=yesterday_next)),
    )
    
    last_30_days_qs = get_last_30_days_watchlist_query(end_date, suspicious_hospitals, districts)
    
    unique_hospitals = base_qs.values('hospital_id').distinct().count()
    
    return {
        'total': aggs['total'],
        'unique_hospitals': unique_hospitals,
        'yesterday': aggs['yesterday'],
        'last_30_days': last_30_days_qs.count()
    }


def get_flagged_claims_details_data(start_date, end_date, districts: List[str], 
                                    search_query: str, page: int, page_size: int) -> Dict[str, Any]:
    """Retrieves paginated and filtered list of flagged claims details."""
    qs, _ = get_watchlist_base_query(start_date, end_date, districts)
    
    if search_query:
        search_terms = [t.strip().lower() for t in search_query.split(',') if t.strip()]
        for term in search_terms:
            qs = qs.filter(
                Q(registration_id__iexact=term) |
                Q(case_id__iexact=term) |
                Q(patient_name__iexact=term) |
                Q(patient_district_name__iexact=term) |
                Q(hospital_id__iexact=term) |
                Q(hospital_name__iexact=term) |
                Q(amount_claim_initiated__iexact=term)
            )
            
    qs = qs.only(
        'registration_id', 'case_id', 'patient_name', 'member_id',
        'patient_district_name', 'preauth_init_date', 'hospital_id',
        'hospital_name', 'amount_claim_initiated'
    )
            
    paginator = Paginator(qs.order_by('preauth_init_date'), page_size)
    page_obj = paginator.get_page(page)
    
    data = []
    for idx, case in enumerate(page_obj.object_list, 1):
        preauth_initiated_date = case.preauth_init_date.strftime('%Y-%m-%d') if case.preauth_init_date else 'N/A'
        preauth_initiated_time = case.preauth_init_date.strftime('%H:%M:%S') if case.preauth_init_date else 'N/A'
        data.append({
            'serial_no': (page_obj.number - 1) * page_size + idx,
            'claim_id': case.registration_id or case.case_id or 'N/A',
            'patient_name': case.patient_name or f"Patient {case.member_id}",
            'district_name': case.patient_district_name or 'N/A',
            'preauth_initiated_date': preauth_initiated_date,
            'preauth_initiated_time': preauth_initiated_time,
            'hospital_id': case.hospital_id or 'N/A',
            'hospital_name': case.hospital_name or 'N/A',
            'amount': float(case.amount_claim_initiated) if case.amount_claim_initiated else 0.0,
            'reason': 'Suspicious hospital'
        })
        
    return {
        'data': data,
        'pagination': {
            'total_records': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }
    }


def get_flagged_claims_by_district_data(start_date, end_date, districts: List[str]) -> Dict[str, list]:
    """Aggregates flagged claims grouped by patient district."""
    qs, _ = get_watchlist_base_query(start_date, end_date, districts)
    district_data = qs.values('patient_district_name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    return {
        'districts': [item['patient_district_name'] or 'Unknown' for item in district_data],
        'counts': [item['count'] for item in district_data]
    }


def get_age_distribution_data(start_date, end_date, districts: List[str]) -> Dict[str, list]:
    """Aggregates age distribution for flagged claims."""
    qs, _ = get_watchlist_base_query(start_date, end_date, districts)
    
    age_groups = {
        '15-29': Count('id', filter=Q(age__gte=15, age__lte=29)),
        '30-44': Count('id', filter=Q(age__gte=30, age__lte=44)),
        '45-59': Count('id', filter=Q(age__gte=45, age__lte=59)),
        '60+': Count('id', filter=Q(age__gte=60))
    }
    
    age_data = qs.aggregate(**age_groups)
    
    return {
        'labels': list(age_data.keys()),
        'data': list(age_data.values()),
        'colors': ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0']
    }


def get_gender_distribution_data(start_date, end_date, districts: List[str]) -> Dict[str, list]:
    """Aggregates gender distribution for flagged claims."""
    qs, _ = get_watchlist_base_query(start_date, end_date, districts)
    
    male_aliases = ['M', 'm', 'MALE', 'male', 'Male']
    female_aliases = ['F', 'f', 'FEMALE', 'female', 'Female']
    
    aggs = qs.aggregate(
        male_count=Count('id', filter=Q(gender__in=male_aliases)),
        female_count=Count('id', filter=Q(gender__in=female_aliases)),
        total_count=Count('id')
    )
    
    male_count = aggs['male_count'] or 0
    female_count = aggs['female_count'] or 0
    unknown_count = (aggs['total_count'] or 0) - (male_count + female_count)
    
    standardized_data = {
        'Male': male_count,
        'Female': female_count,
        'Unknown': unknown_count
    }
        
    labels, data = [], []
    for gender in ['Male', 'Female', 'Unknown']:
        if standardized_data.get(gender, 0) > 0:
            labels.append(gender)
            data.append(standardized_data[gender])
            
    return {
        'labels': labels,
        'data': data,
        'colors': ['#36A2EB', '#FF6384', '#CCCCCC'][:len(labels)]
    }


def get_flagged_claims_geo_counts_data(start_date, end_date, districts: List[str]) -> List[Dict[str, int]]:
    """Maps district counts to SHP File FIDs."""
    qs, _ = get_watchlist_base_query(start_date, end_date, districts)
    agg = qs.values('patient_district_name').annotate(count=Count('id'))
    
    result = []
    for row in agg:
        name = row['patient_district_name']
        cnt = row['count']
        if name:
            fid = SHAPEFILE_DISTRICT_MAPPING.get(name.lower())
            if fid is not None:
                result.append({'fid': fid, 'count': cnt})
                
    return result
