import os
import re
from pathlib import Path

from dotenv import load_dotenv
import requests

load_dotenv(Path(__file__).resolve().parent / '.env')

OPENWA_BASE_URL = os.environ.get('OPENWA_BASE_URL', 'http://127.0.0.1:3000')
OPENWA_API_KEY = os.environ.get('OPENWA_API_KEY', '')
OPENWA_SESSION_ID = os.environ.get('OPENWA_SESSION_ID', '')


def _to_chat_id(phone):
    """Normalize a phone number to an OpenWA chatId.

    Examples:
    - '+974 508 27742' -> '97450827742@c.us'
    - '50827742' -> '97450827742@c.us' (Qatar default)
    """
    digits = re.sub(r'\D', '', str(phone))
    if not digits:
        raise ValueError('phone number is empty')

    if digits.startswith('00'):
        digits = digits[2:]
    elif digits.startswith('+'):
        digits = digits[1:]

    if len(digits) == 8:
        digits = '974' + digits
    elif len(digits) == 10 and digits.startswith('974'):
        digits = digits
    elif len(digits) == 11 and digits.startswith('974'):
        digits = digits
    elif len(digits) == 9 and digits.startswith('6'):
        digits = '974' + digits

    return f"{digits}@c.us"


def send_whatsapp_message(to, text):
    """Generic WhatsApp send via a self-hosted OpenWA gateway. Prints instead of raising if the send fails."""
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/messages/send-text"
    try:
        response = requests.post(
            url,
            headers={"X-API-Key": OPENWA_API_KEY, "Content-Type": "application/json"},
            json={"chatId": _to_chat_id(to), "text": text},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[whatsapp] to={to}\n{text}\n(send failed: {e})")
        return None


def ShortlistToCandidateMessage(candidate_phone, candidate_name, job_title, startup_name, checking_url):
    text = (
        f"Hi {candidate_name}! You've been shortlisted for {job_title} at {startup_name}.\n"
        f"Confirm your interest here: {checking_url}\n\n"
        "This is an automated message. No replies will be monitored."
    )
    return send_whatsapp_message(candidate_phone, text)


def ReminderToCandidateMessage(candidate_phone, candidate_name, job_title, startup_name, checking_url):
    text = (
        f"Hi {candidate_name}, this is a reminder about your application for {job_title} at {startup_name}.\n"
        f"We previously sent you an email with the details. Please use the link below to confirm your interest:\n"
        f"{checking_url}\n\n"
        "This is an automated message. No replies will be monitored."
    )
    return send_whatsapp_message(candidate_phone, text)


def ReviewShortlistToStartupMessage(startup_phone, startup_name, session_url):
    text = (
        f"Hi {startup_name}, you have a new shortlist of candidates waiting for review.\n"
        f"Please fill in your selections here: {session_url}\n\n"
        "This is an automated message. No replies will be monitored."
    )
    return send_whatsapp_message(startup_phone, text)


def CandidateConfirmedToStartupMessage(startup_phone, startup_name, candidate_name, action_url):
    text = (
        f"Hi {startup_name}, {candidate_name} confirmed interest in joining your team.\n"
        f"Schedule an interview or onboard instantly: {action_url}\n\n"
        "This is an automated message. No replies will be monitored."
    )
    return send_whatsapp_message(startup_phone, text)


def InterviewScheduledToCandidateMessage(candidate_phone, candidate_name, startup_name, date, time, location):
    time_part = f" at {time}" if time else ""
    location_part = f"\nLocation: {location}" if location else ""
    text = (
        f"Hi {candidate_name}, your interview with {startup_name} is scheduled for {date}{time_part}.{location_part}\n\n"
        "This is an automated message. No replies will be monitored."
    )
    return send_whatsapp_message(candidate_phone, text)


def _demo():
    assert _to_chat_id('+974 1234 5678') == '97412345678@c.us'
    assert _to_chat_id('(974) 1234-5678') == '97412345678@c.us'
    assert _to_chat_id('50827742') == '97450827742@c.us'
    assert _to_chat_id('+974 508 27742') == '97450827742@c.us'

    global OPENWA_BASE_URL
    real_url, OPENWA_BASE_URL = OPENWA_BASE_URL, 'http://127.0.0.1:1'  # deliberately unreachable
    assert send_whatsapp_message('+974 50827742', 'test') is None  # network failure -> caught, doesn't raise
    OPENWA_BASE_URL = real_url

    print('whatsapp_message: ok')


if __name__ == '__main__':
    _demo()
    send_whatsapp_message('+974 55711987', 'wanna test whatsapp message?')