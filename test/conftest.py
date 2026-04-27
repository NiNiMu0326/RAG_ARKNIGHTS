"""Pytest configuration for all tests."""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set required env vars for testing (before any imports)
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-tests")
