# Frontend Source Backend v1

## Scope

The web admin source screen now talks to the FastAPI source backend.

## Behavior

- On page load, local workspace data renders first.
- The frontend then loads `/api/v1/sources` from `NEXT_PUBLIC_BACKEND_URL`.
- Adding a source writes to the backend first.
- Pausing/enabling a source patches backend status first.
- If the backend is unavailable, the page falls back to local data so the admin UI still runs.

## Links

- Web: `http://localhost:3000/`
- Backend: `http://127.0.0.1:8000`
- Sources: `http://127.0.0.1:8000/api/v1/sources`
