from pathlib import Path

from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import business

app = FastAPI()

TEMPLATES_DIR = Path(__file__).parent / "templates"

class Candidate(BaseModel):
    name: str
    age: int
    email: str
    cv: str

class StartupGroup(BaseModel):
    email: str
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
            startup_emails[startup] = info.email
            for candidate in info.candidates:
                record = candidate.model_dump()
                record["startup"] = startup
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
