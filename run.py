"""
IBM Interview Trainer Agent – Application Entry Point
========================================================
Run with: python run.py
         uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import sys

# Ensure the project root is in Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from config.settings import get_settings

settings = get_settings()


def main():
    print("=" * 70)
    print(f"  {settings.app_name} v{settings.app_version}")
    print(f"  Environment  : {settings.app_env}")
    print(f"  IBM Granite  : {settings.ibm_granite_model_id}")
    print(f"  Host:Port    : {settings.app_host}:{settings.app_port}")
    print(f"  API Docs     : http://{settings.app_host}:{settings.app_port}/docs")
    print("=" * 70)

    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
        log_level=settings.app_log_level.lower(),
        access_log=True,
    )


if __name__ == "__main__":
    main()
