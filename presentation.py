from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import business

app = FastAPI()

class Candidate(BaseModel):
    name: str
    age: int
    email: str
    cv: str


@app.post("/dataentry")
def dataentry(data: list[dict[str, list[Candidate]]]):
    """Each dict maps a startup name to its list of candidates, e.g. [{"StartupA": [...]}]."""
    inserted = []
    for group in data:
        for startup, candidates in group.items():
            for candidate in candidates:
                record = candidate.model_dump()
                record["startup"] = startup
                try:
                    candidate_id = business.add_candidate(record)
                except (business.ValidationError, business.DuplicateError) as e:
                    raise HTTPException(status_code=400, detail=str(e))
                inserted.append({"email": record["email"], "startup": startup, "id": str(candidate_id)})
    return inserted

