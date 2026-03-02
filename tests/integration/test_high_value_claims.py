import pytest
from django.urls import reverse
import json
import datetime

from pmjay_fraud_dashboard_app.models import Last24Hour

@pytest.fixture
def high_value_data(db):
    """Creates baseline data for High Value Claims integration tests."""
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    
    # 1. High value surgical claim (Today)
    Last24Hour.objects.create(
        hospital_id="H1",
        hospital_name="Good Hospital",
        hospital_type="P",
        patient_district_name="Test District",
        hosp_state_name="Test State",
        preauth_init_date=datetime.datetime.combine(today, datetime.time(12, 0)),
        age=35,
        gender="M",
        case_type="SURGICAL",
        amount_claim_initiated=150000,
        registration_id="REG1"
    )

    # 2. High value medical claim (Yesterday)
    Last24Hour.objects.create(
        hospital_id="H2",
        hospital_name="Great Hospital",
        hospital_type="P",
        patient_district_name="Another District",
        hosp_state_name="Test State",
        preauth_init_date=datetime.datetime.combine(yesterday, datetime.time(10, 0)),
        age=65,
        gender="F",
        case_type="MEDICAL",
        amount_claim_initiated=50000,
        registration_id="REG2"
    )

    # 3. Low value claim (Should be ignored by endpoints)
    Last24Hour.objects.create(
        hospital_id="H3",
        hospital_name="Okay Hospital",
        hospital_type="P",
        patient_district_name="Test District",
        hosp_state_name="Test State",
        preauth_init_date=datetime.datetime.combine(today, datetime.time(9, 0)),
        age=20,
        gender="M",
        case_type="MEDICAL",
        amount_claim_initiated=5000,
        registration_id="REG3"
    )


@pytest.mark.integration
@pytest.mark.django_db
class TestHighValueClaimsEndpoints:

    def test_get_high_value_claims_summary(self, client, high_value_data):
        url = reverse('get_high_value_claims')
        thirty_days_ago = (datetime.date.today() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        response = client.get(url, {'start_date': thirty_days_ago})
        
        assert response.status_code == 200
        data = json.loads(response.content)
        
        # We inserted 2 high value claims total
        assert data["total_count"] == 2
        assert data["surgical"]["count"] == 1
        assert data["medical"]["count"] == 1
        assert data["unique_hospitals"] == 3

    def test_get_high_value_claims_details(self, client, high_value_data):
        url = reverse('get_high_value_claims_details')
        thirty_days_ago = (datetime.date.today() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        
        # Test All Cases
        response = client.get(url, {'start_date': thirty_days_ago, 'case_type': 'all'})
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert "pagination" in data
        assert len(data["data"]) == 2
        
        # Test Medical Cases only
        response = client.get(url, {'start_date': thirty_days_ago, 'case_type': 'MEDICAL'})
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert len(data["data"]) == 1
        assert data["data"][0]["case_type"] == "MEDICAL"

    def test_get_high_value_claims_by_district(self, client, high_value_data):
        url = reverse('get_high_value_claims_by_district')
        thirty_days_ago = (datetime.date.today() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        response = client.get(url, {'start_date': thirty_days_ago})
        
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert "Test District" in data["districts"]
        assert "Another District" in data["districts"]

    def test_get_high_value_age_distribution(self, client, high_value_data):
        url = reverse('get_high_value_age_distribution')
        thirty_days_ago = (datetime.date.today() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        response = client.get(url, {'start_date': thirty_days_ago})
        
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert "labels" in data
        assert "data" in data
        assert len(data["data"]) > 0

    def test_get_high_value_gender_distribution(self, client, high_value_data):
        url = reverse('get_high_value_gender_distribution')
        thirty_days_ago = (datetime.date.today() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        response = client.get(url, {'start_date': thirty_days_ago})
        
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert "labels" in data
        assert "data" in data
        
        # One Male, One Female
        male_index = data["labels"].index("Male")
        female_index = data["labels"].index("Female")
        assert data["data"][male_index] == 1
        assert data["data"][female_index] == 1

    def test_get_high_value_claims_geo(self, client, high_value_data):
        url = reverse('high_value_claims_geo')
        thirty_days_ago = (datetime.date.today() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        response = client.get(url, {'start_date': thirty_days_ago})
        
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert isinstance(data, list)
        # Assuming SHAPEFILE_DISTRICT_MAPPING might not map "Test District" or "Another District"
        # We just verify it returns a valid JSON array.
