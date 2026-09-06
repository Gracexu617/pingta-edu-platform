# 教育内容中台

这是根据任务书搭建的 AI 助理平台基础版，当前目标是跑通：

来源管理 -> 采集任务 -> 链接导入/手动录入 -> 资料整理 -> 草稿生成 -> 审核导出 -> 工作区备份

## 当前能力

- 来源管理：登记公众号、视频号、高校官网、教育资讯网站。
- 采集任务：从来源创建任务，跟踪待采集、处理中、已完成。
- 链接导入：读取普通可访问网页的标题和正文。
- 资料库：新增、编辑、删除、搜索、标记状态。
- AI 整理：无模型时用本地规则，有模型时调用 `/api/organize`。
- 草稿生成：无模型时用本地模板，有模型时调用 `/api/generate`。
- 审核中心：编辑、标记、导出、删除草稿。
- 工作区备份：导出/导入 JSON。
- 来源管理已接 FastAPI 后端，默认来源包含 `龙城家长圈`。
- 内容库、采集任务、大 V、常州资讯、热门视频等核心数据已接 FastAPI 后端，并保留本地适配器兜底。
- 常州本地教育资讯：按公开官网、本地媒体和公众号检索词采集，自动分类和重要性标注。
- 热门视频推送：通过 TikHub 采集抖音公开视频，按可配置点赞/收藏门槛筛选，支持 10 分钟自动刷新。
- 推送门槛设置：可在网页热门视频板块随时调整 4 组门槛，保存后立即重算已采集视频。
- 视频转文字：支持本地 Whisper 或豆包/火山云端 ASR，点击单条视频后提取真实音频文稿，清理语气词并生成可读文稿。
- 公众号转化：支持公众号文章检索、转换、导出 HTML/DOCX。

## 本地运行

```bash
pnpm install
pnpm run dev
```

开发地址：

```text
http://localhost:3000/
```

后端 API：

```text
http://127.0.0.1:8000
```

构建验证：

```bash
pnpm run build
```

## 让别人直接使用

公网使用需要同时部署前端、后端和云数据库，并设置访问密码保护付费接口。
具体清单见 `docs/public-deployment.md`。

## 启用真实 AI

复制 `.env.example` 为 `.env.local`，填写：

```bash
AI_PROVIDER=doubao
DOUBAO_API_KEY=你的火山方舟 API Key
DOUBAO_MODEL=你的豆包模型或推理接入点 ID
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000
```

本项目不依赖 OpenAI。除豆包外，还可将 `AI_PROVIDER` 设为 `deepseek` / `qwen` / `zhipu` / `kimi`（逗号分隔可多厂商兜底），并填写对应 `*_API_KEY`（如 `DEEPSEEK_API_KEY`）。`AI_PROVIDER` 留空时默认 `doubao`。

未配置时平台仍可使用，会自动走本地规则和本地模板。

## 启用抖音采集和视频转文字

后端复制 `backend/.env.example` 为 `backend/.env`，至少填写：

```bash
VIDEO_DATA_PROVIDER=tikhub
TIKHUB_API_KEY=你的 TikHub API Key
TRANSCRIPTION_PROVIDER=local-whisper
WHISPER_MODEL_SIZE=small
HF_ENDPOINT=https://hf-mirror.com
HF_HUB_DISABLE_XET=true
```

本地 Whisper 首次转写会下载模型权重，之后复用缓存。视频转文字不依赖 OpenAI 额度。

如需减少本机模型空间占用，可改用豆包/火山云端 ASR：

```bash
TRANSCRIPTION_PROVIDER=doubao
DOUBAO_ASR_API_KEY=你的豆包/火山语音识别 API Key
```

TikHub 仍负责采集视频和获取播放地址；豆包只在点击「提取转写」时负责音频转文字。
为提升成功率，后端会在本机存在 `ffmpeg` 时把视频临时转为 16k 单声道 wav，
再发给豆包。临时音频用完即删，不会长期占用磁盘。

## 关键文件

- `app/page.tsx`：工作台页面。
- `app/lib/platform-api.ts`：前端 API 契约、后端来源客户端和本地适配器。
- `app/lib/workspace.ts`：工作区类型、种子数据、备份构建和备份解析。
- `app/api/import-url/route.ts`：普通网页链接导入。
- `app/api/organize/route.ts`：资料整理接口。
- `app/api/generate/route.ts`：草稿生成接口。
- `app/api/settings/route.ts`：基础配置状态接口。
- `docs/MVP.md`：MVP 范围和后续计划。
- `docs/architecture/production-architecture-v1.md`：生产级架构设计 v1。
- `backend/`：生产后端骨架，当前含 FastAPI、配置、日志、健康检查和测试。
- `prompts/`：AI 助理指令。
- `workflows/`：工作流说明。

## 当前边界

- 当前默认本地数据库为 SQLite；生产部署建议切 PostgreSQL。
- 链接导入不绕过登录、验证码、反爬或平台限制。
- 自动发布公众号/视频号尚未接入。
- 抖音采集依赖 TikHub 合规数据服务；微信视频号真实互动数据仍需后续授权或数据服务接入。
- 本地 Whisper 转写对首次模型下载、CPU 性能和视频音频质量敏感；云端 ASR 需要配置对应服务密钥和余额。
- 视频转文字会清理常见口头语，并拦截疑似背景歌词/非高考升学讲解内容，避免误入正式文稿。
