# Frontend Task Backend v1

## Scope

The web admin task queue now talks to FastAPI.

## Behavior

- Page load reads `/api/v1/collect-tasks`.
- Creating a task from a source writes to the backend.
- Task status changes patch the backend.
- `执行采集` calls the backend executor and adds the result to the content library.
- The page falls back to local task data if the backend is unavailable.
