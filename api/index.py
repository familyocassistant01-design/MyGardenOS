import sys
from pathlib import Path

# Add backend to path so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.main import app
