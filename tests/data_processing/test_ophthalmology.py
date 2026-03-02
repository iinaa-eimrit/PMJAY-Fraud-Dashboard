import pytest
import datetime
from django.urls import reverse
import json

@pytest.mark.data_processing
@pytest.mark.django_db
class TestOphthalmologyDataProcessing:
    """
    These tests cover the Pandas data transformations in the Ophthalmology module.
    They require a healthy Pandas/Numpy environment to run.
    """
    
    def test_get_ophthalmology_cases_api(self, client):
        # Even with an empty DB, the service should return the zeroed schema safely
        url = reverse('get_ophthalmology_cases')
        response = client.get(url)
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert "total" in data
        assert "age_under_40" in data
        assert "ot_cases" in data
        assert "preauth_time" in data
        assert "flagged_hospitals" in data

    def test_get_ophthalmology_details_api(self, client):
        url = reverse('ophth_details')
        response = client.get(url, {'type': 'all', 'page': 1})
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert "data" in data
        assert "pagination" in data
        
    def test_get_ophthalmology_distribution_api(self, client):
        url = reverse('ophth_distribution')
        response = client.get(url)
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert "districts" in data
        assert "counts" in data

    def test_get_ophthalmology_demographics_api(self, client):
        url = reverse('ophth_demographics', args=['age'])
        response = client.get(url)
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert "labels" in data
        assert "data" in data
        assert "colors" in data
