"""
EmailService — all mail sending logic.
Uses Gmail SMTP with App Password (no OAuth needed).

Setup:
  Google Account → Security → 2-Step Verification → App passwords → Mail
  Copy 16-char password → SMTP_PASSWORD in .env
  Set SMTP_ENABLED=true
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from core.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:

    @staticmethod
    def send(
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Core send method. All other methods call this.
        Returns (success, message).
        """
        cfg = get_settings()

        if not cfg.smtp_enabled:
            logger.warning(f"[Email] SMTP disabled — would send to {to_email}: {subject}")
            return False, "SMTP chưa được bật. Kiểm tra SMTP_ENABLED trong .env"

        if not cfg.smtp_user or not cfg.smtp_password:
            return False, "Thiếu SMTP_USER hoặc SMTP_PASSWORD trong .env"

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{cfg.smtp_from_name} <{cfg.smtp_user}>"
            msg["To"] = to_email

            if text_body:
                msg.attach(MIMEText(text_body, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(cfg.smtp_user, cfg.smtp_password.replace(" ", ""))
                server.sendmail(cfg.smtp_user, to_email, msg.as_string())

            logger.info(f"[Email] ✅ Sent → {to_email}: {subject}")
            return True, "Email đã được gửi thành công."

        except smtplib.SMTPAuthenticationError:
            msg = "Xác thực Gmail thất bại. Kiểm tra SMTP_USER và App Password."
            logger.error(f"[Email] ❌ {msg}")
            return False, msg

        except smtplib.SMTPException as e:
            msg = f"Lỗi SMTP: {e}"
            logger.error(f"[Email] ❌ {msg}")
            return False, msg

        except Exception as e:
            msg = f"Lỗi không xác định: {e}"
            logger.error(f"[Email] ❌ {msg}")
            return False, msg

    # ── Email templates ───────────────────────────────────────────────────────

    @staticmethod
    def send_password_reset(
        to_email: str,
        full_name: str,
        username: str,
        temp_password: str,
        reset_by: str,
    ) -> tuple[bool, str]:
        """Send temporary password after admin resets user's password."""
        display = full_name or username
        subject = "[VPEI] Mật khẩu của bạn đã được đặt lại"

        html = f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:'Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6fb;padding:40px 20px;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(13,31,60,.10);">
  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#0d1f3c,#1e3a6e);padding:32px 40px;text-align:center;">
    <div style="font-size:2rem;font-weight:800;color:#fff;letter-spacing:-1px;">
      V<span style="color:#5a9bff;">P</span>EI
    </div>
    <div style="color:rgba(255,255,255,.6);font-size:.8rem;margin-top:4px;letter-spacing:.08em;text-transform:uppercase;">
      Vietnam Port Emission Inventory
    </div>
  </td></tr>
  <!-- Body -->
  <tr><td style="padding:36px 40px;">
    <p style="font-size:1rem;font-weight:600;color:#0d1f3c;margin:0 0 8px;">Xin chào {display},</p>
    <p style="font-size:.9rem;color:#4a5568;line-height:1.6;margin:0 0 24px;">
      Quản trị viên <strong>{reset_by}</strong> vừa đặt lại mật khẩu tài khoản VPEI của bạn.
    </p>
    <!-- Password box -->
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
      <tr><td style="background:#f0f6ff;border:2px dashed #2e7df7;border-radius:12px;padding:20px;text-align:center;">
        <div style="font-size:.75rem;color:#7a8aab;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;">
          Mật khẩu tạm thời
        </div>
        <div style="font-family:'Courier New',monospace;font-size:1.5rem;font-weight:700;color:#0d1f3c;letter-spacing:.15em;">
          {temp_password}
        </div>
        <div style="font-size:.75rem;color:#e53e3e;margin-top:8px;">
          ⚠ Vui lòng đổi mật khẩu ngay sau khi đăng nhập
        </div>
      </td></tr>
    </table>
    <!-- Account info -->
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:#fffbeb;border:1px solid #f6e05e;border-radius:10px;margin-bottom:28px;">
      <tr><td style="padding:14px 18px;">
        <p style="margin:0;font-size:.85rem;color:#7b6002;line-height:1.6;">
          <strong>Thông tin tài khoản:</strong><br>
          👤 Username: <code style="background:#fef3c7;padding:1px 6px;border-radius:4px;">{username}</code><br>
          📧 Email: <code style="background:#fef3c7;padding:1px 6px;border-radius:4px;">{to_email}</code>
        </p>
      </td></tr>
    </table>
    <hr style="border:none;border-top:1px solid #e8ecf4;margin:0 0 20px;">
    <p style="font-size:.78rem;color:#a0aec0;line-height:1.6;margin:0;">
      Email này được gửi tự động bởi hệ thống VPEI.<br>
      Nếu bạn không yêu cầu đặt lại mật khẩu, hãy liên hệ quản trị viên ngay.
    </p>
  </td></tr>
  <!-- Footer -->
  <tr><td style="background:#f4f6fb;padding:16px 40px;text-align:center;border-top:1px solid #e8ecf4;">
    <p style="margin:0;font-size:.75rem;color:#a0aec0;">
      © VPEI – Vietnam Port Emission Inventory · Carbon Monitoring &amp; ESG Platform
    </p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""

        text = (
            f"Xin chào {display},\n\n"
            f"Quản trị viên {reset_by} vừa đặt lại mật khẩu VPEI của bạn.\n\n"
            f"Mật khẩu tạm thời: {temp_password}\n"
            f"Username: {username}\n\n"
            f"Vui lòng đổi mật khẩu sau khi đăng nhập.\n\n"
            f"-- VPEI System"
        )

        return EmailService.send(to_email, subject, html, text)