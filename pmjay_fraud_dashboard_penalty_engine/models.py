from django.db import models
from django.utils import timezone


class PenaltyStatus(models.TextChoices):
    """
    Lifecycle states for a PenaltyCase.

    ACTIVE          → Penalty has been imposed; awaiting compliance.
    REMINDER_SENT   → Officer has sent a formal non-compliance reminder.
    PAID            → Penalty amount confirmed as received.
    NON_COMPLIANT   → Hospital has not complied after reminders.
    CLOSED          → Officer has closed the penalty record.
    """
    ACTIVE          = 'ACTIVE',         'Active'
    REMINDER_SENT   = 'REMINDER_SENT',  'Reminder Sent'
    PAID            = 'PAID',           'Paid'
    NON_COMPLIANT   = 'NON_COMPLIANT',  'Non-Compliant'
    CLOSED          = 'CLOSED',         'Closed'


class PenaltyType(models.TextChoices):
    """
    The kind of closure that generated this penalty.
    """
    PENALTY     = 'PENALTY',    'Closed with Penalty'
    SUSPENSION  = 'SUSPENSION', 'Closed with Suspension'


class PenaltyCase(models.Model):
    """
    Tracks penalties and suspensions imposed when a Show Cause Notice is
    closed with punitive action. Created automatically by close_notice()
    in the show cause services layer when close_type is PENALTY or SUSPENSION.
    """
    id: int
    # ── Link back to Show Cause ──────────────────────────────────────────
    show_cause_notice_id = models.IntegerField(
        db_index=True,
        help_text="PK of the originating ShowCauseNotice (not a FK to avoid circular imports)."
    )

    # ── Hospital identity (denormalised for display without joins) ────────
    hospital_id    = models.CharField(max_length=50, db_index=True)
    hospital_name  = models.CharField(max_length=255)
    hospital_email = models.EmailField(blank=True, default='')
    district_name  = models.CharField(max_length=100, blank=True, default='')
    state_name     = models.CharField(max_length=100, blank=True, default='')

    # ── Penalty classification ────────────────────────────────────────────
    penalty_type = models.CharField(
        max_length=20,
        choices=PenaltyType.choices,
        db_index=True,
    )

    # ── Penalty amount (null = suspension-only, no monetary penalty) ──────
    penalty_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Imposed penalty in INR. Null for pure suspension cases.",
    )

    # ── Suspension period ─────────────────────────────────────────────────
    # suspension_until: null  = suspended until penalty is paid
    # suspension_until: date  = suspended until this fixed calendar date
    suspension_until = models.DateField(
        null=True,
        blank=True,
        help_text="Fixed end date for suspension. Null means 'until penalty is paid'.",
    )

    # ── Status & lifecycle timestamps ─────────────────────────────────────
    status     = models.CharField(
        max_length=20,
        choices=PenaltyStatus.choices,
        default=PenaltyStatus.ACTIVE,
        db_index=True,
    )
    imposed_at   = models.DateTimeField(default=timezone.now, db_index=True)
    reminder_at  = models.DateTimeField(null=True, blank=True)
    resolved_at  = models.DateTimeField(null=True, blank=True)
    closed_at    = models.DateTimeField(null=True, blank=True)

    # ── Audit ─────────────────────────────────────────────────────────────
    created_by = models.CharField(max_length=150)
    notes      = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-imposed_at']
        indexes = [
            models.Index(fields=['hospital_id', 'status']),
        ]

    def __str__(self):
        return f"PEN-{self.id} | {self.hospital_id} | {self.penalty_type} | {self.status}"

    # ── Computed helpers ──────────────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        return self.status in (PenaltyStatus.CLOSED, PenaltyStatus.PAID)

    @property
    def suspension_label(self) -> str:
        """Human-readable suspension period for display."""
        if self.suspension_until:
            return self.suspension_until.strftime('%d %b %Y')
        if self.penalty_amount:
            return 'Until penalty is paid'
        return 'Indefinite'

    def can_send_reminder(self) -> bool:
        return not self.is_terminal

    def can_mark_paid(self) -> bool:
        return (
            self.penalty_amount is not None
            and self.status not in (PenaltyStatus.PAID, PenaltyStatus.CLOSED)
        )

    def can_mark_non_compliant(self) -> bool:
        return not self.is_terminal and self.status != PenaltyStatus.NON_COMPLIANT

    def can_close(self) -> bool:
        return not self.is_terminal


class PenaltyAuditLog(models.Model):
    """
    Immutable audit trail for every action taken on a PenaltyCase.
    """
    penalty_id: int
    ACTION_CHOICES = [
        ('IMPOSED',          'Penalty Imposed'),
        ('REMINDER_SENT',    'Reminder Notice Sent'),
        ('MARKED_PAID',      'Penalty Marked as Paid'),
        ('MARKED_NON_COMPLIANT', 'Marked Non-Compliant'),
        ('CLOSED',           'Case Closed'),
        ('EMAIL_FAILED',     'Email Send Failed'),
    ]

    penalty      = models.ForeignKey(
        PenaltyCase,
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
        return f"{self.penalty_id} | {self.action} | {self.performed_by}"