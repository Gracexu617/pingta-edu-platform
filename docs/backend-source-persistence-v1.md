# Backend Source Persistence v1

## Scope

This milestone replaces in-memory source storage with SQL persistence.

## Added

- SQLAlchemy async engine and session factory.
- `sources` ORM model.
- SQLAlchemy source repository.
- Alembic migration `0001_create_sources`.
- PostgreSQL compose service using `pgvector/pgvector:pg17`.
- Default seed source: `龙城家长圈`.

## Runtime

Local quick run defaults to SQLite:

```bash
cd backend
uvicorn app.main:app --reload
```

PostgreSQL run:

```bash
cd backend
docker compose up -d postgres
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

## Notes

- `DATABASE_AUTO_CREATE=false` is recommended for PostgreSQL production use.
- Schema changes should go through Alembic migrations.
- Data backfills should be separate from schema migrations.
