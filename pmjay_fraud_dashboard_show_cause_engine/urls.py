# Full replacement of the previous version — adds notices/, audit-log/, expire/

from django.urls import path
from . import views

urlpatterns = [
    # ── Issue notices (from dashboard ophthalmology card) ──────────────────
    path('send/', views.send_show_cause, name='show_cause_send'),

    # ── Management page (HTML) ─────────────────────────────────────────────
    # Renders the management page shell; data loaded via AJAX to routes below.
    path('management/', views.management_page, name='show_cause_management'),

    # ── Management page data API ───────────────────────────────────────────
    path('notices/',                    views.list_notices,      name='show_cause_list'),
    path('<int:notice_id>/audit-log/',  views.notice_audit_log,  name='show_cause_audit_log'),
    path('summary/',                    views.summary,           name='show_cause_summary'),

    # ── Lifecycle actions ──────────────────────────────────────────────────
    path('<int:notice_id>/reminder-1/', views.reminder_1, name='show_cause_reminder_1'),
    path('<int:notice_id>/reminder-2/', views.reminder_2, name='show_cause_reminder_2'),
    path('<int:notice_id>/expire/',     views.expire,     name='show_cause_expire'),
    path('<int:notice_id>/close/',      views.close,      name='show_cause_close'),
]