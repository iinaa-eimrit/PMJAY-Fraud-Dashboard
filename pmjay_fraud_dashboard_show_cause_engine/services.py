import logging
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import ShowCauseNotice, ShowCauseAuditLog
from .constants import (
    ShowCauseStatus,
    FIRST_REMINDER_AFTER,
    SECOND_REMINDER_AFTER,
    EXPIRY_AFTER_REMINDER_2,   # ← imported from constants, not defined locally
)
from .selectors import (
    timing_bypass_enabled,
    list_notices,
    serialize_notice,
    list_audit_logs,
)

logger = logging.getLogger(__name__)

# Signatory is fixed per the official BSSS letterhead format
_SIGNATORY_NAME  = "Shailesh Chandra Diwakar, B.A.S"
_SIGNATORY_TITLE = "Administrative Officer"
_SIGNATORY_ORG   = "Bihar Swasthya Suraksha Samiti (BSSS), Patna"

RUPEE = '\u20b9'  # ₹


def _amount_in_words(n_str: str) -> str:
    """Convert a rupee amount string to Indian number words (Lakh/Crore system)."""
    try:
        n = int(float(n_str))
    except Exception:
        return n_str
    if n == 0:
        return 'Zero'
    ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
            'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
            'Seventeen', 'Eighteen', 'Nineteen']
    tw   = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']

    def two(m: int) -> str:
        return ones[m] if m < 20 else (tw[m // 10] + (' ' + ones[m % 10] if m % 10 else '')).strip()

    def three(m: int) -> str:
        return (ones[m // 100] + ' Hundred' + (' ' + two(m % 100) if m % 100 else '')) if m >= 100 else two(m)

    parts: list[str] = []
    cr = n // 10_000_000; n %= 10_000_000
    lk = n // 100_000;    n %= 100_000
    th = n // 1_000;      n %= 1_000
    if cr: parts.append(three(cr) + ' Crore')
    if lk: parts.append(two(lk) + ' Lakh')
    if th: parts.append(two(th) + ' Thousand')
    if n:  parts.append(three(n))
    return ' '.join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Email transport (best-effort, isolated)
# ─────────────────────────────────────────────────────────────────────────────

def send_show_cause_email(hospital_email: str, subject: str, body: str) -> bool:
    """Send an email. Returns True on success, False on failure. Never raises."""
    if not hospital_email:
        logger.warning("send_show_cause_email: empty email address — skipping.")
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
        logger.error("Email send failed to %s: %s", hospital_email, exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Email body builder — BSSS formal letterhead format
# ─────────────────────────────────────────────────────────────────────────────

def _build_email_body(
    hospital_name: str,
    hospital_id: str,
    start_date: str,
    end_date: str,
    notice_type: str = 'SHOW_CAUSE',
    age_count: int | None = None,
    ot_count: int | None = None,
    preauth_count: int | None = None,
    original_issue_date: str = '',
) -> str:
    """
    Builds the formal BSSS-style email body adapted from the official template.

    Args:
        hospital_name:       Full name of the hospital
        hospital_id:         Hospital identifier code
        start_date:          Analytics period start (YYYY-MM-DD)
        end_date:            Analytics period end (YYYY-MM-DD)
        notice_type:         'SHOW_CAUSE' | 'REMINDER_1' | 'REMINDER_2'
        age_count:           Number of Age < 40 violations (None if unavailable)
        ot_count:            Number of OT time violations (None if unavailable)
        preauth_count:       Number of pre-auth time violations (None if unavailable)
        original_issue_date: Formatted date the original notice was issued (for reminders)

    Returns:
        Plain-text email body string.
    """
    today = timezone.now().strftime('%d/%m/%Y')
    has_counts = any(c is not None for c in [age_count, ot_count, preauth_count])
    total = (age_count or 0) + (ot_count or 0) + (preauth_count or 0)

    # ── Violation count block ─────────────────────────────────────────────
    violation_lines = []
    if age_count is not None:
        violation_lines.append(
            f"     (i) Patient age below 40 years             : {age_count} case(s)"
        )
    if ot_count is not None:
        violation_lines.append(
            f"    (ii) OT time violation                      : {ot_count} case(s)"
        )
    if preauth_count is not None:
        violation_lines.append(
            f"   (iii) Pre-authorisation time violation       : {preauth_count} case(s)"
        )
    if has_counts:
        violation_lines.append(
            f"\n         Total flagged cases                     : {total}"
        )
    violation_block = "\n".join(violation_lines)

    # ── Notice-type-specific content ──────────────────────────────────────
    if notice_type == 'SHOW_CAUSE':
        subject_display = (
            "Show Cause Notice - Discrepancy in Ophthalmology Claims under PMJAY"
        )
        if has_counts:
            observation = (
                f"It has been observed from the TMS records under Ayushman Bharat "
                f"Pradhan Mantri Jan Arogya Yojana during the period {start_date} to "
                f"{end_date} that your hospital has been flagged for anomalies in "
                f"Ophthalmology claims as detailed below:\n\n{violation_block}"
            )
        else:
            observation = (
                f"It has been observed from the TMS records under Ayushman Bharat "
                f"Pradhan Mantri Jan Arogya Yojana during the period {start_date} to "
                f"{end_date} that your hospital has been flagged for anomalies in "
                f"Ophthalmology claims under PMJAY guidelines."
            )
        direction = (
            "You are hereby directed to submit a complete and accurate explanation "
            "regarding the above observations, duly supported by relevant documents, "
            "within 07 (seven) days from the date of receipt of this notice. "
            "Your response must be submitted both via email and through registered "
            "post to the specified postal address."
        )
        consequence = (
            "Failure to provide satisfactory clarification may lead to appropriate "
            "action as per scheme guidelines."
        )

    elif notice_type == 'REMINDER_1':
        subject_display = (
            "Reminder: Show Cause Notice — Ophthalmology Claims under PMJAY"
        )
        ref_date = original_issue_date or start_date
        if has_counts:
            observation = (
                f"This is a reminder that your Show Cause Notice dated {ref_date} "
                f"regarding Ophthalmology claim anomalies for the period {start_date} "
                f"to {end_date} remains unresponded. The flagged violations are "
                f"reproduced below for reference:\n\n{violation_block}"
            )
        else:
            observation = (
                f"This is a reminder that your Show Cause Notice dated {ref_date} "
                f"regarding Ophthalmology claim anomalies for the period {start_date} "
                f"to {end_date} remains unresponded."
            )
        direction = (
            "You are once again directed to submit your explanation with supporting "
            "documents immediately."
        )
        consequence = (
            "This is a formal reminder. Continued non-compliance will be treated as "
            "an admission of the stated observations."
        )

    else:  # REMINDER_2
        subject_display = (
            "Final Reminder: Show Cause Notice — Ophthalmology Claims under PMJAY"
        )
        ref_date = original_issue_date or start_date
        if has_counts:
            observation = (
                f"This is your FINAL reminder regarding the Show Cause Notice "
                f"dated {ref_date} concerning Ophthalmology claim anomalies for the "
                f"period {start_date} to {end_date}. Your response has not been "
                f"received to date. The flagged violations are reproduced for "
                f"reference:\n\n{violation_block}"
            )
        else:
            observation = (
                f"This is your FINAL reminder regarding the Show Cause Notice "
                f"dated {ref_date} concerning Ophthalmology claim anomalies for the "
                f"period {start_date} to {end_date}. Your response has not been "
                f"received to date."
            )
        direction = (
            "You are directed to respond IMMEDIATELY. Failure to provide satisfactory "
            "clarification will result in this matter being escalated and appropriate "
            "action taken as per PMJAY scheme guidelines, which may include suspension "
            "of empanelment."
        )
        consequence = (
            "This is the final opportunity to provide your response before escalation."
        )

    # ── Assemble full body ────────────────────────────────────────────────
    body = "\n".join([
        f"To,",
        f"The Director / Proprietor,",
        f"{hospital_name}",
        f"({hospital_id})",
        f"",
        f"Subject: {subject_display}",
        f"",
        f"Sir / Madam,",
        f"",
        observation,
        f"",
        direction,
        f"",
        consequence,
        f"",
        f"\tSincerely Yours,",
        f"\tSd/-",
        f"{_SIGNATORY_NAME}",
        f"{_SIGNATORY_TITLE},",
        f"{_SIGNATORY_ORG}",
        f"",
        f"Date: {today}",
    ])
    return body


# ─────────────────────────────────────────────────────────────────────────────
# Issue notices — bulk
# ─────────────────────────────────────────────────────────────────────────────

def issue_notice_bulk(
    hospital_ids: list,
    start_date: str,
    end_date: str,
    issued_by: str,
    violation_counts: dict | None = None,
) -> dict:
    """
    Issue Show Cause Notices for a list of hospital IDs.

    Args:
        hospital_ids:     List of hospital ID strings.
        start_date:       Analytics period start (YYYY-MM-DD).
        end_date:         Analytics period end (YYYY-MM-DD).
        issued_by:        Username of the officer issuing the notice.
        violation_counts: Optional dict mapping hospital_id → count dict.
                          Example:
                            {
                              "HOSP001": {
                                "age_violation_count":     12,
                                "ot_violation_count":       5,
                                "preauth_violation_count":  3,
                              }
                            }
                          If a hospital is absent from this dict, counts are
                          stored as NULL. The notice is still created; the
                          email will simply omit the per-violation breakdown.

    Returns:
        {
            'issued':          [hospital_ids],
            'already_existed': [hospital_ids],
            'errors':          [{'hospital_id': ..., 'reason': ...}]
        }
    """
    from pmjay_fraud_dashboard_app.models import HospitalBeds

    counts_map = violation_counts or {}
    results: dict = {'issued': [], 'already_existed': [], 'errors': []}
    issue_date_display = timezone.now().strftime('%d/%m/%Y')

    for hospital_id in hospital_ids:
        # ── Step 1: Look up hospital ──────────────────────────────────────
        try:
            hospital = HospitalBeds.objects.get(hospital_id=hospital_id)
        except HospitalBeds.DoesNotExist:
            logger.warning("Hospital %s not in HospitalBeds.", hospital_id)
            results['errors'].append({
                'hospital_id': hospital_id,
                'reason': (
                    'Hospital not found in HospitalBeds. '
                    'Upload the hospital beds list first.'
                ),
            })
            continue

        # ── Step 2: Extract per-hospital violation counts ─────────────────
        h_counts      = counts_map.get(hospital_id, {})
        age_count     = h_counts.get('age_violation_count')
        ot_count      = h_counts.get('ot_violation_count')
        preauth_count = h_counts.get('preauth_violation_count')

        # ── Step 3: Create notice + audit log atomically ──────────────────
        try:
            with transaction.atomic():
                notice, created = ShowCauseNotice.objects.get_or_create(
                    hospital_id=hospital_id,
                    analytics_start_date=start_date,
                    analytics_end_date=end_date,
                    defaults={
                        'hospital_name':           hospital.hospital_name or hospital_id,
                        'hospital_email':          hospital.hospital_email_id or '',
                        'district_name':           hospital.hospital_district or '',
                        'created_by':              issued_by,
                        'status':                  ShowCauseStatus.ISSUED,
                        'age_violation_count':     age_count,
                        'ot_violation_count':      ot_count,
                        'preauth_violation_count': preauth_count,
                    }
                )

                if not created:
                    results['already_existed'].append(hospital_id)
                    continue

                ShowCauseAuditLog.objects.create(
                    notice=notice,
                    action='ISSUED',
                    performed_by=issued_by,
                    notes=(
                        f"Analytics period: {start_date} to {end_date}. "
                        f"Violations — Age<40: {age_count}, "
                        f"OT: {ot_count}, Pre-auth: {preauth_count}."
                    ),
                )

        except Exception as exc:
            logger.error("DB error issuing notice for %s: %s", hospital_id, exc)
            results['errors'].append({
                'hospital_id': hospital_id,
                'reason': f"Database error: {exc}",
            })
            continue

        # ── Step 4: Send email (outside transaction — failure is non-fatal) ─
        body = _build_email_body(
            hospital_name=hospital.hospital_name or '',
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date,
            notice_type='SHOW_CAUSE',
            age_count=age_count,
            ot_count=ot_count,
            preauth_count=preauth_count,
            original_issue_date=issue_date_display,
        )
        email_sent = send_show_cause_email(
            hospital_email=hospital.hospital_email_id or '',
            subject="Show Cause Notice - Opthalmology Claims | PMJAY",
            body=body,
        )
        if not email_sent:
            ShowCauseAuditLog.objects.create(
                notice=notice,
                action='EMAIL_FAILED',
                performed_by=issued_by,
                notes='No valid email on record, or SMTP error.',
            )

        results['issued'].append(hospital_id)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Reminder 1
# ─────────────────────────────────────────────────────────────────────────────

def send_reminder_1(notice_id: int, performed_by: str) -> dict:
    """
    Send the first reminder for a notice.
    Status guard: notice must be ISSUED.
    Timing guard: issued_at + 7 days must have elapsed (waived if bypass enabled).
    """
    try:
        notice = ShowCauseNotice.objects.get(id=notice_id)
    except ShowCauseNotice.DoesNotExist:
        return {'ok': False, 'error': f"Notice {notice_id} not found."}

    if notice.status != ShowCauseStatus.ISSUED:
        return {
            'ok': False,
            'error': f"Reminder 1 requires status ISSUED. Current: {notice.status}",
        }

    if not timing_bypass_enabled():
        elapsed = timezone.now() - notice.issued_at
        if elapsed < FIRST_REMINDER_AFTER:
            days_remaining = (FIRST_REMINDER_AFTER - elapsed).days + 1
            return {
                'ok': False,
                'error': (
                    f"Too early for Reminder 1. "
                    f"{days_remaining} day(s) remaining until the "
                    f"{FIRST_REMINDER_AFTER.days}-day window opens."
                ),
            }

    with transaction.atomic():
        notice.status = ShowCauseStatus.REMINDER_1_SENT
        notice.reminder_1_at = timezone.now()
        notice.save(update_fields=['status', 'reminder_1_at'])
        ShowCauseAuditLog.objects.create(
            notice=notice,
            action='REMINDER_1_SENT',
            performed_by=performed_by,
            notes='Timing bypass active (dev mode).' if timing_bypass_enabled() else '',
        )

    body = _build_email_body(
        hospital_name=notice.hospital_name,
        hospital_id=notice.hospital_id,
        start_date=str(notice.analytics_start_date),
        end_date=str(notice.analytics_end_date),
        notice_type='REMINDER_1',
        age_count=notice.age_violation_count,
        ot_count=notice.ot_violation_count,
        preauth_count=notice.preauth_violation_count,
        original_issue_date=notice.issued_at.strftime('%d/%m/%Y'),
    )
    email_sent = send_show_cause_email(
        hospital_email=notice.hospital_email,
        subject="First Reminder — Show Cause Notice — Ophthalmology Claims | PMJAY",
        body=body,
    )
    if not email_sent:
        ShowCauseAuditLog.objects.create(
            notice=notice,
            action='EMAIL_FAILED',
            performed_by=performed_by,
            notes='Reminder 1 email failed.',
        )

    return {'ok': True, 'error': None, 'notice': serialize_notice(notice)}


# ─────────────────────────────────────────────────────────────────────────────
# Reminder 2
# ─────────────────────────────────────────────────────────────────────────────

def send_reminder_2(notice_id: int, performed_by: str) -> dict:
    """
    Send the second reminder.
    Status guard: notice must be REMINDER_1_SENT.
    Timing guard: reminder_1_at + 7 days must have elapsed (waived if bypass enabled).
    """
    try:
        notice = ShowCauseNotice.objects.get(id=notice_id)
    except ShowCauseNotice.DoesNotExist:
        return {'ok': False, 'error': f"Notice {notice_id} not found."}

    if notice.status != ShowCauseStatus.REMINDER_1_SENT:
        return {
            'ok': False,
            'error': (
                f"Reminder 2 requires status REMINDER_1_SENT. "
                f"Current: {notice.status}"
            ),
        }

    if not timing_bypass_enabled():
        if notice.reminder_1_at is None:
            return {
                'ok': False,
                'error': "reminder_1_at is missing — data integrity issue.",
            }
        elapsed = timezone.now() - notice.reminder_1_at
        if elapsed < SECOND_REMINDER_AFTER:
            days_remaining = (SECOND_REMINDER_AFTER - elapsed).days + 1
            return {
                'ok': False,
                'error': (
                    f"Too early for Reminder 2. "
                    f"{days_remaining} day(s) remaining until the "
                    f"{SECOND_REMINDER_AFTER.days}-day window opens."
                    # ↑ dynamically reads the constant — won't go stale if timing changes
                ),
            }

    with transaction.atomic():
        notice.status = ShowCauseStatus.REMINDER_2_SENT
        notice.reminder_2_at = timezone.now()
        notice.save(update_fields=['status', 'reminder_2_at'])
        ShowCauseAuditLog.objects.create(
            notice=notice,
            action='REMINDER_2_SENT',
            performed_by=performed_by,
            notes='Timing bypass active (dev mode).' if timing_bypass_enabled() else '',
        )

    body = _build_email_body(
        hospital_name=notice.hospital_name,
        hospital_id=notice.hospital_id,
        start_date=str(notice.analytics_start_date),
        end_date=str(notice.analytics_end_date),
        notice_type='REMINDER_2',
        age_count=notice.age_violation_count,
        ot_count=notice.ot_violation_count,
        preauth_count=notice.preauth_violation_count,
        original_issue_date=notice.issued_at.strftime('%d/%m/%Y'),
    )
    email_sent = send_show_cause_email(
        hospital_email=notice.hospital_email,
        subject="Final Reminder — Show Cause Notice — Ophthalmology Claims | PMJAY",
        body=body,
    )
    if not email_sent:
        ShowCauseAuditLog.objects.create(
            notice=notice,
            action='EMAIL_FAILED',
            performed_by=performed_by,
            notes='Reminder 2 email failed.',
        )

    return {'ok': True, 'error': None, 'notice': serialize_notice(notice)}


# ─────────────────────────────────────────────────────────────────────────────
# Mark expired (manual — officer triggered)
# ─────────────────────────────────────────────────────────────────────────────

def mark_expired(notice_id: int, performed_by: str) -> dict:
    """
    Mark a notice as expired.
    Status guard: must not already be CLOSED or EXPIRED.
    Timing guard: EXPIRY_AFTER_REMINDER_2 (3 days) after the most recent
                  action must have elapsed (waived if bypass enabled).
    """
    try:
        notice = ShowCauseNotice.objects.get(id=notice_id)
    except ShowCauseNotice.DoesNotExist:
        return {'ok': False, 'error': f"Notice {notice_id} not found."}

    if notice.status in (ShowCauseStatus.CLOSED, ShowCauseStatus.EXPIRED):
        return {
            'ok': False,
            'error': f"Notice is already in terminal state: {notice.status}",
        }

    if not timing_bypass_enabled():
        ref = notice.reminder_2_at or notice.reminder_1_at or notice.issued_at
        elapsed = timezone.now() - ref
        if elapsed < EXPIRY_AFTER_REMINDER_2:
            days_remaining = (EXPIRY_AFTER_REMINDER_2 - elapsed).days + 1
            return {
                'ok': False,
                'error': (
                    f"Too early to mark as expired. "
                    f"{days_remaining} day(s) remaining before the "
                    f"{EXPIRY_AFTER_REMINDER_2.days}-day expiry window opens."
                ),
            }

    with transaction.atomic():
        notice.status = ShowCauseStatus.EXPIRED
        notice.save(update_fields=['status'])
        ShowCauseAuditLog.objects.create(
            notice=notice,
            action='EXPIRED',
            performed_by=performed_by,
            notes='Timing bypass active (dev mode).' if timing_bypass_enabled() else '',
        )

    return {'ok': True, 'error': None, 'notice': serialize_notice(notice)}


# ─────────────────────────────────────────────────────────────────────────────
# Close notice
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Closure email body builders
# ─────────────────────────────────────────────────────────────────────────────

def _build_close_warning_email(hospital_name: str, hospital_id: str) -> str:
    today = timezone.now().strftime('%d/%m/%Y')
    sig   = _SIGNATORY_NAME.split(',')[0]
    lines = [
        'From,',
        f'{_SIGNATORY_NAME},',
        f'{_SIGNATORY_TITLE},',
        'Bihar Swasthya Suraksha Samiti.',
        '',
        'To,',
        '\tThe Director/Proprietor',
        f'\t{hospital_name}',
        f'\t({hospital_id})',
        '',
        'Subject: Warning Regarding Observed Discrepancies.',
        '',
        'Dear Sir/Madam,',
        '',
        ('With reference to the Show Cause Notice issued pursuant to the discrepancies '
         'found in your hospital and the reply submitted by you in this regard, the matter '
         'was placed before the Internal Committee for detailed examination. The committee '
         'carefully reviewed the discrepancies along with the written explanation submitted '
         'by the hospital.'),
        '',
        ('Since this is the first instance and based on the recommendations of the Internal '
         'Committee, the competent authority has decided to close the matter with a direction '
         "to strictly adhere to the guidelines laid down by NHA and MoU's terms and conditions."),
        '',
        ('Any failure to comply in future may compel this office to initiate appropriate '
         'action, which may include stoppage of payment, suspension, or de-empanelment of '
         'your hospital, as per the applicable guidelines.'),
        '',
        '\t\t\t\t\t\t\t\tSincerely Yours,',
        '\t\t\t\t\t\t\t\t\tSd/-',
        f'({sig})',
        f'{_SIGNATORY_TITLE}',
        '',
        f'Date: {today}',
    ]
    return '\n'.join(lines)

def _build_close_penalty_email(
    hospital_name: str, hospital_id: str,
    penalty_amount: str, suspension_label: str,
) -> str:
    today = timezone.now().strftime('%d/%m/%Y')
    words = _amount_in_words(penalty_amount)
    sig   = _SIGNATORY_NAME.split(',')[0]
    lines = [
        'From,',
        f'{_SIGNATORY_NAME},',
        f'{_SIGNATORY_TITLE},',
        'Bihar Swasthya Suraksha Samiti.',
        '',
        'To,',
        '\tThe Director/Proprietor',
        f'\t{hospital_name}',
        f'\t({hospital_id})',
        '',
        'Subject: Imposition of Penalty and Warning Regarding Observed Discrepancies.',
        '',
        'Dear Sir/Madam,',
        '',
        ('With reference to the Show Cause Notice issued pursuant to the discrepancies '
         'found in your hospital and the reply submitted by you in this regard, the matter '
         'was placed before the Internal Committee for detailed examination. The committee '
         'carefully reviewed the discrepancies along with the written explanation submitted '
         'by the hospital.'),
        '',
        ('Since this is the first instance and based on the recommendations of the Internal '
         'Committee, the competent authority has decided to impose a penalty of '
         f'\u20b9{penalty_amount}/- (Rupees {words} Only) with a direction to strictly '
         "adhere to the guidelines laid down by NHA and MoU's terms and conditions."),
        '',
        ('Any failure to comply in future may compel this office to initiate appropriate '
         'action, which may include stoppage of payment, suspension, or de-empanelment of '
         'your hospital, as per the applicable guidelines.'),
        '',
        '\t\t\t\t\t\t\t\tSincerely Yours,',
        '\t\t\t\t\t\t\t\t\tSd/-',
        f'({sig})',
        f'{_SIGNATORY_TITLE}',
        '',
        f'Date: {today}',
    ]
    return '\n'.join(lines)

def _build_close_suspension_email(
    hospital_name: str, hospital_id: str, suspension_label: str,
) -> str:
    today = timezone.now().strftime('%d/%m/%Y')
    sig   = _SIGNATORY_NAME.split(',')[0]
    lines = [
        'From,',
        f'{_SIGNATORY_NAME},',
        f'{_SIGNATORY_TITLE},',
        'Bihar Swasthya Suraksha Samiti.',
        '',
        'To,',
        '\tThe Director/Proprietor',
        f'\t{hospital_name}',
        f'\t({hospital_id})',
        '',
        '\tSubject: Regarding Suspension of Hospital.',
        '',
        'Dear Sir/Madam,',
        '',
        ('With reference to the discrepancies found in your hospital and the Show Cause '
         'Notice issued in this regard, you were directed to submit your explanation.'),
        '',
        ('In view of the seriousness of the discrepancies observed, and pending detailed '
         'examination of the Show Cause reply and related records, the Competent Authority '
         'has decided to place your hospital under immediate suspension.'),
        '',
        ('The suspension shall remain in force until a final decision is taken after '
         'thorough review of the discrepancies and your explanation. Further action shall '
         'be taken as per the applicable guidelines based on the outcome of the review.'),
        '',
        '\t\t\t\t\t\t\tSincerely Yours,',
        '\t\t\t\t\t\t\tSd/-',
        f'({sig})',
        f'{_SIGNATORY_TITLE}',
        '',
        f'Date: {today}',
    ]
    return '\n'.join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# Close notice
# ─────────────────────────────────────────────────────────────────────────────

def close_notice(
    notice_id: int,
    performed_by: str,
    close_type: str = 'WARNING',      # 'WARNING' | 'PENALTY' | 'SUSPENSION'
    notes: str = '',
    penalty_amount=None,              # Decimal | None — for PENALTY type
    suspension_until=None,            # datetime.date | None — for PENALTY/SUSPENSION
) -> dict:
    """
    Close a Show Cause Notice with one of three outcomes:

    WARNING    — Sends a formal warning email. No PenaltyCase created.
    PENALTY    — Sends penalty order email. Creates PenaltyCase.
    SUSPENSION — Sends suspension order email. Creates PenaltyCase.
    """
    try:
        notice = ShowCauseNotice.objects.get(id=notice_id)
    except ShowCauseNotice.DoesNotExist:
        return {'ok': False, 'error': f"Notice {notice_id} not found."}

    if not notice.can_close():
        return {
            'ok': False,
            'error': f"Notice is already in terminal state: {notice.status}",
        }

    if close_type not in ('WARNING', 'PENALTY', 'SUSPENSION'):
        return {'ok': False, 'error': f"Invalid close_type: {close_type}"}

    # ── Validate type-specific inputs ─────────────────────────────────────
    if close_type == 'PENALTY' and penalty_amount is None:
        return {'ok': False, 'error': 'penalty_amount is required for PENALTY closure.'}

    if close_type == 'SUSPENSION' and suspension_until is None:
        return {'ok': False, 'error': 'suspension_until is required for SUSPENSION closure.'}

    audit_note = f"Close type: {close_type}. {notes}".strip(". ") + "."
    if penalty_amount:
        audit_note += f" Penalty: INR {penalty_amount}."
    if suspension_until:
        audit_note += f" Suspended until: {suspension_until}."

    with transaction.atomic():
        notice.apply_close()
        notice.save(update_fields=['status', 'closed_at'])
        ShowCauseAuditLog.objects.create(
            notice=notice,
            action='CLOSED',
            performed_by=performed_by,
            notes=audit_note,
        )

    # ── Send closure email ────────────────────────────────────────────────
    if close_type == 'WARNING':
        email_subject = "Closure of Show Cause Notice with Warning — PMJAY | BSSS"
        email_body = _build_close_warning_email(notice.hospital_name, notice.hospital_id)
    elif close_type == 'PENALTY':
        # suspension_label for penalty: date string or "Until penalty is paid"
        if suspension_until:
            susp_label = suspension_until.strftime('%d %b %Y')
        else:
            susp_label = "Until penalty is paid"
        email_subject = "Penalty Imposition Order — PMJAY | BSSS"
        email_body = _build_close_penalty_email(
            hospital_name=notice.hospital_name,
            hospital_id=notice.hospital_id,
            penalty_amount=str(penalty_amount),
            suspension_label=susp_label,
        )
    else:  # SUSPENSION
        if suspension_until:
            susp_label = suspension_until.strftime('%d %b %Y')
        else:
            susp_label = "Indefinite"
        email_subject = "Suspension Order — PMJAY | BSSS"
        email_body = _build_close_suspension_email(
            hospital_name=notice.hospital_name,
            hospital_id=notice.hospital_id,
            suspension_label=susp_label,
        )

    email_sent = send_show_cause_email(notice.hospital_email, email_subject, email_body)
    if not email_sent and notice.hospital_email:
        ShowCauseAuditLog.objects.create(
            notice=notice,
            action='EMAIL_FAILED',
            performed_by=performed_by,
            notes=f'{close_type} closure email failed.',
        )

    # ── Create PenaltyCase for PENALTY and SUSPENSION types ───────────────
    if close_type in ('PENALTY', 'SUSPENSION'):
        try:
            from pmjay_fraud_dashboard_penalty_engine.services import create_penalty_case
            from pmjay_fraud_dashboard_penalty_engine.models import PenaltyType
            pen_type = PenaltyType.PENALTY if close_type == 'PENALTY' else PenaltyType.SUSPENSION
            create_penalty_case(
                show_cause_notice_id=notice.pk,
                hospital_id=notice.hospital_id,
                hospital_name=notice.hospital_name,
                hospital_email=notice.hospital_email,
                district_name=notice.district_name or '',
                state_name='',   # ShowCauseNotice does not store state; extend if needed
                penalty_type=pen_type,
                created_by=performed_by,
                penalty_amount=penalty_amount,
                suspension_until=suspension_until,
                notes=notes,
                send_email=False,  # show_cause close_notice already sent the closure email above
            )
        except Exception as exc:
            logger.error("PenaltyCase creation failed for notice %s: %s", notice_id, exc)
            # Non-fatal: notice is already closed; log the failure
            ShowCauseAuditLog.objects.create(
                notice=notice,
                action='EMAIL_FAILED',
                performed_by=performed_by,
                notes=f'PenaltyCase creation failed: {exc}',
            )

    return {'ok': True, 'error': None, 'notice': serialize_notice(notice)}


# ─────────────────────────────────────────────────────────────────────────────
# List notices with pagination (management page API)
# ─────────────────────────────────────────────────────────────────────────────

def get_notices_page(
    status: str | None = None,
    search: str | None = None,
    district: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    """Return a paginated, serialized list of notices for the management page."""
    qs = list_notices(status=status, search=search, district=district)
    total = qs.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size

    return {
        'notices':      [serialize_notice(n) for n in qs[offset: offset + page_size]],
        'total':        total,
        'page':         page,
        'page_size':    page_size,
        'total_pages':  total_pages,
        'has_next':     page < total_pages,
        'has_previous': page > 1,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Summary counts (dashboard card + management page header)
# ─────────────────────────────────────────────────────────────────────────────

def get_summary() -> dict:
    """
    Returns counts for the show cause summary cards.
    'overdue' = REMINDER_2_SENT notices past the 3-day expiry window
                (eligible for auto-expiry but not yet expired).
    """
    today = timezone.now().date()
    overdue_cutoff = timezone.now() - EXPIRY_AFTER_REMINDER_2

    return {
        'issued_today': ShowCauseNotice.objects.filter(
            issued_at__date=today
        ).count(),
        'reminder_1_pending': ShowCauseNotice.objects.filter(
            status=ShowCauseStatus.ISSUED
        ).count(),
        'reminder_2_pending': ShowCauseNotice.objects.filter(
            status=ShowCauseStatus.REMINDER_1_SENT
        ).count(),
        'overdue': ShowCauseNotice.objects.filter(
            status=ShowCauseStatus.REMINDER_2_SENT,
            reminder_2_at__lte=overdue_cutoff,
        ).count(),
        'closed': ShowCauseNotice.objects.filter(
            status=ShowCauseStatus.CLOSED
        ).count(),
        'expired': ShowCauseNotice.objects.filter(
            status=ShowCauseStatus.EXPIRED
        ).count(),
    }