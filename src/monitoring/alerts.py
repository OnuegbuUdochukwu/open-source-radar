from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

import structlog

from src.config import settings
from src.database import Database
from src.models import Alert, Metrics
from src.publisher.github_publisher import GitHubPublisher

logger = structlog.get_logger(__name__)


class AlertManager:
    """Monitors metrics thresholds and triggers alerts.

    When thresholds are exceeded:
    1. Writes alert to database
    2. Creates GitHub issue
    3. Sends email notification (if configured)
    """

    def __init__(self, database: Database, publisher: GitHubPublisher | None = None) -> None:
        self.db = database
        self.publisher = publisher

    async def check_thresholds(self, metrics: Metrics) -> list[Alert]:
        """Check all thresholds and create alerts if exceeded."""
        alerts: list[Alert] = []

        # README size checks
        readme_size_kb = metrics.readme_size_bytes / 1024

        if readme_size_kb >= settings.critical_readme_size_kb:
            alert = Alert(
                level="critical",
                message=(
                    f"README size ({readme_size_kb:.0f} KB) exceeds critical threshold "
                    f"({settings.critical_readme_size_kb} KB)"
                ),
                metric="readme_size",
                value=readme_size_kb,
                threshold=settings.critical_readme_size_kb,
            )
            alerts.append(alert)

        elif readme_size_kb >= settings.warning_readme_size_kb:
            alert = Alert(
                level="warning",
                message=(
                    f"README size ({readme_size_kb:.0f} KB) exceeds warning threshold "
                    f"({settings.warning_readme_size_kb} KB)"
                ),
                metric="readme_size",
                value=readme_size_kb,
                threshold=settings.warning_readme_size_kb,
            )
            alerts.append(alert)

        # Total ideas checks
        if metrics.total_ideas >= settings.critical_total_ideas:
            alert = Alert(
                level="critical",
                message=(
                    f"Total ideas ({metrics.total_ideas}) exceeds critical threshold "
                    f"({settings.critical_total_ideas})"
                ),
                metric="total_ideas",
                value=metrics.total_ideas,
                threshold=settings.critical_total_ideas,
            )
            alerts.append(alert)

        elif metrics.total_ideas >= settings.warning_total_ideas:
            alert = Alert(
                level="warning",
                message=(
                    f"Total ideas ({metrics.total_ideas}) exceeds warning threshold "
                    f"({settings.warning_total_ideas})"
                ),
                metric="total_ideas",
                value=metrics.total_ideas,
                threshold=settings.warning_total_ideas,
            )
            alerts.append(alert)

        for alert in alerts:
            self.db.save_alert(alert)
            if self.publisher:
                await self._trigger_github_issue(alert)

        if alerts:
            logger.warning("thresholds_exceeded", alert_count=len(alerts))
        else:
            logger.info("thresholds_normal")

        return alerts

    async def _trigger_github_issue(self, alert: Alert) -> None:
        """Create a GitHub issue for an alert."""
        if not self.publisher:
            return

        title = f"[{alert.level.upper()}] {alert.message}"
        body = (
            f"## Alert: {alert.level.title()}\n\n"
            f"**Metric:** {alert.metric}\n"
            f"**Current Value:** {alert.value:.1f}\n"
            f"**Threshold:** {alert.threshold}\n"
            f"**Time:** {alert.created_at.isoformat()}\n\n"
            f"### Recommended Action\n\n"
        )

        if "README" in alert.message:
            body += (
                "The README is growing large. Consider:\n"
                "1. Migrating to the JSON API / web platform\n"
                "2. Archiving older ideas\n"
                "3. Truncating descriptions\n"
            )
        else:
            body += (
                "The number of ideas is growing. Consider:\n"
                "1. Implementing pagination\n"
                "2. Archiving stale ideas\n"
                "3. Increasing filtering strictness\n"
            )

        issue_url = await self.publisher.create_issue(title, body)
        if issue_url:
            alert.github_issue_url = issue_url
            self.db.save_alert(alert)

    def send_email_alert(self, alert: Alert) -> None:
        """Send email notification for critical alerts.

        Requires SMTP configuration in environment variables.
        """
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = os.getenv("SMTP_PORT", "587")
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASS")
        alert_email = os.getenv("ALERT_EMAIL")

        if not all([smtp_host, smtp_user, smtp_pass, alert_email]):
            logger.warning("email_alerts_not_configured")
            return

        try:
            msg = EmailMessage()
            msg.set_content(
                f"Alert: {alert.level.upper()}\n\n"
                f"{alert.message}\n\n"
                f"Metric: {alert.metric}\n"
                f"Value: {alert.value}\n"
                f"Threshold: {alert.threshold}\n"
                f"Time: {alert.created_at.isoformat()}"
            )
            msg["Subject"] = f"[Open Source Radar] {alert.level.upper()}: {alert.message[:80]}"
            msg["From"] = smtp_user
            msg["To"] = alert_email

            with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            logger.info("email_alert_sent", alert_id=alert.id, email=alert_email)

        except Exception as e:
            logger.error("email_alert_failed", error=str(e))
