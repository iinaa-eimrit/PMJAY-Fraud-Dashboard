import pytest
import datetime
from django.utils import timezone
from django.http import JsonResponse
import json

from pmjay_fraud_dashboard_app.utils.date_helpers import parse_date, get_default_date_range, get_yesterday
from pmjay_fraud_dashboard_app.utils.pagination import parse_pagination_params, calculate_pagination_metadata
from pmjay_fraud_dashboard_app.utils.responses import success_json, error_json, paginated_json
from pmjay_fraud_dashboard_app.utils.exceptions import ValidationError

@pytest.mark.unit
class TestDateHelpers:
    def test_parse_date_valid(self):
        start, end = parse_date("2023-01-01", "2023-01-31")
        assert start == datetime.date(2023, 1, 1)
        assert end == datetime.date(2023, 1, 31)
        
    def test_parse_date_invalid_fallback(self):
        start, end = parse_date("invalid", "wrong")
        today = datetime.date.today()
        assert start == today
        assert end == today

    def test_get_default_date_range(self):
        start, end = get_default_date_range(30)
        assert end == datetime.date.today()
        assert start == end - datetime.timedelta(days=30)
        
    def test_get_yesterday(self):
        yest = get_yesterday()
        assert yest == datetime.date.today() - datetime.timedelta(days=1)

@pytest.mark.unit
class TestPagination:
    class MockRequest:
        def __init__(self, get_params):
            self.GET = get_params
            
    def test_parse_pagination_params_defaults(self):
        req = self.MockRequest({})
        page, size = parse_pagination_params(req)
        assert page == 1
        assert size == 50
        
    def test_parse_pagination_params_custom(self):
        req = self.MockRequest({'page': '2', 'page_size': '100'})
        page, size = parse_pagination_params(req)
        assert page == 2
        assert size == 100
        
    def test_parse_pagination_params_bounds(self):
        req = self.MockRequest({'page': '-5', 'page_size': '9999'})
        page, size = parse_pagination_params(req)
        assert page == 1
        assert size == 100  # max size cap
        
    def test_calculate_pagination_metadata(self):
        start_idx, end_idx, total_pages = calculate_pagination_metadata(105, 2, 50)
        assert start_idx == 50
        assert end_idx == 100
        assert total_pages == 3

@pytest.mark.unit
class TestResponses:
    def test_success_json(self):
        resp = success_json({"id": 1})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["status"] == "success"
        assert data["data"] == {"id": 1}
        
    def test_error_json(self):
        resp = error_json("Failed", 404)
        assert resp.status_code == 404
        data = json.loads(resp.content)
        assert data["status"] == "error"
        assert data["message"] == "Failed"
