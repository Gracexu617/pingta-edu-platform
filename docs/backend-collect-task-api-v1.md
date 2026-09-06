# Backend Collect Task API v1

## Scope

Adds persisted collection task storage.

## Endpoints

- `GET /api/v1/collect-tasks`
- `POST /api/v1/collect-tasks`
- `PATCH /api/v1/collect-tasks/{task_id}`
- `POST /api/v1/collect-tasks/{task_id}/execute`

## Boundary

- Tasks are created from registered sources.
- Status can move through `待采集`, `处理中`, `已完成`.
- Execution v1 supports public HTML and RSS/Atom URLs, then writes extracted text to materials.
- No scheduler or background worker yet.
