import logging
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import PenaltyCase, PenaltyAuditLog, PenaltyStatus, PenaltyType
from .selectors import list_penalties, serialize_penalty

logger = logging.getLogger(__name__)

# BSSS signatory block — mirrors the show cause engine
_SIGNATORY_NAME  = "Shailesh Chandra Diwakar, B.A.S"
_SIGNATORY_TITLE = "Administrative Officer"
_SIGNATORY_ORG   = "Bihar Swasthya Suraksha Samiti (BSSS), Patna"


# ─────────────────────────────────────────────────────────────────────────────
# Email transport (best-effort, isolated)
# ─────────────────────────────────────────────────────────────────────────────

def _send_email(hospital_email: str, subject: str, body: str) -> bool:
    """Send an email. Returns True on success, False on failure. Never raises."""
    if not hospital_email:
        logger.warning("_send_email: empty recipient — skipping.")
        return False
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[hospital_email],
            fail_silently=False,
        )
        return True
    except Exception as exc:
        logger.error("Penalty email failed to %s: %s", hospital_email, exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Email body builders
# ─────────────────────────────────────────────────────────────────────────────

def _build_warning_email(hospital_name: str, hospital_id: str) -> str:
    today = timezone.now().strftime('%d/%m/%Y')
    return "\n".join([
        "To,",
        "The Director / Proprietor,",
        f"{hospital_name}",
        f"({hospital_id})",
        "",
        "Subject: Formal Warning - Closure of Show Cause Notice under PMJAY",
        "",
        "Sir / Ma'am,",
        "",
        "This is to inform you that the Show Cause Notice issued to your hospital "
        "under the Ayushman Bharat Pradhan Mantri Jan Arogya Yojana (PMJAY) has "
        "been reviewed and is hereby closed.",
        "",
        "However, please be advised that this closure is being effected with a "
        "FORMAL WARNING. Your hospital's claim patterns have been found to contain "
        "anomalies that are inconsistent with scheme guidelines. While no punitive "
        "action is being imposed at this stage, please be advised that:",
        "",
        "  (i)  Your hospital's claims will continue to be monitored closely.",
        " (ii)  Any recurrence of similar anomalies will attract strict disciplinary "
        "action, including but not limited to imposition of financial penalties, "
        "suspension of empanelment, or debarment from the scheme.",
        "",
        "You are hereby directed to ensure strict compliance with all PMJAY claim "
        "submission guidelines with immediate effect.",
        "",
        "\tSincerely Yours,",
        "\tSd/-",
        f"{_SIGNATORY_NAME}",
        f"{_SIGNATORY_TITLE},",
        f"{_SIGNATORY_ORG}",
        "",
        f"Date: {today}",
    ])


def _build_penalty_email(
    hospital_name: str,
    hospital_id: str,
    penalty_amount: str,
    suspension_label: str,
) -> str:
    today = timezone.now().strftime('%d/%m/%Y')
    return "\n".join([
        "To,",
        "The Director / Proprietor,",
        f"{hospital_name}",
        f"({hospital_id})",
        "",
        "Subject: Order for Imposition of Financial Penalty — PMJAY Scheme Violations",
        "",
        "Sir / Madam,",
        "",
        "After due consideration of the Show Cause Notice proceedings and the "
        "response (or lack thereof) received from your hospital, this office has "
        "determined that a financial penalty is warranted for the violations of "
        "PMJAY claim submission guidelines.",
        "",
        "You are hereby informed of the following:",
        "",
        f"  (i)  Penalty Amount Imposed   : INR {penalty_amount}/-",
        f" (ii)  Suspension Period        : {suspension_label}",
        "",
        "The imposed penalty must be deposited to the BSSS designated account "
        "within 30 (thirty) days from the date of this notice, along with a "
        "payment confirmation submitted to this office via email and registered post.",
        "",
        "Your hospital's empanelment status shall remain under the suspension order "
        f"as specified above. Re-instatement of full empanelment will be considered "
        "only after:",
        "  (a) Full payment of the imposed penalty has been confirmed, and",
        "  (b) Satisfactory compliance with PMJAY claim guidelines has been demonstrated.",
        "",
        "Failure to comply with this order within the specified period may result in "
        "permanent debarment from the PMJAY scheme.",
        "",
        "\tSincerely Yours,",
        "\tSd/-",
        f"{_SIGNATORY_NAME}",
        f"{_SIGNATORY_TITLE},",
        f"{_SIGNATORY_ORG}",
        "",
        f"Date: {today}",
    ])


def _build_suspension_email(
    hospital_name: str,
    hospital_id: str,
    suspension_label: str,
) -> str:
    today = timezone.now().strftime('%d/%m/%Y')
    return "\n".join([
        "To,",
        "The Director / Proprietor,",
        f"{hospital_name}",
        f"({hospital_id})",
        "",
        "Subject: Order of Suspension of Empanelment — PMJAY Scheme",
        "",
        "Sir / Madam,",
        "",
        "After due consideration of the Show Cause Notice proceedings and having "
        "found the violations of PMJAY scheme guidelines to be of a serious nature, "
        "this office hereby issues the following ORDER OF SUSPENSION:",
        "",
        f"  Suspension Period: {suspension_label}",
        "",
        "With immediate effect from the date of this notice, your hospital's "
        "empanelment under the Ayushman Bharat Pradhan Mantri Jan Arogya Yojana "
        "(PMJAY) scheme is hereby SUSPENDED for the period stated above.",
        "",
        "During the suspension period:",
        "  (i)  No new pre-authorisation requests shall be processed.",
        " (ii)  No new claims shall be admitted or processed.",
        "(iii)  Existing in-patient cases may be completed subject to individual "
        "review by this office.",
        "",
        "Any attempt to submit claims during the suspension period will be treated "
        "as a further violation and may result in permanent debarment.",
        "",
        "You may appeal this order in writing to the Chief Executive Officer, BSSS, "
        "within 15 (fifteen) days of receipt of this notice.",
        "",
        "\tSincerely Yours,",
        "\tSd/-",
        f"{_SIGNATORY_NAME}",
        f"{_SIGNATORY_TITLE},",
        f"{_SIGNATORY_ORG}",
        "",
        f"Date: {today}",
    ])


def _build_penalty_reminder_email(
    hospital_name: str,
    hospital_id: str,
    penalty_amount: str | None,
    suspension_label: str,
    imposed_date: str,
) -> str:
    today = timezone.now().strftime('%d/%m/%Y')
    amount_line = (
        f"  Penalty Amount Due : INR {penalty_amount}/-\n" if penalty_amount else ""
    )
    return "\n".join([
        "To,",
        "The Director / Proprietor,",
        f"{hospital_name}",
        f"({hospital_id})",
        "",
        "Subject: Reminder — Non-Compliance with Penalty / Suspension Order | PMJAY",
        "",
        "Sir / Madam,",
        "",
        f"This is a formal reminder that as per the penalty / suspension order "
        f"issued on {imposed_date}, the following obligations remain outstanding:",
        "",
        f"{amount_line}  Suspension Period  : {suspension_label}",
        "",
        "As of the date of this notice, your hospital has not provided evidence "
        "of compliance with the above order. You are hereby directed to regularise "
        "your status immediately.",
        "",
        "Continued non-compliance will result in this matter being escalated to "
        "higher authorities and may lead to permanent debarment from the PMJAY scheme.",
        "",
        "\tSincerely Yours,",
        "\tSd/-",
        f"{_SIGNATORY_NAME}",
        f"{_SIGNATORY_TITLE},",
        f"{_SIGNATORY_ORG}",
        "",
        f"Date: {today}",
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Create a PenaltyCase from a Show Cause close action
# ─────────────────────────────────────────────────────────────────────────────

def create_penalty_case(
    show_cause_notice_id: int,
    hospital_id: str,
    hospital_name: str,
    hospital_email: str,
    district_name: str,
    state_name: str,
    penalty_type: str,                     # 'PENALTY' | 'SUSPENSION'
    created_by: str,
    penalty_amount=None,                   # Decimal | None
    suspension_until=None,                 # date | None
    notes: str = '',
    send_email: bool = True,               # Set False when caller already sent the email
) -> PenaltyCase:
    """
    Create a PenaltyCase record and (optionally) send the appropriate email.
    Pass send_email=False when the caller (e.g. close_notice) has already sent
    the closure email, to prevent the hospital receiving two copies.
    Returns the created PenaltyCase.
    """
    with transaction.atomic():
        penalty = PenaltyCase.objects.create(
            show_cause_notice_id=show_cause_notice_id,
            hospital_id=hospital_id,
            hospital_name=hospital_name,
            hospital_email=hospital_email,
            district_name=district_name,
            state_name=state_name,
            penalty_type=penalty_type,
            penalty_amount=penalty_amount,
            suspension_until=suspension_until,
            status=PenaltyStatus.ACTIVE,
            created_by=created_by,
            notes=notes,
        )
        PenaltyAuditLog.objects.create(
            penalty=penalty,
            action='IMPOSED',
            performed_by=created_by,
            notes=notes,
        )

    # Send email outside transaction — failure is non-fatal.
    # Skipped when send_email=False (caller already sent the closure email).
    if send_email:
        if penalty_type == PenaltyType.SUSPENSION:
            subject = "Suspension Order — PMJAY Scheme | BSSS"
            body = _build_suspension_email(
                hospital_name=hospital_name,
                hospital_id=hospital_id,
                suspension_label=penalty.suspension_label,
            )
        else:
            subject = "Penalty Imposition Order — PMJAY Scheme | BSSS"
            body = _build_penalty_email(
                hospital_name=hospital_name,
                hospital_id=hospital_id,
                penalty_amount=str(penalty_amount) if penalty_amount else 'N/A',
                suspension_label=penalty.suspension_label,
            )

        email_sent = _send_email(hospital_email, subject, body)
        if not email_sent and hospital_email:
            PenaltyAuditLog.objects.create(
                penalty=penalty,
                action='EMAIL_FAILED',
                performed_by=created_by,
                notes='Email send failed at creation.',
            )

    return penalty


# ─────────────────────────────────────────────────────────────────────────────
# Reminder notice
# ─────────────────────────────────────────────────────────────────────────────

def send_penalty_reminder(penalty_id: int, performed_by: str) -> dict:
    """Send a formal non-compliance reminder for a penalty case."""
    try:
        penalty = PenaltyCase.objects.get(id=penalty_id)
    except PenaltyCase.DoesNotExist:
        return {'ok': False, 'error': f"Penalty {penalty_id} not found."}

    if not penalty.can_send_reminder():
        return {
            'ok': False,
            'error': f"Cannot send reminder. Status is already terminal: {penalty.status}",
        }

    with transaction.atomic():
        penalty.status = PenaltyStatus.REMINDER_SENT
        penalty.reminder_at = timezone.now()
        penalty.save(update_fields=['status', 'reminder_at'])
        PenaltyAuditLog.objects.create(
            penalty=penalty,
            action='REMINDER_SENT',
            performed_by=performed_by,
            notes='Formal non-compliance reminder issued.',
        )

    body = _build_penalty_reminder_email(
        hospital_name=penalty.hospital_name,
        hospital_id=penalty.hospital_id,
        penalty_amount=str(penalty.penalty_amount) if penalty.penalty_amount else None,
        suspension_label=penalty.suspension_label,
        imposed_date=penalty.imposed_at.strftime('%d/%m/%Y'),
    )
    email_sent = _send_email(
        penalty.hospital_email,
        "Reminder: Non-Compliance with Penalty / Suspension Order | BSSS",
        body,
    )
    if not email_sent and penalty.hospital_email:
        PenaltyAuditLog.objects.create(
            penalty=penalty,
            action='EMAIL_FAILED',
            performed_by=performed_by,
            notes='Reminder email failed.',
        )

    return {'ok': True, 'error': None, 'penalty': serialize_penalty(penalty)}


# ─────────────────────────────────────────────────────────────────────────────
# Mark as paid
# ─────────────────────────────────────────────────────────────────────────────

def mark_penalty_paid(penalty_id: int, performed_by: str, notes: str = '') -> dict:
    """Mark a penalty as paid. Only valid when a monetary penalty exists."""
    try:
        penalty = PenaltyCase.objects.get(id=penalty_id)
    except PenaltyCase.DoesNotExist:
        return {'ok': False, 'error': f"Penalty {penalty_id} not found."}

    if not penalty.can_mark_paid():
        return {
            'ok': False,
            'error': (
                "Cannot mark as paid: either no penalty amount is set, "
                f"or status is already terminal ({penalty.status})."
            ),
        }

    with transaction.atomic():
        penalty.status = PenaltyStatus.PAID
        penalty.resolved_at = timezone.now()
        penalty.save(update_fields=['status', 'resolved_at'])
        PenaltyAuditLog.objects.create(
            penalty=penalty,
            action='MARKED_PAID',
            performed_by=performed_by,
            notes=notes or 'Penalty amount confirmed as received.',
        )

    return {'ok': True, 'error': None, 'penalty': serialize_penalty(penalty)}


# ─────────────────────────────────────────────────────────────────────────────
# Mark as non-compliant
# ─────────────────────────────────────────────────────────────────────────────

def mark_penalty_non_compliant(penalty_id: int, performed_by: str, notes: str = '') -> dict:
    """Flag a penalty case as non-compliant after reminders go unanswered."""
    try:
        penalty = PenaltyCase.objects.get(id=penalty_id)
    except PenaltyCase.DoesNotExist:
        return {'ok': False, 'error': f"Penalty {penalty_id} not found."}

    if not penalty.can_mark_non_compliant():
        return {
            'ok': False,
            'error': (
                f"Cannot mark non-compliant. "
                f"Status is already: {penalty.status}"
            ),
        }

    with transaction.atomic():
        penalty.status = PenaltyStatus.NON_COMPLIANT
        penalty.save(update_fields=['status'])
        PenaltyAuditLog.objects.create(
            penalty=penalty,
            action='MARKED_NON_COMPLIANT',
            performed_by=performed_by,
            notes=notes or 'Hospital has not complied with penalty / suspension order.',
        )

    return {'ok': True, 'error': None, 'penalty': serialize_penalty(penalty)}


# ─────────────────────────────────────────────────────────────────────────────
# Close penalty case
# ─────────────────────────────────────────────────────────────────────────────

def close_penalty_case(penalty_id: int, performed_by: str, notes: str = '') -> dict:
    """Close a penalty record. Available from any non-terminal state."""
    try:
        penalty = PenaltyCase.objects.get(id=penalty_id)
    except PenaltyCase.DoesNotExist:
        return {'ok': False, 'error': f"Penalty {penalty_id} not found."}

    if not penalty.can_close():
        return {
            'ok': False,
            'error': f"Penalty is already in terminal state: {penalty.status}",
        }

    with transaction.atomic():
        penalty.status = PenaltyStatus.CLOSED
        penalty.closed_at = timezone.now()
        penalty.save(update_fields=['status', 'closed_at'])
        PenaltyAuditLog.objects.create(
            penalty=penalty,
            action='CLOSED',
            performed_by=performed_by,
            notes=notes,
        )

    return {'ok': True, 'error': None, 'penalty': serialize_penalty(penalty)}


# ─────────────────────────────────────────────────────────────────────────────
# Paginated list (management page API)
# ─────────────────────────────────────────────────────────────────────────────

def get_penalties_page(
    status: str | None = None,
    penalty_type: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    """Return a paginated, serialized list of penalties."""
    qs = list_penalties(status=status, penalty_type=penalty_type, search=search)
    total = qs.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size

    return {
        'penalties':    [serialize_penalty(p) for p in qs[offset: offset + page_size]],
        'total':        total,
        'page':         page,
        'page_size':    page_size,
        'total_pages':  total_pages,
        'has_next':     page < total_pages,
        'has_previous': page > 1,
    }