# PawCare 🐾

A production-grade pet hospital management platform built with FastAPI, PostgreSQL, Redis, Celery, and OpenAI APIs. Deployed on GCP Cloud Run with automated CI/CD via GitHub Actions.

> Built as a real-world portfolio project — currently being piloted at a pet hospital in Bangalore.

## Live Demo
- **API:** https://pawcare-api-904405147355.asia-south1.run.app
- **Swagger Docs:** https://pawcare-api-904405147355.asia-south1.run.app/docs
- **Health Check:** https://pawcare-api-904405147355.asia-south1.run.app/api/v1/health/ready

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy, Alembic |
| Task Queue | Celery, Redis |
| Database | PostgreSQL (Neon — serverless) |
| Cache / Broker | Redis (Upstash — serverless) |
| AI | OpenAI GPT-4o-mini |
| Auth | JWT + Role-based access control |
| Infrastructure | GCP Cloud Run, GCP Secret Manager, GCP Artifact Registry |
| CI/CD | GitHub Actions |
| Containerization | Docker, Docker Compose |

---

## Architecture

```
                        ┌─────────────────┐
                        │  React Frontend  │
                        └────────┬────────┘
                                 │ HTTPS
                        ┌────────▼────────┐
                        │   FastAPI API    │
                        │  (Cloud Run)     │
                        │  scales 0-3      │
                        └──┬──────────┬───┘
                           │          │
              ┌────────────▼──┐  ┌────▼────────────┐
              │  PostgreSQL   │  │     Redis        │
              │  (Neon)       │  │   (Upstash)      │
              └───────────────┘  └────┬────────────┘
                                      │
                             ┌────────▼────────┐
                             │  Celery Worker   │
                             │  (Cloud Run)     │
                             │  always-on       │
                             └────────┬────────┘
                                      │
                             ┌────────▼────────┐
                             │   OpenAI API     │
                             │  GPT-4o-mini     │
                             └─────────────────┘
```

---

## Features

### Clinical Workflow
- **Multi-role auth** — admin, vet, receptionist with JWT + RBAC
- **Pet & owner management** — full CRUD with search
- **Appointment scheduling** — state machine transitions (scheduled → confirmed → in-progress → completed)
- **Medical records** — linked to appointments, full visit history per pet
- **Billing** — invoice generation with GST, line items, payment tracking

### AI Layer
- **Symptom triage** — owner describes symptoms, AI returns urgency level (emergency / urgent / routine) with reasoning and confidence score
- **History summarizer** — generates pre-consultation clinical summary for vet before appointment
- **Care instructions** — converts clinical notes into plain English post-visit instructions for owner
- Redis caching of AI responses — reduces OpenAI API costs
- Graceful fallback on every AI feature — never returns 500 if OpenAI fails
- Prompt injection protection on all user-provided inputs

### Async Notifications
- Appointment reminders queued via Celery on booking and confirmation
- Post-visit care summaries sent after medical record creation
- Exponential backoff retry logic — max 3 retries (60s, 120s, 240s)
- Daily scheduled reminders via Celery Beat

### Production Patterns
- Structured JSON logging with correlation IDs (request_id on every log line)
- Liveness and readiness health probes with dependency status
- GCP Secret Manager for all credentials — never in code or env files
- Modular monolith — clean separation of concerns, microservices-ready
- Docker multi-stage builds for API and Celery worker separately

---

## API Reference

### Auth
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | /api/v1/auth/login | Login, returns JWT | Public |
| POST | /api/v1/auth/register | Register new user | Public |
| GET | /api/v1/auth/me | Current user profile | Any |

### Patients
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | /api/v1/patients/owners | List owners (search by name, email, phone) | Any |
| POST | /api/v1/patients/owners | Create owner | Any |
| GET | /api/v1/patients/owners/:id | Get owner with pets | Any |
| PATCH | /api/v1/patients/owners/:id | Update owner | Any |
| DELETE | /api/v1/patients/owners/:id | Delete owner | Admin |
| GET | /api/v1/patients/pets | List pets (filter by species) | Any |
| POST | /api/v1/patients/pets | Create pet | Any |
| GET | /api/v1/patients/pets/:id | Get pet with owner | Any |
| PATCH | /api/v1/patients/pets/:id | Update pet | Any |
| DELETE | /api/v1/patients/pets/:id | Delete pet | Admin/Vet |

### Appointments
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | /api/v1/appointments | List (filter by pet, vet, status, date) | Any |
| POST | /api/v1/appointments | Book appointment | Any |
| GET | /api/v1/appointments/:id | Get appointment | Any |
| PATCH | /api/v1/appointments/:id | Update details | Any |
| PATCH | /api/v1/appointments/:id/status | Update status | Any |
| DELETE | /api/v1/appointments/:id | Delete appointment | Admin/Receptionist |

### Medical Records
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | /api/v1/medical-records/pet/:id | Full pet history | Any |
| POST | /api/v1/medical-records | Create record | Vet/Admin |
| GET | /api/v1/medical-records/:id | Get record | Any |
| PATCH | /api/v1/medical-records/:id | Update record | Vet/Admin |
| DELETE | /api/v1/medical-records/:id | Delete record | Admin |

### Billing
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | /api/v1/billing | List invoices | Any |
| POST | /api/v1/billing | Create invoice | Receptionist/Admin |
| GET | /api/v1/billing/:id | Get invoice | Any |
| PATCH | /api/v1/billing/:id | Update invoice | Receptionist/Admin |
| PATCH | /api/v1/billing/:id/pay | Mark as paid | Receptionist/Admin |
| DELETE | /api/v1/billing/:id | Cancel invoice | Admin |

### AI
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | /api/v1/ai/triage | Symptom urgency assessment | Any |
| GET | /api/v1/ai/history-summary/:pet_id | Pre-consultation summary | Any |
| GET | /api/v1/ai/care-instructions/:record_id | Post-visit instructions | Any |

### Health
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | /health | Simple liveness check | Public |
| GET | /api/v1/health/live | Liveness probe | Public |
| GET | /api/v1/health/ready | Readiness probe with dependency status | Public |

---

## Roles & Permissions

| Action | Admin | Vet | Receptionist |
|--------|-------|-----|--------------|
| Manage users | ✅ | ❌ | ❌ |
| View patients | ✅ | ✅ | ✅ |
| Create/edit patients | ✅ | ✅ | ✅ |
| Delete patients | ✅ | ❌ | ❌ |
| Manage appointments | ✅ | ✅ | ✅ |
| Create medical records | ✅ | ✅ | ❌ |
| View medical records | ✅ | ✅ | ✅ |
| Create invoices | ✅ | ❌ | ✅ |
| Mark invoices paid | ✅ | ❌ | ✅ |
| Access AI features | ✅ | ✅ | ✅ |

---

## Local Development

### Prerequisites
- Docker Desktop
- Python 3.11+
- Node.js 18+

### Setup

```bash
# Clone
git clone https://github.com/luhaniwalprabha/pawcare.git
cd pawcare

# Configure environment
cp .env.example .env
# Edit .env with your DB, Redis, and OpenAI credentials

# Start everything
docker compose up --build

# Run migrations (first time only)
alembic upgrade head
```

API runs at `http://localhost:8000`
Swagger docs at `http://localhost:8000/docs`

### Running without Docker (faster for development)

```bash
# Start only DB and Redis in Docker
docker compose up db redis -d

# Python setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Terminal 1 — API
uvicorn main:app --reload

# Terminal 2 — Celery worker
celery -A app.core.celery_app worker --loglevel=info
```

---

## Project Structure

```
pawcare/
├── app/
│   ├── ai/                        # AI service layer
│   │   ├── prompts.py             # All LLM prompts (role, constraints, output format)
│   │   └── service.py             # OpenAI calls, Redis caching, fallbacks, token tracking
│   ├── api/v1/
│   │   ├── router.py              # Central router — all endpoints registered here
│   │   └── endpoints/
│   │       ├── auth.py            # Login, register, me
│   │       ├── patients.py        # Owners and pets CRUD
│   │       ├── appointments.py    # Scheduling with state machine
│   │       ├── medical_records.py # Clinical notes and history
│   │       ├── billing.py         # Invoices and payments
│   │       ├── ai.py              # AI feature endpoints
│   │       └── health.py          # Liveness and readiness probes
│   ├── core/
│   │   ├── config.py              # Pydantic settings — reads from .env
│   │   ├── security.py            # JWT creation/validation, RBAC dependencies
│   │   ├── celery_app.py          # Celery instance and Beat schedule
│   │   └── logging.py             # Structured JSON logging middleware
│   ├── db/
│   │   └── session.py             # SQLAlchemy engine, connection pool, get_db
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── user.py                # User with roles
│   │   ├── patient.py             # Owner and Pet
│   │   └── clinic.py              # Appointment, MedicalRecord, Invoice
│   ├── schemas/                   # Pydantic request/response schemas
│   │   ├── auth.py
│   │   ├── patient.py
│   │   ├── clinic.py
│   │   └── billing.py
│   └── tasks/
│       └── notifications.py       # Celery tasks — reminders, summaries, daily batch
├── alembic/                       # Database migrations
│   └── versions/                  # Auto-generated migration files
├── frontend/                      # React app (in progress)
├── .github/
│   └── workflows/
│       └── deploy.yml             # CI/CD — build, push, deploy on push to main
├── Dockerfile                     # API container
├── Dockerfile.celery              # Celery worker container
├── celery_worker_entrypoint.sh    # Health server + Celery for Cloud Run
├── docker-compose.yml             # Local development stack
├── alembic.ini                    # Alembic configuration
└── requirements.txt
```

---

## Deployment

### Infrastructure

| Service | Platform | Config |
|---------|----------|--------|
| API | GCP Cloud Run | min=0, max=3 instances |
| Celery worker | GCP Cloud Run | min=1, max=1 (always-on) |
| PostgreSQL | Neon (serverless) | Free tier |
| Redis | Upstash (serverless) | Free tier |
| Secrets | GCP Secret Manager | DATABASE_URL, REDIS_URL, SECRET_KEY, OPENAI_API_KEY |
| Images | GCP Artifact Registry | asia-south1 |

### CI/CD Pipeline

Every push to `main`:
```
git push
    ↓
GitHub Actions triggered
    ↓
Build API image + Celery worker image
    ↓
Push both to GCP Artifact Registry
    ↓
Deploy API to Cloud Run
    ↓
Deploy Celery worker to Cloud Run
    ↓
Live in ~3 minutes
```

---

## Architecture Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Architecture | Modular monolith | Easier to build and deploy solo; each module is independently testable; can split to microservices later |
| Task queue | Celery + Redis | Mature, battle-tested, excellent retry primitives, familiar to most backend engineers |
| AI model | GPT-4o-mini | Fast response times, cheap per token, reliable JSON output for structured responses |
| AI caching | Redis | Same symptoms for same pet → same response; caching reduces OpenAI costs significantly |
| Celery on Cloud Run | Service (not Job) | Worker needs to run continuously listening for tasks; Cloud Run Jobs are for finite tasks |
| DB migrations | Alembic | Standard SQLAlchemy tool; migration history is auditable in version control |
| Auth | JWT + RBAC | Stateless — scales horizontally without shared session state |
| Secrets | GCP Secret Manager | Encrypted at rest, access-controlled via IAM, rotatable without redeployment |
| Two env files | .env + .env.docker | localhost vs service names differ between local and Docker; keeps both working |

---

## Roadmap

- [ ] React frontend — dashboard, patients, appointments, billing
- [ ] Rate limiting — per-user Redis-based rate limits on AI endpoints
- [ ] Unit and integration tests
- [ ] Celery Beat — Cloud Scheduler triggering daily reminder jobs
- [ ] Multi-tenant support — multiple hospital branches under one deployment
- [ ] WhatsApp notifications via Twilio (relevant for Indian pet owners)