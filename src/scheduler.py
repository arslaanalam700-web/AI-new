"""
Scheduler: Automates daily brief generation at scheduled intervals or configured time of day.
"""

import time
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from src.workflow import BriefWorkflow


class DailyScheduler:
    """Manages recurring automated brief generation."""

    def __init__(
        self,
        workflow: Optional[BriefWorkflow] = None,
        run_at_hour: int = 8,
        run_at_minute: int = 0,
        webhook_url: Optional[str] = None
    ):
        self.workflow = workflow or BriefWorkflow()
        self.run_at_hour = run_at_hour
        self.run_at_minute = run_at_minute
        self.webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def execute_job(self) -> dict:
        """Run a single execution of the brief workflow and save files."""
        print(f"[{datetime.now(timezone.utc).isoformat()}] 🚀 Starting scheduled AI News Brief generation...")
        brief = self.workflow.run(lookback_hours=24)
        saved = self.workflow.save_brief(brief)
        print(f"[{datetime.now(timezone.utc).isoformat()}] ✅ Saved brief: {saved}")

        if self.webhook_url:
            success = self.workflow.send_webhook(brief, self.webhook_url)
            print(f"[{datetime.now(timezone.utc).isoformat()}] 📡 Webhook notification status: {'Success' if success else 'Failed'}")

        return saved

    def start_background(self) -> None:
        """Start scheduler in background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background schedule runner."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _run_loop(self) -> None:
        """Check every 60 seconds if current time matches scheduled run time."""
        last_run_day = None
        while self._running:
            now = datetime.now(timezone.utc)
            if (
                now.hour == self.run_at_hour
                and now.minute == self.run_at_minute
                and now.day != last_run_day
            ):
                try:
                    self.execute_job()
                    last_run_day = now.day
                except Exception as e:
                    print(f"Scheduler job error: {e}")
            time.sleep(30)


if __name__ == "__main__":
    scheduler = DailyScheduler()
    scheduler.execute_job()
