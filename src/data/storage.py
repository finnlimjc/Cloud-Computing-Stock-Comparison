import re
from datetime import datetime
from pathlib import Path

import pandas as pd

# Storage location
ANALYSES_DIR = Path(__file__).resolve().parents[2] / "analyses-data"

# Filename building and parsing
FILENAME_UNSAFE_PATTERN = re.compile(r"[^A-Za-z0-9-]+")
COLLISION_SUFFIX_PATTERN = re.compile(r"_(\d+)$")
FILENAME_PATTERN = re.compile(r"(.+)_(?:overview|single)_(\d{8}-\d{6})(?:_\d+)?")

# Report metadata parsing
METADATA_PATTERN = re.compile(r"^- ([^:]+):\s*(.*)$")

def _safe_component(value:str) -> str:
    safe = FILENAME_UNSAFE_PATTERN.sub("-", value.strip()).strip("-")
    return safe or "stock"

def utc_offset(moment:datetime) -> str:
    """Format a datetime's UTC offset as UTC+08:00."""
    offset = moment.astimezone().strftime("%z")
    return f"UTC{offset[:3]}:{offset[3:]}"

def format_local_time(value:object) -> str:
    """Format a timestamp in local time as 2026-10-25 00:41:20 UTC+08:00, or return it unchanged when unparseable."""
    timestamp = pd.to_datetime(value, utc=True, errors="coerce") #timestamps without a timezone are treated as UTC
    if pd.isna(timestamp):
        return str(value)
    local = timestamp.to_pydatetime().astimezone()
    return f"{local:%Y-%m-%d %H:%M:%S} {utc_offset(local)}"

def _newest_key(path:Path) -> tuple[int, int]:
    """Return file modification time and collision suffix for sorting."""
    collision = COLLISION_SUFFIX_PATTERN.search(path.stem)
    suffix = int(collision.group(1)) if collision else 0
    return path.stat().st_mtime_ns, suffix

def _markdown_table(headers:list[str], rows:list[list[str]]) -> list[str]:
    """Build Markdown table lines with the first column left-aligned and the rest right-aligned."""
    alignment = ["---"] + ["---:"] * (len(headers) - 1)
    lines = [f"| {' | '.join(headers)} |", f"|{'|'.join(alignment)}|"]
    lines.extend(f"| {' | '.join(row)} |" for row in rows)
    return lines

def make_analysis_markdown(result:dict, sentence:str, created_at:datetime, company_metrics:dict) -> str:
    """Build a Markdown report for a dashboard analysis.
    
    Inputs:
    - result: dashboard analysis result
    - sentence: plain-language summary
    - created_at: report creation time
    - company_metrics: output of dashboard.analysis.collect_company_metrics, with formatted table sections and a note on anything unavailable
    
    Outputs:
    - Complete Markdown report
    """
    stocks = result["stocks"]
    tickers = [stock["ticker"] for stock in stocks.values()]
    analysis_type = "overview" if result["comparison"] else "single"
    title = " vs ".join(tickers) if result["comparison"] else tickers[0]
    
    # Header and summary
    lines = [
        f"# {title}",
        "",
        f"- Analysis type: {analysis_type}",
        f"- Tickers: {', '.join(tickers)}",
        f"- Time range: {result['start_date']:%Y-%m-%d} to {result['end_date']:%Y-%m-%d} ({result['range_label']})",
        f"- Created: {format_local_time(created_at)}",
        "",
        "## In plain words",
        "",
        sentence,
        "",
        "## Metrics",
        "",
        "| Ticker | Latest price | Return over period | Max drawdown | Current drawdown | Sharpe ratio |",
        "|---|---:|---:|---:|---:|---:|"
    ]
    
    # Metrics table
    for stock in stocks.values():
        metrics = stock["metrics"]
        lines.append(
            f"| {stock['ticker']} | ${metrics['Latest price']:,.2f} ({stock['price_at_end_date']:%Y-%m-%d}) | "
            f"{metrics['Return over period']:+.1%} | {metrics['Max drawdown']:.1%} | {metrics['Current drawdown']:.1%} | {metrics['Sharpe ratio']:.2f} |"
        )
    
    # News
    lines.extend(["", "## Latest news", ""])
    if result["news"]:
        lines.extend(
            f"- **{article['ticker']}** · [{article['headline']}]({article['url']}) ({format_local_time(article['created_at'])})"
            for article in result["news"]
        )
    else:
        lines.append("No news articles were available when this analysis was saved.")
    
    # Company metrics
    lines.extend(["", "## Company metrics"])
    for section in company_metrics["sections"]:
        lines.extend(["", f"### {section['title']}", ""])
        if section["note"]:
            lines.extend([section["note"], ""])
        lines.extend(_markdown_table(section["headers"], section["rows"]))
    if company_metrics["note"]:
        lines.extend(["", f"Not included: {company_metrics['note']}"])
    
    markdown = "\n".join(lines) + "\n"
    return markdown

class AnalysisStore:
    """
    Markdown analyses saved in one directory, newest first.
    
    Inputs:
    - directory: folder holding the saved reports
    """
    
    def __init__(self, directory:Path=ANALYSES_DIR) -> None:
        self.directory = directory
    
    @staticmethod
    def make_filename(tickers:list[str], analysis_type:str, created_at:datetime | None=None) -> str:
        """Create a safe, timestamped Markdown filename.
        
        Inputs:
        - tickers: symbols included in the analysis
        - analysis_type: overview or single-stock analysis
        - created_at: optional filename timestamp
        
        Outputs:
        - Markdown filename
        """
        stamp = created_at or datetime.now()
        names = "-vs-".join(_safe_component(ticker) for ticker in tickers) if tickers else "stock"
        kind = "overview" if analysis_type == "overview" else "single"
        filename = f"{names}_{kind}_{stamp:%Y%m%d-%H%M%S}.md"
        return filename
    
    @staticmethod
    def label(path:Path) -> str:
        """Format a saved analysis path as a readable selector label."""
        match = FILENAME_PATTERN.fullmatch(path.stem)
        if not match:
            return path.stem
        names, timestamp = match.groups()
        created = datetime.strptime(timestamp, "%Y%m%d-%H%M%S")
        date_format = "%d %b %H:%M" if created.year == datetime.now().year else "%d %b %Y %H:%M"
        label = f"{names.replace('-vs-', ' vs ')} · {created.strftime(date_format)}"
        return label
    
    @staticmethod
    def details(markdown:str) -> str:
        """Summarize a saved report's metadata in one line."""
        metadata = {}
        for line in markdown.splitlines():
            match = METADATA_PATTERN.match(line)
            if match:
                metadata[match.group(1)] = match.group(2)
        
        analysis_type = metadata.get("Analysis type", "Unavailable")
        if analysis_type != "Unavailable":
            analysis_type = analysis_type.title()
        details = " · ".join(
            [
                f"Tickers: {metadata.get('Tickers', 'Unavailable')}",
                f"Analysis type: {analysis_type}",
                f"Time range: {metadata.get('Time range', 'Unavailable')}",
                f"Created: {metadata.get('Created', 'Unavailable')}"
            ]
        )
        return details
    
    def save(self, markdown:str, tickers:list[str], analysis_type:str, created_at:datetime | None=None) -> Path:
        """Save Markdown without overwriting an earlier analysis.
        
        Inputs:
        - markdown: report content
        - tickers: symbols included in the analysis
        - analysis_type: overview or single-stock analysis
        - created_at: optional filename timestamp
        
        Outputs:
        - Path to the saved report
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        base = self.make_filename(tickers, analysis_type, created_at)
        
        path = self.directory / base
        suffix = 2
        while path.exists():
            path = self.directory / f"{Path(base).stem}_{suffix}.md"
            suffix += 1
        
        path.write_text(markdown, encoding="utf-8")
        return path
    
    def list_saved(self) -> list[Path]:
        """Return saved Markdown analyses, newest file first."""
        self.directory.mkdir(parents=True, exist_ok=True)
        analyses = sorted(self.directory.glob("*.md"), key=_newest_key, reverse=True)
        return analyses
    
    def read(self, path:Path | str) -> str:
        """Read a saved analysis, refusing any file outside the store's directory."""
        resolved = Path(path).resolve()
        if resolved.parent != self.directory.resolve() or resolved.suffix.lower() != ".md":
            raise ValueError("The selected file is not a saved analysis.")
        markdown = resolved.read_text(encoding="utf-8")
        return markdown
