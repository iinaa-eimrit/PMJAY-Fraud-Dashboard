# Validate input → call service → return JSON.
# No business logic here.

import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services import (
    issue_notice_bulk,
    send_reminder_1,
    send_reminder_2,
    close_notice,
    mark_expired,
    get_summary,
    get_notices_page,
)
from .selectors import get_notice, list_audit_logs, timing_bypass_enabled

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Issue notices (from the dashboard ophthalmology card)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def send_show_cause(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    hospital_ids      = data.get('hospitals', [])
    start_date        = data.get('start_date', '').strip()
    end_date          = data.get('end_date', '').strip()
    violation_counts  = data.get('violation_counts', {})   # NEW

    if not hospital_ids:
        return JsonResponse({'error': 'No hospitals provided.'}, status=400)
    if not start_date or not end_date:
        return JsonResponse({'error': 'start_date and end_date are required.'}, status=400)

    from .services import issue_notice_bulk
    results = issue_notice_bulk(
        hospital_ids=hospital_ids,
        start_date=start_date,
        end_date=end_date,
        issued_by=request.user.username,
        violation_counts=violation_counts,
    )

    return JsonResponse({
        'message': (
            f"{len(results['issued'])} notice(s) issued. "
            f"{len(results['already_existed'])} already existed. "
            f"{len(results['errors'])} error(s)."
        ),
        'results': results,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Management page (renders the HTML shell — data loaded via AJAX)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def management_page(request):
    return render(request, 'show_cause_management.html', {
        'active_page': 'show_cause',
        'bypass_timing_active': timing_bypass_enabled(),
    })


# ─────────────────────────────────────────────────────────────────────────────
# List notices API (management page table)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_GET
def list_notices(request):
    status    = request.GET.get('status', '').strip() or None
    search    = request.GET.get('search', '').strip() or None
    district  = request.GET.get('district', '').strip() or None
    page_size = min(int(request.GET.get('page_size', 25)), 100)
    page      = max(int(request.GET.get('page', 1)), 1)

    result = get_notices_page(
        status=status,
        search=search,
        district=district,
        page=page,
        page_size=page_size,
    )
    return JsonResponse(result)


# ─────────────────────────────────────────────────────────────────────────────
# Audit log for a single notice
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_GET
def notice_audit_log(request, notice_id):
    notice = get_notice(notice_id)
    if notice is None:
        return JsonResponse({'error': f'Notice {notice_id} not found.'}, status=404)

    return JsonResponse({
        'notice_id':    notice_id,
        'hospital_name': notice.hospital_name,
        'hospital_id':  notice.hospital_id,
        'logs':         list_audit_logs(notice_id),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle action endpoints
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def reminder_1(request, notice_id):
    result = send_reminder_1(notice_id=notice_id, performed_by=request.user.username)
    return JsonResponse(result, status=200 if result['ok'] else 400)


@login_required
@require_POST
def reminder_2(request, notice_id):
    result = send_reminder_2(notice_id=notice_id, performed_by=request.user.username)
    return JsonResponse(result, status=200 if result['ok'] else 400)


@login_required
@require_POST
def expire(request, notice_id):
    result = mark_expired(notice_id=notice_id, performed_by=request.user.username)
    return JsonResponse(result, status=200 if result['ok'] else 400)


@login_required
@require_POST
def close(request, notice_id):
    """
    POST /api/show-cause/<id>/close/
    Body:
    {
        "close_type":       "WARNING" | "PENALTY" | "SUSPENSION",
        "notes":            "(optional) officer remarks",
        "penalty_amount":   "50000"    (required for PENALTY),
        "suspension_until": "2026-06-30" | null  (optional for PENALTY, required for SUSPENSION)
    }
    """
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}

    close_type = data.get('close_type', 'WARNING').strip().upper()

    # Parse penalty_amount
    penalty_amount = None
    raw_amount = data.get('penalty_amount')
    if raw_amount not in (None, '', 'null'):
        from decimal import Decimal, InvalidOperation
        try:
            penalty_amount = Decimal(str(raw_amount))
        except InvalidOperation:
            return JsonResponse(
                {'error': f"Invalid penalty_amount: {raw_amount}"},
                status=400,
            )

    # Parse suspension_until
    suspension_until = None
    raw_susp = data.get('suspension_until')
    if raw_susp not in (None, '', 'null'):
        import datetime
        try:
            suspension_until = datetime.date.fromisoformat(str(raw_susp))
        except ValueError:
            return JsonResponse(
                {'error': f"Invalid suspension_until date: {raw_susp}. Use YYYY-MM-DD."},
                status=400,
            )

    result = close_notice(
        notice_id=notice_id,
        performed_by=request.user.username,
        close_type=close_type,
        notes=data.get('notes', ''),
        penalty_amount=penalty_amount,
        suspension_until=suspension_until,
    )
    return JsonResponse(result, status=200 if result['ok'] else 400)


@login_required
@require_GET
def summary(request):
    """GET /api/show-cause/summary/"""
    return JsonResponse(get_summary())