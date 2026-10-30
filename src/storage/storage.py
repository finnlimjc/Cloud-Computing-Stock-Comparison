import hashlib
import re
from datetime import date, datetime, timezone

import pandas as pd
from sqlalchemy.exc import IntegrityError

from src.storage import auth
from src.storage.database import DOCUMENT_TYPES, VISIBILITIES, Database
from src.storage.object_store import LocalObjectStore

# Filename building
FILENAME_UNSAFE_PATTERN = re.compile(r"[^A-Za-z0-9-]+")
FILENAME_STAMP_FORMAT = "%Y%m%d-%H%M%SZ" #UTC, matching the created_at column

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

def make_statements_markdown(financial_statements:dict, ticker:str, created_at:datetime) -> str:
    """Build a Markdown report holding one company's financial statements.
    
    Inputs:
    - financial_statements: output of dashboard.analysis.collect_financial_statements
    - ticker: company selected on the Financial Statements tab
    - created_at: report creation time
    
    Outputs:
    - Complete Markdown report
    """
    lines = [
        f"# {financial_statements['title']}: financial statements",
        "",
        "- Analysis type: statements",
        f"- Tickers: {ticker}",
        f"- Created: {format_local_time(created_at)}"
    ]
    if financial_statements["note"]:
        lines.extend(["", financial_statements["note"]])
    
    # How the figures tally
    if financial_statements["tally_notes"]:
        lines.extend(["", "## How the figures tally", ""])
        for note, details in financial_statements["tally_notes"]:
            lines.append(f"- {note}")
            lines.extend(f"    - {detail}" for detail in details)
    
    # Statements and their remaining line items
    for section in financial_statements["sections"]:
        lines.extend(["", f"## {section['title']}", ""])
        if section["note"]:
            lines.extend([section["note"], ""])
        lines.extend(_markdown_table(section["headers"], section["rows"]))
    
    markdown = "\n".join(lines) + "\n"
    return markdown

def make_filename(names:list[str], document_type:str, created_at:datetime, extension:str) -> str:
    """Build a document filename from the same values stored in its database row.
    
    Inputs:
    - names: tickers for generated reports, or the title for uploads
    - document_type: overview, single, statements or upload
    - created_at: the row's creation time, written in UTC
    - extension: file extension without the dot, such as md or pdf
    
    Outputs:
    - Filename such as AAPL-vs-MSFT_overview_20261026-060500Z.md
    """
    joined = "-vs-".join(_safe_component(name) for name in names) if names else "stock"
    stamp = created_at.astimezone(timezone.utc).strftime(FILENAME_STAMP_FORMAT)
    filename = f"{joined[:100]}_{document_type}_{stamp}.{extension}"
    return filename

def make_object_key(owner_id:int, document_id:int, filename:str) -> str:
    return f"users/{owner_id}/{document_id}/{filename}"

class DocumentStore:
    """
    Saved documents for logged-in users: metadata and access rules in the database, file contents in the object store.
    
    Inputs:
    - database: users and document metadata
    - objects: store holding each document's bytes under its object key
    """
    
    def __init__(self, database:Database, objects:LocalObjectStore) -> None:
        self.database = database
        self.objects = objects
        self._dummy_hash = auth.hash_password("unused-password") #checked when a username is unknown so both failures take as long
    
    def register(self, username:str, password:str) -> dict:
        """Create an account, raising ValueError with a readable reason when it cannot."""
        username = auth.normalize_username(username)
        problem = auth.validate_username(username) or auth.validate_password(password)
        if problem:
            raise ValueError(problem)
        try:
            user_id = self.database.create_user(username, auth.hash_password(password))
        except IntegrityError:
            raise ValueError("That username is already taken.") from None
        return {"user_id": user_id, "username": username}
    
    def authenticate(self, username:str, password:str) -> dict | None:
        """Return the user for a correct username and password, otherwise None."""
        user = self.database.get_user_by_name(auth.normalize_username(username))
        stored_hash = user["password_hash"] if user else self._dummy_hash
        if not auth.verify_password(password, stored_hash) or user is None:
            return None
        return {"user_id": user["user_id"], "username": user["username"]}
    
    def save(self, owner_id:int, data:bytes, content_type:str, title:str, document_type:str, visibility:str, tickers:list[str], created_at:datetime, extension:str, start_date:date | None=None, end_date:date | None=None, range_label:str | None=None) -> int:
        """Save a document's row and file together, leaving neither behind if either fails.
        
        Inputs:
        - owner_id: user saving the document
        - data: file contents
        - content_type: media type, such as text/markdown or application/pdf
        - title: name shown in the saved documents list
        - document_type: overview, single, statements or upload
        - visibility: private or public
        - tickers: symbols the document covers, possibly empty for uploads
        - created_at: save time
        - extension: file extension without the dot
        - start_date, end_date, range_label: price range of an overview or single-stock analysis
        
        Outputs:
        - New document_id
        """
        if document_type not in DOCUMENT_TYPES or visibility not in VISIBILITIES:
            raise ValueError("Unknown document type or visibility.")
        created_utc = created_at.astimezone(timezone.utc)
        names = tickers if document_type != "upload" else [title]
        values = {
            "owner_id": owner_id,
            "filename": make_filename(names, document_type, created_utc, extension),
            "title": title,
            "document_type": document_type,
            "visibility": visibility,
            "content_type": content_type,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "start_date": start_date,
            "end_date": end_date,
            "range_label": range_label,
            "created_at": created_utc
        }
        
        with self.database.transaction() as connection: #commits only after the file is written
            document_id = self.database.insert_document(connection, values, tickers)
            object_key = make_object_key(owner_id, document_id, values["filename"])
            self.database.set_object_key(connection, document_id, object_key)
            self.objects.put(object_key, data)
        return document_id
    
    def list_visible(self, user_id:int | None) -> list[dict]:
        return self.database.list_documents(user_id)
    
    def read(self, document_id:int, user_id:int | None) -> tuple[dict, bytes]:
        """Return a document's row and contents, raising ValueError when the user may not see it."""
        document = self.database.get_document(document_id, user_id)
        if document is None:
            raise ValueError("This document does not exist or is private.")
        return document, self.objects.get(document["object_key"])
    
    def set_visibility(self, document_id:int, owner_id:int, visibility:str) -> bool:
        if visibility not in VISIBILITIES:
            raise ValueError("Unknown visibility.")
        return self.database.set_visibility(document_id, owner_id, visibility)
    
    def delete(self, document_id:int, owner_id:int) -> bool:
        """Delete a document's row and file, only for its owner. Returns whether anything was deleted."""
        with self.database.transaction() as connection: #a failed file delete rolls the row back
            object_key = self.database.delete_document(connection, document_id, owner_id)
            if object_key is None:
                return False
            self.objects.delete(object_key)
        return True
    
    @staticmethod
    def label(document:dict) -> str:
        """Format a document as a readable selector label, such as AAPL vs MSFT · 26 Oct 14:05."""
        created = document["created_at"].astimezone()
        date_format = "%d %b %H:%M" if created.year == datetime.now().year else "%d %b %Y %H:%M"
        label = f"{document['title']} · {created.strftime(date_format)}"
        return label
    
    @staticmethod
    def details(document:dict) -> str:
        """Summarize a document's metadata in one line."""
        tickers = ", ".join(document["tickers"]) or "None"
        parts = [f"Tickers: {tickers}", f"Analysis type: {document['document_type'].title()}"]
        if document["start_date"] is not None: #statements and uploads have no price range
            parts.append(f"Time range: {document['start_date']:%Y-%m-%d} to {document['end_date']:%Y-%m-%d} ({document['range_label']})")
        parts.append(f"Created: {format_local_time(document['created_at'])}")
        parts.append(f"Owner: {document['owner']} ({document['visibility'].title()})")
        details = " · ".join(parts)
        return details
