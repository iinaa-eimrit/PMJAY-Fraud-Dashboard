import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from pmjay_fraud_dashboard_show_cause_engine.constants import ShowCauseStatus, EXPIRY_AFTER_REMINDER_2
from pmjay_fraud_dashboard_show_cause_engine.models import ShowCauseNotice, ShowCauseAuditLog

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Expire notices where the 3-day grace period after Reminder 2 has elapsed. "
        "Run with --commit to apply changes; without it this is a dry run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            default=False,
            help='Actually expire the notices. Without this flag, the command only reports what would change.',
        )

    def handle(self, *args, **options):
        commit = options['commit']
        now = timezone.now()
        expiry_cutoff = now - EXPIRY_AFTER_REMINDER_2

        # Find all notices that:
        #   1. Are in REMINDER_2_SENT status
        #   2. Had Reminder 2 sent at least EXPIRY_AFTER_REMINDER_2 (3 days) ago
        overdue_notices = ShowCauseNotice.objects.filter(
            status=ShowCauseStatus.REMINDER_2_SENT,
            reminder_2_at__lte=expiry_cutoff,
        ).select_related()

        count = overdue_notices.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('No overdue notices found. Nothing to expire.'))
            return

        mode = 'DRY RUN' if not commit else 'COMMITTING'
        self.stdout.write(
            self.style.WARNING(f'[{mode}] Found {count} notice(s) eligible for auto-expiry.')
        )

        expired_ids = []

        for notice in overdue_notices:
            days_since_reminder_2 = (now - notice.reminder_2_at).days
            self.stdout.write(
                f'  → {notice.hospital_id} | {notice.hospital_name} | '
                f'Rem.2 sent {days_since_reminder_2} days ago (notice id={notice.id})'
            )

            if commit:
                try:
                    with transaction.atomic():
                        notice.apply_expire()
                        notice.save(update_fields=['status', 'updated_at'])
                        ShowCauseAuditLog.objects.create(
                            notice=notice,
                            action='AUTO_EXPIRED',
                            performed_by='system',
                            notes=(
                                f'Auto-expired by management command. '
                                f'Reminder 2 was sent {days_since_reminder_2} days ago '
                                f'(>{EXPIRY_AFTER_REMINDER_2.days} day grace period).'
                            ),
                        )
                        expired_ids.append(notice.id)
                except Exception as exc:
                    logger.error('Failed to expire notice id=%s: %s', notice.id, exc)
                    self.stdout.write(
                        self.style.ERROR(f'    ERROR expiring notice {notice.id}: {exc}')
                    )

        if commit:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Done. Expired {len(expired_ids)} notice(s): {expired_ids}'
                )
            )
            logger.info('expire_overdue_notices: expired %d notices: %s', len(expired_ids), expired_ids)
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'Dry run complete. Re-run with --commit to expire these {count} notice(s).'
                )
            )