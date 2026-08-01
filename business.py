import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

import persistance
import resend_mail
import whatsapp_message

load_dotenv(Path(__file__).resolve().parent / '.env')

BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:8000')

# ==============================================================================
# Custom Exceptions
# ==============================================================================

class ValidationError(Exception):
    """Raised when input data fails validation."""
    pass

class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""
    pass

class DuplicateError(Exception):
    """Raised when trying to create a record that already exists."""
    pass


# ==============================================================================
# Internal Validators
# ==============================================================================

VALID_CANDIDATE_STATUSES   = {'pending', 'accepted', 'rejected'}
VALID_INTERVIEW_STATUSES   = {'scheduled', 'completed', 'cancelled'}
VALID_INTERVIEW_OUTCOMES   = {'passed', 'failed', 'pending'}
VALID_SHORTLISTED_STATUSES = {'pending', 'claimed', 'invited', 'confirmed', 'declined', 'disabled', 'conflicted'}

DISABLE_CYCLE_DAYS = 90  # ~3 months cooldown after "already employed"
REMINDER_COOLDOWN_HOURS = 24  # don't re-alert the same open task more than once a day

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

def _require(fields: list, data: dict, label: str):
    """Raise ValidationError if any required field is missing or blank."""
    missing = [f for f in fields if not data.get(f)]
    if missing:
        raise ValidationError(f"[{label}] Missing required fields: {', '.join(missing)}")

def _validate_email(email: str):
    if not _EMAIL_RE.match(email):
        raise ValidationError(f"Invalid email address: '{email}'")

def _validate_status(status: str, allowed: set, label: str):
    if status not in allowed:
        raise ValidationError(
            f"[{label}] Invalid status '{status}'. Allowed: {', '.join(sorted(allowed))}"
        )

def _validate_id(id_value, label: str):
    if not id_value or not str(id_value).strip():
        raise ValidationError(f"[{label}] ID must not be empty.")


def _send_email(to: str, subject: str, html: str):
    """Send an email via Resend (resend_mail.py already wires up the API key)."""
    resend_mail.send_email(to, subject, html)


def _send_shortlist_notifications(shortlisted: dict):
    """Notify the candidate they were shortlisted. Startup is notified separately via session link."""
    candidate_name = shortlisted.get('name', '')
    startup_name = shortlisted.get('startup', '')
    job_title = shortlisted.get('job_title') or 'the role'
    candidate_email = shortlisted.get('email')
    startup_email = shortlisted.get('startup_email')
    candidate_phone = shortlisted.get('phone')

    shortlist_id = shortlisted.get('_id') or shortlisted.get('shortlist_id')
    checking_url = shortlisted.get('checking_url')
    if not checking_url and shortlist_id:
        checking_url = f"{BASE_URL}/verify/{shortlist_id}"
    if not checking_url:
        checking_url = f"{BASE_URL}/verify/placeholder"

    if candidate_email:
        resend_mail.ShortlistToCandidateMail(
            candidate_email,
            candidate_name,
            job_title,
            startup_name,
            startup_email or 'onboarding@resend.dev',
            checking_url,
        )

    if candidate_phone:
        whatsapp_message.ShortlistToCandidateMessage(
            candidate_phone,
            candidate_name,
            job_title,
            startup_name,
            checking_url,
        )


def _claim_shortlisted_for_startup(shortlisted_id: str, startup_name: str, startup_email: str):
    """Reserve a shortlisted candidate for one startup, preventing later collisions."""
    if not persistance.claim_shortlisted(shortlisted_id, startup_name, startup_email):
        entry = persistance.get_shortlisted(shortlisted_id)
        if entry and entry.get('status') in {'claimed', 'confirmed', 'invited', 'disabled', 'declined', 'conflicted'}:
            owner = entry.get('claimed_by') or entry.get('conflicted_by') or entry.get('startup')
            raise ValidationError(f"This candidate is already taken by {owner}.")
        raise ValidationError("This candidate is already taken by another startup.")
    return True


def _email_acceptance(candidate: dict):
    candidate_email = candidate.get('email')
    startup_name = candidate.get('startup', '')
    if candidate_email:
        resend_mail.CandidateAcceptedMail(candidate_email, candidate.get('name', ''), startup_name)
        resend_mail.CandidateContractMail(
            candidate_email, candidate.get('name', ''), startup_name, candidate.get('job_title')
        )
    startup_email = candidate.get('startup_email')
    if startup_email:
        resend_mail.StartupOwnerInterviewMail(startup_email, candidate.get('name', ''), startup_name, f"{BASE_URL}/admin")


def _email_rejection(candidate: dict):
    candidate_email = candidate.get('email')
    startup_name = candidate.get('startup', '')
    if candidate_email:
        resend_mail.CandidateRejectedMail(candidate_email, candidate.get('name', ''), startup_name)


def _email_interview_scheduled(candidate: dict, interview: dict):
    candidate_email = candidate.get('email')
    if candidate_email:
        resend_mail.CandidateInterviewScheduledMail(
            candidate_email,
            candidate.get('name', ''),
            candidate.get('startup', ''),
            interview.get('date', ''),
            interview.get('time'),
            interview.get('location'),
            interview.get('notes'),
        )
    candidate_phone = candidate.get('phone')
    if candidate_phone:
        whatsapp_message.InterviewScheduledToCandidateMessage(
            candidate_phone,
            candidate.get('name', ''),
            candidate.get('startup', ''),
            interview.get('date', ''),
            interview.get('time'),
            interview.get('location'),
        )


def _notify_startup_candidate_confirmed(candidate_id: str):
    """Email the startup a link to schedule interview, instant onboard, or reject."""
    candidate = get_candidate(candidate_id)
    startup_email = candidate.get('startup_email')
    token = persistance.create_action_session(
        candidate_id, candidate.get('startup', ''), startup_email or ''
    )
    action_url = f"{BASE_URL}/action/{token}/page"

    if startup_email:
        resend_mail.StartupCandidateConfirmedMail(
            startup_email,
            candidate.get('name', ''),
            candidate.get('startup', ''),
            candidate.get('job_title'),
            action_url,
        )

    startup_phone = candidate.get('startup_phone')
    if startup_phone:
        whatsapp_message.CandidateConfirmedToStartupMessage(
            startup_phone,
            candidate.get('startup', ''),
            candidate.get('name', ''),
            action_url,
        )

    return action_url


# ==============================================================================
# Candidates – Business Layer
# ==============================================================================

def add_candidate(candidate: dict):
    """
    Validate and insert a new candidate.

    Required fields: name, email, startup
    Optional fields: phone, cv_url, notes

    Raises DuplicateError if the email is already registered.
    Returns the inserted candidate ID.
    """
    _require(['name', 'email', 'startup'], candidate, 'Candidate')
    _validate_email(candidate['email'])

    if candidate.get('status'):
        _validate_status(candidate['status'], VALID_CANDIDATE_STATUSES, 'Candidate')

    if persistance.get_candidate_by_email(candidate['email']):
        raise DuplicateError(f"A candidate with email '{candidate['email']}' already exists.")

    candidate['name']    = candidate['name'].strip()
    candidate['email']   = candidate['email'].strip().lower()
    candidate['startup'] = candidate['startup'].strip()

    return persistance.add_candidate(candidate)


def get_candidate(candidate_id: str):
    """
    Fetch a candidate by ID.
    Raises NotFoundError if not found.
    """
    _validate_id(candidate_id, 'Candidate')
    record = persistance.get_candidate(candidate_id)
    if not record:
        raise NotFoundError(f"Candidate '{candidate_id}' not found.")
    return record


def get_candidate_by_email(email: str):
    """Fetch a candidate by email. Raises NotFoundError if not found."""
    _validate_email(email)
    record = persistance.get_candidate_by_email(email.strip().lower())
    if not record:
        raise NotFoundError(f"No candidate with email '{email}'.")
    return record


def get_all_candidates(filters: dict = None):
    """Return all candidates, optionally filtered."""
    return persistance.get_all_candidates(filters)


def get_candidates_by_startup(startup_name: str):
    """Return all candidates for a startup."""
    if not startup_name or not startup_name.strip():
        raise ValidationError("Startup name must not be empty.")
    return persistance.get_candidates_by_startup(startup_name.strip())


def get_candidates_by_status(status: str):
    """Return all candidates with a given status."""
    _validate_status(status, VALID_CANDIDATE_STATUSES, 'Candidate')
    return persistance.get_candidates_by_status(status)


def update_candidate(candidate_id: str, updates: dict):
    """
    Update arbitrary fields on a candidate.
    Validates email and status if they are being changed.
    Returns the modified count.
    """
    _validate_id(candidate_id, 'Candidate')
    if not updates:
        raise ValidationError("No update fields provided.")

    if 'email' in updates:
        _validate_email(updates['email'])
        updates['email'] = updates['email'].strip().lower()

    if 'status' in updates:
        _validate_status(updates['status'], VALID_CANDIDATE_STATUSES, 'Candidate')

    if 'name' in updates:
        updates['name'] = updates['name'].strip()

    return persistance.update_candidate(candidate_id, updates)


def update_candidate_status(candidate_id: str, status: str):
    """Change a candidate's pipeline status."""
    _validate_id(candidate_id, 'Candidate')
    _validate_status(status, VALID_CANDIDATE_STATUSES, 'Candidate')
    return persistance.update_candidate_status(candidate_id, status)


def remove_candidate(candidate_id: str):
    """Delete a candidate. Returns deleted count."""
    _validate_id(candidate_id, 'Candidate')
    get_candidate(candidate_id)         # raises NotFoundError if missing
    return persistance.remove_candidate(candidate_id)


def count_candidates(filters: dict = None):
    """Count candidates matching optional filters."""
    return persistance.count_candidates(filters)


# ==============================================================================
# Interviews – Business Layer
# ==============================================================================

def add_interview(interview: dict):
    """
    Validate and insert a new interview.

    Required fields: candidate_id, startup, date
    Optional fields: time, location, notes, status, outcome

    Returns the inserted interview ID.
    """
    _require(['candidate_id', 'startup', 'date'], interview, 'Interview')

    if interview.get('status'):
        _validate_status(interview['status'], VALID_INTERVIEW_STATUSES, 'Interview')

    if interview.get('outcome'):
        _validate_status(interview['outcome'], VALID_INTERVIEW_OUTCOMES, 'Interview outcome')

    # Ensure candidate exists
    candidate = persistance.get_candidate(interview['candidate_id'])
    if not candidate:
        raise NotFoundError(f"Cannot create interview: candidate '{interview['candidate_id']}' not found.")

    interview['startup'] = interview['startup'].strip()
    return persistance.add_interview(interview)


def get_interview(interview_id: str):
    """Fetch an interview by ID. Raises NotFoundError if not found."""
    _validate_id(interview_id, 'Interview')
    record = persistance.get_interview(interview_id)
    if not record:
        raise NotFoundError(f"Interview '{interview_id}' not found.")
    return record


def get_all_interviews(filters: dict = None):
    """Return all interviews, optionally filtered."""
    return persistance.get_all_interviews(filters)


def get_interviews_by_candidate(candidate_id: str):
    """Return all interviews for a candidate."""
    _validate_id(candidate_id, 'Candidate')
    return persistance.get_interviews_by_candidate(candidate_id)


def get_interviews_by_startup(startup_name: str):
    """Return all interviews linked to a startup."""
    if not startup_name or not startup_name.strip():
        raise ValidationError("Startup name must not be empty.")
    return persistance.get_interviews_by_startup(startup_name.strip())


def get_interviews_by_status(status: str):
    """Return interviews by status."""
    _validate_status(status, VALID_INTERVIEW_STATUSES, 'Interview')
    return persistance.get_interviews_by_status(status)


def update_interview(interview_id: str, updates: dict):
    """Update arbitrary fields on an interview."""
    _validate_id(interview_id, 'Interview')
    if not updates:
        raise ValidationError("No update fields provided.")

    if 'status' in updates:
        _validate_status(updates['status'], VALID_INTERVIEW_STATUSES, 'Interview')

    if 'outcome' in updates:
        _validate_status(updates['outcome'], VALID_INTERVIEW_OUTCOMES, 'Interview outcome')

    return persistance.update_interview(interview_id, updates)


def update_interview_status(interview_id: str, status: str):
    """Change an interview's status."""
    _validate_id(interview_id, 'Interview')
    _validate_status(status, VALID_INTERVIEW_STATUSES, 'Interview')
    return persistance.update_interview_status(interview_id, status)


def update_interview_outcome(interview_id: str, outcome: str):
    """Record the outcome of a completed interview and accept/reject the candidate."""
    _validate_id(interview_id, 'Interview')
    _validate_status(outcome, VALID_INTERVIEW_OUTCOMES, 'Interview outcome')

    interview = get_interview(interview_id)
    result = persistance.update_interview_outcome(interview_id, outcome)

    candidate_id = interview.get('candidate_id')
    if outcome == 'passed' and candidate_id:
        accept_candidate(candidate_id)
    elif outcome == 'failed' and candidate_id:
        reject_candidate(candidate_id)

    return result


def remove_interview(interview_id: str):
    """Delete an interview. Returns deleted count."""
    _validate_id(interview_id, 'Interview')
    get_interview(interview_id)         # raises NotFoundError if missing
    return persistance.remove_interview(interview_id)


def count_interviews(filters: dict = None):
    """Count interviews matching optional filters."""
    return persistance.count_interviews(filters)


# ==============================================================================
# Shortlisted – Business Layer
# ==============================================================================

def add_shortlisted(shortlisted: dict):
    """
    Validate and insert a shortlisted entry.

    Required fields: name, email, startup
    Optional fields: cv_url, notes, status

    Returns the inserted ID.
    """
    _require(['name', 'email', 'startup'], shortlisted, 'Shortlisted')
    _validate_email(shortlisted['email'])

    if shortlisted.get('status'):
        _validate_status(shortlisted['status'], VALID_SHORTLISTED_STATUSES, 'Shortlisted')

    shortlisted['name']    = shortlisted['name'].strip()
    shortlisted['email']   = shortlisted['email'].strip().lower()
    shortlisted['startup'] = shortlisted['startup'].strip()

    shortlisted_id = persistance.add_shortlisted(shortlisted)
    shortlisted['_id'] = str(shortlisted_id)
    shortlisted['shortlist_id'] = str(shortlisted_id)
    _send_shortlist_notifications(shortlisted)
    return shortlisted_id


def get_shortlisted(shortlisted_id: str):
    """Fetch a shortlisted entry by ID. Raises NotFoundError if not found."""
    _validate_id(shortlisted_id, 'Shortlisted')
    record = persistance.get_shortlisted(shortlisted_id)
    if not record:
        raise NotFoundError(f"Shortlisted entry '{shortlisted_id}' not found.")
    return record


def get_all_shortlisted(filters: dict = None):
    """Return all shortlisted entries, optionally filtered."""
    return persistance.get_all_shortlisted(filters)


def get_shortlisted_by_startup(startup_name: str):
    """Return all shortlisted candidates for a startup."""
    if not startup_name or not startup_name.strip():
        raise ValidationError("Startup name must not be empty.")
    return persistance.get_shortlisted_by_startup(startup_name.strip())


def get_shortlisted_by_candidate(candidate_id: str):
    """Return shortlisting records linked to a candidate."""
    _validate_id(candidate_id, 'Candidate')
    return persistance.get_shortlisted_by_candidate(candidate_id)


def get_shortlisted_by_status(status: str):
    """Return shortlisted entries by status."""
    _validate_status(status, VALID_SHORTLISTED_STATUSES, 'Shortlisted')
    return persistance.get_shortlisted_by_status(status)


def update_shortlisted(shortlisted_id: str, updates: dict):
    """Update arbitrary fields on a shortlisted entry."""
    _validate_id(shortlisted_id, 'Shortlisted')
    if not updates:
        raise ValidationError("No update fields provided.")

    if 'email' in updates:
        _validate_email(updates['email'])
        updates['email'] = updates['email'].strip().lower()

    if 'status' in updates:
        _validate_status(updates['status'], VALID_SHORTLISTED_STATUSES, 'Shortlisted')

    if 'name' in updates:
        updates['name'] = updates['name'].strip()

    return persistance.update_shortlisted(shortlisted_id, updates)


def update_shortlisted_status(shortlisted_id: str, status: str):
    """Change a shortlisted entry's status."""
    _validate_id(shortlisted_id, 'Shortlisted')
    _validate_status(status, VALID_SHORTLISTED_STATUSES, 'Shortlisted')
    return persistance.update_shortlisted_status(shortlisted_id, status)


def remove_shortlisted(shortlisted_id: str):
    """Delete a shortlisted entry. Returns deleted count."""
    _validate_id(shortlisted_id, 'Shortlisted')
    get_shortlisted(shortlisted_id)     # raises NotFoundError if missing
    return persistance.remove_shortlisted(shortlisted_id)


def count_shortlisted(filters: dict = None):
    """Count shortlisted entries matching optional filters."""
    return persistance.count_shortlisted(filters)


# ==============================================================================
# Pipeline Operations – Business Layer
# ==============================================================================

def shortlist_to_candidate(shortlisted_id: str):
    """
    Promote a shortlisted person into the Candidates collection.
    Validates the entry exists and isn't already confirmed.
    Returns the new candidate ID.
    """
    _validate_id(shortlisted_id, 'Shortlisted')
    entry = get_shortlisted(shortlisted_id)         # raises NotFoundError if missing

    if entry.get('status') == 'confirmed':
        raise ValidationError(
            f"Shortlisted entry '{shortlisted_id}' is already confirmed as a candidate."
        )
    if entry.get('status') == 'declined':
        raise ValidationError(
            f"Shortlisted entry '{shortlisted_id}' has been declined and cannot be promoted."
        )

    return persistance.shortlist_to_candidate(shortlisted_id)


def schedule_interview_for_candidate(candidate_id: str, interview_details: dict):
    """
    Schedule an interview for an existing candidate.

    Required in interview_details: date
    The candidate must be in 'pending' status (not already accepted/rejected).
    Returns the new interview ID.
    """
    _validate_id(candidate_id, 'Candidate')
    _require(['date'], interview_details, 'Interview details')

    candidate = get_candidate(candidate_id)         # raises NotFoundError if missing
    if candidate.get('status') == 'accepted':
        raise ValidationError(f"Candidate '{candidate_id}' is already accepted.")
    if candidate.get('status') == 'rejected':
        raise ValidationError(f"Candidate '{candidate_id}' has been rejected and cannot be interviewed.")

    interview_id = persistance.schedule_interview_for_candidate(candidate_id, interview_details)
    interview = get_interview(str(interview_id))
    _email_interview_scheduled(candidate, interview)
    return interview_id


def accept_candidate(candidate_id: str):
    """
    Accept a candidate after passing the pipeline.
    Must be in 'pending' status. Emails them the offer + contract follow-up.
    """
    _validate_id(candidate_id, 'Candidate')
    candidate = get_candidate(candidate_id)
    if candidate.get('status') == 'accepted':
        raise ValidationError(f"Candidate '{candidate_id}' is already accepted.")
    if candidate.get('status') == 'rejected':
        raise ValidationError(f"Candidate '{candidate_id}' was rejected and cannot be accepted.")
    result = persistance.accept_candidate(candidate_id)
    _email_acceptance(candidate)
    return result


def reject_candidate(candidate_id: str):
    """
    Reject a candidate.
    Must not already be accepted or rejected. Emails them a rejection follow-up.
    """
    _validate_id(candidate_id, 'Candidate')
    candidate = get_candidate(candidate_id)
    if candidate.get('status') == 'rejected':
        raise ValidationError(f"Candidate '{candidate_id}' is already rejected.")
    if candidate.get('status') == 'accepted':
        raise ValidationError(f"Candidate '{candidate_id}' is already accepted and cannot be rejected.")
    result = persistance.reject_candidate(candidate_id)
    _email_rejection(candidate)
    return result


def instant_onboard_candidate(candidate_id: str):
    """
    Instantly onboard a candidate (skip interview path).
    Only valid for 'pending' candidates. Emails them the offer + contract follow-up.
    """
    _validate_id(candidate_id, 'Candidate')
    candidate = get_candidate(candidate_id)
    if candidate.get('status') != 'pending':
        raise ValidationError(
            f"Instant onboarding only applies to pending candidates. "
            f"Current status: '{candidate.get('status')}'."
        )
    result = persistance.instant_onboard_candidate(candidate_id)
    _email_acceptance(candidate)
    return result


def get_pipeline_summary():
    """Return a count summary across all pipeline stages."""
    return persistance.get_pipeline_summary()


def get_candidate_progress(candidate_id: str):
    """Full picture of one candidate: profile, shortlist bio (major/university/linkedin/cv), and interview history."""
    candidate = get_candidate(candidate_id)     # raises NotFoundError if missing
    shortlisted = persistance.get_shortlisted(candidate['shortlist_id']) if candidate.get('shortlist_id') else None
    interviews = persistance.get_interviews_by_candidate(candidate_id)
    return {'candidate': candidate, 'shortlisted': shortlisted, 'interviews': interviews}


def get_all_startups():
    """Distinct startup names seen so far (every startup enters via a shortlist)."""
    return sorted({entry['startup'] for entry in persistance.get_all_shortlisted() if entry.get('startup')})


def get_startup_summary(startup_name: str):
    """Everything tracked for one startup: shortlist, candidates (interns), interviews, and roll-up counts."""
    if not startup_name or not startup_name.strip():
        raise ValidationError("Startup name must not be empty.")
    startup_name = startup_name.strip()

    shortlisted = get_shortlisted_by_startup(startup_name)
    candidates = get_candidates_by_startup(startup_name)
    interviews = get_interviews_by_startup(startup_name)

    counts = {
        'shortlisted_total':    len(shortlisted),
        'shortlisted_pending':  sum(1 for s in shortlisted if s.get('status') == 'pending'),
        'candidates_total':     len(candidates),
        'candidates_pending':   sum(1 for c in candidates if c.get('status') == 'pending'),
        'candidates_accepted':  sum(1 for c in candidates if c.get('status') == 'accepted'),
        'candidates_rejected':  sum(1 for c in candidates if c.get('status') == 'rejected'),
        'interviews_total':     len(interviews),
        'interviews_scheduled': sum(1 for i in interviews if i.get('status') == 'scheduled'),
        'interviews_completed': sum(1 for i in interviews if i.get('status') == 'completed'),
    }

    return {
        'startup': startup_name,
        'counts': counts,
        'shortlisted': shortlisted,
        'candidates': candidates,
        'interviews': interviews,
    }


# ==============================================================================
# Email Verification – Business Layer
# ==============================================================================

def invite_for_verification(shortlisted_id: str):
    """
    Email a shortlisted entry asking (1) are they already employed elsewhere,
    (2) are they down for the position. Returns the verification token.
    """
    entry = get_shortlisted(shortlisted_id)     # raises NotFoundError if missing

    if entry.get('status') == 'disabled':
        until = entry.get('disabled_until')
        if until and until > datetime.utcnow():
            raise ValidationError(
                f"Shortlisted entry '{shortlisted_id}' is on cooldown until {until.isoformat()}."
            )
    elif entry.get('status') in ('confirmed', 'declined'):
        raise ValidationError(
            f"Shortlisted entry '{shortlisted_id}' has already been processed (status: '{entry['status']}')."
        )

    token = persistance.create_verification(shortlisted_id)
    persistance.update_shortlisted(shortlisted_id, {'status': 'invited'})

    _send_email(
        entry['email'],
        "Are you still available for this position?",
        f"<p>Hi {entry.get('name', '')},</p>"
        f"<p>Please confirm your interest for the {entry.get('startup', '')} position:</p>"
        f'<p><a href="{BASE_URL}/verify/{token}">{BASE_URL}/verify/{token}</a></p>',
    )
    return token


def submit_verification(token: str, already_employed: bool, down_for_position: bool):
    """
    Record a candidate's reply to a verification email.

    - already_employed=True  -> disabled for a 3-month cooldown, nothing further happens.
    - already_employed=False and down_for_position=True  -> promoted to Candidates.
    - already_employed=False and down_for_position=False -> declined.
    """
    verification = persistance.get_verification(token)
    if not verification:
        raise NotFoundError(f"Verification '{token}' not found.")
    if verification['status'] != 'pending':
        raise ValidationError(f"Verification '{token}' has already been used.")

    shortlisted_id = verification['shortlisted_id']

    if already_employed:
        until = datetime.utcnow() + timedelta(days=DISABLE_CYCLE_DAYS)
        persistance.update_shortlisted(shortlisted_id, {'status': 'disabled', 'disabled_until': until})
        persistance.update_verification(token, {'status': 'employed', 'responded_at': datetime.utcnow()})
        return {'result': 'disabled', 'disabled_until': until}

    if down_for_position:
        persistance.update_verification(token, {'status': 'accepted', 'responded_at': datetime.utcnow()})
        candidate_id = shortlist_to_candidate(shortlisted_id)
        action_url = _notify_startup_candidate_confirmed(str(candidate_id))
        return {'result': 'accepted', 'candidate_id': str(candidate_id), 'action_url': action_url}

    persistance.update_verification(token, {'status': 'declined', 'responded_at': datetime.utcnow()})
    update_shortlisted_status(shortlisted_id, 'declined')
    return {'result': 'declined'}


# ==============================================================================
# Startup Selection Sessions – Business Layer
# ==============================================================================

def create_selection_session(startup: str, startup_email: str):
    """
    Start a session letting a startup pick which of their pending shortlisted
    candidates to invite. Emails the startup a link. Returns the session token.
    """
    if not startup or not startup.strip():
        raise ValidationError("Startup name must not be empty.")
    startup = startup.strip()
    _validate_email(startup_email)
    startup_email = startup_email.strip().lower()

    candidates = [c for c in persistance.get_shortlisted_by_startup(startup) if c.get('status') == 'pending']
    if not candidates:
        raise ValidationError(f"No pending shortlisted candidates for startup '{startup}'.")

    token = persistance.create_session(startup, [str(c['_id']) for c in candidates], startup_email)
    _send_email(
        startup_email,
        "Review your shortlist",
        f"<p>Select who to invite from your shortlist:</p>"
        f'<p><a href="{BASE_URL}/session/{token}/page">{BASE_URL}/session/{token}/page</a></p>',
    )

    startup_phone = None
    try:
        startup_phone = persistance.get_shortlisted_by_startup(startup)[0].get('startup_phone') if persistance.get_shortlisted_by_startup(startup) else None
    except Exception:
        startup_phone = None

    if startup_phone:
        whatsapp_message.ReviewShortlistToStartupMessage(startup_phone, startup, f"{BASE_URL}/session/{token}/page")

    return token


def get_selection_session(token: str):
    """Fetch a selection session with its candidate details attached."""
    session = persistance.get_session(token)
    if not session:
        raise NotFoundError(f"Session '{token}' not found.")
    session['candidates'] = [persistance.get_shortlisted(i) for i in session['shortlisted_ids']]
    return session


def set_selection(token: str, shortlisted_id: str, selected: bool):
    """Select or unselect a candidate within an open session."""
    session = persistance.get_session(token)
    if not session:
        raise NotFoundError(f"Session '{token}' not found.")
    if session['status'] != 'open':
        raise ValidationError(f"Session '{token}' is no longer open.")
    if shortlisted_id not in session['shortlisted_ids']:
        raise ValidationError(f"'{shortlisted_id}' is not part of this session.")

    selected_ids = set(session.get('selected_ids', []))
    selected_ids.add(shortlisted_id) if selected else selected_ids.discard(shortlisted_id)

    persistance.update_session(token, {'selected_ids': list(selected_ids)})
    return list(selected_ids)


def submit_selection_session(token: str):
    """Finalize a session: reserve each selected candidate for the startup, then send verification invites."""
    session = persistance.get_session(token)
    if not session:
        raise NotFoundError(f"Session '{token}' not found.")
    if session['status'] != 'open':
        raise ValidationError(f"Session '{token}' has already been submitted.")

    selected_ids = session.get('selected_ids', [])
    if not selected_ids:
        raise ValidationError("No candidates selected in this session.")

    for shortlisted_id in selected_ids:
        entry = persistance.get_shortlisted(shortlisted_id)
        if not entry:
            raise NotFoundError(f"Shortlisted entry '{shortlisted_id}' not found.")
        if entry.get('status') not in {'pending', 'claimed'}:
            owner = entry.get('claimed_by') or entry.get('conflicted_by') or entry.get('startup')
            raise ValidationError(f"Candidate '{entry.get('name')}' is already taken by {owner}.")
        _claim_shortlisted_for_startup(shortlisted_id, session['startup'], session['startup_email'])

    persistance.update_session(token, {'status': 'submitted', 'submitted_at': datetime.utcnow()})
    return [invite_for_verification(sid) for sid in selected_ids]


# ==============================================================================
# Startup Action Sessions – interview / instant onboard / reject after confirmation
# ==============================================================================

def get_action_session(token: str):
    """Fetch an action session with candidate and interview details attached."""
    session = persistance.get_action_session(token)
    if not session:
        raise NotFoundError(f"Action session '{token}' not found.")

    candidate = persistance.get_candidate(session['candidate_id'])
    session['candidate'] = candidate
    if session.get('interview_id'):
        session['interview'] = persistance.get_interview(session['interview_id'])
    return session


def _require_open_action_session(token: str):
    session = persistance.get_action_session(token)
    if not session:
        raise NotFoundError(f"Action session '{token}' not found.")
    if session['status'] == 'completed':
        raise ValidationError("This action has already been completed.")
    return session


def action_schedule_interview(token: str, interview_details: dict):
    """Startup schedules an interview via the action session link."""
    session = _require_open_action_session(token)
    if session['status'] == 'interview_scheduled':
        raise ValidationError("An interview has already been scheduled for this candidate.")

    _require(['date'], interview_details, 'Interview details')
    candidate_id = session['candidate_id']
    interview_id = schedule_interview_for_candidate(candidate_id, interview_details)

    persistance.update_action_session(token, {
        'status': 'interview_scheduled',
        'interview_id': str(interview_id),
    })
    return str(interview_id)


def action_instant_onboard(token: str):
    """Startup skips interview and instantly onboards the candidate."""
    session = _require_open_action_session(token)
    candidate_id = session['candidate_id']
    result = instant_onboard_candidate(candidate_id)
    persistance.update_action_session(token, {'status': 'completed', 'completed_at': datetime.utcnow()})
    return result


def action_reject(token: str):
    """Startup declines the candidate."""
    session = _require_open_action_session(token)
    candidate_id = session['candidate_id']
    result = reject_candidate(candidate_id)
    persistance.update_action_session(token, {'status': 'completed', 'completed_at': datetime.utcnow()})
    return result


def action_interview_outcome(token: str, outcome: str):
    """Startup records interview outcome (passed/failed) and triggers accept/reject."""
    session = persistance.get_action_session(token)
    if not session:
        raise NotFoundError(f"Action session '{token}' not found.")
    if session['status'] != 'interview_scheduled':
        raise ValidationError("No interview has been scheduled for this candidate yet.")
    if session['status'] == 'completed':
        raise ValidationError("This action has already been completed.")

    interview_id = session.get('interview_id')
    if not interview_id:
        raise ValidationError("No interview linked to this action session.")

    result = update_interview_outcome(interview_id, outcome)
    persistance.update_action_session(token, {'status': 'completed', 'completed_at': datetime.utcnow()})
    return result


# ==============================================================================
# Pending-task Alerts – reminds whoever's turn it is, garbage-collects done ones
# ==============================================================================

def _due_for_reminder(entity: dict, now: datetime) -> bool:
    """True if this entity has never been reminded, or its last reminder is stale."""
    last = entity.get('last_reminded_at')
    return not last or (now - last) > timedelta(hours=REMINDER_COOLDOWN_HOURS)


def check_pending_and_alert():
    """
    Sweep every open workflow token (selection session, verification, action session):
    - still open and due -> email whoever needs to act next
    - already resolved   -> delete it, its job is done

    Meant to be called periodically (see presentation.py's background loop) or on
    demand via POST /admin/check-pending. Returns a summary of what happened.
    """
    now = datetime.utcnow()
    reminded = {'sessions': 0, 'verifications': 0, 'action_sessions': 0}

    for session in persistance.get_open_sessions():
        if not _due_for_reminder(session, now):
            continue
        _send_email(
            session['startup_email'],
            f"Reminder: candidates waiting for your review — {session['startup']}",
            f"<p>Hi,</p><p>You still have shortlisted candidates to review for {session['startup']}.</p>"
            f'<p><a href="{BASE_URL}/session/{session["token"]}/page">{BASE_URL}/session/{session["token"]}/page</a></p>',
        )
        persistance.update_session(session['token'], {'last_reminded_at': now})
        reminded['sessions'] += 1

    for verification in persistance.get_pending_verifications():
        if not _due_for_reminder(verification, now):
            continue
        shortlisted = persistance.get_shortlisted(verification['shortlisted_id'])
        if shortlisted:
            _send_email(
                shortlisted['email'],
                f"Reminder: confirm your interest — {shortlisted.get('startup', '')}",
                f"<p>Hi {shortlisted.get('name', '')},</p>"
                f"<p>We're still waiting on your reply for the {shortlisted.get('startup', '')} position.</p>"
                f'<p><a href="{BASE_URL}/verify/{verification["token"]}">{BASE_URL}/verify/{verification["token"]}</a></p>',
            )
        persistance.update_verification(verification['token'], {'last_reminded_at': now})
        reminded['verifications'] += 1

    for action in persistance.get_open_action_sessions():
        if not _due_for_reminder(action, now):
            continue
        candidate = persistance.get_candidate(action['candidate_id']) or {}
        action_url = f"{BASE_URL}/action/{action['token']}/page"
        if action['status'] == 'interview_scheduled':
            subject = f"Reminder: record interview outcome for {candidate.get('name', '')}"
            message = "Please record the interview outcome so we can notify the candidate."
        else:
            subject = f"Reminder: {candidate.get('name', '')} is waiting on you"
            message = "Please choose: schedule an interview, instant onboard, or decline."
        _send_email(
            action['startup_email'],
            subject,
            f"<p>Hi,</p><p>{message}</p>"
            f'<p><a href="{action_url}">{action_url}</a></p>',
        )
        persistance.update_action_session(action['token'], {'last_reminded_at': now})
        reminded['action_sessions'] += 1

    cleaned = {
        'sessions':        persistance.remove_resolved_sessions(),
        'verifications':   persistance.remove_resolved_verifications(),
        'action_sessions': persistance.remove_completed_action_sessions(),
    }

    return {'reminded': reminded, 'cleaned': cleaned}