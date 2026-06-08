"""
Email utilities for GraamCredit.

Two notification types:
  1. Admin contact notification — fires when a contact form is submitted.
  2. Applicant result notification — fires after POST /api/apply.

Both functions are non-blocking best-effort: they log on failure and return
False so the caller can continue normally without crashing the request.

SMTP configuration is read from .env:
  SMTP_HOST     default smtp.gmail.com
  SMTP_PORT     default 587 (STARTTLS)
  SMTP_USER     Gmail address used to send
  SMTP_PASSWORD Gmail App Password (16-char, no spaces)
  ADMIN_EMAIL   Inbox that receives contact notifications
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# ── Shared ─────────────────────────────────────────────────────────────────────

def _smtp_config() -> dict:
    return {
        'host':     os.getenv('SMTP_HOST', 'smtp.gmail.com'),
        'port':     int(os.getenv('SMTP_PORT', '587')),
        'user':     os.getenv('SMTP_USER', ''),
        'password': os.getenv('SMTP_PASSWORD', ''),
        'admin':    os.getenv('ADMIN_EMAIL', ''),
    }


def _send(to: str, subject: str, html: str, plain: str) -> bool:
    cfg = _smtp_config()
    if not cfg['user'] or not cfg['password']:
        print('SMTP not configured — skipping email.')
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = f'GraamCredit <{cfg["user"]}>'
    msg['To']      = to
    msg.attach(MIMEText(plain, 'plain'))
    msg.attach(MIMEText(html,  'html'))

    try:
        with smtplib.SMTP(cfg['host'], cfg['port']) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg['user'], cfg['password'])
            server.sendmail(cfg['user'], to, msg.as_string())
        return True
    except Exception as exc:
        print(f'Email send failed: {exc}')
        return False


# ── Email 1: Admin contact notification ────────────────────────────────────────

def send_contact_notification(name: str, email: str, subject: str, message: str) -> bool:
    cfg = _smtp_config()
    if not cfg['admin']:
        print('ADMIN_EMAIL not set — skipping contact notification.')
        return False

    plain = (
        f'New contact form submission\n{"="*40}\n'
        f'Name   : {name}\nEmail  : {email}\nSubject: {subject}\n\nMessage:\n{message}'
    )

    html = f'''<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:600px;margin:auto;padding:24px;color:#111827;">
  <div style="background:#1D9E75;padding:16px 24px;border-radius:8px 8px 0 0;">
    <h2 style="color:#fff;margin:0;font-size:1.1rem;">📩 New Contact Message — GraamCredit</h2>
  </div>
  <div style="border:1px solid #E5E7EB;border-top:none;padding:24px;border-radius:0 0 8px 8px;">
    <table style="width:100%;border-collapse:collapse;">
      <tr><td style="padding:8px 0;color:#6B7280;font-size:0.85rem;width:100px;">Name</td><td style="padding:8px 0;font-weight:600;">{name}</td></tr>
      <tr><td style="padding:8px 0;color:#6B7280;font-size:0.85rem;">Reply-to</td><td style="padding:8px 0;"><a href="mailto:{email}" style="color:#1D9E75;">{email}</a></td></tr>
      <tr><td style="padding:8px 0;color:#6B7280;font-size:0.85rem;">Subject</td><td style="padding:8px 0;">{subject}</td></tr>
    </table>
    <hr style="border:none;border-top:1px solid #E5E7EB;margin:16px 0;" />
    <p style="color:#374151;white-space:pre-wrap;line-height:1.6;">{message}</p>
  </div>
  <p style="font-size:0.75rem;color:#9CA3AF;text-align:center;margin-top:16px;">GraamCredit Admin Panel · Student Project Demo</p>
</body>
</html>'''

    msg = MIMEMultipart('alternative')
    msg['Subject']  = f'[GraamCredit Contact] {subject}'
    msg['From']     = f'GraamCredit <{cfg["user"]}>'
    msg['To']       = cfg['admin']
    msg['Reply-To'] = email
    msg.attach(MIMEText(plain, 'plain'))
    msg.attach(MIMEText(html,  'html'))

    try:
        with smtplib.SMTP(cfg['host'], cfg['port']) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg['user'], cfg['password'])
            server.sendmail(cfg['user'], cfg['admin'], msg.as_string())
        return True
    except Exception as exc:
        print(f'Contact email failed: {exc}')
        return False


# ── Email 2: Applicant result notification ─────────────────────────────────────

def send_result_notification(
    to_email: str,
    applicant_name: str,
    application_id: str,
    eligible: bool,
    score: int,
    max_loan_amount: int,
    improvement_tips: list[str],
) -> bool:
    if not to_email:
        return False

    subject = (
        f'GraamCredit — Your application {application_id} is {"Pre-approved ✅" if eligible else "under review ❌"}'
    )

    # ── Plain text ──────────────────────────────────────────────────────────────
    if eligible:
        plain = (
            f'Dear {applicant_name},\n\n'
            f'Congratulations! Your GraamCredit application {application_id} has been pre-approved.\n\n'
            f'Eligibility Score : {score}/100\n'
            f'Max Loan Amount   : ₹{max_loan_amount:,}\n\n'
            f'A GraamCredit representative will contact you within 2 business days to guide you through the next steps.\n\n'
            f'GraamCredit Team'
        )
    else:
        tips_text = '\n'.join(f'  • {tip}' for tip in improvement_tips) if improvement_tips else '  • No specific tips available.'
        plain = (
            f'Dear {applicant_name},\n\n'
            f'Thank you for applying. Unfortunately your application {application_id} did not meet our current criteria.\n\n'
            f'Your Score : {score}/100  (minimum required: 40)\n\n'
            f'How to improve:\n{tips_text}\n\n'
            f'You may re-apply after addressing these points.\n\n'
            f'GraamCredit Team'
        )

    # ── HTML ────────────────────────────────────────────────────────────────────
    status_color  = '#22C55E' if eligible else '#EF4444'
    status_label  = 'Pre-Approved ✅' if eligible else 'Not Eligible ❌'
    score_color   = '#22C55E' if score >= 60 else ('#F59E0B' if score >= 40 else '#EF4444')

    if eligible:
        body_html = f'''
    <p style="color:#374151;line-height:1.7;">
      Dear <strong>{applicant_name}</strong>,<br><br>
      Congratulations! Your GraamCredit application has been <strong style="color:#22C55E;">pre-approved</strong>.
      A representative will contact you within 2 business days.
    </p>
    <div style="background:#F0FDF9;border:1px solid #BBF7D0;border-radius:8px;padding:16px 20px;margin:20px 0;">
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px;">
        <div><div style="font-size:0.75rem;color:#6B7280;text-transform:uppercase;letter-spacing:0.05em;">Eligibility Score</div>
          <div style="font-size:1.8rem;font-weight:800;color:{score_color};">{score}<span style="font-size:1rem;font-weight:400;color:#9CA3AF;">/100</span></div>
        </div>
        <div><div style="font-size:0.75rem;color:#6B7280;text-transform:uppercase;letter-spacing:0.05em;">Max Loan Amount</div>
          <div style="font-size:1.8rem;font-weight:800;color:#1D9E75;">₹{max_loan_amount:,}</div>
        </div>
      </div>
    </div>
'''
    else:
        tips_html = ''.join(f'<li style="margin-bottom:6px;">{tip}</li>' for tip in improvement_tips) if improvement_tips else '<li>No specific tips at this time.</li>'
        body_html = f'''
    <p style="color:#374151;line-height:1.7;">
      Dear <strong>{applicant_name}</strong>,<br><br>
      Thank you for applying. Unfortunately your application did not meet our current eligibility criteria.
    </p>
    <div style="background:#FFF7F7;border:1px solid #FECACA;border-radius:8px;padding:16px 20px;margin:20px 0;">
      <div style="font-size:0.75rem;color:#6B7280;text-transform:uppercase;letter-spacing:0.05em;">Your Score</div>
      <div style="font-size:1.8rem;font-weight:800;color:{score_color};">{score}<span style="font-size:1rem;font-weight:400;color:#9CA3AF;">/100</span></div>
      <div style="font-size:0.8rem;color:#9CA3AF;margin-top:2px;">Minimum required: 40</div>
    </div>
    <div style="margin:20px 0;">
      <p style="font-weight:700;margin-bottom:8px;">How to improve your score:</p>
      <ul style="padding-left:20px;color:#374151;line-height:1.8;">{tips_html}</ul>
    </div>
    <p style="color:#6B7280;font-size:0.88rem;">You may re-apply after addressing the points above.</p>
'''

    html = f'''<!DOCTYPE html>
<html>
<body style="font-family:'Segoe UI',sans-serif;max-width:600px;margin:auto;padding:24px;color:#111827;">
  <div style="background:#1D9E75;padding:16px 24px;border-radius:8px 8px 0 0;display:flex;align-items:center;gap:12px;">
    <div style="background:#fff;color:#1D9E75;font-weight:800;padding:4px 10px;border-radius:6px;font-size:1.1rem;">G</div>
    <h2 style="color:#fff;margin:0;font-size:1rem;">GraamCredit Application Result</h2>
    <span style="margin-left:auto;background:{status_color};color:#fff;font-size:0.75rem;font-weight:700;padding:3px 10px;border-radius:999px;">{status_label}</span>
  </div>
  <div style="border:1px solid #E5E7EB;border-top:none;padding:24px;border-radius:0 0 8px 8px;">
    <p style="font-size:0.78rem;color:#9CA3AF;margin-bottom:16px;">Application ID: <strong>{application_id}</strong></p>
    {body_html}
  </div>
  <p style="font-size:0.72rem;color:#9CA3AF;text-align:center;margin-top:16px;">
    This is an automated message from GraamCredit (student project demo).<br>
    No real financial products are offered. For queries, visit our <a href="#" style="color:#1D9E75;">contact page</a>.
  </p>
</body>
</html>'''

    return _send(to_email, subject, html, plain)
