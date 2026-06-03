# PawCare 🐾

Pet hospital management platform — FastAPI + PostgreSQL + Redis + React

## Tech stack
- **Backend**: FastAPI, SQLAlchemy, Alembic, Celery
- **Database**: PostgreSQL, Redis
- **AI**: OpenAI APIs
- **Frontend**: React (Vite)
- **Deploy**: Docker, GCP Cloud Run

## Local setup

### 1. Clone and configure
```bash
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY and change SECRET_KEY
```

### 2. Start database and Redis
```bash
docker-compose up db redis -d
```

### 3. Install Python dependencies
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run database migrations
```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

### 5. Start the API
```bash
uvicorn main:app --reload
# API runs at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### 6. Create first admin user
```bash
# Via API docs at /docs — POST /api/v1/auth/register
# Set role to "admin"
```

### 7. Start frontend
```bash
cd frontend
npm create vite@latest . -- --template react
npm install
npm run dev
# Runs at http://localhost:5173
```

## Project structure
```
pawcare/
├── app/
│   ├── api/v1/endpoints/   # Route handlers
│   ├── core/               # Config, security, auth
│   ├── db/                 # Database session
│   ├── models/             # SQLAlchemy models
│   ├── schemas/            # Pydantic schemas
│   ├── services/           # Business logic
│   └── tasks/              # Celery async tasks
├── alembic/                # DB migrations
├── frontend/               # React app
├── tests/
├── main.py
├── docker-compose.yml
└── Dockerfile
```

## API endpoints (Phase 1)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | /api/v1/auth/login | Login | Public |
| POST | /api/v1/auth/register | Register user | Public |
| GET | /api/v1/auth/me | Current user | Any |
| GET | /api/v1/patients/owners | List owners | Any |
| POST | /api/v1/patients/owners | Create owner | Any |
| GET | /api/v1/patients/owners/:id | Get owner + pets | Any |
| PATCH | /api/v1/patients/owners/:id | Update owner | Any |
| DELETE | /api/v1/patients/owners/:id | Delete owner | Admin |
| GET | /api/v1/patients/pets | List pets | Any |
| POST | /api/v1/patients/pets | Create pet | Any |
| GET | /api/v1/patients/pets/:id | Get pet + owner | Any |
| PATCH | /api/v1/patients/pets/:id | Update pet | Any |
| DELETE | /api/v1/patients/pets/:id | Delete pet | Admin/Vet |

## Roles
- **admin** — full access
- **vet** — clinical access (records, appointments, prescriptions)
- **receptionist** — scheduling and patient registration

## Build phases
- [x] Phase 1 — Scaffold, Auth, RBAC, Patients API
- [ ] Phase 2 — Appointments + Medical Records
- [ ] Phase 3 — Billing + Celery async notifications
- [ ] Phase 4 — AI layer + React frontend + GCP deploy