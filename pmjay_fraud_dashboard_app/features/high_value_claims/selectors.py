from django.db.models import QuerySet
from pmjay_fraud_dashboard_app.models import Last24Hour
import datetime

def high_value_claims_base_query(start_date, end_date) -> QuerySet:
    """
    Returns the base queryset for High Value Claims.
    Filters Last24Hour by hospital_type='P' and the given date range for preauth_init_date.
    """
    cases = Last24Hour.objects.filter(hospital_type='P')
    if start_date and end_date:
        next_day = end_date + datetime.timedelta(days=1)
        cases = cases.filter(
            preauth_init_date__gte=start_date,
            preauth_init_date__lt=next_day,
        )
    return cases
