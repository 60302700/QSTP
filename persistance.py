#!/usr/bin/env python3
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime

client = None
Candidates = None
Interviews = None
Shortlisted = None

# ==============================================================================
# Connection
# ==============================================================================

def connect_to_mongo():
    """Initialize MongoDB connection and collection references."""
    global client, Candidates, Interviews, Shortlisted
    if client is None:
        client = MongoClient(
            'mongodb+srv://abdullah123bin_db_user:wNH8rIzb034KqXxN@cluster0.g2cako5.mongodb.net/'
        )
        db = client['QSTP']
        Candidates = db['Candidates']
        Interviews = db['Interviews']
        Shortlisted = db['Shortlisted']
    return client


# ==============================================================================
# Candidates – CRUD
# ==============================================================================

def add_candidate(candidate):
    """Insert a new candidate document. Returns the inserted ID."""
    connect_to_mongo()
    candidate.setdefault('created_at', datetime.utcnow())
    candidate.setdefault('status', 'pending')       # pending | accepted | rejected
    result = Candidates.insert_one(candidate)
    return result.inserted_id


def get_candidate(candidate_id):
    """Fetch a single candidate by ObjectId (str or ObjectId)."""
    connect_to_mongo()
    return Candidates.find_one({'_id': ObjectId(candidate_id)})


def get_candidate_by_email(email):
    """Fetch a single candidate by email address."""
    connect_to_mongo()
    return Candidates.find_one({'email': email})


def get_all_candidates(filters=None):
    """Return a list of all candidates, optionally filtered."""
    connect_to_mongo()
    return list(Candidates.find(filters or {}))


def get_candidates_by_startup(startup_name):
    """Return all candidates linked to a specific startup."""
    connect_to_mongo()
    return list(Candidates.find({'startup': startup_name}))


def get_candidates_by_status(status):
    """Return all candidates with a given status (pending/accepted/rejected)."""
    connect_to_mongo()
    return list(Candidates.find({'status': status}))


def update_candidate(candidate_id, updates):
    """Update arbitrary fields on a candidate. Returns modified count."""
    connect_to_mongo()
    updates.setdefault('updated_at', datetime.utcnow())
    result = Candidates.update_one(
        {'_id': ObjectId(candidate_id)},
        {'$set': updates}
    )
    return result.modified_count


def update_candidate_status(candidate_id, status):
    """Shortcut to change a candidate's status (pending/accepted/rejected)."""
    return update_candidate(candidate_id, {'status': status})


def remove_candidate(candidate_id):
    """Delete a candidate by ID. Returns deleted count."""
    connect_to_mongo()
    result = Candidates.delete_one({'_id': ObjectId(candidate_id)})
    return result.deleted_count


def count_candidates(filters=None):
    """Count candidates matching optional filters."""
    connect_to_mongo()
    return Candidates.count_documents(filters or {})


# ==============================================================================
# Interviews – CRUD
# ==============================================================================

def add_interview(interview):
    """Insert a new interview document. Returns the inserted ID."""
    connect_to_mongo()
    interview.setdefault('created_at', datetime.utcnow())
    interview.setdefault('status', 'scheduled')      # scheduled | completed | cancelled
    interview.setdefault('outcome', None)             # passed | failed | pending
    result = Interviews.insert_one(interview)
    return result.inserted_id


def get_interview(interview_id):
    """Fetch a single interview by ID."""
    connect_to_mongo()
    return Interviews.find_one({'_id': ObjectId(interview_id)})


def get_all_interviews(filters=None):
    """Return all interviews, optionally filtered."""
    connect_to_mongo()
    return list(Interviews.find(filters or {}))


def get_interviews_by_candidate(candidate_id):
    """Return all interviews for a specific candidate."""
    connect_to_mongo()
    return list(Interviews.find({'candidate_id': str(candidate_id)}))


def get_interviews_by_startup(startup_name):
    """Return all interviews linked to a specific startup."""
    connect_to_mongo()
    return list(Interviews.find({'startup': startup_name}))


def get_interviews_by_status(status):
    """Return all interviews with a given status."""
    connect_to_mongo()
    return list(Interviews.find({'status': status}))


def update_interview(interview_id, updates):
    """Update arbitrary fields on an interview. Returns modified count."""
    connect_to_mongo()
    updates.setdefault('updated_at', datetime.utcnow())
    result = Interviews.update_one(
        {'_id': ObjectId(interview_id)},
        {'$set': updates}
    )
    return result.modified_count


def update_interview_status(interview_id, status):
    """Change interview status (scheduled/completed/cancelled)."""
    return update_interview(interview_id, {'status': status})


def update_interview_outcome(interview_id, outcome):
    """Record interview outcome (passed/failed/pending)."""
    return update_interview(interview_id, {'outcome': outcome, 'status': 'completed'})


def remove_interview(interview_id):
    """Delete an interview by ID. Returns deleted count."""
    connect_to_mongo()
    result = Interviews.delete_one({'_id': ObjectId(interview_id)})
    return result.deleted_count


def count_interviews(filters=None):
    """Count interviews matching optional filters."""
    connect_to_mongo()
    return Interviews.count_documents(filters or {})


# ==============================================================================
# Shortlisted – CRUD
# ==============================================================================

def add_shortlisted(shortlisted):
    """Insert a new shortlisted entry. Returns the inserted ID."""
    connect_to_mongo()
    shortlisted.setdefault('created_at', datetime.utcnow())
    shortlisted.setdefault('status', 'pending')      # pending | confirmed | declined
    result = Shortlisted.insert_one(shortlisted)
    return result.inserted_id


def get_shortlisted(shortlisted_id):
    """Fetch a single shortlisted entry by ID."""
    connect_to_mongo()
    return Shortlisted.find_one({'_id': ObjectId(shortlisted_id)})


def get_all_shortlisted(filters=None):
    """Return all shortlisted entries, optionally filtered."""
    connect_to_mongo()
    return list(Shortlisted.find(filters or {}))


def get_shortlisted_by_startup(startup_name):
    """Return all shortlisted candidates for a specific startup."""
    connect_to_mongo()
    return list(Shortlisted.find({'startup': startup_name}))


def get_shortlisted_by_candidate(candidate_id):
    """Return shortlisting records for a specific candidate."""
    connect_to_mongo()
    return list(Shortlisted.find({'candidate_id': str(candidate_id)}))


def get_shortlisted_by_status(status):
    """Return shortlisted entries with a given status."""
    connect_to_mongo()
    return list(Shortlisted.find({'status': status}))


def update_shortlisted(shortlisted_id, updates):
    """Update arbitrary fields on a shortlisted entry. Returns modified count."""
    connect_to_mongo()
    updates.setdefault('updated_at', datetime.utcnow())
    result = Shortlisted.update_one(
        {'_id': ObjectId(shortlisted_id)},
        {'$set': updates}
    )
    return result.modified_count


def update_shortlisted_status(shortlisted_id, status):
    """Change shortlisted status (pending/confirmed/done)."""
    return update_shortlisted(shortlisted_id, {'status': status})


def remove_shortlisted(shortlisted_id):
    """Delete a shortlisted entry by ID. Returns deleted count."""
    connect_to_mongo()
    result = Shortlisted.delete_one({'_id': ObjectId(shortlisted_id)})
    return result.deleted_count


def count_shortlisted(filters=None):
    """Count shortlisted entries matching optional filters."""
    connect_to_mongo()
    return Shortlisted.count_documents(filters or {})


# ==============================================================================
# Pipeline helpers  (multi-collection workflow operations)
# ==============================================================================

def shortlist_to_candidate(shortlisted_id):
    """
    Move a shortlisted entry into the Candidates collection.
    Marks the shortlisted record as 'confirmed' and creates a new candidate.
    Returns the new candidate's inserted ID.
    """
    entry = get_shortlisted(shortlisted_id)
    if entry is None:
        return None

    update_shortlisted_status(shortlisted_id, 'confirmed')

    candidate = {
        'name':         entry.get('name'),
        'email':        entry.get('email'),
        'startup':      entry.get('startup'),
        'shortlist_id': str(entry['_id']),
        'status':       'pending',
        'created_at':   datetime.utcnow(),
    }
    return add_candidate(candidate)


def schedule_interview_for_candidate(candidate_id, interview_details):
    """
    Create an interview record linked to an existing candidate.
    `interview_details` should contain at least: date, time, location/link.
    Returns the new interview's inserted ID.
    """
    candidate = get_candidate(candidate_id)
    if candidate is None:
        return None

    interview_details['candidate_id'] = str(candidate['_id'])
    interview_details['candidate_name'] = candidate.get('name')
    interview_details['startup'] = candidate.get('startup')
    return add_interview(interview_details)


def accept_candidate(candidate_id):
    """Mark a candidate as accepted after passing the interview."""
    return update_candidate_status(candidate_id, 'accepted')


def reject_candidate(candidate_id):
    """Mark a candidate as rejected."""
    return update_candidate_status(candidate_id, 'rejected')


def instant_onboard_candidate(candidate_id):
    """Mark a candidate for instant onboarding (skip interview)."""
    return update_candidate(candidate_id, {
        'status': 'accepted',
        'onboarding': 'instant',
    })


def get_pipeline_summary():
    """Return a quick summary of counts across all pipeline stages."""
    return {
        'shortlisted_total':     count_shortlisted(),
        'shortlisted_pending':   count_shortlisted({'status': 'pending'}),
        'candidates_total':      count_candidates(),
        'candidates_pending':    count_candidates({'status': 'pending'}),
        'candidates_accepted':   count_candidates({'status': 'accepted'}),
        'candidates_rejected':   count_candidates({'status': 'rejected'}),
        'interviews_total':      count_interviews(),
        'interviews_scheduled':  count_interviews({'status': 'scheduled'}),
        'interviews_completed':  count_interviews({'status': 'completed'}),
    }
