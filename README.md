# AidCare Copilot

AI clinical copilot for Nigerian healthcare. Voice-to-SOAP scribe, multilingual triage, burnout tracking, and handover reports.

## Stack

- **Backend:** FastAPI, PostgreSQL, SQLAlchemy
- **Frontend:** Next.js 16, React 19, Tailwind CSS

## Setup

```bash
# Backend
cd aidcare-backend
cp env.example .env   # set GOOGLE_API_KEY, OPENAI_API_KEY; DATABASE_URL optional (SQLite fallback)
pip install -r requirements.txt
python seed_demo.py   # demo data, password: demo1234
uvicorn main:app --reload --port 8000

# Frontend
cd aidcare-copilot
# Create .env.local with NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm install
npm run dev
```

Open http://localhost:3000. Login: `chioma@lasuth.ng` / `demo1234`.

## Project Structure

| Directory | Description |
|-----------|-------------|
| `aidcare-backend` | FastAPI API, auth, patients, scribe, triage, burnout, handover |
| `aidcare-copilot` | Main clinical UI (dashboard, scribe, patients, burnout, admin) |
| `aidcare-lang` | Multilingual triage (Hausa, Yoruba, Igbo, Pidgin) |
| `aidcare-pwa` | Standalone triage PWA |
| `scripts` | Demo scripts, test instructions |

## Features

- **Scribe:** Voice recording to SOAP notes via OpenAI
- **Triage:** Multilingual symptom intake with risk assessment
- **Patients:** Ward view, consultations, action items
- **Burnout:** Cognitive load scoring, team dashboard, organogram
- **Handover:** Shift handover report generation
- **Admin:** Ward command centre, allocation recommendations

## Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Doctor | chioma@lasuth.ng | demo1234 |
| Hospital Admin | admin@lasuth.ng | demo1234 |
| Org Admin | orgadmin@lagoshealth.ng | demo1234 |
| Super Admin | superadmin@aidcare.ng | demo1234 |

#Demo Video : https://youtu.be/k9qfi4OKaEg
