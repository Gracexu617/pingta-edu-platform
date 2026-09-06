# GitHub 上传说明

请上传这个文件夹里的全部内容：

```text
/Users/xulehan/Desktop/ai助理/platform-clean-upload
```

不要只上传 `backend`，也不要把 `backend/app` 拆到仓库根目录。

## 正确的 GitHub 仓库结构

仓库首页应该能看到：

```text
backend/
app/
public/
docs/
package.json
pnpm-lock.yaml
README.md
```

其中：

- `backend/` 是后端。
- 根目录的 `app/` 是前端。

## Render 后端填写

```text
Language: Docker
Root Directory: backend
```

## Vercel 前端填写

```text
Root Directory: 留空
Framework Preset: Other / Next.js 均可
Build Command: pnpm run build
```

## 不要上传

这些文件已经从干净目录里排除了：

```text
.env
.env.local
backend/.env
local.db
node_modules
dist
build
__pycache__
*.egg-info
```
