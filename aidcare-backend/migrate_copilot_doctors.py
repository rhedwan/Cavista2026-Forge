#!/usr/bin/env python3
"""
Migration: Add email, password_hash, hospital_id, ward_id, role to copilot_doctors.
Runs automatically on startup (start.py). Also run manually: python migrate_copilot_doctors.py
After migration, run seed_demo.py to create login users (chioma@lasuth.ng / demo1234).
"""
import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from aidcare_pipeline.database import engine

def column_exists(conn, table: str, column: str) -> bool:
    r = conn.execute(text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = :t AND column_name = :c
    """), {"t": table, "c": column})
    return r.fetchone() is not None

def migrate():
    with engine.begin() as conn:
        if not column_exists(conn, "copilot_doctors", "email"):
            print("Adding column: email")
            conn.execute(text("ALTER TABLE copilot_doctors ADD COLUMN email VARCHAR(255)"))
            conn.execute(text("UPDATE copilot_doctors SET email = 'migrated_' || doctor_uuid || '@temp.local' WHERE email IS NULL"))
            conn.execute(text("ALTER TABLE copilot_doctors ALTER COLUMN email SET NOT NULL"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_copilot_doctors_email ON copilot_doctors (email)"))
        if not column_exists(conn, "copilot_doctors", "password_hash"):
            print("Adding column: password_hash")
            from aidcare_pipeline.auth import hash_password
            default_hash = hash_password("demo1234")
            conn.execute(text("ALTER TABLE copilot_doctors ADD COLUMN password_hash VARCHAR(255)"))
            conn.execute(text("UPDATE copilot_doctors SET password_hash = :h WHERE password_hash IS NULL"),
                        {"h": default_hash})
            conn.execute(text("ALTER TABLE copilot_doctors ALTER COLUMN password_hash SET NOT NULL"))
        if not column_exists(conn, "copilot_doctors", "hospital_id"):
            print("Adding column: hospital_id")
            conn.execute(text("ALTER TABLE copilot_doctors ADD COLUMN hospital_id INTEGER"))
        if not column_exists(conn, "copilot_doctors", "ward_id"):
            print("Adding column: ward_id")
            conn.execute(text("ALTER TABLE copilot_doctors ADD COLUMN ward_id INTEGER"))
        if not column_exists(conn, "copilot_doctors", "role"):
            print("Adding column: role")
            conn.execute(text("ALTER TABLE copilot_doctors ADD COLUMN role VARCHAR(50) DEFAULT 'doctor' NOT NULL"))
        if not column_exists(conn, "copilot_shifts", "ward_id"):
            print("Adding column: copilot_shifts.ward_id")
            conn.execute(text("ALTER TABLE copilot_shifts ADD COLUMN ward_id INTEGER"))
        if not column_exists(conn, "copilot_consultations", "patient_id"):
            print("Adding column: copilot_consultations.patient_id")
            conn.execute(text("ALTER TABLE copilot_consultations ADD COLUMN patient_id INTEGER"))
        if not column_exists(conn, "copilot_consultations", "transcript"):
            print("Adding column: copilot_consultations.transcript")
            conn.execute(text("ALTER TABLE copilot_consultations ADD COLUMN transcript JSONB"))
    print("Migration complete.")

if __name__ == "__main__":
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL not set. Aborting.")
        exit(1)
    migrate()
