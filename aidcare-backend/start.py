#!/usr/bin/env python3
"""
Start script for Railway deployment
Handles PORT environment variable properly
"""
import os
import sys

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"

    print(f"Starting server on {host}:{port}")

    # Create DB tables + run migrations if DATABASE_URL is set
    if os.environ.get("DATABASE_URL"):
        try:
            from aidcare_pipeline import copilot_models
            copilot_models.create_copilot_tables()
        except Exception as e:
            print(f"WARNING: Could not create database tables: {e}")
        try:
            from migrate_copilot_doctors import migrate
            migrate()
        except Exception as e:
            print(f"WARNING: Migration skipped or failed: {e}")

    # Import uvicorn and run
    import uvicorn
    uvicorn.run("main:app", host=host, port=port, log_level="info")
