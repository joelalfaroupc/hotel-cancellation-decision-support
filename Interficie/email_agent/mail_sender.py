from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path


EMAIL_ENV_KEYS = ("EMAIL_ADDRESS", "EMAIL_PASSWORD", "EMAIL_HOST", "EMAIL_PORT")
INTERFICIE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE_CANDIDATES = (
    INTERFICIE_DIR / ".env",
    INTERFICIE_DIR.parent / ".env",
    INTERFICIE_DIR.parent.parent / ".env",
)


def load_local_env_files() -> None:
    """Load missing SMTP variables from local .env files without overriding the shell."""
    for env_file in ENV_FILE_CANDIDATES:
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("#") or "=" not in cleaned:
                continue
            key, value = cleaned.split("=", 1)
            key = key.strip()
            if key not in EMAIL_ENV_KEYS or os.environ.get(key):
                continue
            os.environ[key] = value.strip().strip('"').strip("'")


@dataclass
class SMTPMailSender:
    email_address: str
    email_password: str
    email_host: str = "smtp.gmail.com"
    email_port: int = 465

    @classmethod
    def from_env(cls) -> "SMTPMailSender":
        load_local_env_files()
        email_address = os.environ.get("EMAIL_ADDRESS")
        email_password = os.environ.get("EMAIL_PASSWORD")
        if not email_address or not email_password:
            raise RuntimeError("EMAIL_ADDRESS and EMAIL_PASSWORD are required to send email")
        return cls(
            email_address=email_address,
            email_password=email_password,
            email_host=os.environ.get("EMAIL_HOST") or "smtp.gmail.com",
            email_port=int(os.environ.get("EMAIL_PORT") or 465),
        )

    def send(self, to_email: str, subject: str, content: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["To"] = to_email
        msg["From"] = self.email_address
        msg.set_content(content)

        try:
            with smtplib.SMTP_SSL(self.email_host, self.email_port) as smtp:
                smtp.login(self.email_address, self.email_password)
                smtp.send_message(msg)
        except smtplib.SMTPAuthenticationError as exc:
            detail = exc.smtp_error.decode("utf-8", errors="ignore") if isinstance(exc.smtp_error, bytes) else str(exc.smtp_error)
            if "Application-specific password required" in detail:
                raise RuntimeError(
                    "SMTP authentication failed: Gmail requires an app password in EMAIL_PASSWORD"
                ) from exc
            raise RuntimeError("SMTP authentication failed: check EMAIL_ADDRESS and EMAIL_PASSWORD") from exc
