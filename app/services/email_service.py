import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def send_password_reset(self, *, to_email: str, full_name: str, reset_url: str) -> bool:
        subject = "Reset your Material Passport OS password"
        html = self._layout(
            heading="Reset your password",
            body=(
                f"Hi {full_name},<br><br>"
                "We received a request to reset your password. "
                "Use the button below to choose a new password."
            ),
            cta_label="Reset password",
            cta_url=reset_url,
        )
        return self._send(to_email=to_email, subject=subject, html=html)

    def send_invite(
        self,
        *,
        to_email: str,
        full_name: str,
        organization_name: str,
        role: str,
        invite_url: str,
    ) -> bool:
        subject = f"You have been invited to {organization_name}"
        html = self._layout(
            heading=f"Join {organization_name}",
            body=(
                f"Hi {full_name},<br><br>"
                f"You have been invited as <strong>{role.replace('_', ' ')}</strong> "
                "to manage environmental product data in Material Passport OS."
            ),
            cta_label="Accept invite",
            cta_url=invite_url,
        )
        return self._send(to_email=to_email, subject=subject, html=html)

    def _send(self, *, to_email: str, subject: str, html: str) -> bool:
        if self.settings.email_provider != "resend" or not self.settings.resend_api_key:
            logger.info("email_delivery_skipped", extra={"to_email": to_email, "subject": subject})
            return False

        try:
            with httpx.Client(timeout=10) as client:
                response = client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.settings.resend_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": self.settings.email_from,
                        "to": [to_email],
                        "subject": subject,
                        "html": html,
                    },
                )
        except httpx.HTTPError as exc:
            logger.warning(
                "email_delivery_error",
                extra={"to_email": to_email, "subject": subject, "error": str(exc)},
            )
            return False
        if response.status_code >= 400:
            logger.warning(
                "email_delivery_failed",
                extra={
                    "to_email": to_email,
                    "subject": subject,
                    "status_code": response.status_code,
                    "response": response.text[:500],
                },
            )
            return False
        logger.info("email_delivered", extra={"to_email": to_email, "subject": subject})
        return True

    def _layout(self, *, heading: str, body: str, cta_label: str, cta_url: str) -> str:
        return f"""
        <div style="font-family: Inter, Arial, sans-serif; color: #17201b; line-height: 1.55;">
          <h1 style="font-size: 22px; margin: 0 0 16px;">{heading}</h1>
          <p style="font-size: 15px; margin: 0 0 24px;">{body}</p>
          <a href="{cta_url}" style="display: inline-block; background: #1f7a4d; color: #ffffff;
             padding: 12px 18px; border-radius: 6px; text-decoration: none; font-weight: 700;">
            {cta_label}
          </a>
          <p style="font-size: 13px; color: #66736b; margin-top: 24px;">
            This link expires automatically. If the button does not work, copy this URL:
            <br>{cta_url}
          </p>
        </div>
        """
