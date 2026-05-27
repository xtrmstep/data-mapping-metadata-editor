"""Export file I/O. All other data is persisted in PostgreSQL via app.services.db."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPORTS_DIR = ROOT / "exports"


def save_export(filename: str, content: str) -> Path:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = EXPORTS_DIR / filename
    out.write_text(content, encoding="utf-8")
    return out
