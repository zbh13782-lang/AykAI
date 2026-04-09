# AykAI

Rag项目

搭建一个模版，以后拿来复用

## 技术栈

LangGraph（主要依靠），langChain

SSE流失输出

多路召回：向量检索 + 关键词检索 ，后面准备尝试Graphrag,todo

父子索引：父块存pg，子块存milvus

多种文本类型：md，pdf

目前的不足（想法）：引入function calling，mcp等

## 启动流程

### 1. 前置要求

- 已安装 Docker Desktop（包含 Docker Compose）并打开
- 在项目根目录准备好环境变量文件

### 2. 配置环境变量

在项目根目录执行：

```bash
cp .env.example .env
```

至少确认这些字段已填写：

- OPENAI_API_KEY
- OPENAI_BASE_URL
- OPENAI_CHAT_MODEL
- OPENAI_EMBEDDING_MODEL
- SMTP_EMAIL
- SMTP_AUTHCODE

说明：

- Go 后端会读取 SMTP 相关配置用于验证码。
- Go 后端会调用 Python 服务，二者通过 INTERNAL_SERVICE_KEY 对齐鉴权。

### 3. 启动 AI 服务和 Go 后端

在项目根目录执行：

```bash
docker compose up -d --build python-api go-backend
```

### 4. 检查启动状态

```bash
docker compose ps
```

至少应看到：

- aykai-api（python-api）为 Up
- aykai-backend（go-backend）为 Up

推荐同时确认依赖服务正常：

- aykai-postgres 为 healthy
- aykai-redis 为 healthy
- aykai-elasticsearch 为 healthy
- milvus-standalone 为 Up

### 5. 接口地址

- Go 后端地址：http://127.0.0.1:9030
- Python AI 地址：http://127.0.0.1:8000

### 6. 快速验证

1) 验证 Python 健康检查

```bash
curl -i http://127.0.0.1:8000/api/health
```

预期返回 200，包含 status=ok。

2) 验证 Go 用户登录接口可访问

```bash
curl -i http://127.0.0.1:9030/api/v1/user/login \
	-H 'Content-Type: application/json' \
	-d '{"username":"test","password":"test"}'
```

账号不存在也没关系，只要返回了业务响应（而不是连接失败）就说明 Go 后端已启动成功。

### 7. 停止服务

```bash
docker compose down
```

若要同时清理数据卷：

```bash
docker compose down -v
```
