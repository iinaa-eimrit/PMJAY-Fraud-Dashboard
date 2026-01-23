"""
pmjay_fraud_dashboard_show_cause_engine/tests/test_suite.py
────────────────────────────────────────────────────────────
Comprehensive test suite for the Show Cause engine.
Covers: domain model, selectors, services, and API views.

Run all:
    docker exec -it pmjay_fraud_dashboard \
        python manage.py test pmjay_fraud_dashboard_show_cause_engine.tests.test_suite -v 2

Run a single class:
    python manage.py test \
        pmjay_fraud_dashboard_show_cause_engine.tests.test_suite.TestSendReminder1Service -v 2
"""

from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from pmjay_fraud_dashboard_show_cause_engine.constants import (
    ShowCauseStatus,
    FIRST_REMINDER_AFTER,
    SECOND_REMINDER_AFTER,
)
from pmjay_fraud_dashboard_show_cause_engine.models import ShowCauseNotice, ShowCauseAuditLog
from pmjay_fraud_dashboard_show_cause_engine.selectors import (
    timing_bypass_enabled,
    list_notices,
    get_notice,
    compute_actions,
    serialize_notice,
    list_audit_logs,
)
from pmjay_fraud_dashboard_show_cause_engine.services import (
    issue_notice_bulk,
    send_reminder_1,
    send_reminder_2,
    mark_expired,
    close_notice,
    get_notices_page,
    get_summary,
)

User = get_user_model()
EXPIRY_AFTER_REMINDER_2 = timedelta(days=3)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures & helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_notice(**kwargs) -> ShowCauseNotice:
    """
    Build an UNSAVED ShowCauseNotice with sensible defaults.
    Used for pure domain / selector tests that don't need DB rows.
    """
    defaults = dict(
        hospital_id="H001",
        hospital_name="Test Hospital",
        hospital_email="hospital@test.com",
        district_name="Test District",
        analytics_start_date="2024-01-01",
        analytics_end_date="2024-01-31",
        status=ShowCauseStatus.ISSUED,
        issued_at=timezone.now(),
        reminder_1_at=None,
        reminder_2_at=None,
        closed_at=None,
        created_by="test_officer",
    )
    defaults.update(kwargs)
    return ShowCauseNotice(**defaults)


def create_notice(**kwargs) -> ShowCauseNotice:
    """
    Create and SAVE a ShowCauseNotice to the test DB.
    Used for service and view tests.
    """
    defaults = dict(
        hospital_id="H001",
        hospital_name="Test Hospital",
        hospital_email="hospital@test.com",
        district_name="Test District",
        analytics_start_date="2024-01-01",
        analytics_end_date="2024-01-31",
        status=ShowCauseStatus.ISSUED,
        issued_at=timezone.now(),
        created_by="test_officer",
    )
    defaults.update(kwargs)
    return ShowCauseNotice.objects.create(**defaults)


def create_hospital_beds(hospital_id="H001", email="hospital@test.com"):
    """Create a HospitalBeds row for service tests that call issue_notice_bulk."""
    from pmjay_fraud_dashboard_app.models import HospitalBeds
    return HospitalBeds.objects.get_or_create(
        hospital_id=hospital_id,
        defaults={
            "hospital_name": "Test Hospital",
            "hospital_district": "Test District",
            "hospital_email_id": email,
            "bed_strength": 50,
        }
    )[0]


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# PART 1: Domain model tests  (no DB, pure logic)
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────


class TestCanSendReminder1(TestCase):
    """can_send_reminder_1() guard — status and timing checks."""

    def test_false_if_not_issued(self):
        for status in [ShowCauseStatus.REMINDER_1_SENT, ShowCauseStatus.REMINDER_2_SENT,
                       ShowCauseStatus.CLOSED, ShowCauseStatus.EXPIRED]:
            n = make_notice(status=status, issued_at=timezone.now() - timedelta(days=10))
            self.assertFalse(n.can_send_reminder_1(), f"Expected False for {status}")

    def test_false_if_too_early(self):
        n = make_notice(issued_at=timezone.now() - timedelta(days=3))
        self.assertFalse(n.can_send_reminder_1())

    def test_true_at_exactly_7_days(self):
        n = make_notice(issued_at=timezone.now() - FIRST_REMINDER_AFTER)
        self.assertTrue(n.can_send_reminder_1())

    def test_true_after_7_days(self):
        n = make_notice(issued_at=timezone.now() - timedelta(days=10))
        self.assertTrue(n.can_send_reminder_1())


class TestApplyReminder1(TestCase):
    """apply_reminder_1() — state mutation."""

    def test_raises_if_too_early(self):
        n = make_notice(issued_at=timezone.now() - timedelta(days=2))
        with self.assertRaises(ValueError):
            n.apply_reminder_1()

    def test_raises_if_wrong_status(self):
        n = make_notice(status=ShowCauseStatus.REMINDER_1_SENT,
                        issued_at=timezone.now() - timedelta(days=10))
        with self.assertRaises(ValueError):
            n.apply_reminder_1()

    def test_sets_status_and_timestamp(self):
        before = timezone.now()
        n = make_notice(issued_at=timezone.now() - timedelta(days=8))
        n.apply_reminder_1()
        self.assertEqual(n.status, ShowCauseStatus.REMINDER_1_SENT)
        self.assertIsNotNone(n.reminder_1_at)
        assert n.reminder_1_at is not None
        self.assertGreaterEqual(n.reminder_1_at, before)

    def test_does_not_modify_issued_at(self):
        original_issued = timezone.now() - timedelta(days=8)
        n = make_notice(issued_at=original_issued)
        n.apply_reminder_1()
        self.assertEqual(n.issued_at, original_issued)


class TestCanSendReminder2(TestCase):
    """can_send_reminder_2() guard."""

    def test_false_if_not_reminder_1_sent(self):
        n = make_notice(status=ShowCauseStatus.ISSUED,
                        reminder_1_at=timezone.now() - timedelta(days=20))
        self.assertFalse(n.can_send_reminder_2())

    def test_false_if_reminder_1_at_missing(self):
        """Data integrity guard — reminder_1_at must exist."""
        n = make_notice(status=ShowCauseStatus.REMINDER_1_SENT, reminder_1_at=None)
        self.assertFalse(n.can_send_reminder_2())

    def test_false_if_too_early(self):
        n = make_notice(status=ShowCauseStatus.REMINDER_1_SENT,
                        reminder_1_at=timezone.now() - timedelta(days=5))
        self.assertFalse(n.can_send_reminder_2())

    def test_true_at_exactly_14_days(self):
        n = make_notice(status=ShowCauseStatus.REMINDER_1_SENT,
                        reminder_1_at=timezone.now() - SECOND_REMINDER_AFTER)
        self.assertTrue(n.can_send_reminder_2())

    def test_true_after_14_days(self):
        n = make_notice(status=ShowCauseStatus.REMINDER_1_SENT,
                        reminder_1_at=timezone.now() - timedelta(days=20))
        self.assertTrue(n.can_send_reminder_2())


class TestApplyReminder2(TestCase):

    def test_raises_if_wrong_status(self):
        n = make_notice(status=ShowCauseStatus.ISSUED)
        with self.assertRaises(ValueError):
            n.apply_reminder_2()

    def test_raises_if_reminder_1_at_missing(self):
        n = make_notice(status=ShowCauseStatus.REMINDER_1_SENT, reminder_1_at=None)
        with self.assertRaises(ValueError):
            n.apply_reminder_2()

    def test_raises_if_too_early(self):
        n = make_notice(status=ShowCauseStatus.REMINDER_1_SENT,
                        reminder_1_at=timezone.now() - timedelta(days=3))
        with self.assertRaises(ValueError):
            n.apply_reminder_2()

    def test_sets_status_and_timestamp(self):
        before = timezone.now()
        n = make_notice(status=ShowCauseStatus.REMINDER_1_SENT,
                        reminder_1_at=timezone.now() - timedelta(days=15))
        n.apply_reminder_2()
        self.assertEqual(n.status, ShowCauseStatus.REMINDER_2_SENT)
        self.assertIsNotNone(n.reminder_2_at)
        assert n.reminder_2_at is not None
        self.assertGreaterEqual(n.reminder_2_at, before)


class TestClose(TestCase):

    def test_can_close_from_any_active_status(self):
        for status in [ShowCauseStatus.ISSUED, ShowCauseStatus.REMINDER_1_SENT,
                       ShowCauseStatus.REMINDER_2_SENT]:
            n = make_notice(status=status)
            self.assertTrue(n.can_close(), f"Expected can_close True for {status}")

    def test_cannot_close_terminal_states(self):
        for status in [ShowCauseStatus.CLOSED, ShowCauseStatus.EXPIRED]:
            n = make_notice(status=status)
            self.assertFalse(n.can_close(), f"Expected can_close False for {status}")

    def test_apply_close_sets_fields(self):
        before = timezone.now()
        n = make_notice(status=ShowCauseStatus.REMINDER_1_SENT)
        n.apply_close()
        self.assertEqual(n.status, ShowCauseStatus.CLOSED)
        self.assertIsNotNone(n.closed_at)
        assert n.closed_at is not None
        self.assertGreaterEqual(n.closed_at, before)

    def test_apply_close_raises_if_already_closed(self):
        n = make_notice(status=ShowCauseStatus.CLOSED)
        with self.assertRaises(ValueError):
            n.apply_close()

    def test_apply_close_raises_if_expired(self):
        n = make_notice(status=ShowCauseStatus.EXPIRED)
        with self.assertRaises(ValueError):
            n.apply_close()


class TestExpiry(TestCase):

    def test_cannot_expire_closed(self):
        n = make_notice(status=ShowCauseStatus.CLOSED)
        self.assertFalse(n.can_mark_expired())

    def test_cannot_expire_already_expired(self):
        n = make_notice(status=ShowCauseStatus.EXPIRED)
        self.assertFalse(n.can_mark_expired())

    def test_can_expire_after_window_lapsed_from_issued(self):
        """Old ISSUED notice with no reminders can be expired."""
        n = make_notice(status=ShowCauseStatus.ISSUED,
                        issued_at=timezone.now() - timedelta(days=20))
        self.assertTrue(n.can_mark_expired())

    def test_can_expire_after_window_lapsed_from_reminder_2(self):
        n = make_notice(
            status=ShowCauseStatus.REMINDER_2_SENT,
            reminder_1_at=timezone.now() - timedelta(days=20),
            reminder_2_at=timezone.now() - timedelta(days=5),
        )
        self.assertTrue(n.can_mark_expired())

    def test_cannot_expire_too_soon_after_reminder_2(self):
        n = make_notice(
            status=ShowCauseStatus.REMINDER_2_SENT,
            reminder_1_at=timezone.now() - timedelta(days=17),
            reminder_2_at=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(n.can_mark_expired())

    def test_apply_expire_sets_status(self):
        n = make_notice(status=ShowCauseStatus.ISSUED,
                        issued_at=timezone.now() - timedelta(days=20))
        n.apply_expire()
        self.assertEqual(n.status, ShowCauseStatus.EXPIRED)

    def test_apply_expire_raises_if_not_expired_eligible(self):
        n = make_notice(status=ShowCauseStatus.ISSUED,
                        issued_at=timezone.now() - timedelta(days=1))
        with self.assertRaises(ValueError):
            n.apply_expire()


class TestIsTerminal(TestCase):

    def test_true_for_closed_and_expired(self):
        for status in [ShowCauseStatus.CLOSED, ShowCauseStatus.EXPIRED]:
            n = make_notice(status=status)
            self.assertTrue(n.is_terminal)

    def test_false_for_all_active_statuses(self):
        for status in [ShowCauseStatus.ISSUED, ShowCauseStatus.REMINDER_1_SENT,
                       ShowCauseStatus.REMINDER_2_SENT]:
            n = make_notice(status=status)
            self.assertFalse(n.is_terminal)


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# PART 2: Selector tests  (uses DB)
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────


class TestTimingBypass(TestCase):
    """timing_bypass_enabled() reads from settings correctly."""

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=True)
    def test_explicit_true(self):
        self.assertTrue(timing_bypass_enabled())

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_explicit_false(self):
        self.assertFalse(timing_bypass_enabled())

    @override_settings(DEBUG=True)
    def test_falls_back_to_debug_true(self):
        # Remove the explicit key if it happens to be set
        from django.conf import settings
        if hasattr(settings, 'SHOW_CAUSE_BYPASS_TIMING'):
            del settings.SHOW_CAUSE_BYPASS_TIMING
        self.assertTrue(timing_bypass_enabled())

    @override_settings(DEBUG=False)
    def test_falls_back_to_debug_false(self):
        from django.conf import settings
        if hasattr(settings, 'SHOW_CAUSE_BYPASS_TIMING'):
            del settings.SHOW_CAUSE_BYPASS_TIMING
        self.assertFalse(timing_bypass_enabled())


class TestListNotices(TestCase):

    def setUp(self):
        create_notice(hospital_id="H001", status=ShowCauseStatus.ISSUED, district_name="Patna")
        create_notice(hospital_id="H002", status=ShowCauseStatus.REMINDER_1_SENT, district_name="Gaya")
        create_notice(hospital_id="H003", status=ShowCauseStatus.CLOSED, district_name="Patna",
                      analytics_start_date="2024-02-01", analytics_end_date="2024-02-28")

    def test_returns_all_when_no_filters(self):
        self.assertEqual(list_notices().count(), 3)

    def test_filter_by_status(self):
        qs = list_notices(status=ShowCauseStatus.ISSUED)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().hospital_id, "H001")

    def test_filter_all_explicit(self):
        """Passing 'ALL' as status should return everything."""
        self.assertEqual(list_notices(status='ALL').count(), 3)

    def test_filter_by_district(self):
        qs = list_notices(district="Patna")
        self.assertEqual(qs.count(), 2)

    def test_search_by_hospital_id(self):
        qs = list_notices(search="H002")
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().hospital_id, "H002")

    def test_search_is_case_insensitive(self):
        create_notice(hospital_id="H004", hospital_name="City Eye Hospital",
                      analytics_start_date="2024-03-01", analytics_end_date="2024-03-31")
        qs = list_notices(search="eye hospital")
        self.assertEqual(qs.count(), 1)

    def test_combined_status_and_district(self):
        qs = list_notices(status=ShowCauseStatus.ISSUED, district="Patna")
        self.assertEqual(qs.count(), 1)

    def test_no_results_returns_empty_queryset(self):
        qs = list_notices(search="NONEXISTENT_XYZ")
        self.assertEqual(qs.count(), 0)

    def test_default_order_is_newest_first(self):
        notices = list(list_notices())
        # H003 was created last but issued_at is all roughly now — check order is stable
        self.assertEqual(len(notices), 3)


class TestGetNotice(TestCase):

    def test_returns_notice_if_found(self):
        n = create_notice()
        found = get_notice(n.id)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, n.id)  # type: ignore[union-attr]

    def test_returns_none_if_not_found(self):
        result = get_notice(99999)
        self.assertIsNone(result)


class TestComputeActions(TestCase):
    """compute_actions() returns correct flags for each lifecycle state."""

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_issued_too_early_no_actions(self):
        n = make_notice(status=ShowCauseStatus.ISSUED,
                        issued_at=timezone.now() - timedelta(days=1))
        actions = compute_actions(n)
        self.assertFalse(actions['can_send_reminder_1'])
        self.assertFalse(actions['can_send_reminder_2'])
        self.assertTrue(actions['can_close'])  # Close always available
        self.assertFalse(actions['can_mark_expired'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_issued_7_days_later_rem1_available(self):
        n = make_notice(status=ShowCauseStatus.ISSUED,
                        issued_at=timezone.now() - timedelta(days=8))
        actions = compute_actions(n)
        self.assertTrue(actions['can_send_reminder_1'])
        self.assertFalse(actions['can_send_reminder_2'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=True)
    def test_bypass_enables_rem1_immediately(self):
        n = make_notice(status=ShowCauseStatus.ISSUED,
                        issued_at=timezone.now())  # just now
        actions = compute_actions(n)
        self.assertTrue(actions['can_send_reminder_1'])
        self.assertTrue(actions['bypass_timing_active'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_reminder_1_sent_too_early_no_rem2(self):
        n = make_notice(status=ShowCauseStatus.REMINDER_1_SENT,
                        reminder_1_at=timezone.now() - timedelta(days=3))
        actions = compute_actions(n)
        self.assertFalse(actions['can_send_reminder_1'])
        self.assertFalse(actions['can_send_reminder_2'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_reminder_1_sent_14_days_later_rem2_available(self):
        n = make_notice(status=ShowCauseStatus.REMINDER_1_SENT,
                        reminder_1_at=timezone.now() - timedelta(days=15))
        actions = compute_actions(n)
        self.assertFalse(actions['can_send_reminder_1'])
        self.assertTrue(actions['can_send_reminder_2'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_closed_no_actions(self):
        n = make_notice(status=ShowCauseStatus.CLOSED,
                        closed_at=timezone.now())
        actions = compute_actions(n)
        self.assertFalse(actions['can_send_reminder_1'])
        self.assertFalse(actions['can_send_reminder_2'])
        self.assertFalse(actions['can_close'])
        self.assertFalse(actions['can_mark_expired'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_days_until_reminder_1_positive_when_future(self):
        """days_until_reminder_1 should be positive when the deadline is in the future."""
        n = make_notice(status=ShowCauseStatus.ISSUED,
                        issued_at=timezone.now() - timedelta(days=3))
        actions = compute_actions(n)
        # Rem1 due in 4 days (7 - 3 = 4)
        self.assertIsNotNone(actions['days_until_reminder_1'])
        self.assertGreater(actions['days_until_reminder_1'], 0)

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_days_until_reminder_1_negative_when_overdue(self):
        """days_until_reminder_1 should be negative when overdue."""
        n = make_notice(status=ShowCauseStatus.ISSUED,
                        issued_at=timezone.now() - timedelta(days=10))
        actions = compute_actions(n)
        self.assertLess(actions['days_until_reminder_1'], 0)


class TestSerializeNotice(TestCase):
    """serialize_notice() returns all expected keys with correct types."""

    REQUIRED_KEYS = [
        'id', 'hospital_id', 'hospital_name', 'hospital_email',
        'district_name', 'analytics_start_date', 'analytics_end_date',
        'status', 'status_display', 'issued_at', 'issued_at_fmt',
        'reminder_1_at', 'reminder_1_at_fmt', 'reminder_2_at', 'reminder_2_at_fmt',
        'closed_at', 'closed_at_fmt', 'days_since_issued', 'created_by', 'actions',
    ]

    def test_all_keys_present(self):
        n = create_notice()
        serialized = serialize_notice(n)
        for key in self.REQUIRED_KEYS:
            self.assertIn(key, serialized, f"Missing key: {key}")

    def test_null_timestamp_fields_are_none(self):
        n = create_notice()  # reminder_1_at etc. are null
        serialized = serialize_notice(n)
        self.assertIsNone(serialized['reminder_1_at'])
        self.assertIsNone(serialized['reminder_1_at_fmt'])

    def test_actions_nested_dict_has_can_flags(self):
        n = create_notice()
        serialized = serialize_notice(n)
        actions = serialized['actions']
        self.assertIn('can_send_reminder_1', actions)
        self.assertIn('can_send_reminder_2', actions)
        self.assertIn('can_close', actions)
        self.assertIn('can_mark_expired', actions)


class TestListAuditLogs(TestCase):

    def test_returns_empty_list_for_new_notice(self):
        n = create_notice()
        logs = list_audit_logs(n.id)
        self.assertEqual(logs, [])

    def test_returns_logs_in_chronological_order(self):
        n = create_notice()
        ShowCauseAuditLog.objects.create(notice=n, action='ISSUED',     performed_by='officer1')
        ShowCauseAuditLog.objects.create(notice=n, action='REMINDER_1_SENT', performed_by='officer2')
        logs = list_audit_logs(n.id)
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]['action'], 'ISSUED')
        self.assertEqual(logs[1]['action'], 'REMINDER_1_SENT')

    def test_log_dict_has_required_fields(self):
        n = create_notice()
        ShowCauseAuditLog.objects.create(notice=n, action='ISSUED', performed_by='officer1', notes='test')
        log = list_audit_logs(n.id)[0]
        for key in ['action', 'action_display', 'performed_by', 'performed_at',
                    'performed_at_fmt', 'notes']:
            self.assertIn(key, log, f"Missing key: {key}")

    def test_action_display_is_human_readable(self):
        n = create_notice()
        ShowCauseAuditLog.objects.create(notice=n, action='ISSUED', performed_by='officer')
        log = list_audit_logs(n.id)[0]
        self.assertEqual(log['action_display'], 'Notice Issued')


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# PART 3: Service tests  (uses DB + mocks)
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────


class TestIssueNoticeBulk(TestCase):
    """issue_notice_bulk() — all paths including DB and email."""

    def setUp(self):
        self.hospital = create_hospital_beds(hospital_id="H001", email="h1@test.com")

    @patch('pmjay_fraud_dashboard_show_cause_engine.services.send_show_cause_email')
    def test_creates_notice_and_audit_log(self, mock_email):
        mock_email.return_value = True
        results = issue_notice_bulk(['H001'], '2024-01-01', '2024-01-31', 'officer1')
        self.assertEqual(results['issued'], ['H001'])
        self.assertEqual(results['errors'], [])
        self.assertEqual(ShowCauseNotice.objects.count(), 1)
        self.assertEqual(ShowCauseAuditLog.objects.filter(action='ISSUED').count(), 1)

    @patch('pmjay_fraud_dashboard_show_cause_engine.services.send_show_cause_email')
    def test_email_failure_creates_email_failed_log(self, mock_email):
        mock_email.return_value = False
        results = issue_notice_bulk(['H001'], '2024-01-01', '2024-01-31', 'officer1')
        self.assertIn('H001', results['issued'])
        self.assertEqual(ShowCauseAuditLog.objects.filter(action='EMAIL_FAILED').count(), 1)

    @patch('pmjay_fraud_dashboard_show_cause_engine.services.send_show_cause_email')
    def test_duplicate_returns_already_existed(self, mock_email):
        mock_email.return_value = True
        issue_notice_bulk(['H001'], '2024-01-01', '2024-01-31', 'officer1')
        results = issue_notice_bulk(['H001'], '2024-01-01', '2024-01-31', 'officer1')
        self.assertEqual(results['already_existed'], ['H001'])
        self.assertEqual(ShowCauseNotice.objects.count(), 1)  # Still only 1

    def test_hospital_not_found_returns_error(self):
        results = issue_notice_bulk(['UNKNOWN'], '2024-01-01', '2024-01-31', 'officer1')
        self.assertEqual(results['errors'][0]['hospital_id'], 'UNKNOWN')
        self.assertIn('not found', results['errors'][0]['reason'])

    @patch('pmjay_fraud_dashboard_show_cause_engine.services.send_show_cause_email')
    def test_bulk_mixed_results(self, mock_email):
        """Mix of success, not-found, and already-issued in one call."""
        mock_email.return_value = True
        create_hospital_beds(hospital_id="H002", email="h2@test.com")
        issue_notice_bulk(['H001'], '2024-01-01', '2024-01-31', 'officer1')

        results = issue_notice_bulk(
            ['H001', 'H002', 'MISSING'],
            '2024-01-01', '2024-01-31',
            'officer1'
        )
        self.assertIn('H001', results['already_existed'])
        self.assertIn('H002', results['issued'])
        self.assertEqual(results['errors'][0]['hospital_id'], 'MISSING')

    @patch('pmjay_fraud_dashboard_show_cause_engine.services.send_show_cause_email')
    def test_notice_status_is_issued_after_creation(self, mock_email):
        mock_email.return_value = True
        issue_notice_bulk(['H001'], '2024-01-01', '2024-01-31', 'officer1')
        n = ShowCauseNotice.objects.get(hospital_id='H001')
        self.assertEqual(n.status, ShowCauseStatus.ISSUED)

    @patch('pmjay_fraud_dashboard_show_cause_engine.services.send_show_cause_email')
    def test_same_hospital_different_date_range_creates_new_notice(self, mock_email):
        mock_email.return_value = True
        issue_notice_bulk(['H001'], '2024-01-01', '2024-01-31', 'officer1')
        results = issue_notice_bulk(['H001'], '2024-02-01', '2024-02-28', 'officer1')
        self.assertIn('H001', results['issued'])
        self.assertEqual(ShowCauseNotice.objects.count(), 2)


class TestSendReminder1Service(TestCase):
    """send_reminder_1() service — all paths."""

    def setUp(self):
        self.notice = create_notice(
            issued_at=timezone.now() - timedelta(days=8)
        )

    def test_not_found(self):
        result = send_reminder_1(99999, 'officer')
        self.assertFalse(result['ok'])
        self.assertIn('not found', result['error'])

    def test_wrong_status(self):
        self.notice.status = ShowCauseStatus.REMINDER_1_SENT
        self.notice.save()
        result = send_reminder_1(self.notice.id, 'officer')
        self.assertFalse(result['ok'])
        self.assertIn('ISSUED', result['error'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_too_early_without_bypass(self):
        self.notice.issued_at = timezone.now() - timedelta(days=2)
        self.notice.save()
        result = send_reminder_1(self.notice.id, 'officer')
        self.assertFalse(result['ok'])
        self.assertIn('Too early', result['error'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    @patch('pmjay_fraud_dashboard_show_cause_engine.services.send_show_cause_email')
    def test_success_after_7_days(self, mock_email):
        mock_email.return_value = True
        result = send_reminder_1(self.notice.id, 'officer')
        self.assertTrue(result['ok'])
        self.notice.refresh_from_db()
        self.assertEqual(self.notice.status, ShowCauseStatus.REMINDER_1_SENT)
        self.assertIsNotNone(self.notice.reminder_1_at)

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=True)
    @patch('pmjay_fraud_dashboard_show_cause_engine.services.send_show_cause_email')
    def test_success_with_bypass_even_if_too_early(self, mock_email):
        mock_email.return_value = True
        self.notice.issued_at = timezone.now()  # just now — would normally fail
        self.notice.save()
        result = send_reminder_1(self.notice.id, 'officer')
        self.assertTrue(result['ok'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    @patch('pmjay_fraud_dashboard_show_cause_engine.services.send_show_cause_email')
    def test_audit_log_written_on_success(self, mock_email):
        mock_email.return_value = True
        send_reminder_1(self.notice.id, 'officer')
        self.assertEqual(
            ShowCauseAuditLog.objects.filter(
                notice=self.notice, action='REMINDER_1_SENT'
            ).count(), 1
        )

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    @patch('pmjay_fraud_dashboard_show_cause_engine.services.send_show_cause_email')
    def test_email_failure_writes_email_failed_log(self, mock_email):
        mock_email.return_value = False
        result = send_reminder_1(self.notice.id, 'officer')
        self.assertTrue(result['ok'])  # Service succeeds despite email failing
        self.assertEqual(
            ShowCauseAuditLog.objects.filter(notice=self.notice, action='EMAIL_FAILED').count(), 1
        )

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    @patch('pmjay_fraud_dashboard_show_cause_engine.services.send_show_cause_email')
    def test_returns_serialized_notice_on_success(self, mock_email):
        mock_email.return_value = True
        result = send_reminder_1(self.notice.id, 'officer')
        self.assertIn('notice', result)
        self.assertEqual(result['notice']['status'], ShowCauseStatus.REMINDER_1_SENT)


class TestSendReminder2Service(TestCase):

    def setUp(self):
        self.notice = create_notice(
            status=ShowCauseStatus.REMINDER_1_SENT,
            issued_at=timezone.now() - timedelta(days=25),
            reminder_1_at=timezone.now() - timedelta(days=15),
        )

    def test_not_found(self):
        result = send_reminder_2(99999, 'officer')
        self.assertFalse(result['ok'])

    def test_wrong_status(self):
        self.notice.status = ShowCauseStatus.ISSUED
        self.notice.save()
        result = send_reminder_2(self.notice.id, 'officer')
        self.assertFalse(result['ok'])
        self.assertIn('REMINDER_1_SENT', result['error'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_too_early_without_bypass(self):
        self.notice.reminder_1_at = timezone.now() - timedelta(days=3)
        self.notice.save()
        result = send_reminder_2(self.notice.id, 'officer')
        self.assertFalse(result['ok'])
        self.assertIn('Too early', result['error'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    @patch('pmjay_fraud_dashboard_show_cause_engine.services.send_show_cause_email')
    def test_success(self, mock_email):
        mock_email.return_value = True
        result = send_reminder_2(self.notice.id, 'officer')
        self.assertTrue(result['ok'])
        self.notice.refresh_from_db()
        self.assertEqual(self.notice.status, ShowCauseStatus.REMINDER_2_SENT)
        self.assertIsNotNone(self.notice.reminder_2_at)


class TestMarkExpiredService(TestCase):

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_not_found(self):
        result = mark_expired(99999, 'officer')
        self.assertFalse(result['ok'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_already_closed(self):
        n = create_notice(status=ShowCauseStatus.CLOSED, closed_at=timezone.now())
        result = mark_expired(n.id, 'officer')
        self.assertFalse(result['ok'])
        self.assertIn('terminal', result['error'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_already_expired(self):
        n = create_notice(status=ShowCauseStatus.EXPIRED)
        result = mark_expired(n.id, 'officer')
        self.assertFalse(result['ok'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_too_early(self):
        n = create_notice(
            status=ShowCauseStatus.REMINDER_2_SENT,
            reminder_2_at=timezone.now() - timedelta(hours=6),
        )
        result = mark_expired(n.id, 'officer')
        self.assertFalse(result['ok'])
        self.assertIn('Too early', result['error'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=True)
    def test_success_with_bypass(self):
        n = create_notice(status=ShowCauseStatus.REMINDER_2_SENT,
                          reminder_2_at=timezone.now())  # just now
        result = mark_expired(n.id, 'officer')
        self.assertTrue(result['ok'])
        n.refresh_from_db()
        self.assertEqual(n.status, ShowCauseStatus.EXPIRED)

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_success_after_3_days(self):
        n = create_notice(
            status=ShowCauseStatus.REMINDER_2_SENT,
            issued_at=timezone.now() - timedelta(days=25),
            reminder_1_at=timezone.now() - timedelta(days=18),
            reminder_2_at=timezone.now() - timedelta(days=4),
        )
        result = mark_expired(n.id, 'officer')
        self.assertTrue(result['ok'])
        self.assertEqual(
            ShowCauseAuditLog.objects.filter(notice=n, action='EXPIRED').count(), 1
        )


class TestCloseNoticeService(TestCase):

    def test_not_found(self):
        result = close_notice(99999, 'officer')
        self.assertFalse(result['ok'])

    def test_cannot_close_already_closed(self):
        n = create_notice(status=ShowCauseStatus.CLOSED, closed_at=timezone.now())
        result = close_notice(n.id, 'officer')
        self.assertFalse(result['ok'])

    def test_close_from_issued(self):
        n = create_notice(status=ShowCauseStatus.ISSUED)
        result = close_notice(n.id, 'officer', notes='Resolved')
        self.assertTrue(result['ok'])
        n.refresh_from_db()
        self.assertEqual(n.status, ShowCauseStatus.CLOSED)
        self.assertIsNotNone(n.closed_at)

    def test_close_from_reminder_1_sent(self):
        n = create_notice(status=ShowCauseStatus.REMINDER_1_SENT,
                          reminder_1_at=timezone.now() - timedelta(days=8))
        result = close_notice(n.id, 'officer')
        self.assertTrue(result['ok'])

    def test_close_from_reminder_2_sent(self):
        n = create_notice(status=ShowCauseStatus.REMINDER_2_SENT,
                          reminder_1_at=timezone.now() - timedelta(days=18),
                          reminder_2_at=timezone.now() - timedelta(days=4))
        result = close_notice(n.id, 'officer')
        self.assertTrue(result['ok'])

    def test_notes_stored_in_audit_log(self):
        n = create_notice()
        close_notice(n.id, 'officer', notes='Hospital complied')
        log = ShowCauseAuditLog.objects.get(notice=n, action='CLOSED')
        self.assertEqual(log.notes, 'Hospital complied')

    def test_empty_notes_accepted(self):
        n = create_notice()
        result = close_notice(n.id, 'officer', notes='')
        self.assertTrue(result['ok'])

    def test_returns_serialized_notice(self):
        n = create_notice()
        result = close_notice(n.id, 'officer')
        self.assertIn('notice', result)
        self.assertEqual(result['notice']['status'], ShowCauseStatus.CLOSED)


class TestGetNoticesPage(TestCase):
    """get_notices_page() — pagination arithmetic."""

    def setUp(self):
        for i in range(7):
            create_notice(
                hospital_id=f"HOSP{i:03}",
                analytics_start_date=f"2024-0{(i % 9) + 1}-01",
                analytics_end_date=f"2024-0{(i % 9) + 1}-28",
            )

    def test_first_page(self):
        result = get_notices_page(page=1, page_size=3)
        self.assertEqual(len(result['notices']), 3)
        self.assertEqual(result['total'], 7)
        self.assertEqual(result['total_pages'], 3)
        self.assertTrue(result['has_next'])
        self.assertFalse(result['has_previous'])

    def test_last_page(self):
        result = get_notices_page(page=3, page_size=3)
        self.assertEqual(len(result['notices']), 1)  # 7 % 3 = 1
        self.assertFalse(result['has_next'])
        self.assertTrue(result['has_previous'])

    def test_page_clamps_to_1_if_below(self):
        result = get_notices_page(page=-5, page_size=3)
        self.assertEqual(result['page'], 1)

    def test_page_clamps_to_max_if_above(self):
        result = get_notices_page(page=999, page_size=3)
        self.assertEqual(result['page'], result['total_pages'])

    def test_status_filter_passed_through(self):
        ShowCauseNotice.objects.update(status=ShowCauseStatus.CLOSED)
        result = get_notices_page(status=ShowCauseStatus.ISSUED)
        self.assertEqual(result['total'], 0)


class TestGetSummary(TestCase):

    def test_all_zero_when_empty(self):
        summary = get_summary()
        self.assertEqual(summary['issued_today'], 0)
        self.assertEqual(summary['reminder_1_pending'], 0)
        self.assertEqual(summary['reminder_2_pending'], 0)
        self.assertEqual(summary['overdue'], 0)
        self.assertEqual(summary['closed'], 0)
        self.assertEqual(summary['expired'], 0)

    def test_counts_reflect_db(self):
        create_notice(status=ShowCauseStatus.ISSUED)
        create_notice(status=ShowCauseStatus.REMINDER_1_SENT,
                      reminder_1_at=timezone.now() - timedelta(days=1),
                      analytics_start_date="2024-02-01",
                      analytics_end_date="2024-02-28")
        create_notice(status=ShowCauseStatus.CLOSED,
                      closed_at=timezone.now(),
                      analytics_start_date="2024-03-01",
                      analytics_end_date="2024-03-31")
        summary = get_summary()
        self.assertEqual(summary['issued_today'], 3)  # All created today
        self.assertEqual(summary['reminder_1_pending'], 1)
        self.assertEqual(summary['reminder_2_pending'], 1)
        self.assertEqual(summary['closed'], 1)


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# PART 4: API View tests  (full HTTP stack)
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────


class BaseViewTest(TestCase):
    """Shared setup: creates a logged-in test client."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='test_officer',
            password='testpass123',
        )
        self.client.login(username='test_officer', password='testpass123')

    def post_json(self, url, data=None):
        import json
        from django.test import RequestFactory
        return self.client.post(
            url,
            data=json.dumps(data or {}),
            content_type='application/json',
        )


class TestAuthenticationRequired(BaseViewTest):
    """All endpoints require login — unauthenticated → 302."""

    def test_unauthenticated_send_show_cause(self):
        self.client.logout()
        res = self.client.post('/api/show-cause/send/')
        self.assertEqual(res.status_code, 302)

    def test_unauthenticated_list_notices(self):
        self.client.logout()
        res = self.client.get('/api/show-cause/notices/')
        self.assertEqual(res.status_code, 302)

    def test_unauthenticated_summary(self):
        self.client.logout()
        res = self.client.get('/api/show-cause/summary/')
        self.assertEqual(res.status_code, 302)

    def test_unauthenticated_management_page(self):
        self.client.logout()
        res = self.client.get('/api/show-cause/management/')
        self.assertEqual(res.status_code, 302)


class TestSendShowCauseView(BaseViewTest):

    def test_missing_hospitals_returns_400(self):
        res = self.post_json('/api/show-cause/send/', {'hospitals': []})
        self.assertEqual(res.status_code, 400)

    def test_missing_start_date_returns_400(self):
        res = self.post_json('/api/show-cause/send/', {
            'hospitals': ['H001'],
            'end_date': '2024-01-31'
        })
        self.assertEqual(res.status_code, 400)

    def test_missing_end_date_returns_400(self):
        res = self.post_json('/api/show-cause/send/', {
            'hospitals': ['H001'],
            'start_date': '2024-01-01'
        })
        self.assertEqual(res.status_code, 400)

    def test_invalid_json_returns_400(self):
        res = self.client.post(
            '/api/show-cause/send/',
            data='not json at all',
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)

    def test_get_method_not_allowed(self):
        res = self.client.get('/api/show-cause/send/')
        self.assertEqual(res.status_code, 405)

    @patch('pmjay_fraud_dashboard_show_cause_engine.services.send_show_cause_email')
    def test_success_returns_200_with_message(self, mock_email):
        mock_email.return_value = True
        create_hospital_beds('H001')
        res = self.post_json('/api/show-cause/send/', {
            'hospitals': ['H001'],
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('message', data)
        self.assertIn('results', data)


class TestListNoticesView(BaseViewTest):

    def test_returns_200_with_pagination(self):
        create_notice()
        res = self.client.get('/api/show-cause/notices/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('notices', data)
        self.assertIn('total', data)
        self.assertIn('total_pages', data)

    def test_status_filter_param(self):
        create_notice(status=ShowCauseStatus.ISSUED)
        create_notice(hospital_id='H002', status=ShowCauseStatus.CLOSED,
                      closed_at=timezone.now(),
                      analytics_start_date="2024-02-01",
                      analytics_end_date="2024-02-28")
        res = self.client.get('/api/show-cause/notices/?status=ISSUED')
        data = res.json()
        self.assertEqual(data['total'], 1)

    def test_page_size_capped_at_100(self):
        res = self.client.get('/api/show-cause/notices/?page_size=9999')
        # Should not crash and should cap silently
        self.assertEqual(res.status_code, 200)

    def test_post_method_not_allowed(self):
        res = self.client.post('/api/show-cause/notices/')
        self.assertEqual(res.status_code, 405)


class TestAuditLogView(BaseViewTest):

    def test_returns_404_for_nonexistent_notice(self):
        res = self.client.get('/api/show-cause/99999/audit-log/')
        self.assertEqual(res.status_code, 404)

    def test_returns_200_with_logs_list(self):
        n = create_notice()
        ShowCauseAuditLog.objects.create(notice=n, action='ISSUED', performed_by='officer')
        res = self.client.get(f'/api/show-cause/{n.id}/audit-log/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('logs', data)
        self.assertEqual(len(data['logs']), 1)

    def test_post_method_not_allowed(self):
        n = create_notice()
        res = self.client.post(f'/api/show-cause/{n.id}/audit-log/')
        self.assertEqual(res.status_code, 405)


class TestReminder1View(BaseViewTest):

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_too_early_returns_400(self):
        n = create_notice(issued_at=timezone.now())
        res = self.post_json(f'/api/show-cause/{n.id}/reminder-1/')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['ok'])

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=True)
    @patch('pmjay_fraud_dashboard_show_cause_engine.services.send_show_cause_email')
    def test_success_returns_200_with_notice(self, mock_email):
        mock_email.return_value = True
        n = create_notice(status=ShowCauseStatus.ISSUED, issued_at=timezone.now())
        res = self.post_json(f'/api/show-cause/{n.id}/reminder-1/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['ok'])
        self.assertIn('notice', data)
        self.assertEqual(data['notice']['status'], ShowCauseStatus.REMINDER_1_SENT)

    def test_get_method_not_allowed(self):
        n = create_notice()
        res = self.client.get(f'/api/show-cause/{n.id}/reminder-1/')
        self.assertEqual(res.status_code, 405)


class TestReminder2View(BaseViewTest):

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=True)
    @patch('pmjay_fraud_dashboard_show_cause_engine.services.send_show_cause_email')
    def test_success_with_bypass(self, mock_email):
        mock_email.return_value = True
        n = create_notice(
            status=ShowCauseStatus.REMINDER_1_SENT,
            reminder_1_at=timezone.now(),
        )
        res = self.post_json(f'/api/show-cause/{n.id}/reminder-2/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['notice']['status'], ShowCauseStatus.REMINDER_2_SENT)

    def test_wrong_status_returns_400(self):
        n = create_notice(status=ShowCauseStatus.ISSUED)
        res = self.post_json(f'/api/show-cause/{n.id}/reminder-2/')
        self.assertEqual(res.status_code, 400)


class TestExpireView(BaseViewTest):

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=True)
    def test_success_with_bypass(self):
        n = create_notice(status=ShowCauseStatus.REMINDER_2_SENT,
                          reminder_2_at=timezone.now())
        res = self.post_json(f'/api/show-cause/{n.id}/expire/')
        self.assertEqual(res.status_code, 200)
        n.refresh_from_db()
        self.assertEqual(n.status, ShowCauseStatus.EXPIRED)

    def test_cannot_expire_closed_notice(self):
        n = create_notice(status=ShowCauseStatus.CLOSED, closed_at=timezone.now())
        res = self.post_json(f'/api/show-cause/{n.id}/expire/')
        self.assertEqual(res.status_code, 400)


class TestCloseView(BaseViewTest):

    def test_success_without_notes(self):
        n = create_notice()
        res = self.post_json(f'/api/show-cause/{n.id}/close/')
        self.assertEqual(res.status_code, 200)
        n.refresh_from_db()
        self.assertEqual(n.status, ShowCauseStatus.CLOSED)

    def test_success_with_notes(self):
        n = create_notice()
        res = self.post_json(f'/api/show-cause/{n.id}/close/', {'notes': 'Resolved'})
        self.assertEqual(res.status_code, 200)
        log = ShowCauseAuditLog.objects.get(notice=n, action='CLOSED')
        self.assertEqual(log.notes, 'Resolved')

    def test_cannot_close_twice(self):
        n = create_notice(status=ShowCauseStatus.CLOSED, closed_at=timezone.now())
        res = self.post_json(f'/api/show-cause/{n.id}/close/')
        self.assertEqual(res.status_code, 400)

    def test_response_contains_updated_notice(self):
        n = create_notice()
        res = self.post_json(f'/api/show-cause/{n.id}/close/')
        data = res.json()
        self.assertIn('notice', data)
        self.assertIsNotNone(data['notice']['closed_at'])

    def test_empty_body_accepted(self):
        """close/ should work with no body at all."""
        n = create_notice()
        res = self.client.post(
            f'/api/show-cause/{n.id}/close/',
            data='',
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)


class TestSummaryView(BaseViewTest):

    def test_returns_all_expected_keys(self):
        res = self.client.get('/api/show-cause/summary/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        for key in ['issued_today', 'reminder_1_pending', 'reminder_2_pending',
                    'overdue', 'closed', 'expired']:
            self.assertIn(key, data, f"Missing summary key: {key}")

    def test_post_not_allowed(self):
        res = self.client.post('/api/show-cause/summary/')
        self.assertEqual(res.status_code, 405)


class TestManagementPageView(BaseViewTest):

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=True)
    def test_renders_with_dev_bypass_context(self):
        res = self.client.get('/api/show-cause/management/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Dev / Test Mode', res.content)

    @override_settings(SHOW_CAUSE_BYPASS_TIMING=False)
    def test_renders_without_dev_banner_in_production(self):
        res = self.client.get('/api/show-cause/management/')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b'Dev / Test Mode', res.content)

    def test_uses_correct_template(self):
        res = self.client.get('/api/show-cause/management/')
        self.assertTemplateUsed(res, 'show_cause_management.html')