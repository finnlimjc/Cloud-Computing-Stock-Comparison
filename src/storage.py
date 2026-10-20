from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

ANALYSES_DIR = Path(__file__).resolve().parent.parent / "analyses-data"


def _safe_component(value:str) -> str:
    safe = re.sub(r"[^A-Za-z0-9-]+", "-", value.strip()).strip("-")
    return safe or "stock"


def make_filename(
    tickers:list[str],
    analysis_type:str,
    created_at:datetime | None=None,
) -> str:
    """Create a safe, timestamped Markdown filename."""
    stamp = created_at or datetime.now()
    if len(tickers) > 1:
        names = "-vs-".join(_safe_component(ticker) for ticker in tickers)
    else:
        names = _safe_component(tickers[0] if tickers else "stock")
    kind = "overview" if analysis_type == "overview" else "single"
    return f"{names}_{kind}_{stamp:%Y%m%d-%H%M%S}.md"


def save_analysis(
    markdown:str,
    tickers:list[str],
    analysis_type:str,
    created_at:datetime | None=None,
) -> Path:
    """Save Markdown beneath the project root without overwriting an earlier analysis."""
    ANALYSES_DIR.mkdir(parents=True, exist_ok=True)
    base = make_filename(tickers, analysis_type, created_at)
    path = ANALYSES_DIR / base
    suffix = 2
    while path.exists():
        path = ANALYSES_DIR / f"{Path(base).stem}_{suffix}.md"
        suffix += 1
    path.write_text(markdown, encoding="utf-8")
    return path


def list_analyses() -> list[Path]:
    """Return saved Markdown analyses, newest file first."""
    ANALYSES_DIR.mkdir(parents=True, exist_ok=True)

    def newest_key(path:Path) -> tuple[int, int]:
        collision = re.search(r"_(\d+)$", path.stem)
        suffix = int(collision.group(1)) if collision else 0
        return path.stat().st_mtime_ns, suffix

    return sorted(ANALYSES_DIR.glob("*.md"), key=newest_key, reverse=True)


def read_analysis(path:Path | str) -> str:
    """Read an analysis only from the project analyses-data directory."""
    resolved = Path(path).resolve()
    if resolved.parent != ANALYSES_DIR.resolve() or resolved.suffix.lower() != ".md":
        raise ValueError("The selected file is not a saved analysis.")
    return resolved.read_text(encoding="utf-8")
