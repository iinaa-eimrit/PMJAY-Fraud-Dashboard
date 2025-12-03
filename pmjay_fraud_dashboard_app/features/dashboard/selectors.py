from typing import List, Tuple
from django.db.models import QuerySet
from pmjay_fraud_dashboard_app.models import Last24Hour, SuspiciousHospital
from datetime import timedelta

def get_distinct_districts() -> List[str]:
    """Fetch a list of distinct patient district names."""
    districts = Last24Hour.objects.values_list('patient_district_name', flat=True).distinct()
    return [d for d in districts if d]

def get_distinct_states() -> List[str]:
    """Fetch a list of distinct hospital state names."""
    states = Last24Hour.objects.values_list('hosp_state_name', flat=True).distinct()
    return [s for s in states if s]

def get_watchlist_base_query(start_date, end_date, districts: List[str] = None) -> Tuple[QuerySet, QuerySet]:
    """
    Returns a tuple of (base_qs, suspicious_hospitals_qs) representing 
    patients admitted in watchlist hospitals within the given date range.
    """
    suspicious_hospitals = SuspiciousHospital.objects.values_list('hospital_id', flat=True)
    next_day = end_date + timedelta(days=1)
    base_qs = Last24Hour.objects.filter(
        hospital_id__in=suspicious_hospitals,
        hospital_type='P'
    )
    if start_date and end_date:
        next_day = end_date + timedelta(days=1)
        base_qs = base_qs.filter(
            preauth_init_date__gte=start_date,
            preauth_init_date__lt=next_day
        )
    if districts:
        base_qs = base_qs.filter(patient_district_name__in=districts)
        
    return base_qs, suspicious_hospitals

def get_last_30_days_watchlist_query(end_date, suspicious_hospitals, districts: List[str] = None) -> QuerySet:
    """Fetch watchlist cases for the last 30 days up to end_date."""
    thirty_days_ago = end_date - timedelta(days=30)
    next_day = end_date + timedelta(days=1)
    
    last_30_days = Last24Hour.objects.filter(
        hospital_id__in=suspicious_hospitals,
        hospital_type='P',
        preauth_init_date__gte=thirty_days_ago,
        preauth_init_date__lt=next_day
    )
    if districts:
        last_30_days = last_30_days.filter(patient_district_name__in=districts)
    return last_30_days
