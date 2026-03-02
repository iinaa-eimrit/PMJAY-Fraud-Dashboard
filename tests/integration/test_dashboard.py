import pytest
from django.urls import reverse
import json
import datetime
from django.utils import timezone

from pmjay_fraud_dashboard_app.models import SuspiciousHospital, Last24Hour, HospitalBeds

@pytest.fixture
def dashboard_data(db):
    """Creates baseline data for dashboard integration tests."""
    # Create watchlist hospital
    SuspiciousHospital.objects.create(hospital_id="H1", hospital_name="Bad Hospital")
    
    # Create Last24Hour claim for that hospital
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    
    Last24Hour.objects.create(
        hospital_id="H1",
        hospital_name="Bad Hospital",
        hospital_type="P",
        patient_district_name="Test District",
        hosp_state_name="Test State",
        preauth_init_date=datetime.datetime.combine(today, datetime.time(12, 0)),
        age=35,
        gender="M",
        amount_preauth_initiated=5000,
        registration_id="REG1"
    )

    Last24Hour.objects.create(
        hospital_id="H1",
        hospital_name="Bad Hospital",
        hospital_type="P",
        patient_district_name="Test District",
        hosp_state_name="Test State",
        preauth_init_date=datetime.datetime.combine(yesterday, datetime.time(10, 0)),
        age=45,
        gender="F",
        amount_preauth_initiated=3000,
        registration_id="REG2"
    )

@pytest.mark.integration
@pytest.mark.django_db
class TestDashboardEndpoints:

    def test_get_districts(self, client, dashboard_data):
        url = reverse('get_districts')
        response = client.get(url)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "Test District" in data["districts"]

    def test_get_states(self, client, dashboard_data):
        url = reverse('get_states')
        response = client.get(url)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "Test State" in data["states"]

    def test_get_flagged_claims(self, client, dashboard_data):
        url = reverse('get_flagged_claims')
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        response = client.get(url, {'start_date': yesterday})
        assert response.status_code == 200
        data = json.loads(response.content)
        
        # We inserted 2 claims total
        assert data["total"] == 2
        assert data["yesterday"] == 1
        
    def test_get_flagged_claims_details(self, client, dashboard_data):
        url = reverse('get_flagged_claims_details')
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        response = client.get(url, {'start_date': yesterday})
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert "pagination" in data
        assert len(data["data"]) == 2
        assert data["data"][0]["district_name"] == "Test District"

    def test_get_age_distribution(self, client, dashboard_data):
        url = reverse('get_age_distribution')
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        response = client.get(url, {'start_date': yesterday})
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert "labels" in data
        assert "data" in data
        # We have one age 35, one age 45
        assert len(data["data"]) > 0

    def test_get_gender_distribution(self, client, dashboard_data):
        url = reverse('get_gender_distribution')
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        response = client.get(url, {'start_date': yesterday})
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert "Male" in data["labels"]
        assert "Female" in data["labels"]
