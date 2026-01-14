"""
Selectors: pure read-only query functions for PenaltyCases.
No side effects. Safe to call from anywhere.
"""

import logging
from django.db.models import Q
from django.utils import timezone

from .models import PenaltyCase, PenaltyAuditLog, PenaltyStatus, PenaltyType

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Single-object lookups
# ─────────────────────────────────────────────────────────────────────────────

def get_penalty(penalty_id: int) -> PenaltyCase | None:
    """Return a single PenaltyCase by PK, or None if not found."""
    try:
        return PenaltyCase.objects.get(id=penalty_id)
    except PenaltyCase.DoesNotExist:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Filtered querysets
# ─────────────────────────────────────────────────────────────────────────────

def list_penalties(
    status: str | None = None,
    penalty_type: str | None = None,
    search: str | None = None,
    order_by: str = '-imposed_at',
):
    """
    Return a filtered, ordered QuerySet of PenaltyCases.
    Caller is responsible for slicing / paginating.
    """
    qs = PenaltyCase.objects.all()

    if status and status != 'ALL':
        qs = qs.filter(status=status)

    if penalty_type and penalty_type != 'ALL':
        qs = qs.filter(penalty_type=penalty_type)

    if search:
        qs = qs.filter(
            Q(hospital_id__icontains=search) |
            Q(hospital_name__icontains=search)
        )

    return qs.order_by(order_by)


# ─────────────────────────────────────────────────────────────────────────────
# Audit logs
# ─────────────────────────────────────────────────────────────────────────────

def list_penalty_audit_logs(penalty_id: int) -> list[dict]:
    """Return the full audit trail for a penalty as a list of dicts."""
    action_labels = dict(PenaltyAuditLog.ACTION_CHOICES)
    logs = PenaltyAuditLog.objects.filter(penalty_id=penalty_id).order_by('performed_at')
    return [
        {
            'action':           log.action,
            'action_display':   action_labels.get(log.action, log.action),
            'performed_by':     log.performed_by,
            'performed_at':     log.performed_at.isoformat(),
            'performed_at_fmt': log.performed_at.strftime('%d %b %Y, %H:%M'),
            'notes':            log.notes,
        }
        for log in logs
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Summary counts
# ─────────────────────────────────────────────────────────────────────────────

def get_penalty_summary() -> dict:
    """Returns counts for the penalty summary stat cards."""
    return {
        'active':          PenaltyCase.objects.filter(status=PenaltyStatus.ACTIVE).count(),
        'reminder_sent':   PenaltyCase.objects.filter(status=PenaltyStatus.REMINDER_SENT).count(),
        'non_compliant':   PenaltyCase.objects.filter(status=PenaltyStatus.NON_COMPLIANT).count(),
        'paid':            PenaltyCase.objects.filter(status=PenaltyStatus.PAID).count(),
        'closed':          PenaltyCase.objects.filter(status=PenaltyStatus.CLOSED).count(),
        'total':           PenaltyCase.objects.count(),
        'by_type': {
            'penalty':    PenaltyCase.objects.filter(penalty_type=PenaltyType.PENALTY).count(),
            'suspension': PenaltyCase.objects.filter(penalty_type=PenaltyType.SUSPENSION).count(),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Serializers
# ─────────────────────────────────────────────────────────────────────────────

def serialize_penalty(p: PenaltyCase) -> dict:
    """Convert a PenaltyCase to a JSON-safe dict for API responses."""
    return {
        'id':                   p.pk,
        'show_cause_notice_id': p.show_cause_notice_id,
        'hospital_id':          p.hospital_id,
        'hospital_name':        p.hospital_name,
        'hospital_email':       p.hospital_email,
        'district_name':        p.district_name,
        'state_name':           p.state_name,
        'penalty_type':         p.penalty_type,
        'penalty_type_display': p.get_penalty_type_display(),  # type: ignore[attr-defined]
        'penalty_amount':       str(p.penalty_amount) if p.penalty_amount is not None else None,
        'suspension_until':     str(p.suspension_until) if p.suspension_until else None,
        'suspension_label':     p.suspension_label,
        'status':               p.status,
        'status_display':       p.get_status_display(),  # type: ignore[attr-defined]
        'imposed_at':           p.imposed_at.isoformat(),
        'imposed_at_fmt':       p.imposed_at.strftime('%d %b %Y'),
        'reminder_at':          p.reminder_at.isoformat() if p.reminder_at else None,
        'reminder_at_fmt':      p.reminder_at.strftime('%d %b %Y') if p.reminder_at else None,
        'resolved_at':          p.resolved_at.isoformat() if p.resolved_at else None,
        'notes':                p.notes,
        'created_by':           p.created_by,
        'actions': {
            'can_send_reminder':       p.can_send_reminder(),
            'can_mark_paid':           p.can_mark_paid(),
            'can_mark_non_compliant':  p.can_mark_non_compliant(),
            'can_close':               p.can_close(),
        },
    }