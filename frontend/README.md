# AykAI 前端

React 18 + TypeScript + Vite 前端，对接 Go 后端（`:9030`）与 Python AI 服务（`:8000`）。

## 目录结构

```
frontend/
├── src/
│   ├── api/          # 统一封装：status_code 解包、JWT 注入、SSE 流式
│   ├── components/   # SessionList / MessageList / ChatInput
│   ├── context/      # AuthContext（JWT + username 持久化到 localStorage）
│   ├── pages/        # LoginPage / RegisterPage / ChatPage
│   └── styles/       # 全局 CSS（深色主题）
├── index.html
├── package.json
└── vite.config.ts    # /api → http://127.0.0.1:9030 的开发代理
```

## 启动流程

### 1. 先起后端

**前端依赖 Go 后端 + Python AI 服务**，先按仓库根目录的 [`Readme.md`](../Readme.md) 把 docker stack 拉起来：

```bash
# 在仓库根目录
cp .env.example .env                                   # 首次需要
docker compose up -d --build python-api go-backend
docker compose ps                                      # 确认都是 Up / healthy
```

应看到以下容器全部运行中：

- `aykai-backend`（Go，`:9030`）
- `aykai-api`（Python AI，`:8000`）
- `aykai-postgres`、`aykai-redis`、`aykai-elasticsearch`、`milvus-standalone`

快速验证：

```bash
curl -i http://127.0.0.1:8000/api/health             # Python：期望 200
curl -i http://127.0.0.1:9030/api/v1/user/login \
     -H 'Content-Type: application/json' \
     -d '{"username":"test","password":"test"}'      # Go：返回业务响应即可
```

### 2. 安装前端依赖

```bash
cd frontend
npm install
```

只需首次或 `package.json` 变动后执行。

### 3. 启动前端（开发模式）

```bash
npm run dev
```

启动成功后 Vite 会打印：

```
  VITE v5.4.x  ready
  ➜  Local:   http://localhost:5173/
```

Vite dev server 默认监听 `http://localhost:5173`，并把 `/api/**` 请求代理到 `http://127.0.0.1:9030`（见 `vite.config.ts`），所以浏览器不会遇到跨域。

> 若 5173 端口被占用，可改端口：`npm run dev -- --port 5180`。
> 若后端端口不是 9030，同步改 `vite.config.ts` 里的 `target`。

### 4. 在浏览器里用起来

打开 `http://localhost:5173/`，页面会自动跳转到 `/login`：

1. **注册**（可选）`/register`
   - 输入邮箱 → 点「发送验证码」（60s 冷却）
   - 收到验证码后填入，并设置密码，提交
   - 注册成功后系统会用邮件把 **11 位数字用户名** 发给你（Go 后端自动生成）
2. **登录** `/login`
   - 用户名用上一步邮件里的 11 位数字
   - 密码为注册时设置的密码
   - 登录成功后 JWT 存到 localStorage（键 `aykai_token` / `aykai_username`），页面跳转到 `/chat`
3. **聊天** `/chat`
   - 左栏：`+ 新对话` 开新会话；下方列出已有会话，点击切换
   - 右侧：输入问题按 Enter 发送（Shift+Enter 换行），答案逐字流式渲染
   - `上传 Markdown`：把 `.md` 文件投喂给当前会话的知识库，成功会在右下角弹 toast
   - 右上角 `登出` 清 token，回到登录页
   - Token 失效（后端返回 `status_code` 为 2006 / 2007）会自动登出并回到 `/login`

### 5. 生产构建

```bash
cd frontend
npm run build     # tsc -b && vite build，产物在 dist/
npm run preview   # 本机预览构建产物（:4173）
```

生产部署时可以把 `dist/` 交给 Nginx，或在 Go 后端里用 `StaticFS` 挂载 `dist/`（本仓库暂未集成，视部署方式自选）。

## 常见问题

- **`npm run dev` 起来后页面空白 / 404**：确认浏览器打开的是 `http://localhost:5173`（不是 `file://` 或 backend 的 9030）。
- **登录一直转圈 / 报 `Failed to fetch`**：检查 `docker compose ps`，确认 `aykai-backend` 是 Up；再试 `curl http://127.0.0.1:9030/api/v1/user/login`。
- **发送问题后助手气泡一直空 / 出现 JSON 原文**：说明 SSE 未解包，优先看浏览器 Network 里 `send-stream-new-session` 的 `Content-Type`；正常应是 `text/event-stream`。
- **注册收不到验证码**：确认 `.env` 里 `SMTP_EMAIL` / `SMTP_AUTHCODE` 已正确配置，并重启 Go 后端容器。
- **想用已有账号跳过注册**：直接往 `chathistory.users` 表里 `INSERT` 一行（密码列存 MD5 哈希）即可。

## 接口映射速查

| 功能 | 方法 | 路径 | 是否需 JWT |
|---|---|---|---|
| 发送注册验证码 | `POST` | `/api/v1/user/captcha` | 否 |
| 注册 | `POST` | `/api/v1/user/register` | 否 |
| 登录 | `POST` | `/api/v1/user/login` | 否 |
| 会话列表 | `GET` | `/api/v1/AI/chat/sessions` | 是 |
| 会话历史 | `POST` | `/api/v1/AI/chat/history` | 是 |
| 新会话流式问答 | `POST` | `/api/v1/AI/chat/send-stream-new-session` | 是 |
| 已有会话流式问答 | `POST` | `/api/v1/AI/chat/send-stream` | 是 |
| 上传 Markdown 入库 | `POST` | `/api/v1/AI/chat/upload-md` | 是 |

统一返回包裹：`{ status_code, status_msg, ...data }`，`status_code === 1000` 视为成功，`2006 / 2007` 视为认证失败并自动登出。
