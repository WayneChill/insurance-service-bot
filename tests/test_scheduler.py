import os
import unittest
from unittest.mock import Mock, patch

import scheduler


class SchedulerTests(unittest.TestCase):
    def test_only_sync_jobs_are_scheduled(self):
        # Use real APScheduler jobs, without starting its background thread.
        with patch.object(scheduler.BackgroundScheduler, "start"):
            scheduled = scheduler.start_scheduler(Mock())
        jobs = {job.id: job for job in scheduled.get_jobs()}
        self.assertEqual(set(jobs), {"property_renewal_sync", "judgment_sync"})
        self.assertIs(jobs["property_renewal_sync"].func, scheduler.run_daily_sync)
        self.assertIs(jobs["judgment_sync"].func, scheduler._sync_judgments)
        self.assertEqual(str(jobs["property_renewal_sync"].trigger), "cron[hour='0', minute='0']")
        self.assertEqual(str(jobs["judgment_sync"].trigger), "cron[hour='16,18,20', minute='10']")

    def test_daily_sync_runs_without_line_token_or_sending_messages(self):
        db = Mock()
        with patch.dict(os.environ, {"LINE_USER_ID": "test-owner"}, clear=True), \
                patch.object(scheduler, "_sync_property_renewals") as sync, \
                patch.object(scheduler, "_build_morning_report") as report, \
                patch("urllib.request.urlopen") as network:
            scheduler.run_daily_sync(db)
        sync.assert_called_once_with(db, "test-owner")
        report.assert_not_called()
        network.assert_not_called()

    def test_missing_owner_does_not_sync_to_anyone(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(scheduler, "_sync_property_renewals") as sync:
            scheduler.run_daily_sync(Mock())
        sync.assert_not_called()


if __name__ == "__main__":
    unittest.main()
