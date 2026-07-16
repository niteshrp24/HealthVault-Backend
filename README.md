# HealthVault — Medical Records Management Platform

> A secure, consent-based digital health records platform that allows
> pathlabs and hospitals to manage patient reports and enables patients
> to control access to their own medical data.

---

## What is HealthVault?

In India, when a patient visits a new pathlab or hospital, they often have
to repeat tests they have already done elsewhere — simply because there is
no secure way to share those records with the new provider. Reports are
scattered across WhatsApp chats, paper printouts, and email attachments
with no access control whatsoever.

HealthVault solves this by providing a unified platform where:

- **Pathlabs and hospitals** can upload patient reports directly to a
  secure digital locker
- **Patients** own their records and can share them with any provider
  on their own terms — choosing exactly which reports to share,
  with which lab, and until what date
- **Platform administrators** manage lab registrations, storage quotas,
  subscriptions, and platform analytics

Access is always consent-based. The patient approves every share request
with an OTP, sets the expiry, and can revoke access at any time.

---

## Three Portal Architecture

The platform consists of three completely separate portals, each with
its own authentication method and set of permissions.

### Admin Portal
The platform owner. Responsible for registering labs and hospitals,
assigning storage limits and subscription durations, sending notifications
to labs, deactivating accounts, and monitoring platform-wide analytics.
Logs in with username and password.

### Lab / Hospital Portal
For pathlab owners and hospital administrators. After being registered
by the admin, a lab can upload PDF reports for patients, view their own
reports and any reports shared via consent, send consent requests to
patients, and track their storage usage.
Logs in with phone number and password.

### Patient / User Portal
For end users — the patients. Patients self-register, verify their phone
number via WhatsApp OTP, and get a secure digital health locker. They can
view all their reports, manage incoming consent requests, choose what to
share and for how long, and revoke access at any time.
Logs in with phone number via WhatsApp OTP only — no password needed.

---

## Key Features

- **Consent-based sharing** — Patients approve every access request with
  an OTP, set a custom expiry date, and can revoke anytime
- **OTP security** — Cryptographically secure OTP generation using
  Python `secrets` module, SHA-256 hashed before storage, never plain text
- **Redis rate limiting** — Maximum 5 OTP attempts per 5-minute window,
  tracked atomically in Redis with automatic TTL expiry
- **Portal-aware JWT** — Admin, lab, and user tokens carry a portal
  claim. Tokens cannot be cross-used between portals
- **Secure PDF access** — Files are never served directly. Short-lived
  presigned URLs (60 seconds) are generated per request via MinIO/S3
- **Storage quota enforcement** — Per-lab storage tracked in real time
  using atomic database operations
- **Async task processing** — All external API calls (Twilio, ZeptoMail)
  run via Celery workers so API responses are never blocked
- **Lazy expiry pattern** — Consent and plan expiry is enforced at
  request time by the view layer, not dependent on background jobs
- **Multi-channel notifications** — Admin can message labs via in-app,
  email, SMS, or WhatsApp simultaneously

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web Framework | Django 5 + Django REST Framework |
| Database | PostgreSQL |
| Cache & Message Broker | Redis |
| Async Task Queue | Celery + Celery Beat |
| File Storage | MinIO (S3-compatible, swappable to AWS S3) |
| WhatsApp & SMS | Twilio |
| Email | ZeptoMail via SMTP |
| Authentication | JWT via SimpleJWT (custom portal-aware backend) |
| Timezone | Asia/Kolkata (IST) throughout |

---


```
healthcare_platform/
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── celery_app.py
│   └── wsgi.py
│
├── apps/
│   ├── core/
│   │   ├── models.py
│   │   ├── permissions.py
│   │   ├── pagination.py
│   │   └── utils/
│   │       ├── otp.py
│   │       ├── redis_otp.py
│   │       ├── storage.py
│   │       ├── uid_generator.py
│   │       ├── whatsapp.py
│   │       ├── email.py
│   │       └── timezone_utils.py
│   │
│   ├── accounts/
│   │   ├── models.py
│   │   ├── backends.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── tasks.py
│   │   └── urls/
│   │       ├── auth.py
│   │       ├── admin_portal.py
│   │       ├── lab_portal.py
│   │       └── user_portal.py
│   │
│   ├── reports/
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── tasks.py
│   │
│   ├── consent/
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── tasks.py
│   │
│   ├── notifications/
│   │   ├── models.py
│   │   ├── views.py
│   │   └── tasks.py
│   │
│   ├── subscriptions/
│   │   └── views.py
│   │
│   └── analytics/
│       └── views.py
│
├── requirements/
│   ├── base.txt
│   └── development.txt
│
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── manage.py
```
---

## API Overview

36 REST endpoints across four groups.

| Group | Endpoints | Authentication |
|---|---|---|
| Authentication | 6 | Open (no token required) |
| Admin Portal | 16 | Admin JWT token |
| Lab / Hospital Portal | 10 | Lab JWT token |
| Patient / User Portal | 10 | User JWT token |

Base URL: `http://127.0.0.1:8000/api/v1/`

---

## Local Development Setup

### Prerequisites

Make sure the following are installed on your machine:

- Python 3.12+
- Git
- Docker (for PostgreSQL, Redis, MinIO)

---

### Step 1 — Clone the Repository

```bash
git clone git@github.com:niteshrp24/healthvault-backend.git
cd healthvault-backend
```

---

### Step 2 — Create and Activate Virtual Environment

```bash
# Create
python -m venv env

# Activate on Windows
env\Scripts\activate

# Activate on Mac / Linux
source env/bin/activate
```

---

### Step 3 — Install Dependencies

```bash
pip install -r requirements/development.txt
```

---

### Step 4 — Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` and fill in all required values. The key ones are:

```env
SECRET_KEY=               # Generate with: python -c "import secrets; print(secrets.token_urlsafe(50))"
DB_NAME=phr_db
DB_USER=phr_user
DB_PASSWORD=phr_pass
REDIS_URL=redis://localhost:6379/0
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_STORAGE_BUCKET_NAME=healthvault-reports
AWS_S3_ENDPOINT_URL=http://localhost:9000
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_SMS_FROM=
ZEPTO_SMTP_PASSWORD=
ZEPTO_FROM_EMAIL=
```

---

### Step 5 — Start Required Services

Run each of these in a separate terminal or run them detached with `-d`.

**PostgreSQL:**
```bash
docker run -d \
  --name healthvault-db \
  -p 5432:5432 \
  -e POSTGRES_DB=phr_db \
  -e POSTGRES_USER=phr_user \
  -e POSTGRES_PASSWORD=phr_pass \
  postgres:16-alpine
```

**Redis:**
```bash
docker run -d \
  --name healthvault-redis \
  -p 6379:6379 \
  redis:7-alpine
```

**MinIO (local S3-compatible storage):**
```bash
docker run -d \
  --name healthvault-minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

After starting MinIO, open `http://localhost:9001` in your browser,
log in with `minioadmin / minioadmin`, and create a bucket named
`healthvault-reports`.

---

### Step 6 — Run Database Migrations

```bash
python manage.py makemigrations accounts reports consent notifications subscriptions analytics core
python manage.py migrate
```

---

### Step 7 — Create Admin Account

```bash
python manage.py create_admin \
  --username admin \
  --email admin@example.com \
  --password yourpassword
```

---

### Step 8 — Start All Services

Open four separate terminals:

**Terminal 1 — Django development server:**
```bash
python manage.py runserver
```

**Terminal 2 — Celery worker (processes async tasks):**
```bash
celery -A config.celery_app worker --pool=solo -l info
```

**Terminal 3 — Celery beat (runs periodic housekeeping tasks):**
```bash
celery -A config.celery_app beat -l info
```

The API is now available at `http://127.0.0.1:8000/api/v1/`

---

### Step 9 — Verify Setup

Test the admin login endpoint:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/admin/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "yourpassword"}'
```

A successful response returns an `access` token and a `refresh` token.

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Django secret key — keep private |
| `DEBUG` | Yes | `True` for development, `False` for production |
| `ALLOWED_HOSTS` | Yes | Comma-separated list of allowed hosts |
| `DB_NAME` | Yes | PostgreSQL database name |
| `DB_USER` | Yes | PostgreSQL username |
| `DB_PASSWORD` | Yes | PostgreSQL password |
| `DB_HOST` | No | Database host (default: localhost) |
| `DB_PORT` | No | Database port (default: 5432) |
| `REDIS_URL` | Yes | Redis connection URL |
| `AWS_ACCESS_KEY_ID` | Yes | MinIO or S3 access key |
| `AWS_SECRET_ACCESS_KEY` | Yes | MinIO or S3 secret key |
| `AWS_STORAGE_BUCKET_NAME` | Yes | Bucket name for report storage |
| `AWS_S3_ENDPOINT_URL` | No | Set for MinIO, leave empty for AWS S3 |
| `TWILIO_ACCOUNT_SID` | Yes | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Yes | Twilio auth token |
| `TWILIO_WHATSAPP_FROM` | Yes | Twilio WhatsApp sender number |
| `TWILIO_SMS_FROM` | Yes | Twilio SMS sender number |
| `ZEPTO_SMTP_PASSWORD` | Yes | ZeptoMail SMTP API key |
| `ZEPTO_FROM_EMAIL` | Yes | Verified sender email address |
| `ZEPTO_FROM_NAME` | No | Sender display name (default: HealthVault) |
| `SIGNED_URL_EXPIRY_SECONDS` | No | Presigned URL TTL for viewing (default: 60) |
| `DOWNLOAD_URL_EXPIRY_SECONDS` | No | Presigned URL TTL for download (default: 300) |
| `CORS_ALLOWED_ORIGINS` | Yes | Comma-separated frontend origins |

---

## Security Notes

- Never commit the `.env` file — it is listed in `.gitignore`
- All OTPs are SHA-256 hashed before database storage
- JWT tokens carry portal claims and cannot be cross-used between portals
- PDF files are accessed only via short-lived presigned URLs
- Consent expiry is enforced at the view layer on every request
- Storage quota is updated atomically to prevent race conditions

---

## License

Private project — All rights reserved.
