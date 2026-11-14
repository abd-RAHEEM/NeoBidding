#!/usr/bin/env python3
"""Convenience root wrapper for backend/scripts/test_connections.py"""
import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from scripts.test_connections import main

if __name__ == "__main__":
    main()
