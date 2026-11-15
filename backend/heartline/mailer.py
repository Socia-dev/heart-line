"""Optional: send one invitation by real email, typically to a judge's own address during the demo.

Configured in backend/.env, either Resend:
    RESEND_API_KEY, EMAIL_FROM
or plain SMTP:
    SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, EMAIL_FROM
HEARTLINE_PUBLIC_URL sets the base of the booking link (default http://localhost:5173).

The email carries the same neutral text as the SMS: no patient name, no condition, no case details.
The address typed in is used to send and is not stored.
"""
from __future__ import annotations

import base64
import json
import os
import re
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage

from . import voice

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class MailUnavailable(Exception):
    pass


def provider() -> str | None:
    if os.environ.get("RESEND_API_KEY") and os.environ.get("EMAIL_FROM"):
        return "resend"
    if os.environ.get("SMTP_HOST") and os.environ.get("EMAIL_FROM"):
        return "smtp"
    return None


def status() -> dict:
    return {"configured": provider() is not None, "provider": provider(),
            "how": "Add RESEND_API_KEY and EMAIL_FROM (or SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD and EMAIL_FROM) "
                   "to backend/.env, then restart the API."}


def link(token: str) -> str:
    base = (os.environ.get("HEARTLINE_PUBLIC_URL") or "http://localhost:5173").rstrip("/")
    return f"{base}/#/i/{token}"


def compose(token: str) -> dict:
    """The email, in Arabic then English. The same for every relative."""
    url = link(token)
    subject = "دعوة لفحص كوليسترول مجاني | Invitation to a free cholesterol check"
    ar = ("مرحباً،\n\nندعوك لإجراء فحص كوليسترول مجاني يستغرق نحو 10 دقائق، ولا تحتاج إلى الصيام. ارتفاع الكوليسترول ينتقل "
          "كثيراً بين أفراد العائلة، وعلاجه سهل عند اكتشافه مبكراً.\n\nاختر الموعد المناسب من هنا:\n" + url +
          "\n\nالقرار لك، والفحص مجاني وسري.\nبرنامج صحة الأسرة في أبوظبي")
    en = ("Hello,\n\nYou are invited to a free cholesterol check. It takes about 10 minutes and you do not need to fast. "
          "High cholesterol often runs in families and is easy to treat when it is found early.\n\nChoose a time here:\n"
          + url + "\n\nIt is your choice, and the check is free and private.\nAbu Dhabi family health programme")
    note = "\n\n---\nDemo on synthetic data. This invitation was sent from the Heart Line prototype."
    text = ar + "\n\n" + en + note
    html = (f'<div dir="rtl" lang="ar" style="font-family:Tahoma,sans-serif;font-size:16px;line-height:1.7">'
            f'{ar.replace(url, f"<a href={url!r}>{url}</a>").replace(chr(10), "<br>")}</div><hr style="border:0;margin:24px 0">'
            f'<div lang="en" style="font-family:Arial,sans-serif;font-size:16px;line-height:1.5">'
            f'{en.replace(url, f"<a href={url!r}>{url}</a>").replace(chr(10), "<br>")}</div>'
            f'<p style="color:#70666a;font-size:13px">Demo on synthetic data. Sent from the Heart Line prototype.</p>')
    attachments = []
    for lang in ("ar", "en"):
        try:
            attachments.append({"filename": f"invitation-{lang}.mp3", "path": str(voice.clip(lang))})
        except voice.VoiceUnavailable:
            pass  # no key: the email links to the page, which can read the text aloud with the device voice
    return {"subject": subject, "text": text, "html": html, "link": url, "voice_notes": [a["filename"] for a in attachments],
            "_attachments": attachments}


def _resend(to: str, mail: dict):
    body = {"from": os.environ["EMAIL_FROM"], "to": [to], "subject": mail["subject"], "text": mail["text"],
            "html": mail["html"],
            "attachments": [{"filename": a["filename"], "content": base64.b64encode(open(a["path"], "rb").read()).decode()}
                            for a in mail["_attachments"]]}
    req = urllib.request.Request("https://api.resend.com/emails", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
    except urllib.error.HTTPError as e:
        raise MailUnavailable(f"The email service refused it (HTTP {e.code}).") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise MailUnavailable(f"The email service could not be reached ({type(e).__name__}).") from None


def _smtp(to: str, mail: dict):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = os.environ["EMAIL_FROM"], to, mail["subject"]
    m.set_content(mail["text"])
    m.add_alternative(mail["html"], subtype="html")
    for a in mail["_attachments"]:
        m.add_attachment(open(a["path"], "rb").read(), maintype="audio", subtype="mpeg", filename=a["filename"])
    try:
        with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT") or 587), timeout=30) as s:
            s.starttls()
            if os.environ.get("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
            s.send_message(m)
    except (smtplib.SMTPException, OSError) as e:
        raise MailUnavailable(f"The mail server refused it ({type(e).__name__}).") from None


def send(to: str, token: str) -> dict:
    p = provider()
    if p is None:
        raise MailUnavailable("Email sending is not set up.")
    if not EMAIL.match(to or ""):
        raise MailUnavailable("That does not look like an email address.")
    mail = compose(token)
    (_resend if p == "resend" else _smtp)(to, mail)
    return {"sent": True, "provider": p, "voice_notes": mail["voice_notes"]}
