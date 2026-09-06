# Backend

FastAPI backend for the AI education intelligence platform.

## Included

- FastAPI app factory.
- Environment settings via `pydantic-settings`.
- Structured baseline logging.
- Request ID middleware.
- `/health` endpoint.
- `/api/v1/sources` source management endpoint.
- `/api/v1/materials` content library endpoint.
- `/api/v1/collect-tasks` collection task endpoint.
- `/api/v1/materials` material processing endpoint.
- `/api/v1/search` content search endpoint.
- `/api/v1/influencers` influencer profile and distillation endpoint.
- `/api/v1/changzhou-news` Changzhou local education intelligence collection.
- `/api/v1/social-videos` hot video collection, thresholds, transcript and manuscript endpoints.
- `/api/v1/social-creators` creator pool endpoint.
- `/api/v1/wechat` WeChat article search, transform and export endpoints.
- Default source seed: `龙城家长圈`.
- SQLAlchemy async repositories and Alembic migrations through `0014_add_social_video_transcripts`.
- Optional TikHub integration for Douyin video discovery.
- Optional local Whisper or Doubao/Volcengine ASR integration for video speech-to-text.
- Pytest + httpx async API test.
- Dockerfile.

## Run

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Local default uses `sqlite+aiosqlite:///./local.db` for quick development.

PostgreSQL:

```bash
docker compose up -d postgres
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Health:

```bash
curl http://localhost:8000/health
```

Sources:

```bash
curl http://localhost:8000/api/v1/sources
```

Materials:

```bash
curl http://localhost:8000/api/v1/materials
```

Collect tasks:

```bash
curl http://localhost:8000/api/v1/collect-tasks
```

Execute a task:

```bash
curl -X POST http://localhost:8000/api/v1/collect-tasks/1/execute
```

Create source:

```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{"name":"常州教育发布","type":"公众号","url":"https://mp.weixin.qq.com/","note":"公开信息来源"}'
```

Hot video thresholds:

```bash
curl http://localhost:8000/api/v1/social-videos/hot-thresholds
```

Generate transcript for a collected video:

```bash
curl -X POST http://localhost:8000/api/v1/social-videos/1/transcript
```

Enable TikHub + video transcription in `.env`:

```bash
VIDEO_DATA_PROVIDER=tikhub
TIKHUB_API_KEY=your_tikhub_key
TRANSCRIPTION_PROVIDER=local-whisper
WHISPER_MODEL_SIZE=small
HF_ENDPOINT=https://hf-mirror.com
HF_HUB_DISABLE_XET=true
```

The first local Whisper run downloads model weights; later runs reuse the local cache. OpenAI is not required for video transcription.

To avoid local model downloads, use Doubao/Volcengine cloud ASR instead:

```bash
VIDEO_DATA_PROVIDER=tikhub
TIKHUB_API_KEY=your_tikhub_key
TRANSCRIPTION_PROVIDER=doubao
DOUBAO_ASR_API_KEY=your_doubao_asr_key
```

TikHub still handles discovery and play URLs. Doubao ASR only runs when a user clicks transcript extraction for one video.
If `ffmpeg` is available, the backend first converts the downloaded video to a
temporary 16 kHz mono wav file before sending it to ASR. Temporary audio files
are deleted immediately after use.

## Test

```bash
cd backend
python -m ruff check .
python -m pytest
```

## Current Boundary

- Core data is persisted through SQLAlchemy.
- Tests use temporary SQLite databases; production config uses PostgreSQL via `asyncpg`.
- Douyin hot video discovery depends on TikHub or another compliant data provider.
- WeChat Channels real interaction data still needs authorized API or a compliant data service.
- Local Whisper currently rejects files larger than 120 MB; cloud ASR requires service credentials and balance.
- Transcript post-processing removes common Chinese filler words and rejects likely background lyrics or non-Gaokao speech before saving a manuscript.
- Production deployment should move recurring collectors into a durable worker/queue process.

## Next

- Add durable workers and retryable task records for long-running media transcription.
- Add PostgreSQL + pgvector deployment profile for production RAG.
- Add authorized WeChat Channels data ingestion.
