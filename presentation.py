import asyncio
import os
from pathlib import Path

from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import business

app = FastAPI()

TEMPLATES_DIR = Path(__file__).parent / "templates"

PENDING_CHECK_INTERVAL_SECONDS = int(os.environ.get("PENDING_CHECK_INTERVAL_SECONDS", 3600))


@app.on_event("startup")
async def _start_pending_checker():
    """Background loop: sweeps for pending tasks right away, then every interval — fully automatic, no manual trigger needed."""
    async def loop():
        while True:
            try:
                await asyncio.to_thread(business.check_pending_and_alert)
            except Exception as e:
                print(f"[pending-checker] sweep failed: {e}")
            await asyncio.sleep(PENDING_CHECK_INTERVAL_SECONDS)
    asyncio.create_task(loop())

class Candidate(BaseModel):
    name: str
    age: int
    email: str
    cv: str
    phone: str | None = None
    major: str | None = None
    university: str | None = None
    linkedin: str | None = None
    job_title: str | None = None
    checking_url: str | None = None

class StartupGroup(BaseModel):
    email: str
    phone: str | None = None
    candidates: list[Candidate]

class VerificationReply(BaseModel):
    already_employed: bool
    down_for_position: bool

class InterviewDetails(BaseModel):
    date: str
    time: str | None = None
    location: str | None = None
    notes: str | None = None

class InterviewOutcome(BaseModel):
    outcome: str  # passed | failed | pending


def _jsonable(value):
    """Recursively stringify ObjectId so Mongo docs can be returned as JSON."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _coerce_startup_group(info):
    if isinstance(info, StartupGroup):
        return info
    if isinstance(info, dict):
        candidates = []
        for candidate in info.get("candidates", []):
            if isinstance(candidate, Candidate):
                candidates.append(candidate)
            else:
                candidates.append(Candidate(**candidate))
        return StartupGroup(
            email=info.get("email", ""),
            phone=info.get("phone"),
            candidates=candidates,
        )
    raise TypeError(f"Unsupported startup payload: {type(info).__name__}")


def _candidate_record(candidate):
    if isinstance(candidate, Candidate):
        return candidate.model_dump()
    if isinstance(candidate, dict):
        return dict(candidate)
    raise TypeError(f"Unsupported candidate payload: {type(candidate).__name__}")


def _handle(fn, *args, **kwargs):
    try:
        return _jsonable(fn(*args, **kwargs))
    except business.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except business.DuplicateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except business.ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/dataentry")
def dataentry(data: list[dict[str, StartupGroup]]):
    """
    Each dict maps a startup name to its email + candidate list, e.g.
    [{"StartupA": {"email": "hr@startupa.com", "candidates": [...]}}].
    Adds candidates to the shortlist (not straight to Candidates), then emails
    each startup a link to review and pick who gets invited.
    """
    shortlisted = []
    startup_emails = {}
    for group in data:
        for startup, info in group.items():
            startup_group = _coerce_startup_group(info)
            startup_emails[startup] = startup_group.email
            for candidate in startup_group.candidates:
                record = _candidate_record(candidate)
                record["startup"] = startup
                record["startup_email"] = startup_group.email
                record["startup_phone"] = startup_group.phone
                shortlisted_id = _handle(business.add_shortlisted, record)
                shortlisted.append({"email": record["email"], "startup": startup, "id": str(shortlisted_id)})

    sessions = {
        startup: _handle(business.create_selection_session, startup, email)
        for startup, email in startup_emails.items()
    }
    return {"shortlisted": shortlisted, "sessions": sessions}


# ==============================================================================
# Startup selection sessions – startup picks who from their shortlist gets invited
# ==============================================================================

@app.post("/startups/{startup}/session")
def start_selection_session(startup: str, startup_email: str):
    """Email the startup a session link to review and select their shortlist."""
    token = _handle(business.create_selection_session, startup, startup_email)
    return {"token": token}


@app.get("/session/{token}")
def view_session(token: str):
    return _handle(business.get_selection_session, token)


@app.get("/session/{token}/page", response_class=HTMLResponse)
def session_page(token: str):
    """Handlebars page: startup views its shortlist and selects who to invite."""
    return (TEMPLATES_DIR / "session.html").read_text()


@app.post("/session/{token}/select/{shortlisted_id}")
def select_candidate(token: str, shortlisted_id: str):
    return {"selected_ids": _handle(business.set_selection, token, shortlisted_id, True)}


@app.post("/session/{token}/deselect/{shortlisted_id}")
def deselect_candidate(token: str, shortlisted_id: str):
    return {"selected_ids": _handle(business.set_selection, token, shortlisted_id, False)}


@app.post("/session/{token}/submit")
def submit_session(token: str):
    """Send the verification email to every candidate the startup selected."""
    tokens = _handle(business.submit_selection_session, token)
    return {"verification_tokens": tokens}


# ==============================================================================
# Candidate verification – the yes/no reply to the invite email
# ==============================================================================

@app.get("/verify/{token}", response_class=HTMLResponse)
def verify_page(token: str):
    """Handlebars page: candidate answers the yes/no verification questions."""
    return (TEMPLATES_DIR / "verify.html").read_text()


@app.post("/verify/{token}")
def verify(token: str, reply: VerificationReply):
    return _handle(business.submit_verification, token, reply.already_employed, reply.down_for_position)


# ==============================================================================
# Candidate pipeline – interview (default) or instant onboarding, then accept/reject
# ==============================================================================

@app.post("/candidates/{candidate_id}/interview")
def schedule_interview(candidate_id: str, details: InterviewDetails):
    interview_details = {k: v for k, v in details.model_dump().items() if v is not None}
    interview_id = _handle(business.schedule_interview_for_candidate, candidate_id, interview_details)
    return {"interview_id": str(interview_id)}


@app.post("/interviews/{interview_id}/outcome")
def set_interview_outcome(interview_id: str, body: InterviewOutcome):
    return {"modified": _handle(business.update_interview_outcome, interview_id, body.outcome)}


@app.post("/candidates/{candidate_id}/instant-onboard")
def instant_onboard(candidate_id: str):
    return {"modified": _handle(business.instant_onboard_candidate, candidate_id)}


@app.post("/candidates/{candidate_id}/accept")
def accept_candidate_endpoint(candidate_id: str):
    """Marks accepted and emails the offer + contract follow-up."""
    return {"modified": _handle(business.accept_candidate, candidate_id)}


@app.post("/candidates/{candidate_id}/reject")
def reject_candidate_endpoint(candidate_id: str):
    """Marks rejected and emails the rejection follow-up."""
    return {"modified": _handle(business.reject_candidate, candidate_id)}


# ==============================================================================
# Startup action sessions – schedule interview / instant onboard / reject
# ==============================================================================

@app.get("/action/{token}")
def view_action_session(token: str):
    return _handle(business.get_action_session, token)


@app.get("/action/{token}/page", response_class=HTMLResponse)
def action_page(token: str):
    """Startup page: schedule interview, instant onboard, or decline."""
    return (TEMPLATES_DIR / "action.html").read_text()


@app.post("/action/{token}/interview")
def action_schedule_interview(token: str, details: InterviewDetails):
    interview_details = {k: v for k, v in details.model_dump().items() if v is not None}
    interview_id = _handle(business.action_schedule_interview, token, interview_details)
    return {"interview_id": interview_id}


@app.post("/action/{token}/instant-onboard")
def action_instant_onboard(token: str):
    return {"modified": _handle(business.action_instant_onboard, token)}


@app.post("/action/{token}/reject")
def action_reject(token: str):
    return {"modified": _handle(business.action_reject, token)}


@app.post("/action/{token}/outcome")
def action_interview_outcome(token: str, body: InterviewOutcome):
    return {"modified": _handle(business.action_interview_outcome, token, body.outcome)}


# ==============================================================================
# Admin dashboard – overview + candidate lookup for the middleman
# ==============================================================================

@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return (TEMPLATES_DIR / "admin.html").read_text()


@app.get("/admin/summary")
def admin_summary():
    return _handle(business.get_pipeline_summary)


@app.get("/admin/candidates")
def admin_candidates():
    return _handle(business.get_all_candidates)


@app.get("/admin/candidates/{candidate_id}")
def admin_candidate_detail(candidate_id: str):
    """Full picture of one candidate: profile, shortlist bio, and interview history."""
    return _handle(business.get_candidate_progress, candidate_id)


@app.get("/admin/startups")
def admin_startups():
    return _handle(business.get_all_startups)


@app.get("/admin/startups/{startup}")
def admin_startup_detail(startup: str):
    """Everything tracked for one startup: shortlist, interns/candidates, interviews, and counts."""
    return _handle(business.get_startup_summary, startup)


@app.post("/admin/check-pending")
def admin_check_pending():
    """
    Manually trigger the pending-task reminder sweep: emails whoever needs to act
    on each open session/verification/action, and deletes tokens already resolved.
    Also runs automatically every PENDING_CHECK_INTERVAL_SECONDS (default 1h).
    """
    return _handle(business.check_pending_and_alert)
