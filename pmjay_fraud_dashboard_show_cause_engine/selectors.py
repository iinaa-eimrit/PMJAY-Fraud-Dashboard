# Selectors: pure read-only query functions.
# No side effects. No state changes. Safe to call from anywhere.
#
# Pattern:
#   - get_*()       → return a single object or None
#   - list_*()      → return a QuerySet (lazy, caller decides pagination)
#   - serialize_*() → convert a model instance to a JSON-safe dict
#   - compute_*()   → derive calculated values from a model instance

import logging
from django.db.models import Q
from django.conf import settings
from django.utils import timezone

from .models import ShowCauseNotice, ShowCauseAuditLog
from .constants import ShowCauseStatus, FIRST_REMINDER_AFTER, SECOND_REMINDER_AFTER

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Dev bypass helper
# ─────────────────────────────────────────────────────────────────────────────

def timing_bypass_enabled() -> bool:
    """
    When True, the 7-day and 14-day timing windows are waived for actions.
    This allows officers to test the full lifecycle without waiting.

    Controlled by settings.SHOW_CAUSE_BYPASS_TIMING.
    Defaults to settings.DEBUG so it's on in local dev and off in production
    without any manual configuration change needed.

    To explicitly disable in dev:   SHOW_CAUSE_BYPASS_TIMING = False
    To explicitly enable in prod:   SHOW_CAUSE_BYPASS_TIMING = True  ← don't do this
    """
    return getattr(settings, 'SHOW_CAUSE_BYPASS_TIMING', getattr(settings, 'DEBUG', False))


# ─────────────────────────────────────────────────────────────────────────────
# Querysets
# ─────────────────────────────────────────────────────────────────────────────

def list_notices(
    status: str | None = None,
    search: str | None = None,
    district: str | None = None,
    order_by: str = '-issued_at',
):
    """
    Return a filtered, ordered QuerySet of ShowCauseNotices.
    Caller is responsible for slicing / paginating.

    Args:
        status:   Filter by ShowCauseStatus value (e.g. 'ISSUED'). None = all.
        search:   Case-insensitive search against hospital_id and hospital_name.
        district: Case-insensitive filter on district_name.
        order_by: Django ORM order_by string.
    """
    qs = ShowCauseNotice.objects.all()

    if status and status != 'ALL':
        qs = qs.filter(status=status)

    if district:
        qs = qs.filter(district_name__icontains=district)

    if search:
        qs = qs.filter(
            Q(hospital_id__icontains=search) |
            Q(hospital_name__icontains=search)
        )

    return qs.order_by(order_by)


def get_notice(notice_id: int) -> ShowCauseNotice | None:
    """Return a single notice by PK, or None if not found."""
    try:
        return ShowCauseNotice.objects.get(id=notice_id)
    except ShowCauseNotice.DoesNotExist:
        return None


def list_audit_logs(notice_id: int) -> list[dict]:
    """
    Return the full audit trail for a notice as a list of dicts.
    Ordered chronologically (oldest first).
    """
    action_labels = dict(ShowCauseAuditLog.ACTION_CHOICES)
    logs = ShowCauseAuditLog.objects.filter(notice_id=notice_id).order_by('performed_at')
    return [
        {
            'action':          log.action,
            'action_display':  action_labels.get(log.action, log.action),
            'performed_by':    log.performed_by,
            'performed_at':    log.performed_at.isoformat(),
            'performed_at_fmt': log.performed_at.strftime('%d %b %Y, %H:%M'),
            'notes':           log.notes,
        }
        for log in logs
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Computed actions — determines what an officer can do right now
# ─────────────────────────────────────────────────────────────────────────────

def compute_actions(notice: ShowCauseNotice) -> dict:
    """
    Returns a dict of booleans describing what actions are available,
    plus timing information for display in the UI.

    When timing_bypass_enabled() is True (i.e. DEBUG mode), the 7-day and
    14-day windows are waived. Status guards are always enforced.

    Keys:
        can_send_reminder_1  (bool)
        can_send_reminder_2  (bool)
        can_close            (bool)
        can_mark_expired     (bool)
        reminder_1_due_at    (ISO string | null) — when Rem 1 becomes available
        reminder_2_due_at    (ISO string | null) — when Rem 2 becomes available
        expiry_due_at        (ISO string | null) — 3 days after Rem 2
        days_until_reminder_1 (int | null)       — negative = overdue
        days_until_reminder_2 (int | null)       — negative = overdue
        days_until_expiry    (int | null)
        bypass_timing_active (bool)              — shown as a badge in dev
    """
    bypass = timing_bypass_enabled()
    now = timezone.now()

    # ── Reminder 1 availability ───────────────────────────────────────────────
    r1_due = notice.issued_at + FIRST_REMINDER_AFTER
    timing_ok_r1 = bypass or (now >= r1_due)
    can_r1 = (notice.status == ShowCauseStatus.ISSUED) and timing_ok_r1

    # ── Reminder 2 availability ───────────────────────────────────────────────
    r2_due = (notice.reminder_1_at + SECOND_REMINDER_AFTER) if notice.reminder_1_at else None
    timing_ok_r2 = bool(r2_due and (bypass or (now >= r2_due)))
    can_r2 = (
        notice.status == ShowCauseStatus.REMINDER_1_SENT
        and notice.reminder_1_at is not None
        and timing_ok_r2
    )

    # ── Expiry — 3 days after Reminder 2 ─────────────────────────────────────
    # Using a 3-day window as specified (separate from the 14-day SECOND_REMINDER_AFTER)
    from datetime import timedelta
    EXPIRY_AFTER_REMINDER_2 = timedelta(days=3)
    expiry_ref = notice.reminder_2_at or notice.reminder_1_at or notice.issued_at
    expiry_due = expiry_ref + EXPIRY_AFTER_REMINDER_2
    can_expire = (
        notice.status not in (ShowCauseStatus.CLOSED, ShowCauseStatus.EXPIRED)
        and (bypass or now >= expiry_due)
    )

    # ── Close — available from any active state ───────────────────────────────
    can_close = notice.can_close()

    # ── Days-until helpers (positive = future, negative = overdue) ────────────
    def days_until(dt) -> int | None:
        if dt is None:
            return None
        return (dt.date() - now.date()).days

    # Only surface relevant timing to the frontend
    d_r1 = days_until(r1_due) if notice.status == ShowCauseStatus.ISSUED else None
    d_r2 = days_until(r2_due) if notice.status == ShowCauseStatus.REMINDER_1_SENT else None
    d_exp = (
        days_until(expiry_due)
        if notice.status == ShowCauseStatus.REMINDER_2_SENT
        else None
    )

    return {
        'can_send_reminder_1':  can_r1,
        'can_send_reminder_2':  can_r2,
        'can_close':            can_close,
        'can_mark_expired':     can_expire,
        'reminder_1_due_at':    r1_due.isoformat(),
        'reminder_2_due_at':    r2_due.isoformat() if r2_due else None,
        'expiry_due_at':        expiry_due.isoformat(),
        'days_until_reminder_1': d_r1,
        'days_until_reminder_2': d_r2,
        'days_until_expiry':     d_exp,
        'bypass_timing_active': bypass,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Serializers
# ─────────────────────────────────────────────────────────────────────────────

def serialize_notice(notice: ShowCauseNotice) -> dict:
    """Convert a ShowCauseNotice instance to a JSON-safe dict for API responses."""
    now = timezone.now()
    return {
        'id':                    notice.pk,
        'hospital_id':           notice.hospital_id,
        'hospital_name':         notice.hospital_name,
        'hospital_email':        notice.hospital_email,
        'district_name':         notice.district_name or '',
        'analytics_start_date':  str(notice.analytics_start_date),
        'analytics_end_date':    str(notice.analytics_end_date),
        'status':                notice.status,
        'status_display':        notice.get_status_display(),  # type: ignore[attr-defined]
        'issued_at':             notice.issued_at.isoformat(),
        'issued_at_fmt':         notice.issued_at.strftime('%d %b %Y'),
        'reminder_1_at':         notice.reminder_1_at.isoformat() if notice.reminder_1_at else None,
        'reminder_1_at_fmt':     notice.reminder_1_at.strftime('%d %b %Y') if notice.reminder_1_at else None,
        'reminder_2_at':         notice.reminder_2_at.isoformat() if notice.reminder_2_at else None,
        'reminder_2_at_fmt':     notice.reminder_2_at.strftime('%d %b %Y') if notice.reminder_2_at else None,
        'closed_at':             notice.closed_at.isoformat() if notice.closed_at else None,
        'closed_at_fmt':         notice.closed_at.strftime('%d %b %Y') if notice.closed_at else None,
        'days_since_issued':     (now - notice.issued_at).days,
        'created_by':            notice.created_by,
        'actions':               compute_actions(notice),
    }