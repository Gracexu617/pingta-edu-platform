# Backend Material API v1

## Scope

Adds persisted content library storage.

## Endpoints

- `GET /api/v1/materials`
- `POST /api/v1/materials`
- `PATCH /api/v1/materials/{material_id}`

## Boundary

- Stores text, summary, tags, source metadata and status.
- Does not yet generate embeddings.
- Does not yet run OCR or speech-to-text.
