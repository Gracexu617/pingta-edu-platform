# 私密公网版部署说明

目标：让别人打开一个网址就能使用平台，同时保护 TikHub、豆包等付费额度。

## 推荐组合

- 前端：Vercel 或 Cloudflare Pages
- 后端：Render / Railway / Fly.io / 云服务器
- 数据库：Supabase Postgres / Render Postgres
- 访问控制：第一版使用 `APP_ACCESS_PASSWORD` 共享访问密码

## 后端环境变量

在后端部署平台填写：

```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
APP_ACCESS_PASSWORD=设置一个只发给内部使用者的密码
CORS_ORIGINS='["https://你的前端域名"]'
DATABASE_URL=postgresql+asyncpg://用户名:密码@主机:端口/数据库
DATABASE_AUTO_CREATE=true

VIDEO_DATA_PROVIDER=tikhub
TIKHUB_API_KEY=你的 TikHub API Key
TIKHUB_BASE_URL=https://api.tikhub.io
SOCIAL_VIDEO_AUTO_COLLECT_ENABLED=true
SOCIAL_VIDEO_AUTO_COLLECT_INTERVAL_SECONDS=600

TRANSCRIPTION_PROVIDER=doubao
DOUBAO_ASR_API_KEY=你的豆包语音识别 Key

MANUSCRIPT_PROVIDER=rule
LLM_PROVIDER=doubao
DOUBAO_API_KEY=你的火山方舟 Key
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=你的模型或推理接入点 ID
```

## 前端环境变量

在前端部署平台填写：

```bash
NEXT_PUBLIC_BACKEND_URL=https://你的后端域名
AI_PROVIDER=doubao
DOUBAO_API_KEY=你的火山方舟 Key
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=你的模型或推理接入点 ID
```

## 访问方式

1. 用户打开前端网址。
2. 如果后端设置了 `APP_ACCESS_PASSWORD`，页面会要求输入访问密码。
3. 密码正确后，浏览器会记住密码，后续采集、转写、导出都会自动带上密码。

## 部署检查

后端上线后先访问：

```text
https://你的后端域名/health
```

返回 `status: ok` 后，再检查前端：

- 常州情报能加载
- 热门视频能加载
- 点“立即采集”能返回结果
- 点“提取转写”能生成真实文稿
- 公众号导出能下载文件

## 注意

- 不要把 `.env`、`backend/.env`、API Key 或数据库密码提交到代码仓库。
- 正式给客户使用前，建议升级为用户账号系统和使用量统计。
- 如果视频采集或转写失败，优先检查 TikHub/豆包余额和后端日志。
