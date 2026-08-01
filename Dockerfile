# ─── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install dependencies into a virtual-env so the final image stays tiny
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ─── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

LABEL maintainer="QSTP Team"
LABEL description="QSTP – Startup Talent Pipeline API (FastAPI + MongoDB)"

WORKDIR /app

# Bring the pre-built venv from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY presentation.py business.py persistance.py resend_mail.py ./
COPY templates/ ./templates/

# ── Environment variables (override at runtime via `docker run -e` or .env) ──
# Required:
#   MONGODB_URI        – MongoDB connection string
#   RESEND_API_KEY     – Resend email API key
# Optional:
#   BASE_URL           – Public URL of this service  (default: http://127.0.0.1:8000)
#   RESEND_FROM        – Default "from" email address (default: onboarding@resend.dev)

EXPOSE 8000

# Run with uvicorn; bind 0.0.0.0 so the port is reachable outside the container
CMD ["uvicorn", "presentation:app", "--host", "0.0.0.0", "--port", "8000"]
