import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set default DATABASE_URL if not provided
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///./mygardenos_dev.db"

from app.main import app

# ASGI application for Vercel

