"""SQLAlchemy persistence primitives used by API routes and services."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from fastapi import Request
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool

from .settings import Settings


class Base(DeclarativeBase):
    """Declarative base for all local persistence tables."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


class AssetRecord(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    warnings: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    # SQLite DateTime drops timezone offsets; retain the parser's original ISO string.
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_now_iso, nullable=False)


class DocumentBlockRecord(Base):
    __tablename__ = "document_blocks"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(128), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    block_type: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paragraph: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    block_order: Mapped[int] = mapped_column(Integer, nullable=False)
    block_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)


class RubricProfileRecord(Base):
    __tablename__ = "rubric_profiles"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_rubric_name_version"),)

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    source_asset_id: Mapped[str | None] = mapped_column(String(128), ForeignKey("assets.id"), nullable=True)
    source_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    warnings: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_ledger_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class RubricCriterionRecord(Base):
    __tablename__ = "rubric_criteria"
    __table_args__ = (UniqueConstraint("rubric_id", "criterion_id", name="uq_rubric_criterion"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    rubric_id: Mapped[str] = mapped_column(String(128), ForeignKey("rubric_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    criterion_id: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    scale_min: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    scale_max: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    evidence_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ReviewJobRecord(Base):
    __tablename__ = "review_jobs"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    asset_id: Mapped[str | None] = mapped_column(String(128), ForeignKey("assets.id"), nullable=True)
    rubric_profile_id: Mapped[str | None] = mapped_column(String(128), ForeignKey("rubric_profiles.id"), nullable=True)
    asset_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rubric_source_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_snapshot_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    options: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    state_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    state: Mapped[str] = mapped_column(String(64), nullable=False, default="CREATED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)


class DecisionLedgerRecord(Base):
    """Minimal human decision ledger used by rubric publication and later reviews."""

    __tablename__ = "decision_ledger"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    decided_by: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_refs: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)
    supersedes: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ModelConfigRecord(Base):
    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)


_ENGINE_CACHE: dict[str, Engine] = {}


def get_engine(settings: Settings | None = None) -> Engine:
    """Return a cached SQLite engine for the configured local data directory."""

    config = settings or Settings()
    db_path = config.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    key = str(db_path)
    if key not in _ENGINE_CACHE:
        engine = create_engine(
            f"sqlite:///{db_path.as_posix()}",
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
            future=True,
        )

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection: Any, _: Any) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

        _ENGINE_CACHE[key] = engine
    return _ENGINE_CACHE[key]


def init_db(settings: Settings | None = None) -> Engine:
    """Create all current tables and return the configured engine."""

    engine = get_engine(settings)
    Base.metadata.create_all(bind=engine)
    _ensure_additive_schema_compatibility(engine)
    return engine


def _ensure_additive_schema_compatibility(engine: Engine) -> None:
    """Add newly introduced nullable/defaulted columns to an existing local DB.

    v0.1 intentionally has no migration framework, but databases created by an
    earlier build must remain usable after models evolve. SQLite create_all only
    creates missing tables; it does not add columns to an existing table. Only
    additive changes are performed here.
    """

    additions = {
        "assets": {
            "error_code": "VARCHAR(64)",
        },
        "document_blocks": {
            "metadata": "JSON NOT NULL DEFAULT '{}'",
        },
        "review_jobs": {
            "asset_sha256": "VARCHAR(128)",
            "rubric_source_hash": "VARCHAR(128)",
            "input_snapshot_hash": "VARCHAR(128)",
            "options": "JSON NOT NULL DEFAULT '{}'",
            "state_snapshot": "JSON NOT NULL DEFAULT '{}'",
            "result_snapshot": "JSON NOT NULL DEFAULT '{}'",
        },
    }
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table_name, columns in additions.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for name, declaration in columns.items():
                if name not in existing_columns:
                    connection.execute(
                        text(
                            f'ALTER TABLE "{table_name}" '
                            f'ADD COLUMN "{name}" {declaration}'
                        )
                    )


def _session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=init_db(settings), autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(settings: Settings | None = None) -> Iterator[Session]:
    """Yield a transaction-scoped Session and always rollback failed work."""

    session = _session_factory(settings)()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI dependency yielding a committed or rolled-back Session."""

    settings = getattr(request.app.state, "settings", None)
    with session_scope(settings) as session:
        yield session


class SqlAlchemyAssetStore:
    """Persistence adapter implementing the asset route store contract."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def save(self, asset: Any) -> Any:
        canonical_id: str | None = None
        with session_scope(self.settings) as session:
            existing_by_hash = session.query(AssetRecord).filter_by(sha256=asset.sha256).first()
            if existing_by_hash is not None and existing_by_hash.id != asset.id:
                # Content identity wins over upload request identity. This makes
                # repeated uploads return the first asset and its block lineage.
                canonical_id = existing_by_hash.id
            else:
                existing = session.get(AssetRecord, asset.id)
                if existing is None:
                    existing = AssetRecord(
                        id=asset.id,
                        filename=asset.filename,
                        media_type=asset.media_type,
                        size_bytes=asset.size_bytes,
                        sha256=asset.sha256,
                        status=asset.status.value,
                        storage_path=str(asset.storage_path),
                        parse_error=asset.parse_error,
                        error_code=asset.error_code,
                        warnings=list(asset.warnings),
                        created_at=asset.created_at or _utc_now_iso(),
                    )
                    session.add(existing)
                else:
                    existing.status = asset.status.value
                    existing.parse_error = asset.parse_error
                    existing.error_code = asset.error_code
                    existing.warnings = list(asset.warnings)
                for block in asset.blocks:
                    row = session.get(DocumentBlockRecord, block.block_id)
                    if row is None:
                        session.add(
                            DocumentBlockRecord(
                                id=block.block_id,
                                asset_id=asset.id,
                                block_type=block.block_type,
                                text=block.text,
                                page=block.page,
                                paragraph=block.paragraph,
                                line_start=block.line_start,
                                line_end=block.line_end,
                                block_order=block.block_order,
                                block_metadata=dict(block.metadata),
                            )
                        )
        if canonical_id is not None:
            return self.get(canonical_id)
        return self.get(asset.id) or asset

    def get(self, asset_id: str) -> Any | None:
        from backend.app.domain.assets import Asset, DocumentBlock, ParseStatus, ParsedDocument

        with session_scope(self.settings) as session:
            record = session.get(AssetRecord, asset_id)
            if record is None:
                return None
            rows = session.query(DocumentBlockRecord).filter_by(asset_id=asset_id).order_by(DocumentBlockRecord.block_order).all()
            blocks = tuple(
                DocumentBlock(
                    block_id=row.id,
                    asset_id=row.asset_id,
                    block_type=row.block_type,
                    text=row.text,
                    page=row.page,
                    paragraph=row.paragraph,
                    line_start=row.line_start,
                    line_end=row.line_end,
                    block_order=row.block_order,
                    metadata=dict(row.block_metadata or {}),
                )
                for row in rows
            )
            status = ParseStatus(record.status)
            parsed = ParsedDocument(status=status, blocks=blocks, warnings=tuple(record.warnings or ()), error_code=record.error_code, error_message=record.parse_error)
            return Asset(
                id=record.id,
                filename=record.filename,
                media_type=record.media_type,
                size_bytes=record.size_bytes,
                sha256=record.sha256,
                status=status,
                storage_path=Path(record.storage_path),
                parsed_document=parsed,
                parse_error=record.parse_error,
                created_at=record.created_at if isinstance(record.created_at, str) else record.created_at.isoformat() if record.created_at else None,
            )

    def list(self) -> list[Any]:
        with session_scope(self.settings) as session:
            ids = [row.id for row in session.query(AssetRecord.id).order_by(AssetRecord.created_at.desc()).all()]
        return [asset for asset_id in ids if (asset := self.get(asset_id)) is not None]


class SqlAlchemyRubricRepository:
    """Persistence adapter for rubric drafts and publication decisions."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @staticmethod
    def _draft_from_records(profile: RubricProfileRecord, criteria: list[RubricCriterionRecord]):
        from backend.app.domain.rubrics import RubricCriterion, RubricDraft, RubricStatus

        return RubricDraft(
            id=profile.id,
            name=profile.name,
            version=profile.version,
            source_asset_id=profile.source_asset_id or "unknown",
            source_hash=profile.source_hash,
            criteria=[RubricCriterion(id=row.criterion_id, label=row.label, description=row.description, weight=row.weight, scale_min=row.scale_min, scale_max=row.scale_max, evidence_required=row.evidence_required) for row in criteria],
            warnings=list(profile.warnings or []),
            status=RubricStatus(profile.status),
            published_at=profile.published_at,
            decision_ledger_id=profile.decision_ledger_id,
        )

    def create(self, rubric: Any) -> Any:
        from backend.app.services.rubric_importer import RubricImportError

        with session_scope(self.settings) as session:
            if session.query(RubricProfileRecord).filter_by(name=rubric.name, version=rubric.version).first():
                raise RubricImportError(f"rubric name and version already exist: {rubric.name} {rubric.version}")
            session.add(RubricProfileRecord(id=rubric.id, name=rubric.name, version=rubric.version, source_asset_id=rubric.source_asset_id, source_hash=rubric.source_hash, status=rubric.status.value, warnings=list(rubric.warnings), published_at=rubric.published_at))
            session.flush()
            for criterion in rubric.criteria:
                session.add(RubricCriterionRecord(id=f"{rubric.id}:{criterion.id}", rubric_id=rubric.id, criterion_id=criterion.id, label=criterion.label, description=criterion.description, weight=criterion.weight, scale_min=criterion.scale_min, scale_max=criterion.scale_max, evidence_required=criterion.evidence_required))
        return rubric

    def list(self) -> list[Any]:
        with session_scope(self.settings) as session:
            profiles = session.query(RubricProfileRecord).order_by(RubricProfileRecord.name, RubricProfileRecord.version).all()
            return [self._draft_from_records(profile, session.query(RubricCriterionRecord).filter_by(rubric_id=profile.id).order_by(RubricCriterionRecord.id).all()) for profile in profiles]

    def get(self, rubric_id: str) -> Any | None:
        with session_scope(self.settings) as session:
            profile = session.get(RubricProfileRecord, rubric_id)
            if profile is None:
                return None
            criteria = session.query(RubricCriterionRecord).filter_by(rubric_id=rubric_id).order_by(RubricCriterionRecord.id).all()
            return self._draft_from_records(profile, criteria)

    def publish(self, rubric: Any, decision: Any) -> None:
        from backend.app.services.rubric_importer import RubricImportError

        with session_scope(self.settings) as session:
            profile = session.get(RubricProfileRecord, rubric.id)
            if profile is None:
                raise RubricImportError("rubric not found")
            profile.status = rubric.status.value
            profile.published_at = rubric.published_at
            profile.decision_ledger_id = decision.id
            session.add(DecisionLedgerRecord(id=decision.id, subject_type="rubric_profile", subject_id=rubric.id, decided_by=decision.decided_by, decision=decision.decision, rationale=decision.rationale, evidence_refs=list(decision.evidence_ids), decided_at=decision.decided_at, supersedes=decision.supersedes))

    def update(self, rubric: Any) -> Any:
        """Update a draft rubric and replace its criteria atomically."""

        from backend.app.services.rubric_importer import RubricImportError

        with session_scope(self.settings) as session:
            profile = session.get(RubricProfileRecord, rubric.id)
            if profile is None:
                raise RubricImportError("rubric not found")
            if profile.status == "published":
                raise RubricImportError("published rubric cannot be edited")
            # Pydantic's model_copy(update=...) intentionally skips validation;
            # enforce the repository invariant at the persistence boundary too.
            if getattr(rubric.status, "value", rubric.status) != "draft":
                raise RubricImportError("only draft rubrics can be edited")
            duplicate = (
                session.query(RubricProfileRecord)
                .filter(
                    RubricProfileRecord.name == rubric.name,
                    RubricProfileRecord.version == rubric.version,
                    RubricProfileRecord.id != rubric.id,
                )
                .first()
            )
            if duplicate is not None:
                raise RubricImportError(f"rubric name and version already exist: {rubric.name} {rubric.version}")
            profile.name = rubric.name
            profile.version = rubric.version
            profile.source_asset_id = rubric.source_asset_id
            profile.source_hash = rubric.source_hash
            profile.status = rubric.status.value
            profile.warnings = list(rubric.warnings)
            session.query(RubricCriterionRecord).filter_by(rubric_id=rubric.id).delete(synchronize_session=False)
            session.flush()
            for criterion in rubric.criteria:
                session.add(
                    RubricCriterionRecord(
                        id=f"{rubric.id}:{criterion.id}",
                        rubric_id=rubric.id,
                        criterion_id=criterion.id,
                        label=criterion.label,
                        description=criterion.description,
                        weight=criterion.weight,
                        scale_min=criterion.scale_min,
                        scale_max=criterion.scale_max,
                        evidence_required=criterion.evidence_required,
                    )
                )
        return rubric

class SqlAlchemyReviewJobRepository:
    """Repository that freezes an asset/rubric pair for a review job."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @staticmethod
    def _to_domain(row: ReviewJobRecord):
        from backend.app.domain.review_jobs import ReviewJob, ReviewJobStatus

        return ReviewJob(
            id=row.id,
            asset_id=row.asset_id or "",
            rubric_profile_id=row.rubric_profile_id or "",
            asset_sha256=row.asset_sha256 or "",
            rubric_source_hash=row.rubric_source_hash or "",
            input_snapshot_hash=row.input_snapshot_hash or "",
            state=ReviewJobStatus(row.state),
            options=dict(row.options or {}),
            state_snapshot=dict(row.state_snapshot or {}),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def create(self, job: Any) -> Any:
        from backend.app.services.review_jobs import ReviewJobError

        with session_scope(self.settings) as session:
            if session.get(ReviewJobRecord, job.id) is not None:
                raise ReviewJobError("review job already exists")
            session.add(
                ReviewJobRecord(
                    id=job.id,
                    asset_id=job.asset_id,
                    rubric_profile_id=job.rubric_profile_id,
                    asset_sha256=job.asset_sha256,
                    rubric_source_hash=job.rubric_source_hash,
                    input_snapshot_hash=job.input_snapshot_hash,
                    state=job.state.value,
                    options=dict(job.options),
                    state_snapshot=dict(job.state_snapshot or {}),
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                )
            )
        return job

    def get(self, job_id: str) -> Any | None:
        with session_scope(self.settings) as session:
            row = session.get(ReviewJobRecord, job_id)
            return self._to_domain(row) if row is not None else None

    def update(self, job: Any) -> Any:
        from backend.app.services.review_jobs import ReviewJobError

        with session_scope(self.settings) as session:
            row = session.get(ReviewJobRecord, job.id)
            if row is None:
                raise ReviewJobError("review job not found")
            row.asset_id = job.asset_id
            row.rubric_profile_id = job.rubric_profile_id
            row.asset_sha256 = job.asset_sha256
            row.rubric_source_hash = job.rubric_source_hash
            row.input_snapshot_hash = job.input_snapshot_hash
            row.options = dict(job.options)
            row.state_snapshot = dict(job.state_snapshot or {})
            row.state = job.state.value
            row.updated_at = job.updated_at
        return job

    def list(self) -> list[Any]:
        with session_scope(self.settings) as session:
            rows = session.query(ReviewJobRecord).order_by(ReviewJobRecord.created_at.desc()).all()
            return [self._to_domain(row) for row in rows]

    def save_result_snapshot(self, review_id: str, snapshot: dict[str, Any]) -> None:
        """Atomically replace the validated JSON result for a review job."""
        from backend.app.services.review_results import ReviewResultError

        with session_scope(self.settings) as session:
            row = session.get(ReviewJobRecord, review_id)
            if row is None:
                raise ReviewResultError("review job not found")
            row.result_snapshot = dict(snapshot)

    def get_result_snapshot(self, review_id: str) -> dict[str, Any] | None:
        with session_scope(self.settings) as session:
            row = session.get(ReviewJobRecord, review_id)
            if row is None or not row.result_snapshot:
                return None
            return dict(row.result_snapshot)

    def save_decision(self, decision: dict[str, Any]) -> None:
        with session_scope(self.settings) as session:
            session.add(DecisionLedgerRecord(**decision))


class SqlAlchemyModelConfigRepository:
    """Persistence adapter for encrypted runtime model configurations."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @staticmethod
    def _public(row: ModelConfigRecord) -> dict[str, Any]:
        return {
            "id": row.id, "provider": row.provider, "base_url": row.base_url,
            "model": row.model, "is_active": row.is_active,
            "api_key_configured": bool(row.encrypted_api_key),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def has_any(self) -> bool:
        with session_scope(self.settings) as session:
            return session.query(ModelConfigRecord).first() is not None

    def list(self) -> list[dict[str, Any]]:
        with session_scope(self.settings) as session:
            return [self._public(row) for row in session.query(ModelConfigRecord).order_by(ModelConfigRecord.updated_at.desc()).all()]

    def get(self, config_id: str) -> dict[str, Any] | None:
        with session_scope(self.settings) as session:
            row = session.get(ModelConfigRecord, config_id)
            return self._public(row) if row else None

    def get_secret(self, config_id: str) -> str | None:
        with session_scope(self.settings) as session:
            row = session.get(ModelConfigRecord, config_id)
            return row.encrypted_api_key if row else None

    def get_active(self) -> dict[str, Any] | None:
        with session_scope(self.settings) as session:
            row = session.query(ModelConfigRecord).filter_by(is_active=True).first()
            return self._public(row) if row else None

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        with session_scope(self.settings) as session:
            if payload.get("is_active"):
                session.query(ModelConfigRecord).update({"is_active": False})
            row = ModelConfigRecord(**payload)
            session.add(row)
            session.flush()
            return self._public(row)

    def update(self, config_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        with session_scope(self.settings) as session:
            row = session.get(ModelConfigRecord, config_id)
            if row is None:
                return None
            if payload.get("is_active"):
                session.query(ModelConfigRecord).update({"is_active": False})
            for key, value in payload.items():
                setattr(row, key, value)
            row.updated_at = _utc_now()
            session.flush()
            return self._public(row)

    def delete(self, config_id: str) -> bool:
        with session_scope(self.settings) as session:
            row = session.get(ModelConfigRecord, config_id)
            if row is None:
                return False
            session.delete(row)
            return True

    def get_row(self, config_id: str) -> ModelConfigRecord | None:
        with session_scope(self.settings) as session:
            row = session.get(ModelConfigRecord, config_id)
            if row is None:
                return None
            return row

