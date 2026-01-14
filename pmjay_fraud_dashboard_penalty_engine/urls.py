from django.urls import path
from . import views

app_name = 'pmjay_fraud_dashboard_penalty_engine'

# Mount under: path('penalty/', include('pmjay_fraud_dashboard_penalty_engine.urls'))
# in your project's root urls.py

urlpatterns = [
    # ── Management page (HTML shell) ───────────────────────────────────────
    path('management/',                     views.management_page,      name='penalty_management'),

    # ── Data API ───────────────────────────────────────────────────────────
    path('api/cases/',                      views.list_penalties_view,  name='penalty_list'),
    path('api/summary/',                    views.summary,              name='penalty_summary'),
    path('api/export/',                     views.export_excel,         name='penalty_export'),
    path('api/<int:penalty_id>/audit-log/', views.penalty_audit_log,    name='penalty_audit_log'),

    # ── Lifecycle actions ──────────────────────────────────────────────────
    path('api/<int:penalty_id>/reminder/',       views.reminder,             name='penalty_reminder'),
    path('api/<int:penalty_id>/mark-paid/',      views.mark_paid,            name='penalty_mark_paid'),
    path('api/<int:penalty_id>/non-compliant/',  views.mark_non_compliant,   name='penalty_non_compliant'),
    path('api/<int:penalty_id>/close/',          views.close,                name='penalty_close'),
]