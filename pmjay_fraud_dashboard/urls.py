from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('pmjay_fraud_dashboard_app.urls')),
    path('api/show-cause/', include('pmjay_fraud_dashboard_show_cause_engine.urls')),
    path('show-cause/', include('pmjay_fraud_dashboard_show_cause_engine.urls')),
    path('penalty/', include('pmjay_fraud_dashboard_penalty_engine.urls')),
    path('api/penalty/', include('pmjay_fraud_dashboard_penalty_engine.urls')),
    path('health/', include('pmjay_fraud_dashboard_app.features.health.urls')),
]
