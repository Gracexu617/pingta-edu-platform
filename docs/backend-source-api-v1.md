# Backend Source API v1

## Scope

This milestone adds the first backend business API: monitored source management.

## Endpoints

- `GET /api/v1/sources`: list sources.
- `POST /api/v1/sources`: create source.
- `PATCH /api/v1/sources/{source_id}`: update source metadata or status.

## Default Sources

- `龙城家长圈`: 微信公众号, enabled.
- `常州教育资讯`: demo local education news source, enabled.

## Error Rules

- Duplicate source name: `409`.
- Missing source: `404`.
- Invalid payload: `422`.

## Implementation Boundary

- Uses a SQLAlchemy async repository behind a repository interface.
- Keeps service and API layers independent from storage.
- Production config uses PostgreSQL via `postgresql+asyncpg`.
- Tests use temporary SQLite databases with the same repository contract.
- Alembic migration `0001_create_sources` owns the `sources` schema.
