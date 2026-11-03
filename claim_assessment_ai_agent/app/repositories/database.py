from __future__ import annotations

from pathlib import Path

from sqlalchemy import (
    JSON,
    Column,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.errors import AppError

metadata = MetaData()
records = Table(
    "records",
    metadata,
    Column("id", String, primary_key=True),
    Column("kind", String, nullable=False, index=True),
    Column("parent", String, nullable=False, index=True),
    Column("data", JSON, nullable=False),
)
runs = Table(
    "assessments",
    metadata,
    Column("id", String, primary_key=True),
    Column("claim_id", String, nullable=False, index=True),
    Column("session_id", String, nullable=False, index=True),
    Column("version", Integer, nullable=False),
    Column("status", String, nullable=False),
    Column("data", JSON, nullable=False),
    UniqueConstraint("claim_id", "version"),
)
Index(
    "one_running_assessment_per_claim",
    runs.c.claim_id,
    unique=True,
    sqlite_where=runs.c.status == "running",
)


class Database:
    """Short transactions only. Application snapshots are immutable JSON records."""

    def __init__(self, url: str):
        self.engine = create_async_engine(url)
        if self.engine.url.get_backend_name() != "sqlite":
            raise ValueError("MVP supports SQLite only")
        db_path = self.engine.url.database
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.run_sync(metadata.create_all)
            rows = (await conn.execute(select(runs).where(runs.c.status == "running"))).mappings()
            for row in rows:
                data = dict(row["data"], status="failed", error="interrupted_by_restart")
                await conn.execute(
                    update(runs).where(runs.c.id == row["id"]).values(status="failed", data=data)
                )

    async def close(self) -> None:
        await self.engine.dispose()

    async def ready(self) -> None:
        async with self.engine.connect() as conn:
            await conn.execute(select(1))

    async def put(self, kind: str, id_: str, parent: str, data: dict) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(insert(records).values(id=id_, kind=kind, parent=parent, data=data))

    async def replace(self, kind: str, id_: str, data: dict) -> None:
        async with self.engine.begin() as conn:
            result = await conn.execute(
                update(records).where(records.c.id == id_, records.c.kind == kind).values(data=data)
            )
            if not result.rowcount:
                raise AppError(404, "not_found", f"Unknown {kind}")

    async def get(self, kind: str, id_: str) -> dict:
        async with self.engine.connect() as conn:
            result = await conn.scalar(
                select(records.c.data).where(records.c.id == id_, records.c.kind == kind)
            )
        if result is None:
            raise AppError(404, "not_found", f"Unknown {kind}")
        return result

    async def list(self, kind: str, parent: str | None = None) -> list[dict]:
        query = select(records.c.data).where(records.c.kind == kind).order_by(records.c.id)
        if parent is not None:
            query = query.where(records.c.parent == parent)
        async with self.engine.connect() as conn:
            return list((await conn.scalars(query)).all())

    async def create_claim(self, claim: dict, documents: list[dict]) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(
                insert(records).values(
                    id=claim["id"], kind="claim", parent=claim["session_id"], data=claim
                )
            )
            if documents:
                await conn.execute(
                    insert(records),
                    [
                        {"id": d["id"], "kind": "document", "parent": claim["id"], "data": d}
                        for d in documents
                    ],
                )

    async def create_run(self, data: dict) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(
                insert(runs).values(
                    id=data["id"],
                    claim_id=data["claim_id"],
                    session_id=data["session_id"],
                    version=data["version"],
                    status=data["status"],
                    data=data,
                )
            )

    async def update_run(self, data: dict) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(
                update(runs).where(runs.c.id == data["id"]).values(status=data["status"], data=data)
            )

    async def get_run(self, id_: str) -> dict:
        async with self.engine.connect() as conn:
            result = await conn.scalar(select(runs.c.data).where(runs.c.id == id_))
        if result is None:
            raise AppError(404, "assessment_not_found", "Unknown assessment")
        return result

    async def list_runs(self, claim_id: str) -> list[dict]:
        async with self.engine.connect() as conn:
            return list(
                (
                    await conn.scalars(
                        select(runs.c.data)
                        .where(runs.c.claim_id == claim_id)
                        .order_by(runs.c.version)
                    )
                ).all()
            )
