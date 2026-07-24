"""
Premium HTML email templates for CAZO EASM.
All templates are responsive, accessible, and work across Gmail, Outlook, Apple Mail, Yahoo.
"""

from app.config import settings as _settings

_FRONTEND_BASE = _settings.FRONTEND_URL.rstrip("/")

BRAND_COLOR = "#2563EB"
BRAND_COLOR_DARK = "#1D4ED8"
BG_COLOR = "#FFFFFF"
TEXT_COLOR = "#1F2937"
TEXT_MUTED = "#6B7280"
BORDER_COLOR = "#E5E7EB"
FOOTER_BG = "#F9FAFB"


def _base(title: str, body_html: str, preview_text: str = "") -> str:
    """Base email wrapper with consistent branding."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<title>{title}</title>
<!--[if mso]>
<noscript><xml>
<o:OfficeDocumentSettings>
<o:PixelsPerInch>96</o:PixelsPerInch>
</o:OfficeDocumentSettings>
</xml></noscript>
<![endif]-->
<style>
  body {{ margin: 0; padding: 0; background-color: #F3F4F6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; -webkit-font-smoothing: antialiased; }}
  .email-wrapper {{ width: 100%; background-color: #F3F4F6; padding: 40px 0; }}
  .email-container {{ max-width: 560px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .email-header {{ padding: 32px 40px 24px; text-align: center; }}
  .email-body {{ padding: 0 40px 32px; }}
  .email-footer {{ padding: 24px 40px; background: #F9FAFB; border-top: 1px solid #E5E7EB; text-align: center; }}
  .logo {{ font-size: 20px; font-weight: 700; color: #2563EB; letter-spacing: -0.5px; }}
  .logo-icon {{ display: inline-block; width: 32px; height: 32px; background: #2563EB; color: #FFF; border-radius: 8px; text-align: center; line-height: 32px; font-weight: 700; font-size: 14px; margin-right: 8px; vertical-align: middle; }}
  h1 {{ font-size: 22px; font-weight: 700; color: #1F2937; margin: 0 0 8px; }}
  p {{ font-size: 14px; line-height: 1.6; color: #4B5563; margin: 0 0 16px; }}
  .btn {{ display: inline-block; padding: 12px 28px; background: #2563EB; color: #FFFFFF !important; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px; mso-padding-alt: 0; }}
  .btn:hover {{ background: #1D4ED8; }}
  .btn-secondary {{ background: #F3F4F6; color: #374151 !important; border: 1px solid #D1D5DB; }}
  .btn-secondary:hover {{ background: #E5E7EB; }}
  .card {{ background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 20px; margin: 16px 0; }}
  .code {{ font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; font-size: 24px; font-weight: 700; color: #2563EB; letter-spacing: 4px; text-align: center; padding: 16px; background: #EFF6FF; border-radius: 8px; border: 1px dashed #BFDBFE; }}
  .divider {{ border: none; border-top: 1px solid #E5E7EB; margin: 24px 0; }}
  .footer-text {{ font-size: 12px; color: #9CA3AF; line-height: 1.5; }}
  .footer-text a {{ color: #6B7280; text-decoration: underline; }}
  .security-badge {{ display: inline-block; padding: 4px 10px; background: #FEF3C7; color: #92400E; border-radius: 12px; font-size: 11px; font-weight: 600; }}
  .alert {{ padding: 12px 16px; border-radius: 8px; margin: 16px 0; font-size: 13px; }}
  .alert-warning {{ background: #FEF3C7; border: 1px solid #FDE68A; color: #92400E; }}
  .alert-danger {{ background: #FEE2E2; border: 1px solid #FECACA; color: #991B1B; }}
  .alert-success {{ background: #D1FAE5; border: 1px solid #A7F3D0; color: #065F46; }}
  .info-row {{ display: flex; padding: 8px 0; border-bottom: 1px solid #F3F4F6; }}
  .info-label {{ font-size: 13px; color: #6B7280; width: 100px; }}
  .info-value {{ font-size: 13px; color: #1F2937; font-weight: 500; }}
  @media (prefers-color-scheme: dark) {{
    .email-container {{ background: #111827 !important; }}
    .email-header, .email-body {{ background: #111827 !important; }}
    h1, p, .info-value {{ color: #F9FAFB !important; }}
    .card {{ background: #1F2937 !important; border-color: #374151 !important; }}
    .email-footer {{ background: #1F2937 !important; border-color: #374151 !important; }}
    .footer-text, .footer-text a {{ color: #9CA3AF !important; }}
  }}
</style>
</head>
<body>
<div class="email-wrapper">
  <div class="email-container">
    <div class="email-header">
      <div class="logo"><span class="logo-icon">C</span>CAZO</div>
    </div>
    <div class="email-body">
      {body_html}
    </div>
    <div class="email-footer">
      <p class="footer-text">
        &copy; 2026 CAZO. All rights reserved.<br>
        <a href="#">Unsubscribe</a> &middot; <a href="#">Privacy Policy</a> &middot; <a href="#">Terms of Service</a><br>
        Need help? <a href="mailto:support@cazo.io">support@cazo.io</a>
      </p>
    </div>
  </div>
</div>
</body>
</html>"""


# ==================== EMAIL TEMPLATES ====================

def welcome_email(name: str, verify_url: str) -> tuple[str, str]:
    """Welcome email after registration."""
    html = _base("Welcome to CAZO EASM", f"""
      <h1>Welcome to CAZO EASM, {name}!</h1>
      <p>You're now part of a community of security professionals using CAZO EASM to map, monitor, and secure their external attack surface.</p>
      <div class="card">
        <p style="margin:0;font-size:13px;color:#6B7280;">Get started by verifying your email address:</p>
      </div>
      <div style="text-align:center;margin:24px 0;">
        <a href="{verify_url}" class="btn">Verify Email Address</a>
      </div>
      <p style="font-size:13px;color:#6B7280;">This link expires in 24 hours. If you didn't create an account, you can safely ignore this email.</p>
    """, "Welcome to CAZO EASM! Verify your email to get started.")
    return f"Welcome to CAZO EASM, {name}", html


def verify_email(name: str, verify_url: str) -> tuple[str, str]:
    """Email verification."""
    html = _base("Verify Your Email", f"""
      <h1>Verify your email address</h1>
      <p>Hi {name}, click the button below to verify your email address and activate your CAZO EASM account.</p>
      <div style="text-align:center;margin:24px 0;">
        <a href="{verify_url}" class="btn">Verify Email Address</a>
      </div>
      <p style="font-size:13px;color:#6B7280;">This link expires in 24 hours. If you didn't request this, please ignore this email.</p>
    """, "Verify your email address for CAZO EASM.")
    return "Verify your email address", html


def email_verified(name: str) -> tuple[str, str]:
    """Confirmation after email verification."""
    html = _base("Email Verified", f"""
      <div style="text-align:center;margin-bottom:24px;">
        <div style="display:inline-block;width:48px;height:48px;background:#D1FAE5;border-radius:50%;text-align:center;line-height:48px;font-size:24px;">&#10003;</div>
      </div>
      <h1 style="text-align:center;">Email Verified!</h1>
      <p style="text-align:center;">Your email address has been verified. Your CAZO EASM account is now fully active.</p>
      <div style="text-align:center;margin:24px 0;">
        <a href="{_FRONTEND_BASE}/dashboard" class="btn">Go to Dashboard</a>
      </div>
    """, "Your email has been verified. Welcome to CAZO EASM!")
    return "Email Verified", html


def password_reset(name: str, reset_url: str) -> tuple[str, str]:
    """Password reset request."""
    html = _base("Reset Your Password", f"""
      <h1>Reset your password</h1>
      <p>Hi {name}, we received a request to reset the password for your CAZO EASM account.</p>
      <div style="text-align:center;margin:24px 0;">
        <a href="{reset_url}" class="btn">Reset Password</a>
      </div>
      <p style="font-size:13px;color:#6B7280;">This link expires in 30 minutes. If you didn't request a password reset, your account is safe — no action needed.</p>
      <div class="alert alert-warning">
        <strong>Security tip:</strong> Choose a strong, unique password that you don't use elsewhere.
      </div>
    """, "Reset your CAZO EASM password.")
    return "Reset your password", html


def password_changed(name: str, ip_address: str) -> tuple[str, str]:
    """Password change confirmation."""
    html = _base("Password Changed", f"""
      <div style="text-align:center;margin-bottom:24px;">
        <div style="display:inline-block;width:48px;height:48px;background:#D1FAE5;border-radius:50%;text-align:center;line-height:48px;font-size:24px;">&#10003;</div>
      </div>
      <h1 style="text-align:center;">Password Changed</h1>
      <p style="text-align:center;">Your CAZO EASM password has been successfully changed.</p>
      <div class="card">
        <div class="info-row"><span class="info-label">When</span><span class="info-value">{ip_address}</span></div>
      </div>
      <div class="alert alert-warning">
        <strong>Didn't change your password?</strong> Contact <a href="mailto:support@cazo.io">support@cazo.io</a> immediately.
      </div>
    """, "Your CAZO EASM password has been changed.")
    return "Password Changed", html


def email_changed(name: str, old_email: str, new_email: str, verify_url: str) -> tuple[str, str]:
    """Email change confirmation."""
    html = _base("Email Change Request", f"""
      <h1>Email change requested</h1>
      <p>Hi {name}, we received a request to change the email address on your CAZO EASM account.</p>
      <div class="card">
        <div class="info-row"><span class="info-label">From</span><span class="info-value">{old_email}</span></div>
        <div class="info-row"><span class="info-label">To</span><span class="info-value">{new_email}</span></div>
      </div>
      <div style="text-align:center;margin:24px 0;">
        <a href="{verify_url}" class="btn">Confirm Email Change</a>
      </div>
      <p style="font-size:13px;color:#6B7280;">If you didn't request this change, please secure your account immediately.</p>
    """, "Confirm your email change on CAZO EASM.")
    return "Confirm email change", html


def new_login(name: str, ip_address: str, browser: str, os_name: str, location: str = "", is_new_device: bool = False) -> tuple[str, str]:
    """New login notification."""
    device_badge = '<span class="security-badge">New Device</span>' if is_new_device else ""
    html = _base("New Login Detected", f"""
      <h1>New login detected {device_badge}</h1>
      <p>Hi {name}, we detected a new sign-in to your CAZO EASM account.</p>
      <div class="card">
        <div class="info-row"><span class="info-label">Browser</span><span class="info-value">{browser}</span></div>
        <div class="info-row"><span class="info-label">OS</span><span class="info-value">{os_name}</span></div>
        <div class="info-row"><span class="info-label">IP</span><span class="info-value">{ip_address}</span></div>
        {f'<div class="info-row"><span class="info-label">Location</span><span class="info-value">{location}</span></div>' if location else ''}
      </div>
      <p style="font-size:13px;color:#6B7280;">If this was you, no action needed. If you don't recognize this activity, please change your password immediately.</p>
    """, f"New login to your CAZO EASM account from {ip_address}.")
    return "New login detected", html


def mfa_enabled(name: str) -> tuple[str, str]:
    """MFA enabled confirmation."""
    html = _base("MFA Enabled", """
      <div style="text-align:center;margin-bottom:24px;">
        <div style="display:inline-block;width:48px;height:48px;background:#D1FAE5;border-radius:50%;text-align:center;line-height:48px;font-size:24px;">&#128274;</div>
      </div>
      <h1 style="text-align:center;">Two-Factor Authentication Enabled</h1>
      <p style="text-align:center;">Two-factor authentication has been enabled on your CAZO EASM account. Your account is now more secure.</p>
      <div class="alert alert-success">
        <strong>Important:</strong> Store your backup codes in a safe place. You'll need them if you lose access to your authenticator app.
      </div>
    """, "Two-factor authentication has been enabled on your CAZO EASM account.")
    return "MFA Enabled", html


def mfa_disabled(name: str, ip_address: str) -> tuple[str, str]:
    """MFA disabled notification."""
    html = _base("MFA Disabled", f"""
      <h1>Two-Factor Authentication Disabled</h1>
      <p>Hi {name}, two-factor authentication has been disabled on your CAZO EASM account.</p>
      <div class="card">
        <div class="info-row"><span class="info-label">IP</span><span class="info-value">{ip_address}</span></div>
      </div>
      <div class="alert alert-warning">
        <strong>Didn't do this?</strong> Your account security may be at risk. Change your password immediately and contact support.
      </div>
    """, "Two-factor authentication has been disabled on your CAZO EASM account.")
    return "MFA Disabled", html


def account_locked(name: str, reason: str = "Too many failed login attempts") -> tuple[str, str]:
    """Account locked notification."""
    html = _base("Account Locked", f"""
      <h1>Account Locked</h1>
      <p>Hi {name}, your CAZO EASM account has been temporarily locked.</p>
      <div class="card">
        <div class="info-row"><span class="info-label">Reason</span><span class="info-value">{reason}</span></div>
      </div>
      <p>Your account will be automatically unlocked in 15 minutes. If you need immediate access, contact support.</p>
      <div class="alert alert-danger">
        <strong>Security notice:</strong> If you didn't attempt to log in, your credentials may be compromised. We recommend changing your password.
      </div>
    """, "Your CAZO EASM account has been locked for security.")
    return "Account Locked", html


def invitation_email(inviter_name: str, org_name: str, role: str, accept_url: str) -> tuple[str, str]:
    """Team invitation email."""
    html = _base("You're Invited to CAZO EASM", f"""
      <h1>You're invited to join {org_name}</h1>
      <p><strong>{inviter_name}</strong> has invited you to join their team on CAZO EASM as a <strong>{role}</strong>.</p>
      <div class="card">
        <div class="info-row"><span class="info-label">Organization</span><span class="info-value">{org_name}</span></div>
        <div class="info-row"><span class="info-label">Role</span><span class="info-value">{role}</span></div>
        <div class="info-row"><span class="info-label">Invited by</span><span class="info-value">{inviter_name}</span></div>
      </div>
      <div style="text-align:center;margin:24px 0;">
        <a href="{accept_url}" class="btn">Accept Invitation</a>
      </div>
      <p style="font-size:13px;color:#6B7280;">This invitation expires in 7 days. If you don't have an CAZO EASM account, you'll be prompted to create one.</p>
    """, f"{inviter_name} invited you to join {org_name} on CAZO EASM.")
    return f"Join {org_name} on CAZO EASM", html


def invitation_accepted(name: str, org_name: str) -> tuple[str, str]:
    """Invitation accepted notification to the inviter."""
    html = _base("Invitation Accepted", f"""
      <h1>Invitation Accepted</h1>
      <p><strong>{name}</strong> has accepted your invitation and joined your team on CAZO EASM.</p>
      <div class="card">
        <div class="info-row"><span class="info-label">Member</span><span class="info-value">{name}</span></div>
        <div class="info-row"><span class="info-label">Organization</span><span class="info-value">{org_name}</span></div>
      </div>
    """, f"{name} accepted your invitation to {org_name}.")
    return "Invitation Accepted", html


def security_alert(name: str, alert_type: str, details: str) -> tuple[str, str]:
    """Generic security alert."""
    html = _base("Security Alert", f"""
      <h1>Security Alert</h1>
      <p>Hi {name}, we detected unusual activity on your CAZO EASM account.</p>
      <div class="alert alert-danger">
        <strong>{alert_type}</strong><br>{details}
      </div>
      <p>If you don't recognize this activity, please take immediate action:</p>
      <ul style="font-size:14px;color:#4B5563;line-height:1.8;">
        <li>Change your password</li>
        <li>Enable two-factor authentication</li>
        <li>Review your active sessions</li>
      </ul>
      <div style="text-align:center;margin:24px 0;">
        <a href="{_FRONTEND_BASE}/settings" class="btn">Review Security Settings</a>
      </div>
    """, f"Security alert: {alert_type}")
    return "Security Alert", html


def workspace_created(name: str, org_name: str) -> tuple[str, str]:
    """Workspace created confirmation."""
    html = _base("Workspace Created", f"""
      <div style="text-align:center;margin-bottom:24px;">
        <div style="display:inline-block;width:48px;height:48px;background:#EFF6FF;border-radius:50%;text-align:center;line-height:48px;font-size:24px;">&#127970;</div>
      </div>
      <h1 style="text-align:center;">Workspace Created</h1>
      <p style="text-align:center;">Your workspace <strong>{org_name}</strong> has been created on CAZO EASM.</p>
      <div style="text-align:center;margin:24px 0;">
        <a href="{_FRONTEND_BASE}/dashboard" class="btn">Go to Dashboard</a>
      </div>
    """, f"Your workspace {org_name} is ready on CAZO EASM.")
    return "Workspace Created", html


# ==================== NOTIFICATION EMAIL TEMPLATES ====================
# Used by the centralized notification dispatch service.
# All use light-mode styling for maximum email client compatibility.


def scan_completed_email(name: str, domain: str, subdomains: int, vulns: int, scan_url: str) -> tuple[str, str]:
    """Scan completion notification email."""
    stats_html = ""
    if subdomains:
        stats_html += f'<div class="info-row"><span class="info-label">Subdomains</span><span class="info-value">{subdomains}</span></div>'
    if vulns:
        stats_html += f'<div class="info-row"><span class="info-label">Vulnerabilities</span><span class="info-value" style="color:#DC2626;">{vulns}</span></div>'
    if not stats_html:
        stats_html = '<p style="font-size:13px;color:#6B7280;">No issues detected.</p>'

    html = _base(f"Scan Completed: {domain}", f"""
      <h1>Scan Completed</h1>
      <p>Hi {name}, your scan for <strong>{domain}</strong> has completed.</p>
      <div class="card">
        {stats_html}
      </div>
      <div style="text-align:center;margin:24px 0;">
        <a href="{_FRONTEND_BASE}{scan_url}" class="btn">View Scan Results</a>
      </div>
    """, f"Scan completed for {domain}. {subdomains} subdomains, {vulns} vulnerabilities.")
    return f"Scan completed: {domain}", html


def scan_failed_email(name: str, domain: str, error: str, scan_url: str) -> tuple[str, str]:
    """Scan failure notification email."""
    html = _base(f"Scan Failed: {domain}", f"""
      <h1>Scan Failed</h1>
      <p>Hi {name}, your scan for <strong>{domain}</strong> has failed.</p>
      <div class="alert alert-danger">
        <strong>Error:</strong> {error}
      </div>
      <div style="text-align:center;margin:24px 0;">
        <a href="{_FRONTEND_BASE}{scan_url}" class="btn">View Details</a>
      </div>
    """, f"Scan failed for {domain}: {error}")
    return f"Scan failed: {domain}", html


def new_finding_email(name: str, domain: str, vuln_name: str, severity: str, scan_url: str) -> tuple[str, str]:
    """New vulnerability finding notification email."""
    severity_colors = {
        "critical": ("#DC2626", "#FEE2E2", "#991B1B"),
        "high": ("#EA580C", "#FFF7ED", "#9A3412"),
        "medium": ("#D97706", "#FFFBEB", "#92400E"),
        "low": ("#2563EB", "#EFF6FF", "#1E40AF"),
    }
    color, bg, text_color = severity_colors.get(severity.lower(), ("#6B7280", "#F3F4F6", "#374151"))

    html = _base(f"New {severity.title()} Finding: {vuln_name}", f"""
      <h1>New Vulnerability Found</h1>
      <p>Hi {name}, a <strong style="color:{color};">{severity.upper()}</strong> vulnerability was detected on <strong>{domain}</strong>.</p>
      <div class="card">
        <div class="info-row"><span class="info-label">Severity</span><span class="info-value"><span style="display:inline-block;padding:2px 8px;background:{bg};color:{text_color};border-radius:10px;font-size:11px;font-weight:600;">{severity.upper()}</span></span></div>
        <div class="info-row"><span class="info-label">Finding</span><span class="info-value">{vuln_name}</span></div>
        <div class="info-row"><span class="info-label">Domain</span><span class="info-value">{domain}</span></div>
      </div>
      <div style="text-align:center;margin:24px 0;">
        <a href="{_FRONTEND_BASE}{scan_url}" class="btn">Review Finding</a>
      </div>
    """, f"New {severity} finding: {vuln_name} on {domain}")
    return f"[{severity.upper()}] {vuln_name} — {domain}", html


def ssl_expiring_email(name: str, hostname: str, days_left: int, cert_url: str) -> tuple[str, str]:
    """SSL certificate expiring notification email."""
    urgency = "expired" if days_left <= 0 else f"expires in {days_left} day{'s' if days_left != 1 else ''}"
    alert_class = "alert-danger" if days_left <= 3 else "alert-warning"

    html = _base(f"SSL Certificate Expiring: {hostname}", f"""
      <h1>SSL Certificate Expiring</h1>
      <p>Hi {name}, the SSL certificate for <strong>{hostname}</strong> {urgency}.</p>
      <div class="alert {alert_class}">
        <strong>{'Expired' if days_left <= 0 else 'Days remaining'}:</strong> {abs(days_left) if days_left <= 0 else days_left}
      </div>
      <div style="text-align:center;margin:24px 0;">
        <a href="{_FRONTEND_BASE}{cert_url}" class="btn">View Certificate Details</a>
      </div>
    """, f"SSL certificate for {hostname} {urgency}.")
    return f"SSL {'expired' if days_left <= 0 else 'expiring'}: {hostname}", html


def new_shadow_asset_email(name: str, domain: str, asset_count: int, shadow_url: str) -> tuple[str, str]:
    """New shadow asset detected notification email."""
    html = _base(f"Shadow Assets Detected: {domain}", f"""
      <h1>Shadow Assets Detected</h1>
      <p>Hi {name}, CAZO detected <strong>{asset_count}</strong> potential shadow asset{'s' if asset_count != 1 else ''} associated with <strong>{domain}</strong>.</p>
      <div class="card">
        <p style="margin:0;font-size:13px;color:#6B7280;">Shadow assets are infrastructure that may belong to your organization but aren't in your known inventory. Review them to ensure they're authorized.</p>
      </div>
      <div style="text-align:center;margin:24px 0;">
        <a href="{_FRONTEND_BASE}{shadow_url}" class="btn">Review Shadow Assets</a>
      </div>
    """, f"{asset_count} shadow asset{'s' if asset_count != 1 else ''} detected for {domain}.")
    return f"Shadow assets detected: {domain}", html


def new_cve_email(name: str, domain: str, cve_id: str, severity: str, tech_name: str, cve_url: str) -> tuple[str, str]:
    """New CVE match notification email."""
    html = _base(f"New CVE Match: {cve_id}", f"""
      <h1>New CVE Match</h1>
      <p>Hi {name}, a new CVE was matched against your technology stack on <strong>{domain}</strong>.</p>
      <div class="card">
        <div class="info-row"><span class="info-label">CVE ID</span><span class="info-value" style="font-family:monospace;">{cve_id}</span></div>
        <div class="info-row"><span class="info-label">Severity</span><span class="info-value">{severity.upper()}</span></div>
        <div class="info-row"><span class="info-label">Technology</span><span class="info-value">{tech_name}</span></div>
        <div class="info-row"><span class="info-label">Domain</span><span class="info-value">{domain}</span></div>
      </div>
      <div style="text-align:center;margin:24px 0;">
        <a href="{_FRONTEND_BASE}{cve_url}" class="btn">Review CVE Match</a>
      </div>
    """, f"New CVE match: {cve_id} on {tech_name} ({domain}).")
    return f"[{severity.upper()}] {cve_id} — {tech_name}", html


def security_event_email(name: str, event_type: str, ip: str, browser: str, timestamp: str) -> tuple[str, str]:
    """Security event notification email (login, password change, email change)."""
    html = _base(event_type, f"""
      <h1>{event_type}</h1>
      <p>Hi {name}, a security event was detected on your account.</p>
      <div class="card">
        <div class="info-row"><span class="info-label">Event</span><span class="info-value">{event_type}</span></div>
        <div class="info-row"><span class="info-label">IP Address</span><span class="info-value" style="font-family:monospace;">{ip}</span></div>
        <div class="info-row"><span class="info-label">Device</span><span class="info-value">{browser[:60]}</span></div>
        <div class="info-row"><span class="info-label">Time</span><span class="info-value">{timestamp}</span></div>
      </div>
      <div class="alert alert-warning">
        <strong>If this wasn't you,</strong> change your password immediately and enable two-factor authentication.
      </div>
      <div style="text-align:center;margin:24px 0;">
        <a href="{_FRONTEND_BASE}/settings/security" class="btn">Review Security Settings</a>
      </div>
    """, f"Security alert: {event_type} on your CAZO account.")
    return f"Security Alert: {event_type}", html
