# AykAI

Rag项目

搭建一个模版，以后拿来复用

## 技术栈

LangGraph，langChain

SSE

多路召回：Vector + bm25，后面准备尝试Graphrag,todo

父子索引：父块存pg，子块存milvus（本机）

多种文本类型：md，pdf todo

## 1. 启动流程

本项目默认使用 uv 进行 Python 环境与依赖管理。

### 1.1 前置要求

- uv（https://docs.astral.sh/uv/）
- Docker Desktop（含 docker compose）
- Python 3.14+

### 1.2 初始化 Python 环境并安装依赖

在项目根目录执行：

```bash
uv venv --python 3.14
uv sync --extra dev
```

说明：

- uv 会基于 pyproject.toml 安装运行依赖
- --extra dev 会额外安装 pytest 等开发依赖

### 1.3 配置环境变量

```bash
cp .env.example .env
```

然后编辑 .env，至少填这 4 项：

- OPENAI_API_KEY
- OPENAI_BASE_URL
- OPENAI_EMBEDDING_MODEL
- OPENAI_CHAT_MODEL

### 1.4 启动数据库与向量库

```bash
docker compose up -d
docker compose ps
```

预期看到：

- AykAI-postgres: healthy
- milvus-etcd: up
- milvus-minio: up
- milvus-standalone: up

### 1.5 启动 API

```bash
uv run python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

默认地址：

- http://127.0.0.1:8000

## 2. 快速自检

```bash
curl -i http://127.0.0.1:8000/api/health
```

预期返回 200：

```json
{"status":"ok","app":"AykAI"}
```
