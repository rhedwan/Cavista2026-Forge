# AidCare Testing Instructions

Hand this to your tester along with the scripts in this folder.

---

## What to Test

1. **Demo script** – What to say and do for each feature (Triage, Scribe, etc.)
2. **API (backend)** – automated script
3. **Frontend (UI)** – manual checklist

---

## Demo Script (Start Here)

**`scripts/DEMO_SCRIPT.md`** – Use this for demonstrating or testing the app. It includes:

- Exact phrases to **speak** or type for Triage (English, Pidgin, voice)
- Exact phrases to **speak** for Scribe (doctor consultation, Pidgin)
- Step-by-step flows for Patients and Handover
- Suggested demo order

---

## Setup (One-Time)

### 1. Clone and install

```bash
# Backend
cd aidcare-backend
pip install -r requirements.txt

# Frontend
cd aidcare-copilot
npm install
```

### 2. Environment

- Backend: Ensure `aidcare-backend/.env` exists with:  
  `DATABASE_URL`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`
- Frontend: `.env.local` with `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`

### 3. Database and seed data

```bash
cd aidcare-backend
python seed_demo.py
```

This creates demo users. Use **chioma@lasuth.ng** / **demo1234** to log in.

---

## Run API Tests

**Option A – Python (recommended):**

```bash
# From project root
pip install requests   # if not already installed
python scripts/run_api_tests.py
```

**Option B – Shell (quick smoke test):**

```bash
chmod +x scripts/quick_smoke_test.sh
./scripts/quick_smoke_test.sh
# Or with custom URL: ./scripts/quick_smoke_test.sh https://your-api.com
```

For a different backend URL:

```bash
python scripts/run_api_tests.py --base-url https://your-api.example.com
```

To skip AI-heavy triage tests (faster):

```bash
python scripts/run_api_tests.py --skip-ai
```

**Expected:** All tests pass. If any fail, note the error message.

---

## Run Manual UI Tests / Demo

1. Start backend: `cd aidcare-backend && uvicorn main:app --reload` (or use live backend)
2. Start frontend: `cd aidcare-copilot && npm run dev`
3. Open **`scripts/DEMO_SCRIPT.md`** – follow the script: say the phrases, click the buttons
4. Optionally use `scripts/manual_test_checklist.md` for a full checklist
5. Record any bugs in the "Notes for Tester" table

---

## What to Report Back

1. **API test output** – Full terminal output from `run_api_tests.py`
2. **Checklist** – Completed `manual_test_checklist.md` (or a copy with checkmarks)
3. **Bugs** – List of issues with: page, steps to reproduce, expected vs actual
4. **Environment** – OS, browser(s), Node/Python versions if something fails
