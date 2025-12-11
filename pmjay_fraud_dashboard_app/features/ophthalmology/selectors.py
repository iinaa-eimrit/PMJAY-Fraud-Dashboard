from typing import Dict
from pmjay_fraud_dashboard_app.models import HospitalBeds

def get_hospital_district_map() -> Dict[str, str]:
    """
    Returns a dictionary mapping hospital_id to hospital_district
    sourced from the HospitalBeds authoritative table.
    """
    return {
        rec['hospital_id']: rec['hospital_district'] or 'N/A'
        for rec in HospitalBeds.objects.values('hospital_id', 'hospital_district')
    }
