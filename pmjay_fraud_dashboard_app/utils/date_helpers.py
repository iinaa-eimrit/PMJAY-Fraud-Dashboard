import datetime
from django.utils import timezone
from typing import Tuple

def parse_date(start_date_str: str, end_date_str: str) -> Tuple[datetime.date, datetime.date]:
    """
    Parses start and end date strings from request parameters.
    Falls back to current local date if parsing fails or values are missing.
    """
    try:
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else timezone.now()
        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)
        start_date = start_date.date()
    except ValueError:
        start_date = datetime.date.today()
        
    try:
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else timezone.now()
        if timezone.is_naive(end_date):
            end_date = timezone.make_aware(end_date)
        end_date = end_date.date()
    except ValueError:
        end_date = datetime.date.today()
        
    return start_date, end_date

def get_default_date_range(days: int = 30) -> Tuple[datetime.date, datetime.date]:
    """Returns a default date range ending today and starting 'days' ago."""
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days)
    return start_date, end_date

def get_yesterday() -> datetime.date:
    """Returns yesterday's date."""
    return datetime.date.today() - datetime.timedelta(days=1)
