import os
from pathlib import Path

from dotenv import load_dotenv
import resend

load_dotenv(Path(__file__).resolve().parent / '.env')

resend.api_key = os.environ['RESEND_API_KEY']

DEFAULT_FROM = os.environ.get('RESEND_FROM', 'onboarding@resend.dev')


def send_email(to, subject, html, from_email=DEFAULT_FROM):
    """Generic email send via Resend. Prints instead of raising if the send fails."""
    try:
        return resend.emails.send({
            "from": from_email,
            "to": to,
            "subject": subject,
            "html": html,
        })
    except Exception as e:
        print(f"[email] to={to} subject={subject!r}\n{html}\n(send failed: {e})")
        return None


def ShortlistToCandidateMail(candidate_email, candidate_name, job_title, startup_name, startup_email, checking_url):
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
    return send_email(candidate_email, subject, body, from_email=startup_email)

