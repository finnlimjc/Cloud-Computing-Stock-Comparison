from contextlib import AbstractContextManager
from datetime import datetime, timezone

from sqlalchemy import (Boolean, CheckConstraint, Column, Connection, Date, DateTime, ForeignKey, Index, Integer,
                        MetaData, String, Table, create_engine, delete, event, false, insert, inspect, or_, select, text, true, update)

# Allowed column values
VISIBILITIES = ["private", "public"]
DOCUMENT_TYPES = ["overview", "single", "statements", "upload"]

# Schema (portable SQL: the same tables are created on SQLite locally and PostgreSQL on RDS)
metadata = MetaData()

# Table details are recorded under documentation/database-tables.md
users = Table(
    "users",
    metadata,
    Column("user_id", Integer, primary_key=True, autoincrement=True),
    Column("username", String(32), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("is_admin", Boolean, nullable=False, server_default=false()),
    Column("created_at", DateTime(timezone=True), nullable=False)
)

documents = Table(
    "documents",
    metadata,
    Column("document_id", Integer, primary_key=True, autoincrement=True),
    Column("owner_id", Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
    Column("filename", String(255), nullable=False),
    Column("object_key", String(512), unique=True), #set in the same transaction once document_id is known
    Column("title", String(255), nullable=False),
    Column("document_type", String(16), nullable=False),
    Column("visibility", String(8), nullable=False),
    Column("content_type", String(64), nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("start_date", Date),
    Column("end_date", Date),
    Column("range_label", String(32)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(f"visibility IN ({', '.join(repr(value) for value in VISIBILITIES)})", name="ck_documents_visibility"),
    CheckConstraint(f"document_type IN ({', '.join(repr(value) for value in DOCUMENT_TYPES)})", name="ck_documents_type"),
    Index("ix_documents_owner_created", "owner_id", "created_at"),
    Index("ix_documents_visibility_created", "visibility", "created_at")
)

document_tickers = Table(
    "document_tickers",
    metadata,
    Column("document_id", Integer, ForeignKey("documents.document_id", ondelete="CASCADE"), primary_key=True),
    Column("ticker", String(16), primary_key=True),
    Column("position", Integer, nullable=False), #keeps the order the tickers were entered in
    Index("ix_document_tickers_ticker", "ticker")
)

def _enable_sqlite_foreign_keys(dbapi_connection:object, connection_record:object) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON") #Enforces ForeignKey(..., ondelete="CASCADE")
    cursor.close()

def _as_utc(moment:datetime) -> datetime:
    """Attach UTC to timestamps SQLite returns without a timezone."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)

def _visible_to(user_id:int | None, is_admin:bool) -> object:
    """Filter documents to those a user may see: their own plus every public one, or everything for an admin. Visitors who are not logged in see nothing."""
    if is_admin:
        return true()
    if user_id is None:
        return false()
    return or_(documents.c.owner_id == user_id, documents.c.visibility == "public")

class Database:
    """
    Users and document metadata, through SQLAlchemy Core so the URL alone picks SQLite or PostgreSQL.
    
    Inputs:
    - url: SQLAlchemy database URL, such as sqlite:///local-data/app.db
    """
    
    def __init__(self, url:str) -> None:
        self.engine = create_engine(url)
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", _enable_sqlite_foreign_keys) #SQLite ignores ON DELETE CASCADE without this
        metadata.create_all(self.engine)
        self._add_missing_columns()
    
    def _add_missing_columns(self) -> None:
        """Add users.is_admin to databases created before it existed, because create_all skips tables that already exist."""
        columns = [column["name"] for column in inspect(self.engine).get_columns("users")]
        if "is_admin" not in columns:
            with self.transaction() as connection:
                connection.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE"))
    
    def transaction(self) -> AbstractContextManager[Connection]:
        """Open a connection whose changes commit together, or roll back if anything raises."""
        return self.engine.begin()
    
    def create_user(self, username:str, password_hash:str, is_admin:bool=False) -> int:
        """Insert a user and return their id, raising IntegrityError when the username is taken."""
        values = {"username": username, "password_hash": password_hash, "is_admin": is_admin, "created_at": datetime.now(timezone.utc)}
        with self.transaction() as connection:
            result = connection.execute(insert(users).values(**values))
        return result.inserted_primary_key[0]
    
    def get_user_by_name(self, username:str) -> dict | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(users).where(users.c.username == username)).first()
        if row is None:
            return None
        return dict(row._mapping)
    
    def insert_document(self, connection:Connection, values:dict, tickers:list[str]) -> int:
        """Insert a document row and its tickers within the caller's transaction.
        
        Inputs:
        - connection: open transaction from Database.transaction
        - values: documents column values, without document_id or object_key
        - tickers: symbols covered by the document, in display order
        
        Outputs:
        - New document_id
        """
        result = connection.execute(insert(documents).values(**values))
        document_id = result.inserted_primary_key[0]
        if tickers:
            ticker_rows = [{"document_id": document_id, "ticker": ticker, "position": position} for position, ticker in enumerate(tickers)]
            connection.execute(insert(document_tickers), ticker_rows)
        return document_id
    
    def set_object_key(self, connection:Connection, document_id:int, object_key:str) -> None:
        connection.execute(update(documents).where(documents.c.document_id == document_id).values(object_key=object_key))
    
    def _attach_tickers(self, connection:Connection, rows:list[dict]) -> list[dict]:
        """Add each document's ordered tickers and timezone-aware created_at."""
        document_ids = [row["document_id"] for row in rows]
        tickers = {document_id: [] for document_id in document_ids}
        query = (
            select(document_tickers.c.document_id, document_tickers.c.ticker)
            .where(document_tickers.c.document_id.in_(document_ids))
            .order_by(document_tickers.c.document_id, document_tickers.c.position)
        )
        for document_id, ticker in connection.execute(query):
            tickers[document_id].append(ticker)
        for row in rows:
            row["tickers"] = tickers[row["document_id"]]
            row["created_at"] = _as_utc(row["created_at"])
        return rows
    
    def _documents_query(self, user_id:int | None, is_admin:bool) -> object:
        query = (
            select(documents, users.c.username.label("owner"))
            .join(users, users.c.user_id == documents.c.owner_id)
            .where(_visible_to(user_id, is_admin))
        )
        return query
    
    def list_documents(self, user_id:int | None, is_admin:bool=False) -> list[dict]:
        """Return the documents a user may see, newest first (none when user_id is None, every document for an admin)."""
        query = self._documents_query(user_id, is_admin).order_by(documents.c.created_at.desc(), documents.c.document_id.desc())
        with self.engine.connect() as connection:
            rows = [dict(row._mapping) for row in connection.execute(query)]
            return self._attach_tickers(connection, rows)
    
    def get_document(self, document_id:int, user_id:int | None, is_admin:bool=False) -> dict | None:
        """Return one document if the user may see it, otherwise None."""
        query = self._documents_query(user_id, is_admin).where(documents.c.document_id == document_id)
        with self.engine.connect() as connection:
            row = connection.execute(query).first()
            if row is None:
                return None
            return self._attach_tickers(connection, [dict(row._mapping)])[0]
    
    def set_visibility(self, document_id:int, owner_id:int, visibility:str) -> bool:
        """Change a document's visibility, only for its owner. Returns whether a row changed."""
        query = (
            update(documents)
            .where(documents.c.document_id == document_id, documents.c.owner_id == owner_id)
            .values(visibility=visibility)
        )
        with self.transaction() as connection:
            result = connection.execute(query)
        return result.rowcount == 1
    
    def delete_document(self, connection:Connection, document_id:int, owner_id:int | None) -> str | None:
        """Delete a document within the caller's transaction, returning its object key or None if nothing was deleted.
        
        Inputs:
        - connection: open transaction from Database.transaction
        - document_id: document to delete
        - owner_id: only delete if this user owns it; None deletes whoever owns it (admin)
        
        Outputs:
        - Object key of the deleted file, or None
        """
        query = delete(documents).where(documents.c.document_id == document_id)
        if owner_id is not None:
            query = query.where(documents.c.owner_id == owner_id)
        return connection.execute(query.returning(documents.c.object_key)).scalar_one_or_none()
