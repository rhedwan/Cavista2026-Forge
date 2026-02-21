# main.py — Thin entrypoint that mounts all routers
import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aidcare_pipeline import copilot_models
from aidcare_pipeline.database import SessionLocal

# --- Routers ---
from routers.auth import router as auth_router
from routers.orgs import router as orgs_router
from routers.doctors import router as doctors_router
from routers.patients import router as patients_router
from routers.scribe import router as scribe_router
from routers.handover import router as handover_router
from routers.burnout import router as burnout_router
from routers.triage import router as triage_router

# --- App ---
app = FastAPI(title="AidCare AI Assistant API", version="2.0.0")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://triage.theaidcare.com",
        "https://lang.theaidcare.com",
        "https://aidcare-lang.vercel.app",
        "https://cavista2026.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.(vercel\.app|up\.railway\.app)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Mount Routers ---
app.include_router(auth_router)
app.include_router(orgs_router)
app.include_router(doctors_router)
app.include_router(patients_router)
app.include_router(scribe_router)
app.include_router(handover_router)
app.include_router(burnout_router)
app.include_router(triage_router)


# --- Lifecycle Events ---
@app.on_event("startup")
async def startup_event():
    print("AidCare API v2 starting up...")
    try:
        copilot_models.create_copilot_tables()
        print("Database tables checked/created.")
    except Exception as e:
        print(f"WARNING: Table creation failed: {e}")
    print("AidCare API v2 startup complete.")


@app.on_event("shutdown")
async def shutdown_event():
    print("AidCare API v2 shutting down.")


# --- Health ---
@app.get("/")
async def root():
    return {"message": "AidCare API v2. Use /docs for documentation."}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}
