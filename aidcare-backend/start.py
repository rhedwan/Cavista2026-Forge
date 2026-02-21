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

    # Create DB tables if DATABASE_URL is set (safe to run on every startup — create_all is idempotent)
    if os.environ.get("DATABASE_URL"):
        try:
            from aidcare_pipeline.db_models import create_db_and_tables
            create_db_and_tables()
        except Exception as e:
            print(f"WARNING: Could not create database tables: {e}")

    # Import uvicorn and run
    import uvicorn
    uvicorn.run("main:app", host=host, port=port, log_level="info")
