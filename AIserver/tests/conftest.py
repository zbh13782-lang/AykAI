from pathlib import Path
import sys

# Ensure repository root is importable for api/ and src/ modules.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
