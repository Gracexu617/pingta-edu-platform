# Collector Executor v1

## Scope

Adds manual execution for collection tasks.

## Supported

- Public HTML pages.
- RSS/Atom XML feeds.
- Extracted text is written to `/api/v1/materials`.
- Task status becomes `处理中`, then `已完成`.

## Not Supported

- Login-only pages.
- CAPTCHA or anti-bot bypass.
- Video/audio transcription.
- Background scheduling.
