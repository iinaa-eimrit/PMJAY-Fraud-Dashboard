from django.db import models
from django.utils import timezone

from .constants import (
    ShowCauseStatus,
    CaseType,
    FIRST_REMINDER_AFTER,
    SECOND_REMINDER_AFTER,
    EXPIRY_AFTER_REMINDER_2,
)


class ShowCauseNotice(models.Model):
    # Explicit PK for type checkers (Django auto-generates this)
    id: int

    #  Hospital identity
    hospital_id    = models.CharField(max_length=50)
    hospital_name  = models.CharField(max_length=255)
    hospital_email = models.EmailField(blank=True, default='')
    district_name  = models.CharField(max_length=100, blank=True, default='')

    #  Analytics period this notice covers
    analytics_start_date = models.DateField()
    analytics_end_date   = models.DateField()

    #  Case classification
    case_type = models.CharField(
        max_length=20,
        choices=CaseType.choices,
        default=CaseType.OPTHALMOLOGY,
    )
    
    age_violation_count     = models.PositiveIntegerField(null=True, blank=True)
    ot_violation_count      = models.PositiveIntegerField(null=True, blank=True)
    preauth_violation_count = models.PositiveIntegerField(null=True, blank=True)

    #  Lifecycle status 
    status = models.CharField(
        max_length=20,
        choices=ShowCauseStatus.choices,
        default=ShowCauseStatus.ISSUED,
        db_index=True,
    )

    #  Timestamps 
    # issued_at is the clock start for the entire lifecycle.
    # It is INDEPENDENT of analytics_start_date / analytics_end_date.
    # An officer may issue a notice today for violations that occurred months ago.
    issued_at     = models.DateTimeField(default=timezone.now, db_index=True)
    reminder_1_at = models.DateTimeField(null=True, blank=True)
    reminder_2_at = models.DateTimeField(null=True, blank=True)
    closed_at     = models.DateTimeField(null=True, blank=True)

    #  Audit
    created_by = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('hospital_id', 'analytics_start_date', 'analytics_end_date')]
        ordering = ['-issued_at']

    def __str__(self):
        return f"SCN-{self.pk} | {self.hospital_id} | {self.status}"

    #  Computed properties 

    @property
    def is_terminal(self) -> bool:
        return self.status in (ShowCauseStatus.CLOSED, ShowCauseStatus.EXPIRED)

    #  Guard methods — pure, no side effects 

    def can_send_reminder_1(self) -> bool:
        """
        True when:
          - status is ISSUED
          - at least FIRST_REMINDER_AFTER (7 days) have elapsed since issued_at
        """
        if self.status != ShowCauseStatus.ISSUED:
            return False
        return (timezone.now() - self.issued_at) >= FIRST_REMINDER_AFTER

    def can_send_reminder_2(self) -> bool:
        """
        True when:
          - status is REMINDER_1_SENT
          - reminder_1_at is set (data integrity guard)
          - at least SECOND_REMINDER_AFTER (7 days) have elapsed since reminder_1_at
        """
        if self.status != ShowCauseStatus.REMINDER_1_SENT:
            return False
        if self.reminder_1_at is None:
            return False
        return (timezone.now() - self.reminder_1_at) >= SECOND_REMINDER_AFTER

    def can_mark_expired(self) -> bool:
        if self.is_terminal:
            return False
        ref = self.reminder_2_at or self.reminder_1_at or self.issued_at
        return (timezone.now() - ref) >= EXPIRY_AFTER_REMINDER_2

    def can_close(self) -> bool:
        """Close is available from any non-terminal state."""
        return not self.is_terminal

    def apply_reminder_1(self) -> None:
        if not self.can_send_reminder_1():
            raise ValueError(
                f"Cannot send Reminder 1. Status={self.status}, "
                f"issued_at={self.issued_at}. "
                f"Required: status=ISSUED and {FIRST_REMINDER_AFTER.days} days elapsed."
            )
        self.status = ShowCauseStatus.REMINDER_1_SENT
        self.reminder_1_at = timezone.now()

    def apply_reminder_2(self) -> None:
        if not self.can_send_reminder_2():
            raise ValueError(
                f"Cannot send Reminder 2. Status={self.status}, "
                f"reminder_1_at={self.reminder_1_at}. "
                f"Required: status=REMINDER_1_SENT and "
                f"{SECOND_REMINDER_AFTER.days} days elapsed."
            )
        self.status = ShowCauseStatus.REMINDER_2_SENT
        self.reminder_2_at = timezone.now()

    def apply_expire(self) -> None:
        if not self.can_mark_expired():
            raise ValueError(
                f"Cannot mark as expired. Status={self.status}. "
                f"Either already terminal, or the {EXPIRY_AFTER_REMINDER_2.days}-day "
                f"grace period has not elapsed."
            )
        self.status = ShowCauseStatus.EXPIRED

    def apply_close(self) -> None:
        if not self.can_close():
            raise ValueError(
                f"Cannot close notice. Status={self.status} is already terminal."
            )
        self.status = ShowCauseStatus.CLOSED
        self.closed_at = timezone.now()


class ShowCauseAuditLog(models.Model):
    # Explicit FK _id for type checkers
    notice_id: int

    ACTION_CHOICES = [
        ('ISSUED',          'Notice Issued'),
        ('REMINDER_1_SENT', '1st Reminder Sent'),
        ('REMINDER_2_SENT', '2nd Reminder Sent'),
        ('EXPIRED',         'Notice Expired'),
        ('AUTO_EXPIRED',    'Auto-Expired by System'),
        ('CLOSED',          'Closed by Officer'),
        ('EMAIL_FAILED',    'Email Send Failed'),
    ]

    notice       = models.ForeignKey(
        ShowCauseNotice,
        on_delete=models.CASCADE,
        related_name='audit_logs',
    )
    action       = models.CharField(max_length=30, choices=ACTION_CHOICES)
    performed_by = models.CharField(max_length=150)
    performed_at = models.DateTimeField(auto_now_add=True)
    notes        = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['performed_at']

    def __str__(self):
        return f"{self.notice.pk} | {self.action} | {self.performed_by}"