import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
import resend

load_dotenv(Path(__file__).resolve().parent / '.env')

DEFAULT_FROM = os.getenv('RESEND_FROM', 'onboarding@resend.dev')


def send_email(to, subject, html, from_email=None, api_key=None, reply_to=None, attachments=None):
    """Send an email via Resend using the configured API key."""
    resolved_api_key = (api_key or os.getenv('RESEND_API_KEY', '')).strip()
    if not resolved_api_key:
        raise RuntimeError('Missing RESEND_API_KEY')

    resend.api_key = resolved_api_key
    resolved_from = from_email or DEFAULT_FROM

    payload = {
        "from": resolved_from,
        "to": to,
        "subject": subject,
        "html": html,
    }
    if reply_to:
        payload["reply_to"] = reply_to
    if attachments:
        payload["attachments"] = attachments

    try:
        return resend.Emails.send(payload)
    except Exception as e:
        print(f"[email] to={to} subject={subject!r}\n{html}\n(send failed: {e})")
        return None


def ShortlistToCandidateMail(candidate_email, candidate_name, job_title, startup_name, startup_email, checking_url, api_key=None):
    subject = f"Congratulations! You've been shortlisted for {job_title} at {startup_name}"
    body = f"""
    Dear {candidate_name},

    We are thrilled to inform you that you have been shortlisted for the position of {job_title} at {startup_name}.

    Please find the details below:
    - Startup Name: {startup_name}
    - Job Title: {job_title}

    Please click the link below to confirm your interest:
    {checking_url}

    Best regards,
    {startup_name} Team
    """
    return send_email(
        candidate_email,
        subject,
        body,
        from_email=DEFAULT_FROM,
        api_key=api_key,
        reply_to=startup_email,
    )


def StartupOwnerInterviewMail(startup_email, candidate_name, startup_name, interview_link, api_key=None):
    subject = f"Interview setup requested for {candidate_name}"
    body = f"""Hello,

The candidate {candidate_name} is ready for the next step with {startup_name}.

Please set up the interview process and confirm the time slot.

Interview link: {interview_link}

Best regards,
Larus Team
"""
    return send_email(
        startup_email,
        subject,
        body,
        from_email=DEFAULT_FROM,
        api_key=api_key,
        reply_to=startup_email,
    )


def StartupCandidateConfirmedMail(startup_email, candidate_name, startup_name, job_title, action_url, api_key=None):
    subject = f"{candidate_name} confirmed interest — schedule interview or onboard"
    body = f"""Hello,

Great news! {candidate_name} has confirmed they are available for the {job_title or 'role'} at {startup_name}.

Please choose your next step:
- Schedule an interview (set date, time, and location)
- Instant onboard (skip interview and send offer)
- Decline the candidate

Take action here: {action_url}

Best regards,
Larus Team
"""
    return send_email(
        startup_email,
        subject,
        body,
        from_email=DEFAULT_FROM,
        api_key=api_key,
        reply_to=startup_email,
    )


def CandidateInterviewScheduledMail(candidate_email, candidate_name, startup_name, date, time, location, notes, api_key=None):
    subject = f"Interview scheduled with {startup_name}"
    time_line = f"\nTime: {time}" if time else ""
    location_line = f"\nLocation: {location}" if location else ""
    notes_line = f"\nNotes: {notes}" if notes else ""
    body = f"""Hello {candidate_name},

Your interview with {startup_name} has been scheduled.

Date: {date}{time_line}{location_line}{notes_line}

Please arrive on time and bring any materials requested by the startup.

Best regards,
Larus Team
"""
    return send_email(
        candidate_email,
        subject,
        body,
        from_email=DEFAULT_FROM,
        api_key=api_key,
        reply_to=None,
    )


def CandidateAcceptedMail(candidate_email, candidate_name, startup_name, api_key=None):
    subject = f"You have been accepted by {startup_name}"
    body = f"""Hello {candidate_name},

Congratulations — {startup_name} has accepted your application.

The next step will be shared with you shortly.

Best regards,
Larus Team
"""
    return send_email(
        candidate_email,
        subject,
        body,
        from_email=DEFAULT_FROM,
        api_key=api_key,
        reply_to=None,
    )


def _pdf_escape(text):
    return text.replace('\\', r'\\').replace('(', r'\(').replace(')', r'\)')


def _dummy_contract_pdf(candidate_name, startup_name, job_title):
    """Build a minimal, valid one-page PDF from scratch (no external PDF lib needed)."""
    today = date.today().isoformat()
    lines = [
        f"Offer & Contract Placeholder - {startup_name}",
        "",
        f"Candidate: {candidate_name}",
        f"Position: {job_title or 'Intern'}",
        f"Date: {today}",
        "",
        "This is a DUMMY contract generated automatically for demo purposes.",
        "It is not a legally binding document. A real contract will follow",
        "from the startup's HR team.",
        "",
        f"{startup_name} Team",
    ]
    stream_parts = ["BT", "/F1 12 Tf", "50 740 Td", "14 TL"]
    for i, line in enumerate(lines):
        if i:
            stream_parts.append("T*")
        stream_parts.append(f"({_pdf_escape(line)}) Tj")
    stream_parts.append("ET")
    stream = "\n".join(stream_parts).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_start = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode()
    out += f"startxref\n{xref_start}\n%%EOF".encode()
    return bytes(out)


def CandidateContractMail(candidate_email, candidate_name, startup_name, job_title=None, api_key=None):
    """Send the candidate a dummy contract PDF once they're accepted (interview pass or instant onboard)."""
    subject = f"Your contract from {startup_name}"
    body = f"""Hello {candidate_name},

Attached is your contract for the {job_title or 'role'} at {startup_name}.

Please review it — the startup's HR team will follow up with next steps.

Best regards,
Larus Team
"""
    pdf_bytes = _dummy_contract_pdf(candidate_name, startup_name, job_title)
    attachments = [{
        "filename": "contract.pdf",
        "content": list(pdf_bytes),
        "content_type": "application/pdf",
    }]
    return send_email(
        candidate_email,
        subject,
        body,
        from_email=DEFAULT_FROM,
        api_key=api_key,
        reply_to=None,
        attachments=attachments,
    )


def CandidateRejectedMail(candidate_email, candidate_name, startup_name, api_key=None):
    subject = f"Update on your application to {startup_name}"
    body = f"""Hello {candidate_name},

Thank you for your time. {startup_name} has decided not to move forward with your application at this stage.

We appreciate your interest and wish you the best in your search.

Best regards,
Larus Team
"""
    return send_email(
        candidate_email,
        subject,
        body,
        from_email=DEFAULT_FROM,
        api_key=api_key,
        reply_to=None,
    )

