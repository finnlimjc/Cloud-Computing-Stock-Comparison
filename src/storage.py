from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

ANALYSES_DIR = Path(__file__).resolve().parent.parent / "analyses-data"


def _safe_component(value:str) -> str:
    """Convert a ticker or name into a filename-safe component.

    Inputs:
    - value: text to include in a filename

    Outputs:
    - Safe filename component, or the default stock name
    """
    # This part replaces unsupported characters and handles empty values.
    safe = re.sub(r"[^A-Za-z0-9-]+", "-", value.strip()).strip("-")
    return safe or "stock"


def make_filename(
    tickers:list[str],
    analysis_type:str,
    created_at:datetime | None=None,
) -> str:
    """Create a safe, timestamped Markdown filename.

    Inputs:
    - tickers: symbols included in the analysis
    - analysis_type: overview or single-stock analysis
    - created_at: optional filename timestamp

    Outputs:
    - Markdown filename
    """
    # This part selects filename names and normalizes the analysis type.
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
    """Save Markdown without overwriting an earlier analysis.

    Inputs:
    - markdown: report content
    - tickers: symbols included in the analysis
    - analysis_type: overview or single-stock analysis
    - created_at: optional filename timestamp

    Outputs:
    - Path to the saved report
    """
    # This part creates the storage directory and chooses a base filename.
    ANALYSES_DIR.mkdir(parents=True, exist_ok=True)
    base = make_filename(tickers, analysis_type, created_at)
    path = ANALYSES_DIR / base
    suffix = 2
    # This part adds a suffix if the filename already exists.
    while path.exists():
        path = ANALYSES_DIR / f"{Path(base).stem}_{suffix}.md"
        suffix += 1
    # This part writes and returns the report path.
    path.write_text(markdown, encoding="utf-8")
    return path


def list_analyses() -> list[Path]:
    """Return saved Markdown analyses, newest file first.

    Inputs:
    - None

    Outputs:
    - Saved report paths in newest-first order
    """
    # This part ensures the storage directory exists.
    ANALYSES_DIR.mkdir(parents=True, exist_ok=True)

    def newest_key(path:Path) -> tuple[int, int]:
        """Return file modification time and collision suffix for sorting.

        Inputs:
        - path: saved report path

        Outputs:
        - Modification time and numeric suffix
        """
        # This part extracts the collision suffix and file modification time.
        collision = re.search(r"_(\d+)$", path.stem)
        suffix = int(collision.group(1)) if collision else 0
        return path.stat().st_mtime_ns, suffix

    # This part sorts all saved reports from newest to oldest.
    return sorted(ANALYSES_DIR.glob("*.md"), key=newest_key, reverse=True)


def read_analysis(path:Path | str) -> str:
    """Read a saved analysis from the project analyses-data directory.

    Inputs:
    - path: selected report path

    Outputs:
    - Saved Markdown report
    """
    # This part resolves and validates the selected report path.
    resolved = Path(path).resolve()
    if resolved.parent != ANALYSES_DIR.resolve() or resolved.suffix.lower() != ".md":
        raise ValueError("The selected file is not a saved analysis.")
    # This part reads the validated report as UTF-8 text.
    return resolved.read_text(encoding="utf-8")
