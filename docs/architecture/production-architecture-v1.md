# 生产级 AI 教育情报平台架构 v1

## 目标

建设 7x24 自动运行平台：

- 自动监控公众号、视频号、网站、RSS 等来源。
- 自动抓取、解析、OCR、转写、摘要、标签、Embedding、入库。
- 持续蒸馏教育行业大 V。
- 持续收集常州本地教育资讯。
- 建立高校知识库。
- 支持语义搜索、RAG、问答、趋势分析、主题聚类、报告。
- 支持模块化扩展数据源、AI 模型、工作流。

## 技术选型

### 已确认建议

- Backend: Python + FastAPI
- Worker: Celery
- Queue: Redis
- Database: PostgreSQL + pgvector
- Object Storage: MinIO 起步，后续可换 S3/OSS
- Frontend: 当前 Next/Vinext MVP 可继续演进；生产后台可重构为标准 Next.js
- AI Gateway: OpenAI 默认，预留 Claude、Gemini、DeepSeek、OpenRouter
- Deploy: Docker Compose 起步，后续 Kubernetes 可选

### 核心原则

- Clean Architecture。
- Connector 插件化。
- Workflow 配置化。
- AI Provider 适配器化。
- 数据处理幂等。
- 任务可重试、可观测、可恢复。
- 所有 AI 输出保留来源、模型、prompt、版本。

## 总体架构

```text
Frontend Admin
  |
FastAPI API
  |
Use Cases / Domain Services
  |
Repositories / Connectors / AI Gateway
  |
PostgreSQL + pgvector / Redis / MinIO
  |
Celery Workers + Scheduler
```

## 服务划分

```text
api              FastAPI HTTP API
worker-crawl     来源监控、抓取
worker-parse     正文、图片、PDF、HTML 解析
worker-media     OCR、语音转文字
worker-ai        摘要、标签、实体、Embedding
worker-report    周报、月报、专题报告
scheduler        定时任务
frontend         管理后台
postgres         主数据库 + pgvector
redis            队列和缓存
minio            原始文件、图片、音频、视频、PDF
```

## 后端目录结构

```text
backend/
  app/
    main.py
    api/
      routes/
      deps.py
    core/
      config.py
      logging.py
      security.py
    domain/
      entities.py
      value_objects.py
      events.py
    use_cases/
      collect_source.py
      process_document.py
      run_rag_query.py
      distill_influencer.py
      update_university.py
    infrastructure/
      db/
        models.py
        repositories.py
        migrations/
      object_storage/
      queue/
      connectors/
      ai/
    workers/
      celery_app.py
      crawl_tasks.py
      parse_tasks.py
      ai_tasks.py
      report_tasks.py
    schemas/
    tests/
```

## 前端目录结构

```text
frontend/
  app/
  components/
  features/
    dashboard/
    sources/
    tasks/
    documents/
    search/
    influencers/
    local-edu/
    universities/
    reports/
    settings/
  lib/
```

## 数据库设计

### sources

来源配置。

```text
id uuid pk
name text
type enum: wechat_official, video_channel, website, rss, university, manual
url text
auth_type text nullable
config jsonb
poll_interval_minutes int
status enum: active, paused, error
last_checked_at timestamptz
created_at timestamptz
updated_at timestamptz
```

### crawl_jobs

采集任务。

```text
id uuid pk
source_id uuid fk
status enum: pending, running, success, failed, cancelled
job_type enum: scheduled, manual, retry
started_at timestamptz
finished_at timestamptz
error text
metadata jsonb
created_at timestamptz
```

### raw_items

原始发现项，用于去重和增量。

```text
id uuid pk
source_id uuid fk
external_id text nullable
url text
title text
published_at timestamptz nullable
content_hash text
media_hash text nullable
raw_payload jsonb
first_seen_at timestamptz
last_seen_at timestamptz
status enum: new, processed, duplicate, failed
```

### documents

标准化内容。

```text
id uuid pk
raw_item_id uuid fk
source_id uuid fk
title text
content text
content_type enum: article, video, image, pdf, post
language text
summary text
importance int
status enum: draft, processed, reviewed, archived
metadata jsonb
created_at timestamptz
updated_at timestamptz
```

### document_versions

版本管理。

```text
id uuid pk
document_id uuid fk
version int
content text
summary text
change_reason text
created_by text
created_at timestamptz
```

### media_assets

媒体文件。

```text
id uuid pk
document_id uuid fk
type enum: image, audio, video, pdf
storage_url text
original_url text nullable
ocr_text text nullable
transcript text nullable
metadata jsonb
created_at timestamptz
```

### chunks

RAG 切块。

```text
id uuid pk
document_id uuid fk
chunk_index int
text text
token_count int
metadata jsonb
created_at timestamptz
```

### embeddings

向量。

```text
id uuid pk
chunk_id uuid fk
model text
embedding vector(1536)
created_at timestamptz
```

### tags / document_tags

标签体系。

```text
tags:
id uuid pk
name text unique
category text nullable

document_tags:
document_id uuid fk
tag_id uuid fk
confidence numeric
```

### entities

实体：学校、地区、政策、人物、专业。

```text
id uuid pk
name text
type enum: school, university, policy, person, major, region, event
aliases text[]
metadata jsonb
```

### document_entities

```text
document_id uuid fk
entity_id uuid fk
confidence numeric
context text
```

### influencers

大 V。

```text
id uuid pk
name text
platform text
source_id uuid fk nullable
description text
status text
created_at timestamptz
```

### influencer_profiles

大 V 数字画像。

```text
id uuid pk
influencer_id uuid fk
profile_version int
education_philosophy text
core_opinions jsonb
analysis_frameworks jsonb
writing_style jsonb
expression_habits jsonb
mentioned_schools jsonb
parent_questions jsonb
trend_summary text
valid_from timestamptz
created_at timestamptz
```

### universities

高校主表。

```text
id uuid pk
name text
province text
city text
level text
type text
website text
metadata jsonb
updated_at timestamptz
```

### university_metrics

高校时序数据。

```text
id uuid pk
university_id uuid fk
metric_type text
year int
province text nullable
major text nullable
value jsonb
source_document_id uuid fk nullable
created_at timestamptz
```

### alerts

重要更新。

```text
id uuid pk
document_id uuid fk
alert_type text
severity enum: low, medium, high, critical
title text
message text
status enum: new, acknowledged, resolved
created_at timestamptz
```

### ai_runs

AI 调用审计。

```text
id uuid pk
workflow_name text
provider text
model text
prompt_hash text
input jsonb
output jsonb
token_usage jsonb
latency_ms int
status enum: success, failed
error text nullable
created_at timestamptz
```

### workflow_runs

工作流执行记录。

```text
id uuid pk
workflow_name text
status enum: pending, running, success, failed
input jsonb
output jsonb
error text nullable
started_at timestamptz
finished_at timestamptz
```

## API 设计

### Sources

```text
GET    /api/sources
POST   /api/sources
GET    /api/sources/{id}
PATCH  /api/sources/{id}
DELETE /api/sources/{id}
POST   /api/sources/{id}/test
POST   /api/sources/{id}/collect
```

### Jobs

```text
GET    /api/jobs
GET    /api/jobs/{id}
POST   /api/jobs/{id}/retry
POST   /api/jobs/{id}/cancel
```

### Documents

```text
GET    /api/documents
POST   /api/documents/import-url
GET    /api/documents/{id}
PATCH  /api/documents/{id}
POST   /api/documents/{id}/reprocess
GET    /api/documents/{id}/versions
GET    /api/documents/{id}/media
```

### Search / RAG

```text
POST /api/search/fulltext
POST /api/search/semantic
POST /api/rag/query
POST /api/rag/suggest-sources
```

### Influencers

```text
GET   /api/influencers
POST  /api/influencers
GET   /api/influencers/{id}/profile
POST  /api/influencers/{id}/distill
GET   /api/influencers/{id}/reports
```

### Local Education

```text
GET  /api/local-edu/feed
GET  /api/local-edu/alerts
POST /api/local-edu/alerts/{id}/ack
GET  /api/local-edu/trends
```

### Universities

```text
GET  /api/universities
GET  /api/universities/{id}
GET  /api/universities/{id}/metrics
POST /api/universities/{id}/refresh
```

### Reports

```text
GET  /api/reports
POST /api/reports/generate
GET  /api/reports/{id}
```

### System

```text
GET /api/system/health
GET /api/system/metrics
GET /api/system/settings
```

## 采集方案

### RSS

- 轮询 feed。
- 使用 item guid/link 去重。
- 抓正文页面。
- 进入标准处理管线。

### 普通网站

- 配置 URL、列表页选择器、详情页选择器。
- 使用 `httpx` 抓取。
- 使用 `trafilatura` / `readability-lxml` 提取正文。
- 失败进入人工处理队列。

### 微信公众号

合规路径优先：

- 用户提供文章链接。
- 自有公众号开放接口。
- 公开可访问页面。
- 第三方合法数据源。

不做：

- 绕登录。
- 绕验证码。
- 破解签名。
- 强爬受限接口。

### 视频号

第一阶段：

- 手动上传视频。
- 粘贴文案。
- 粘贴公开可访问链接。
- 语音转文字。

第二阶段：

- 若有官方/授权接口，再接自动监控。

## 数据处理管线

```text
detect_new_item
deduplicate
fetch_raw_content
extract_text
extract_media
ocr_images
transcribe_video
normalize_document
chunk_text
summarize
extract_keywords
classify_tags
extract_entities
generate_embedding
persist_document
update_profiles
create_alerts
```

## 任务状态机

### Crawl Job

```text
pending
running
success
failed
cancelled
```

失败策略：

- 网络错误：指数退避重试。
- 解析错误：进入人工处理。
- 权限错误：来源标记 error。
- 重复内容：标记 duplicate。

### Document Processing

```text
raw
extracted
enriched
embedded
reviewed
archived
failed
```

## AI 工作流

### 内容整理

输入：正文、标题、来源、媒体文本。  
输出：摘要、标签、关键词、实体、重要度。

### 大 V 蒸馏

输入：大 V 最近 N 篇内容。  
输出：

- 教育理念
- 核心观点
- 分析框架
- 写作风格
- 表达习惯
- 常提学校
- 家长问题
- 观点变化

### 常州教育预警

输入：本地教育内容流。  
输出：分类、重要度、预警、影响分析。

### 高校更新

输入：高校官网、招生政策、公开数据。  
输出：高校资料更新、指标版本。

### RAG 问答

输入：自然语言问题。  
流程：query rewrite、hybrid search、rerank、answer with citations。  
输出：答案、引用、可信度、待核实项。

## Docker Compose 草案

```yaml
services:
  api:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    env_file: .env
    depends_on: [postgres, redis, minio]

  worker:
    build: ./backend
    command: celery -A app.workers.celery_app worker -l info
    env_file: .env
    depends_on: [postgres, redis, minio]

  scheduler:
    build: ./backend
    command: celery -A app.workers.celery_app beat -l info
    env_file: .env
    depends_on: [redis]

  frontend:
    build: ./frontend
    env_file: .env
    ports: ["3000:3000"]

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: edu_intel
      POSTGRES_USER: edu
      POSTGRES_PASSWORD: edu
    volumes: ["postgres_data:/var/lib/postgresql/data"]

  redis:
    image: redis:7

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: miniosecret
    volumes: ["minio_data:/data"]

volumes:
  postgres_data:
  minio_data:
```

## 环境变量

```text
DATABASE_URL=
REDIS_URL=
OBJECT_STORAGE_ENDPOINT=
OBJECT_STORAGE_ACCESS_KEY=
OBJECT_STORAGE_SECRET_KEY=
# 大模型（不依赖 OpenAI；兼容 OpenAI /chat/completions 协议）
LLM_PROVIDER=doubao
DOUBAO_API_KEY=
DEEPSEEK_API_KEY=
QWEN_API_KEY=
ZHIPU_API_KEY=
KIMI_API_KEY=
EMBEDDING_MODEL=
OCR_PROVIDER=
TRANSCRIPTION_PROVIDER=
LOG_LEVEL=
```

## 测试策略

- Domain unit tests。
- Repository integration tests。
- Connector contract tests。
- Worker task tests。
- API tests。
- RAG golden tests。
- AI output schema tests。
- E2E smoke tests。

## 监控

- Structured JSON logs。
- Request ID。
- Job ID。
- AI run ID。
- Prometheus metrics。
- Grafana dashboard。
- Sentry error capture。
- Dead letter queue。

## 分阶段实现

### Phase 1: Backend skeleton

- FastAPI app。
- Config。
- Logging。
- PostgreSQL。
- Alembic。
- Health check。
- Test harness。

### Phase 2: Data model

- SQLAlchemy models。
- Repository。
- Migrations。
- Seed data。

### Phase 3: Source + job system

- sources API。
- crawl_jobs API。
- Celery + Redis。
- Scheduler。

### Phase 4: Connectors

- RSS connector。
- Website connector。
- Manual URL import。

### Phase 5: Processing pipeline

- HTML extraction。
- Media extraction。
- OCR adapter。
- Transcription adapter。
- Chunking。

### Phase 6: AI enrichment

- AI gateway。
- Summary。
- Tags。
- Entities。
- Embeddings。

### Phase 7: Search + RAG

- pgvector search。
- Hybrid search。
- RAG answer with citations。

### Phase 8: Intelligence modules

- Influencer distillation。
- Changzhou local education alerts。
- University KB。

### Phase 9: Production ops

- Docker Compose。
- CI。
- Monitoring。
- Backups。
- Deployment docs。

## 待确认决策

1. 前端是否保留当前 Vinext，还是生产版迁移标准 Next.js。
2. OCR 首选：PaddleOCR、本地模型、云服务。
3. 转写首选：OpenAI Whisper API、本地 Whisper、其他云服务。
4. 向量库：仅 pgvector，还是 pgvector + Qdrant。
5. 知识图谱：Phase 1 不做，后续 Neo4j 可选。
