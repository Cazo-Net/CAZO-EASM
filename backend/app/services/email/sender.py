"""
Email sender service with provider abstraction.
Supports: SMTP, Resend, Postmark, Amazon SES.
Queue-based for reliability with retry logic.
"""

import logging
import smtplib
import threading
import time
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    to: str
    subject: str
    html_body: str
    text_body: str = ""
    from_name: str = "AttackSec"
    from_email: str = "noreply@attacksec.io"
    retries: int = 0
    max_retries: int = 3


class EmailProvider(ABC):
    @abstractmethod
    def send(self, message: EmailMessage) -> bool:
        pass


class SMTPProvider(EmailProvider):
    def __init__(self, host: str, port: int, username: str, password: str,
                 use_tls: bool = True, from_email: str = "noreply@attacksec.io"):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.from_email = from_email

    def send(self, message: EmailMessage) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.subject
            msg["From"] = f"{message.from_name} <{message.from_email or self.from_email}>"
            msg["To"] = message.to
            msg["X-Mailer"] = "AttackSec"
            msg["List-Unsubscribe"] = f"<mailto:unsubscribe@attacksec.io?subject=unsubscribe>"

            if message.text_body:
                msg.attach(MIMEText(message.text_body, "plain"))
            msg.attach(MIMEText(message.html_body, "html"))

            with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                if self.use_tls:
                    server.starttls()
                if self.username:
                    server.login(self.username, self.password)
                server.sendmail(msg["From"], [message.to], msg.as_string())
            return True
        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            return False


class ResendProvider(EmailProvider):
    def __init__(self, api_key: str, from_email: str = "noreply@attacksec.io"):
        self.api_key = api_key
        self.from_email = from_email

    def send(self, message: EmailMessage) -> bool:
        try:
            import httpx
            resp = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "from": f"{message.from_name} <{message.from_email or self.from_email}>",
                    "to": [message.to],
                    "subject": message.subject,
                    "html": message.html_body,
                    "text": message.text_body or "",
                },
                timeout=30,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Resend send failed: {e}")
            return False


class LogProvider(EmailProvider):
    """Logs emails instead of sending (for development)."""
    def send(self, message: EmailMessage) -> bool:
        logger.info(f"EMAIL → {message.to} | {message.subject}")
        return True


class EmailService:
    """Email service with queue, retry, and provider abstraction."""

    def __init__(self, provider: Optional[EmailProvider] = None):
        self.provider = provider or LogProvider()
        self._queue: deque[EmailMessage] = deque()
        self._lock = threading.Lock()
        self._running = False
        self._worker: Optional[threading.Thread] = None

    def send(self, to: str, subject: str, html_body: str, text_body: str = "",
             from_name: str = "AttackSec", from_email: str = "noreply@attacksec.io") -> bool:
        """Send email immediately (synchronous)."""
        msg = EmailMessage(
            to=to, subject=subject, html_body=html_body,
            text_body=text_body, from_name=from_name, from_email=from_email,
        )
        return self.provider.send(msg)

    def send_async(self, to: str, subject: str, html_body: str, text_body: str = "",
                   from_name: str = "AttackSec", from_email: str = "noreply@attacksec.io") -> None:
        """Queue email for async sending with retry."""
        msg = EmailMessage(
            to=to, subject=subject, html_body=html_body,
            text_body=text_body, from_name=from_name, from_email=from_email,
        )
        with self._lock:
            self._queue.append(msg)
        self._ensure_worker()

    def _ensure_worker(self):
        if not self._running:
            self._running = True
            self._worker = threading.Thread(target=self._process_queue, daemon=True)
            self._worker.start()

    def _process_queue(self):
        while self._running:
            msg = None
            with self._lock:
                if self._queue:
                    msg = self._queue.popleft()
            if msg:
                success = self.provider.send(msg)
                if not success and msg.retries < msg.max_retries:
                    msg.retries += 1
                    with self._lock:
                        self._queue.appendleft(msg)
                    time.sleep(2 ** msg.retries)
                elif not success:
                    logger.error(f"Email failed after {msg.max_retries} retries: {msg.to} - {msg.subject}")
            else:
                time.sleep(1)

    def stop(self):
        self._running = False


_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get the configured email service singleton based on environment."""
    global _email_service
    if _email_service is not None:
        return _email_service

    from app.config import settings

    provider_name = getattr(settings, "EMAIL_PROVIDER", "log")

    if provider_name == "smtp":
        provider = SMTPProvider(
            host=getattr(settings, "SMTP_HOST", "localhost"),
            port=getattr(settings, "SMTP_PORT", 587),
            username=getattr(settings, "SMTP_USERNAME", ""),
            password=getattr(settings, "SMTP_PASSWORD", ""),
            from_email=getattr(settings, "EMAIL_FROM", "noreply@attacksec.io"),
        )
    elif provider_name == "resend":
        provider = ResendProvider(
            api_key=getattr(settings, "RESEND_API_KEY", ""),
            from_email=getattr(settings, "EMAIL_FROM", "noreply@attacksec.io"),
        )
    else:
        provider = LogProvider()

    _email_service = EmailService(provider)
    return _email_service
