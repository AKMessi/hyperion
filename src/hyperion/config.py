from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATABASE_FILE = os.path.join(PROJECT_ROOT, 'hyperion.db')