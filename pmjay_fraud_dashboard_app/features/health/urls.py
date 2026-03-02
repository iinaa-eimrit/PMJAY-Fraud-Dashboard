from django.urls import path
from . import views

urlpatterns = [
    path('live', views.liveness_check, name='health_live'),
    path('ready', views.readiness_check, name='health_ready'),
]
