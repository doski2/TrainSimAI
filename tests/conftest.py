import sys
from pathlib import Path


# Add repository root to sys.path so tests can import runtime/* modules
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

