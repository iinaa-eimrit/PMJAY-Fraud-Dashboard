from django.db import models
from datetime import timedelta


class ShowCauseStatus(models.TextChoices):
    """
    Ordered lifecycle states for a ShowCauseNotice.

    ISSUED         → Notice has been sent to the hospital for the first time.
    REMINDER_1_SENT → First follow-up reminder has been sent (≥7 days after issue).
    REMINDER_2_SENT → Second follow-up reminder has been sent (≥14 days after issue).
    EXPIRED        → Notice window has lapsed with no hospital response.
                     Set manually by an officer (no background jobs).
    CLOSED         → Officer has reviewed and formally closed the notice.
    """
    ISSUED          = "ISSUED",          "Issued"
    REMINDER_1_SENT = "REMINDER_1_SENT", "1st Reminder Sent"
    REMINDER_2_SENT = "REMINDER_2_SENT", "2nd Reminder Sent"
    EXPIRED         = "EXPIRED",         "Expired"
    CLOSED          = "CLOSED",          "Closed by Officer"


class CaseType(models.TextChoices):
    """
    The category of medical anomaly that triggered the notice.
    Spell correctly — 'PH' not 'TH'.
    """
    OPTHALMOLOGY = "OPTHALMOLOGY", "Opthalmology"


FIRST_REMINDER_AFTER  = timedelta(days=7)   # Earliest reminder_1 can be sent
SECOND_REMINDER_AFTER = timedelta(days=7)  # Earliest reminder_2 can be sent after reminder_1
EXPIRY_AFTER_REMINDER_2 = timedelta(days=3) # Auto-expiry after reminder_2 if no response