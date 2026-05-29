import os
from datetime import datetime


def notification_providers() -> dict:
    return {
        "email_configured": bool(os.getenv("SMTP_HOST") or os.getenv("EMAILJS_PUBLIC_KEY")),
        "sms_configured": bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN")),
        "whatsapp_configured": bool(os.getenv("TWILIO_WHATSAPP_FROM")),
    }


def create_notification(
    db,
    user_id: int | None,
    title: str,
    message: str,
    notification_type: str = "info",
    channel: str = "in_app",
    related_type: str | None = None,
    related_id: int | None = None,
) -> int:
    cursor = db.execute(
        """
        INSERT INTO notifications
            (user_id, title, message, type, channel, related_type, related_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            title,
            message,
            notification_type,
            channel,
            related_type,
            related_id,
            datetime.utcnow().isoformat(timespec="seconds"),
        ),
    )
    return int(cursor.lastrowid)


def queue_external_notification(channel: str, destination: str, payload: dict) -> dict:
    return {
        "queued": False,
        "channel": channel,
        "destination": destination,
        "payload": payload,
        "message": "External notification provider is not configured. Add SMTP, EmailJS, or Twilio variables to enable this.",
    }

