# QSTP – Startup Talent Pipeline API

A **FastAPI** back-end that manages the full candidate lifecycle for startup hiring:  
shortlisting → startup selection → candidate verification → interviews → accept / reject.

Built with **MongoDB** for persistence and **Resend** for transactional emails.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| Database | MongoDB 7 |
| Email | Resend |
| Containerization | Docker + Docker Compose |

---

## Quick Start (Docker – recommended)

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/QSTP.git
cd QSTP
```

### 2. Create your `.env` file

```bash
cp .env.example .env
# Edit .env and set your real RESEND_API_KEY
```

### 3. Start the services

```bash
docker compose up --build -d
```

This spins up:
- **`qstp-api`** – the FastAPI app on [http://localhost:8000](http://localhost:8000)
- **`qstp-mongo`** – a MongoDB 7 instance on port 27017

### 4. Verify

```bash
# Check running containers
docker compose ps

# View live logs
docker compose logs -f app

# Open the API docs
# http://localhost:8000/docs
```

### 5. Stop

```bash
docker compose down          # stop containers
docker compose down -v       # stop + delete database volume
```

---

## Quick Start (Local – no Docker)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Make sure MongoDB is running locally, then:
cp .env.example .env
# Edit .env → set MONGODB_URI=mongodb://localhost:27017/QSTP and RESEND_API_KEY

uvicorn presentation:app --reload
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MONGODB_URI` | ✅ | — | MongoDB connection string |
| `RESEND_API_KEY` | ✅ | — | Resend email API key |
| `BASE_URL` | ❌ | `http://127.0.0.1:8000` | Public URL of the service |
| `RESEND_FROM` | ❌ | `onboarding@resend.dev` | Default sender email |

---

## Project Structure

```
QSTP/
├── presentation.py      # FastAPI routes (presentation layer)
├── business.py          # Business logic & validation
├── persistance.py       # MongoDB data-access layer
├── resend_mail.py       # Email helpers (Resend SDK)
├── templates/
│   ├── session.html     # Startup selection page
│   └── verify.html      # Candidate verification page
├── requirements.txt     # Python dependencies
├── Dockerfile           # Multi-stage Docker image
├── docker-compose.yml   # App + MongoDB orchestration
├── .dockerignore        # Files excluded from Docker build
├── .env.example         # Environment variable template
└── .gitignore
```

---

## API Documentation

Once the server is running, visit:

- **Swagger UI** – [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc** – [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## License

MIT
